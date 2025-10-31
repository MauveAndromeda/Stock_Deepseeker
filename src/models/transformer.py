"""
Transformer模型用于市场预测
基于最新的Transformer架构（2025）
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass
import math


@dataclass
class TransformerConfig:
    """Transformer配置"""
    # 模型维度
    d_model: int = 512
    nhead: int = 8
    num_encoder_layers: int = 6
    num_decoder_layers: int = 6
    dim_feedforward: int = 2048
    dropout: float = 0.1

    # 序列长度
    max_seq_length: int = 512

    # 输入输出
    input_dim: int = 64  # 输入特征维度
    output_dim: int = 1  # 输出维度（预测价格/收益率）

    # 训练参数
    learning_rate: float = 1e-4
    weight_decay: float = 1e-5
    warmup_steps: int = 1000
    max_grad_norm: float = 1.0

    # 位置编码
    use_learned_positional: bool = True
    use_temporal_encoding: bool = True


class PositionalEncoding(nn.Module):
    """位置编码"""

    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        # 创建位置编码
        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))

        pe = torch.zeros(max_len, 1, d_model)
        pe[:, 0, 0::2] = torch.sin(position * div_term)
        pe[:, 0, 1::2] = torch.cos(position * div_term)

        self.register_buffer('pe', pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [seq_len, batch_size, d_model]
        """
        x = x + self.pe[:x.size(0)]
        return self.dropout(x)


class LearnedPositionalEncoding(nn.Module):
    """可学习的位置编码"""

    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        self.pe = nn.Parameter(torch.randn(max_len, 1, d_model))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [seq_len, batch_size, d_model]
        """
        x = x + self.pe[:x.size(0)]
        return self.dropout(x)


class TemporalEncoding(nn.Module):
    """时间编码 - 考虑交易日、小时等时间特征"""

    def __init__(self, d_model: int):
        super().__init__()
        self.hour_embed = nn.Embedding(24, d_model // 4)
        self.day_of_week_embed = nn.Embedding(7, d_model // 4)
        self.day_of_month_embed = nn.Embedding(31, d_model // 4)
        self.month_embed = nn.Embedding(12, d_model // 4)

    def forward(
        self,
        hour: torch.Tensor,
        day_of_week: torch.Tensor,
        day_of_month: torch.Tensor,
        month: torch.Tensor
    ) -> torch.Tensor:
        """
        Args:
            hour, day_of_week, day_of_month, month: [seq_len, batch_size]

        Returns:
            [seq_len, batch_size, d_model]
        """
        h = self.hour_embed(hour)
        dow = self.day_of_week_embed(day_of_week)
        dom = self.day_of_month_embed(day_of_month)
        m = self.month_embed(month)

        return torch.cat([h, dow, dom, m], dim=-1)


class MultiHeadAttentionWithRelativePosition(nn.Module):
    """带相对位置编码的多头注意力机制"""

    def __init__(self, d_model: int, nhead: int, dropout: float = 0.1, max_relative_position: int = 128):
        super().__init__()
        assert d_model % nhead == 0

        self.d_model = d_model
        self.nhead = nhead
        self.d_k = d_model // nhead
        self.max_relative_position = max_relative_position

        self.q_linear = nn.Linear(d_model, d_model)
        self.k_linear = nn.Linear(d_model, d_model)
        self.v_linear = nn.Linear(d_model, d_model)
        self.out_linear = nn.Linear(d_model, d_model)

        self.dropout = nn.Dropout(dropout)

        # 相对位置编码
        self.relative_position_k = nn.Embedding(2 * max_relative_position + 1, self.d_k)
        self.relative_position_v = nn.Embedding(2 * max_relative_position + 1, self.d_k)

    def _get_relative_positions(self, length: int) -> torch.Tensor:
        """生成相对位置矩阵"""
        range_vec = torch.arange(length)
        range_mat = range_vec.unsqueeze(0).repeat(length, 1)
        distance_mat = range_mat - range_mat.transpose(0, 1)
        distance_mat_clipped = torch.clamp(distance_mat, -self.max_relative_position, self.max_relative_position)
        final_mat = distance_mat_clipped + self.max_relative_position
        return final_mat

    def forward(
        self,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            query, key, value: [seq_len, batch_size, d_model]
            mask: [seq_len, seq_len]

        Returns:
            output: [seq_len, batch_size, d_model]
            attention_weights: [batch_size, nhead, seq_len, seq_len]
        """
        batch_size = query.size(1)
        seq_len = query.size(0)

        # Linear projections
        Q = self.q_linear(query).view(seq_len, batch_size, self.nhead, self.d_k).transpose(0, 1).transpose(1, 2)
        K = self.k_linear(key).view(seq_len, batch_size, self.nhead, self.d_k).transpose(0, 1).transpose(1, 2)
        V = self.v_linear(value).view(seq_len, batch_size, self.nhead, self.d_k).transpose(0, 1).transpose(1, 2)
        # Q, K, V: [batch_size, nhead, seq_len, d_k]

        # 计算注意力分数
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.d_k)

        # 添加相对位置编码
        relative_positions = self._get_relative_positions(seq_len).to(query.device)
        rel_k = self.relative_position_k(relative_positions)  # [seq_len, seq_len, d_k]
        rel_scores = torch.einsum('bhqd,qkd->bhqk', Q, rel_k)
        scores = scores + rel_scores

        # 应用mask
        if mask is not None:
            scores = scores.masked_fill(mask == 0, float('-inf'))

        # Softmax
        attention_weights = F.softmax(scores, dim=-1)
        attention_weights = self.dropout(attention_weights)

        # 应用注意力到values
        context = torch.matmul(attention_weights, V)  # [batch_size, nhead, seq_len, d_k]

        # 添加相对位置到values
        rel_v = self.relative_position_v(relative_positions)  # [seq_len, seq_len, d_k]
        rel_weights = attention_weights.mean(dim=1)  # [batch_size, seq_len, seq_len]
        rel_context = torch.einsum('bqk,qkd->bqd', rel_weights, rel_v)  # [batch_size, seq_len, d_k]
        rel_context = rel_context.unsqueeze(1).repeat(1, self.nhead, 1, 1)  # [batch_size, nhead, seq_len, d_k]
        context = context + rel_context

        # Concatenate heads
        context = context.transpose(1, 2).contiguous().view(seq_len, batch_size, self.d_model)

        # Final linear projection
        output = self.out_linear(context)

        return output, attention_weights


