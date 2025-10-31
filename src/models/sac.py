"""
SAC (Soft Actor-Critic) 强化学习算法
用于交易策略学习（2025最新版本）
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import deque
import random
import gymnasium as gym
from gymnasium import spaces


@dataclass
class SACConfig:
    """SAC配置"""
    # 网络架构
    state_dim: int = 128
    action_dim: int = 3  # buy, sell, hold
    hidden_dims: List[int] = field(default_factory=lambda: [256, 256, 128])

    # 学习参数
    learning_rate: float = 3e-4
    gamma: float = 0.99  # 折扣因子
    tau: float = 0.005  # 软更新系数
    alpha: float = 0.2  # 熵系数
    auto_entropy_tuning: bool = True  # 自动调节熵系数

    # 经验回放
    buffer_size: int = 1000000
    batch_size: int = 256
    min_replay_size: int = 10000

    # 训练
    gradient_steps: int = 1
    target_update_interval: int = 1
    max_grad_norm: float = 1.0

    # 探索
    initial_epsilon: float = 1.0
    final_epsilon: float = 0.01
    epsilon_decay: int = 100000


class ReplayBuffer:
    """经验回放缓冲区"""

    def __init__(self, capacity: int):
        self.buffer = deque(maxlen=capacity)

    def push(
        self,
        state: np.ndarray,
        action: np.ndarray,
        reward: float,
        next_state: np.ndarray,
        done: bool
    ):
        """添加经验"""
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int) -> Tuple:
        """采样一批经验"""
        batch = random.sample(self.buffer, batch_size)

        states, actions, rewards, next_states, dones = zip(*batch)

        return (
            np.array(states),
            np.array(actions),
            np.array(rewards, dtype=np.float32),
            np.array(next_states),
            np.array(dones, dtype=np.uint8)
        )

    def __len__(self) -> int:
        return len(self.buffer)


class Actor(nn.Module):
    """Actor网络 - 输出动作分布"""

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dims: List[int],
        log_std_min: float = -20,
        log_std_max: float = 2
    ):
        super().__init__()

        self.log_std_min = log_std_min
        self.log_std_max = log_std_max

        # 构建网络
        layers = []
        input_dim = state_dim

        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(input_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.1)
            ])
            input_dim = hidden_dim

        self.backbone = nn.Sequential(*layers)

        # 输出层
        self.mean_linear = nn.Linear(input_dim, action_dim)
        self.log_std_linear = nn.Linear(input_dim, action_dim)

    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        前向传播

        Args:
            state: [batch_size, state_dim]

        Returns:
            mean: [batch_size, action_dim]
            log_std: [batch_size, action_dim]
        """
        x = self.backbone(state)

        mean = self.mean_linear(x)
        log_std = self.log_std_linear(x)
        log_std = torch.clamp(log_std, self.log_std_min, self.log_std_max)

        return mean, log_std

    def sample(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        采样动作

        Returns:
            action: [batch_size, action_dim]
            log_prob: [batch_size, 1]
        """
        mean, log_std = self.forward(state)
        std = log_std.exp()

        # 重参数化技巧
        normal = torch.distributions.Normal(mean, std)
        x_t = normal.rsample()  # reparameterization trick

        # Tanh squashing
        action = torch.tanh(x_t)

        # 计算log probability
        log_prob = normal.log_prob(x_t)

        # 应用tanh变换的Jacobian校正
        log_prob -= torch.log(1 - action.pow(2) + 1e-6)
        log_prob = log_prob.sum(dim=-1, keepdim=True)

        return action, log_prob


class Critic(nn.Module):
    """Critic网络 - Q函数"""

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dims: List[int]
    ):
        super().__init__()

        # 构建网络
        layers = []
        input_dim = state_dim + action_dim

        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(input_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.1)
            ])
            input_dim = hidden_dim

        layers.append(nn.Linear(input_dim, 1))

        self.network = nn.Sequential(*layers)

    def forward(self, state: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        """
        前向传播

        Args:
            state: [batch_size, state_dim]
            action: [batch_size, action_dim]

        Returns:
            q_value: [batch_size, 1]
        """
        x = torch.cat([state, action], dim=-1)
        return self.network(x)


class SACAgent:
    """
    SAC智能体
    实现最新的SAC算法（2025版本）
    """

    def __init__(self, config: SACConfig, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        self.config = config
        self.device = device

        # 创建网络
        self.actor = Actor(
            config.state_dim,
            config.action_dim,
            config.hidden_dims
        ).to(device)

        self.critic1 = Critic(
            config.state_dim,
            config.action_dim,
            config.hidden_dims
        ).to(device)

        self.critic2 = Critic(
            config.state_dim,
            config.action_dim,
            config.hidden_dims
        ).to(device)

        # 目标网络
        self.critic1_target = Critic(
            config.state_dim,
            config.action_dim,
            config.hidden_dims
        ).to(device)

        self.critic2_target = Critic(
            config.state_dim,
            config.action_dim,
            config.hidden_dims
        ).to(device)

        # 复制权重到目标网络
        self.critic1_target.load_state_dict(self.critic1.state_dict())
        self.critic2_target.load_state_dict(self.critic2.state_dict())

        # 优化器
        self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=config.learning_rate)
        self.critic1_optimizer = optim.Adam(self.critic1.parameters(), lr=config.learning_rate)
        self.critic2_optimizer = optim.Adam(self.critic2.parameters(), lr=config.learning_rate)

        # 自动熵调节
        if config.auto_entropy_tuning:
            self.target_entropy = -torch.prod(torch.Tensor([config.action_dim]).to(device)).item()
            self.log_alpha = torch.zeros(1, requires_grad=True, device=device)
            self.alpha_optimizer = optim.Adam([self.log_alpha], lr=config.learning_rate)
            self.alpha = self.log_alpha.exp()
        else:
            self.alpha = torch.tensor(config.alpha, device=device)

        # 经验回放
        self.replay_buffer = ReplayBuffer(config.buffer_size)

        # 训练统计
        self.total_steps = 0
        self.episode_rewards = []
        self.losses = {
            "actor": [],
            "critic1": [],
            "critic2": [],
            "alpha": []
        }

    def select_action(self, state: np.ndarray, evaluate: bool = False) -> np.ndarray:
        """
        选择动作

        Args:
            state: 状态
            evaluate: 是否为评估模式（不添加噪声）

        Returns:
            动作
        """
        state = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        if evaluate:
            with torch.no_grad():
                mean, _ = self.actor(state)
                action = torch.tanh(mean)
        else:
            with torch.no_grad():
                action, _ = self.actor.sample(state)

        return action.cpu().numpy()[0]

    def update(self) -> Dict[str, float]:
        """
        更新网络

        Returns:
            损失字典
        """
        if len(self.replay_buffer) < self.config.min_replay_size:
            return {}

        losses = {}

        for _ in range(self.config.gradient_steps):
            # 采样batch
            states, actions, rewards, next_states, dones = self.replay_buffer.sample(self.config.batch_size)

            states = torch.FloatTensor(states).to(self.device)
            actions = torch.FloatTensor(actions).to(self.device)
            rewards = torch.FloatTensor(rewards).unsqueeze(1).to(self.device)
            next_states = torch.FloatTensor(next_states).to(self.device)
            dones = torch.FloatTensor(dones).unsqueeze(1).to(self.device)

            # ====== 更新Critic ======
            with torch.no_grad():
                next_actions, next_log_probs = self.actor.sample(next_states)

                target_q1 = self.critic1_target(next_states, next_actions)
                target_q2 = self.critic2_target(next_states, next_actions)
                target_q = torch.min(target_q1, target_q2) - self.alpha * next_log_probs

                target_value = rewards + (1 - dones) * self.config.gamma * target_q

            current_q1 = self.critic1(states, actions)
            current_q2 = self.critic2(states, actions)

            critic1_loss = F.mse_loss(current_q1, target_value)
            critic2_loss = F.mse_loss(current_q2, target_value)

            # 更新critic1
            self.critic1_optimizer.zero_grad()
            critic1_loss.backward()
            nn.utils.clip_grad_norm_(self.critic1.parameters(), self.config.max_grad_norm)
            self.critic1_optimizer.step()

            # 更新critic2
            self.critic2_optimizer.zero_grad()
            critic2_loss.backward()
            nn.utils.clip_grad_norm_(self.critic2.parameters(), self.config.max_grad_norm)
            self.critic2_optimizer.step()

            # ====== 更新Actor ======
            new_actions, log_probs = self.actor.sample(states)
            q1_new = self.critic1(states, new_actions)
            q2_new = self.critic2(states, new_actions)
            q_new = torch.min(q1_new, q2_new)

            actor_loss = (self.alpha * log_probs - q_new).mean()

            self.actor_optimizer.zero_grad()
            actor_loss.backward()
            nn.utils.clip_grad_norm_(self.actor.parameters(), self.config.max_grad_norm)
            self.actor_optimizer.step()

            # ====== 更新Alpha（熵系数）======
            if self.config.auto_entropy_tuning:
                alpha_loss = -(self.log_alpha * (log_probs + self.target_entropy).detach()).mean()

                self.alpha_optimizer.zero_grad()
                alpha_loss.backward()
                self.alpha_optimizer.step()

                self.alpha = self.log_alpha.exp()
                losses["alpha"] = alpha_loss.item()

            # ====== 软更新目标网络 ======
            if self.total_steps % self.config.target_update_interval == 0:
                self._soft_update(self.critic1, self.critic1_target)
                self._soft_update(self.critic2, self.critic2_target)

            losses["actor"] = actor_loss.item()
            losses["critic1"] = critic1_loss.item()
            losses["critic2"] = critic2_loss.item()

            self.total_steps += 1

        return losses

    def _soft_update(self, source: nn.Module, target: nn.Module):
        """软更新目标网络"""
        for target_param, param in zip(target.parameters(), source.parameters()):
            target_param.data.copy_(
                target_param.data * (1.0 - self.config.tau) + param.data * self.config.tau
            )

    def save(self, path: str):
        """保存模型"""
        torch.save({
            "actor": self.actor.state_dict(),
            "critic1": self.critic1.state_dict(),
            "critic2": self.critic2.state_dict(),
            "critic1_target": self.critic1_target.state_dict(),
            "critic2_target": self.critic2_target.state_dict(),
            "actor_optimizer": self.actor_optimizer.state_dict(),
            "critic1_optimizer": self.critic1_optimizer.state_dict(),
            "critic2_optimizer": self.critic2_optimizer.state_dict(),
            "log_alpha": self.log_alpha if self.config.auto_entropy_tuning else None,
            "total_steps": self.total_steps,
        }, path)

    def load(self, path: str):
        """加载模型"""
        checkpoint = torch.load(path, map_location=self.device)

        self.actor.load_state_dict(checkpoint["actor"])
        self.critic1.load_state_dict(checkpoint["critic1"])
        self.critic2.load_state_dict(checkpoint["critic2"])
        self.critic1_target.load_state_dict(checkpoint["critic1_target"])
        self.critic2_target.load_state_dict(checkpoint["critic2_target"])

        self.actor_optimizer.load_state_dict(checkpoint["actor_optimizer"])
        self.critic1_optimizer.load_state_dict(checkpoint["critic1_optimizer"])
        self.critic2_optimizer.load_state_dict(checkpoint["critic2_optimizer"])

        if self.config.auto_entropy_tuning and checkpoint["log_alpha"] is not None:
            self.log_alpha.data = checkpoint["log_alpha"]
            self.alpha = self.log_alpha.exp()

        self.total_steps = checkpoint["total_steps"]


class TradingEnvironment(gym.Env):
    """
    交易环境
    符合Gymnasium接口
    """

    def __init__(
        self,
        data: np.ndarray,
        initial_balance: float = 100000,
        commission_rate: float = 0.001,
        max_position: float = 1.0
    ):
        """
        Args:
            data: [num_timesteps, num_features] 市场数据
            initial_balance: 初始资金
            commission_rate: 佣金率
            max_position: 最大仓位
        """
        super().__init__()

        self.data = data
        self.num_timesteps = len(data)
        self.num_features = data.shape[1]

        self.initial_balance = initial_balance
        self.commission_rate = commission_rate
        self.max_position = max_position

        # 定义状态和动作空间
        # 状态：市场特征 + 当前持仓 + 账户余额 + PnL等
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.num_features + 10,),  # 额外10个维度用于账户状态
            dtype=np.float32
        )

        # 动作：连续动作 [-1, 1] 表示仓位调整
        self.action_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(1,),
            dtype=np.float32
        )

        self.reset()

    def reset(self, seed: Optional[int] = None, options: Optional[Dict] = None) -> Tuple[np.ndarray, Dict]:
        """重置环境"""
        super().reset(seed=seed)

        self.current_step = 0
        self.balance = self.initial_balance
        self.position = 0.0  # 当前仓位（-1到1）
        self.entry_price = 0.0
        self.total_pnl = 0.0
        self.trades = []

        return self._get_observation(), {}

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """执行一步"""
        # 解析动作
        target_position = np.clip(action[0], -self.max_position, self.max_position)

        # 计算仓位变化
        position_change = target_position - self.position

        # 获取当前价格
        current_price = self.data[self.current_step, 0]  # 假设第一列是价格

        # 执行交易
        if abs(position_change) > 0.01:  # 最小交易阈值
            # 计算交易成本
            trade_value = abs(position_change) * self.balance
            commission = trade_value * self.commission_rate

            # 更新持仓
            if self.position != 0:
                # 平仓部分或全部
                pnl = (current_price - self.entry_price) * self.position * self.balance / self.entry_price
                self.total_pnl += pnl
                self.balance += pnl

            self.position = target_position
            self.entry_price = current_price
            self.balance -= commission

            self.trades.append({
                "step": self.current_step,
                "position": self.position,
                "price": current_price,
                "commission": commission
            })

        # 计算奖励
        reward = self._calculate_reward()

        # 移动到下一步
        self.current_step += 1

        # 检查是否结束
        terminated = self.current_step >= self.num_timesteps - 1
        truncated = self.balance <= 0  # 爆仓

        return self._get_observation(), reward, terminated, truncated, self._get_info()

    def _get_observation(self) -> np.ndarray:
        """获取当前状态"""
        market_features = self.data[self.current_step]

        account_features = np.array([
            self.position,
            self.balance / self.initial_balance,  # 归一化余额
            self.total_pnl / self.initial_balance,  # 归一化PnL
            len(self.trades) / 1000,  # 归一化交易次数
            self.current_step / self.num_timesteps,  # 进度
            0, 0, 0, 0, 0  # 预留
        ], dtype=np.float32)

        return np.concatenate([market_features, account_features])

    def _calculate_reward(self) -> float:
        """计算奖励"""
        # 基于PnL和风险的奖励
        if self.current_step == 0:
            return 0.0

        prev_price = self.data[self.current_step - 1, 0]
        current_price = self.data[self.current_step, 0]

        # 计算收益率
        if prev_price > 0:
            return_rate = (current_price - prev_price) / prev_price
            reward = return_rate * self.position * 100  # 缩放奖励
        else:
            reward = 0.0

        # 惩罚过度交易
        if len(self.trades) > 0 and self.trades[-1]["step"] == self.current_step:
            reward -= 0.01

        return reward

    def _get_info(self) -> Dict:
        """获取额外信息"""
        return {
            "balance": self.balance,
            "position": self.position,
            "total_pnl": self.total_pnl,
            "num_trades": len(self.trades),
            "return_rate": (self.balance + self.total_pnl - self.initial_balance) / self.initial_balance
        }

    def render(self):
        """渲染环境"""
        pass
