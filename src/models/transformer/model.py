"""
Transformer Model for Time Series Prediction
Advanced architecture for stock price and market prediction
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Optional, Tuple
import math
from loguru import logger


class PositionalEncoding(nn.Module):
    """
    Positional encoding for transformer
    Injects information about relative/absolute position of tokens
    """

    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        # Create positional encoding matrix
        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model)
        )

        pe = torch.zeros(max_len, 1, d_model)
        pe[:, 0, 0::2] = torch.sin(position * div_term)
        pe[:, 0, 1::2] = torch.cos(position * div_term)

        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Tensor of shape (seq_len, batch, d_model)

        Returns:
            Tensor with positional encoding added
        """
        x = x + self.pe[: x.size(0)]
        return self.dropout(x)


class MultiHeadAttention(nn.Module):
    """
    Multi-head attention mechanism
    Allows model to attend to information from different representation subspaces
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        assert d_model % num_heads == 0, "d_model must be divisible by num_heads"

        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads

        # Linear projections
        self.query = nn.Linear(d_model, d_model)
        self.key = nn.Linear(d_model, d_model)
        self.value = nn.Linear(d_model, d_model)
        self.output = nn.Linear(d_model, d_model)

        self.dropout = nn.Dropout(dropout)
        self.scale = math.sqrt(self.head_dim)

    def forward(
        self,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            query: Query tensor (seq_len, batch, d_model)
            key: Key tensor (seq_len, batch, d_model)
            value: Value tensor (seq_len, batch, d_model)
            mask: Optional mask tensor

        Returns:
            Output tensor and attention weights
        """
        batch_size = query.size(1)

        # Linear projections and reshape
        Q = self.query(query).view(
            -1, batch_size, self.num_heads, self.head_dim
        ).transpose(0, 2)
        K = self.key(key).view(
            -1, batch_size, self.num_heads, self.head_dim
        ).transpose(0, 2)
        V = self.value(value).view(
            -1, batch_size, self.num_heads, self.head_dim
        ).transpose(0, 2)

        # Calculate attention scores
        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale

        # Apply mask if provided
        if mask is not None:
            scores = scores.masked_fill(mask == 0, float("-inf"))

        # Apply softmax
        attention_weights = F.softmax(scores, dim=-1)
        attention_weights = self.dropout(attention_weights)

        # Apply attention to values
        context = torch.matmul(attention_weights, V)

        # Reshape and project
        context = (
            context.transpose(0, 2)
            .contiguous()
            .view(-1, batch_size, self.d_model)
        )
        output = self.output(context)

        return output, attention_weights