class MarketTransformer(nn.Module):
    """
    市场预测Transformer模型
    使用最新的架构改进（2025）
    """

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.config = config

        # 输入嵌入
        self.input_embedding = nn.Linear(config.input_dim, config.d_model)

        # 位置编码
        if config.use_learned_positional:
            self.positional_encoding = LearnedPositionalEncoding(
                config.d_model,
                config.max_seq_length,
                config.dropout
            )
        else:
            self.positional_encoding = PositionalEncoding(
                config.d_model,
                config.max_seq_length,
                config.dropout
            )

        # 时间编码
        if config.use_temporal_encoding:
            self.temporal_encoding = TemporalEncoding(config.d_model)

        # Transformer编码器
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.d_model,
            nhead=config.nhead,
            dim_feedforward=config.dim_feedforward,
            dropout=config.dropout,
            batch_first=False,
            norm_first=True  # Pre-LN (更稳定)
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=config.num_encoder_layers,
            norm=nn.LayerNorm(config.d_model)
        )

        # 输出层
        self.output_projection = nn.Sequential(
            nn.Linear(config.d_model, config.dim_feedforward),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.dim_feedforward, config.output_dim)
        )

        # 初始化权重
        self._init_weights()

    def _init_weights(self):
        """初始化模型权重"""
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)

    def forward(
        self,
        x: torch.Tensor,
        temporal_features: Optional[Dict[str, torch.Tensor]] = None,
        mask: Optional[torch.Tensor] = None
    ) -> Dict[str, torch.Tensor]:
        """
        前向传播

        Args:
            x: [batch_size, seq_len, input_dim] 输入特征
            temporal_features: 时间特征字典 {hour, day_of_week, day_of_month, month}
            mask: [seq_len, seq_len] 注意力mask

        Returns:
            字典包含:
                - predictions: [batch_size, seq_len, output_dim] 预测值
                - embeddings: [batch_size, seq_len, d_model] 特征嵌入
        """
        batch_size, seq_len, _ = x.shape

        # 转换维度 [batch_size, seq_len, input_dim] -> [seq_len, batch_size, input_dim]
        x = x.transpose(0, 1)

        # 输入嵌入
        x = self.input_embedding(x)  # [seq_len, batch_size, d_model]

        # 添加位置编码
        x = self.positional_encoding(x)

        # 添加时间编码
        if self.config.use_temporal_encoding and temporal_features is not None:
            temporal_enc = self.temporal_encoding(
                temporal_features['hour'].transpose(0, 1),
                temporal_features['day_of_week'].transpose(0, 1),
                temporal_features['day_of_month'].transpose(0, 1),
                temporal_features['month'].transpose(0, 1)
            )
            x = x + temporal_enc

        # Transformer编码
        encoder_output = self.transformer_encoder(x, mask=mask)
        # encoder_output: [seq_len, batch_size, d_model]

        # 输出投影
        predictions = self.output_projection(encoder_output)
        # predictions: [seq_len, batch_size, output_dim]

        # 转换回 [batch_size, seq_len, ...]
        predictions = predictions.transpose(0, 1)
        embeddings = encoder_output.transpose(0, 1)

        return {
            "predictions": predictions,
            "embeddings": embeddings
        }

    def predict_next(
        self,
        x: torch.Tensor,
        temporal_features: Optional[Dict[str, torch.Tensor]] = None,
        num_steps: int = 1
    ) -> torch.Tensor:
        """
        预测未来N步

        Args:
            x: [batch_size, seq_len, input_dim]
            temporal_features: 时间特征
            num_steps: 预测步数

        Returns:
            [batch_size, num_steps, output_dim] 预测值
        """
        self.eval()
        predictions = []

        current_seq = x

        with torch.no_grad():
            for step in range(num_steps):
                # 前向传播
                output = self.forward(current_seq, temporal_features)
                next_pred = output["predictions"][:, -1:, :]  # [batch_size, 1, output_dim]
                predictions.append(next_pred)

                # 如果需要继续预测，需要更新输入序列
                # 这里简化处理，实际应该根据预测值构造新的输入特征
                if step < num_steps - 1:
                    # 滚动窗口：移除第一个时间步，添加预测值
                    # 注意：这里需要将预测值转换为完整的特征向量
                    # 简化处理：只使用最后几个时间步
                    current_seq = torch.cat([
                        current_seq[:, 1:, :],
                        torch.zeros(x.size(0), 1, x.size(2), device=x.device)
                    ], dim=1)

        return torch.cat(predictions, dim=1)