class TransformerEncoderLayer(nn.Module):
    """Single transformer encoder layer"""

    def __init__(
        self,
        d_model: int,
        num_heads: int,
        d_ff: int,
        dropout: float = 0.1,
    ):
        super().__init__()

        # Multi-head attention
        self.self_attn = MultiHeadAttention(d_model, num_heads, dropout)

        # Feed-forward network
        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, d_model),
        )

        # Layer normalization
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

        self.dropout = nn.Dropout(dropout)

    def forward(
        self, x: torch.Tensor, mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Args:
            x: Input tensor (seq_len, batch, d_model)
            mask: Optional attention mask

        Returns:
            Output tensor
        """
        # Self-attention with residual connection
        attn_output, _ = self.self_attn(x, x, x, mask)
        x = self.norm1(x + self.dropout(attn_output))

        # Feed-forward with residual connection
        ff_output = self.ff(x)
        x = self.norm2(x + self.dropout(ff_output))

        return x


class TimeSeriesTransformer(nn.Module):
    """
    Transformer model for time series prediction
    Designed for stock price and market prediction
    """

    def __init__(
        self,
        input_dim: int,
        d_model: int = 512,
        num_heads: int = 8,
        num_layers: int = 6,
        d_ff: int = 2048,
        dropout: float = 0.1,
        max_len: int = 5000,
        output_dim: int = 1,
    ):
        """
        Args:
            input_dim: Input feature dimension
            d_model: Model dimension
            num_heads: Number of attention heads
            num_layers: Number of encoder layers
            d_ff: Feed-forward dimension
            dropout: Dropout rate
            max_len: Maximum sequence length
            output_dim: Output dimension (1 for price prediction)
        """
        super().__init__()

        self.input_dim = input_dim
        self.d_model = d_model
        self.output_dim = output_dim

        # Input projection
        self.input_projection = nn.Linear(input_dim, d_model)

        # Positional encoding
        self.pos_encoding = PositionalEncoding(d_model, max_len, dropout)

        # Transformer encoder layers
        self.encoder_layers = nn.ModuleList(
            [
                TransformerEncoderLayer(d_model, num_heads, d_ff, dropout)
                for _ in range(num_layers)
            ]
        )

        # Output layers
        self.output_projection = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, output_dim),
        )

        # Initialize weights
        self._init_weights()

        logger.info(
            f"Initialized Transformer: input_dim={input_dim}, d_model={d_model}, "
            f"num_heads={num_heads}, num_layers={num_layers}"
        )

    def _init_weights(self):
        """Initialize model weights"""
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)

    def forward(
        self, x: torch.Tensor, mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Forward pass

        Args:
            x: Input tensor (batch, seq_len, input_dim)
            mask: Optional attention mask

        Returns:
            Output predictions (batch, output_dim)
        """
        # Reshape to (seq_len, batch, input_dim)
        x = x.transpose(0, 1)

        # Project input to model dimension
        x = self.input_projection(x)

        # Add positional encoding
        x = self.pos_encoding(x)

        # Pass through encoder layers
        for layer in self.encoder_layers:
            x = layer(x, mask)

        # Take the last time step
        x = x[-1]  # (batch, d_model)

        # Project to output dimension
        output = self.output_projection(x)

        return output

    def predict_sequence(
        self, x: torch.Tensor, steps: int = 1
    ) -> torch.Tensor:
        """
        Predict multiple steps into the future

        Args:
            x: Input tensor (batch, seq_len, input_dim)
            steps: Number of steps to predict

        Returns:
            Predictions (batch, steps, output_dim)
        """
        self.eval()
        predictions = []

        with torch.no_grad():
            for _ in range(steps):
                # Predict next step
                pred = self.forward(x)
                predictions.append(pred)

                # Update input sequence
                # This is a simplified version - in practice, you'd want to
                # incorporate the prediction back into the feature vector
                x = torch.cat([x[:, 1:, :], pred.unsqueeze(1)], dim=1)

        return torch.stack(predictions, dim=1)


class TemporalFusionTransformer(nn.Module):
    """
    Advanced Temporal Fusion Transformer
    Incorporates static covariates, known future inputs, and observed inputs
    """

    def __init__(
        self,
        static_dim: int,
        historical_dim: int,
        future_dim: int,
        d_model: int = 512,
        num_heads: int = 8,
        num_layers: int = 6,
        dropout: float = 0.1,
        output_dim: int = 1,
    ):
        super().__init__()

        self.static_dim = static_dim
        self.historical_dim = historical_dim
        self.future_dim = future_dim
        self.d_model = d_model

        # Static covariate encoding
        self.static_encoder = nn.Sequential(
            nn.Linear(static_dim, d_model),
            nn.ReLU(),
            nn.Dropout(dropout),
        )

        # Historical input encoding
        self.historical_encoder = nn.LSTM(
            historical_dim,
            d_model // 2,
            num_layers=2,
            batch_first=True,
            dropout=dropout,
            bidirectional=True,
        )

        # Future input encoding
        self.future_encoder = nn.Linear(future_dim, d_model)

        # Attention mechanism
        self.temporal_attention = MultiHeadAttention(
            d_model, num_heads, dropout
        )

        # Transformer layers
        self.transformer = TimeSeriesTransformer(
            input_dim=d_model,
            d_model=d_model,
            num_heads=num_heads,
            num_layers=num_layers,
            dropout=dropout,
            output_dim=output_dim,
        )

        logger.info("Initialized Temporal Fusion Transformer")

    def forward(
        self,
        static: torch.Tensor,
        historical: torch.Tensor,
        future: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            static: Static features (batch, static_dim)
            historical: Historical time series (batch, hist_len, historical_dim)
            future: Known future inputs (batch, fut_len, future_dim)

        Returns:
            Predictions (batch, output_dim)
        """
        batch_size = static.size(0)

        # Encode static features
        static_encoded = self.static_encoder(static)  # (batch, d_model)

        # Encode historical sequence
        hist_encoded, _ = self.historical_encoder(
            historical
        )  # (batch, hist_len, d_model)

        # Encode future inputs
        future_encoded = self.future_encoder(future)  # (batch, fut_len, d_model)

        # Combine historical and future
        temporal_features = torch.cat(
            [hist_encoded, future_encoded], dim=1
        )  # (batch, total_len, d_model)

        # Apply temporal attention with static context
        static_expanded = static_encoded.unsqueeze(1).expand(
            -1, temporal_features.size(1), -1
        )
        temporal_features = temporal_features + static_expanded

        # Pass through transformer
        output = self.transformer(temporal_features)

        return output