class TimeSeriesTransformer(nn.Module):
    """
    时间序列Transformer - 专门用于多变量时间序列预测
    """

    def __init__(
        self,
        input_dim: int,
        d_model: int = 512,
        nhead: int = 8,
        num_layers: int = 6,
        dim_feedforward: int = 2048,
        dropout: float = 0.1,
        max_seq_length: int = 512
    ):
        super().__init__()

        self.input_dim = input_dim
        self.d_model = d_model

        # 输入投影
        self.input_projection = nn.Linear(input_dim, d_model)

        # 位置编码
        self.positional_encoding = PositionalEncoding(d_model, max_seq_length, dropout)

        # Transformer层
        self.transformer = nn.Transformer(
            d_model=d_model,
            nhead=nhead,
            num_encoder_layers=num_layers,
            num_decoder_layers=num_layers,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=False,
            norm_first=True
        )

        # 输出层
        self.output_projection = nn.Linear(d_model, input_dim)

    def forward(
        self,
        src: torch.Tensor,
        tgt: torch.Tensor,
        src_mask: Optional[torch.Tensor] = None,
        tgt_mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Args:
            src: [batch_size, src_seq_len, input_dim]
            tgt: [batch_size, tgt_seq_len, input_dim]
            src_mask, tgt_mask: attention masks

        Returns:
            [batch_size, tgt_seq_len, input_dim]
        """
        # 转换维度
        src = src.transpose(0, 1)  # [src_seq_len, batch_size, input_dim]
        tgt = tgt.transpose(0, 1)  # [tgt_seq_len, batch_size, input_dim]

        # 投影和位置编码
        src = self.positional_encoding(self.input_projection(src))
        tgt = self.positional_encoding(self.input_projection(tgt))

        # Transformer
        output = self.transformer(src, tgt, src_mask=src_mask, tgt_mask=tgt_mask)

        # 输出投影
        output = self.output_projection(output)

        # 转换回 [batch_size, seq_len, input_dim]
        return output.transpose(0, 1)


# 辅助函数

def create_causal_mask(seq_len: int, device: torch.device) -> torch.Tensor:
    """创建因果mask（防止看到未来信息）"""
    mask = torch.triu(torch.ones(seq_len, seq_len, device=device), diagonal=1)
    return mask == 0


def create_padding_mask(lengths: torch.Tensor, max_len: int, device: torch.device) -> torch.Tensor:
    """创建padding mask"""
    batch_size = lengths.size(0)
    mask = torch.arange(max_len, device=device).expand(batch_size, max_len) < lengths.unsqueeze(1)
    return mask
