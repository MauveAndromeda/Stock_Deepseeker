"""
SAC (Soft Actor-Critic) Trading Agent
State-of-the-art off-policy RL algorithm for continuous control
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
from typing import Tuple, Optional
from collections import deque
import random
from loguru import logger

from src.utils.config import get_config


class ReplayBuffer:
    """Experience replay buffer for SAC"""

    def __init__(self, capacity: int = 1000000):
        self.buffer = deque(maxlen=capacity)

    def push(
        self,
        state: np.ndarray,
        action: np.ndarray,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ):
        """Add experience to buffer"""
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int) -> Tuple:
        """Sample batch of experiences"""
        batch = random.sample(self.buffer, batch_size)

        states, actions, rewards, next_states, dones = zip(*batch)

        return (
            np.array(states),
            np.array(actions),
            np.array(rewards),
            np.array(next_states),
            np.array(dones),
        )

    def __len__(self) -> int:
        return len(self.buffer)


class Actor(nn.Module):
    """Actor network (policy)"""

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dim: int = 256,
        max_action: float = 1.0,
    ):
        super().__init__()

        self.fc1 = nn.Linear(state_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.mean = nn.Linear(hidden_dim, action_dim)
        self.log_std = nn.Linear(hidden_dim, action_dim)

        self.max_action = max_action
        self.min_log_std = -20
        self.max_log_std = 2

    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass - outputs mean and log_std of action distribution"""
        x = F.relu(self.fc1(state))
        x = F.relu(self.fc2(x))

        mean = self.mean(x)
        log_std = self.log_std(x)
        log_std = torch.clamp(log_std, self.min_log_std, self.max_log_std)

        return mean, log_std

    def sample(
        self, state: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Sample action from policy"""
        mean, log_std = self.forward(state)
        std = log_std.exp()

        # Reparameterization trick
        normal = torch.distributions.Normal(mean, std)
        x_t = normal.rsample()  # Sample with reparameterization

        # Apply tanh squashing
        action = torch.tanh(x_t) * self.max_action

        # Calculate log probability
        log_prob = normal.log_prob(x_t)
        # Enforcing action bounds (tanh correction)
        log_prob -= torch.log(self.max_action * (1 - action.pow(2)) + 1e-6)
        log_prob = log_prob.sum(1, keepdim=True)

        return action, log_prob


class Critic(nn.Module):
    """Critic network (Q-function)"""

    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 256):
        super().__init__()

        # Q1
        self.fc1 = nn.Linear(state_dim + action_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, 1)

        # Q2
        self.fc4 = nn.Linear(state_dim + action_dim, hidden_dim)
        self.fc5 = nn.Linear(hidden_dim, hidden_dim)
        self.fc6 = nn.Linear(hidden_dim, 1)

    def forward(
        self, state: torch.Tensor, action: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass - outputs two Q-values"""
        sa = torch.cat([state, action], 1)

        # Q1
        q1 = F.relu(self.fc1(sa))
        q1 = F.relu(self.fc2(q1))
        q1 = self.fc3(q1)

        # Q2
        q2 = F.relu(self.fc4(sa))
        q2 = F.relu(self.fc5(q2))
        q2 = self.fc6(q2)

        return q1, q2


class SACTradingAgent:
    """
    SAC Trading Agent
    Learns optimal trading policy through interaction with environment
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dim: int = 256,
        lr: float = 3e-4,
        gamma: float = 0.99,
        tau: float = 0.005,
        alpha: float = 0.2,
        auto_alpha: bool = True,
    ):
        """
        Args:
            state_dim: State dimension
            action_dim: Action dimension
            hidden_dim: Hidden layer dimension
            lr: Learning rate
            gamma: Discount factor
            tau: Soft update parameter
            alpha: Temperature parameter
            auto_alpha: Automatically tune alpha
        """
        self.config = get_config()

        self.gamma = gamma
        self.tau = tau
        self.alpha = alpha
        self.auto_alpha = auto_alpha

        # Device
        self.device = torch.device(
            f"cuda:{self.config.model.gpu_device}"
            if self.config.model.use_gpu and torch.cuda.is_available()
            else "cpu"
        )

        # Networks
        self.actor = Actor(state_dim, action_dim, hidden_dim).to(self.device)
        self.critic = Critic(state_dim, action_dim, hidden_dim).to(self.device)
        self.critic_target = Critic(state_dim, action_dim, hidden_dim).to(
            self.device
        )

        # Copy critic to target
        self.critic_target.load_state_dict(self.critic.state_dict())

        # Optimizers
        self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=lr)
        self.critic_optimizer = optim.Adam(self.critic.parameters(), lr=lr)

        # Automatic entropy tuning
        if self.auto_alpha:
            self.target_entropy = -action_dim
            self.log_alpha = torch.zeros(1, requires_grad=True, device=self.device)
            self.alpha_optimizer = optim.Adam([self.log_alpha], lr=lr)

        # Replay buffer
        self.replay_buffer = ReplayBuffer(
            capacity=self.config.model.sac_buffer_size
        )

        logger.info(
            f"SAC Agent initialized: state_dim={state_dim}, "
            f"action_dim={action_dim}, device={self.device}"
        )

    def select_action(
        self, state: np.ndarray, eval_mode: bool = False
    ) -> np.ndarray:
        """Select action from policy"""
        state = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        if eval_mode:
            with torch.no_grad():
                mean, _ = self.actor(state)
                action = torch.tanh(mean) * self.actor.max_action
        else:
            with torch.no_grad():
                action, _ = self.actor.sample(state)

        return action.cpu().numpy()[0]

    def train(self, batch_size: int = 256) -> dict:
        """Train the agent on a batch of experiences"""
        if len(self.replay_buffer) < batch_size:
            return {}

        # Sample batch
        states, actions, rewards, next_states, dones = self.replay_buffer.sample(
            batch_size
        )

        # Convert to tensors
        states = torch.FloatTensor(states).to(self.device)
        actions = torch.FloatTensor(actions).to(self.device)
        rewards = torch.FloatTensor(rewards).unsqueeze(1).to(self.device)
        next_states = torch.FloatTensor(next_states).to(self.device)
        dones = torch.FloatTensor(dones).unsqueeze(1).to(self.device)

        # Update critic
        with torch.no_grad():
            next_actions, next_log_probs = self.actor.sample(next_states)
            q1_next, q2_next = self.critic_target(next_states, next_actions)
            q_next = torch.min(q1_next, q2_next) - self.alpha * next_log_probs
            q_target = rewards + (1 - dones) * self.gamma * q_next

        q1, q2 = self.critic(states, actions)
        critic_loss = F.mse_loss(q1, q_target) + F.mse_loss(q2, q_target)

        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        self.critic_optimizer.step()

        # Update actor
        new_actions, log_probs = self.actor.sample(states)
        q1_new, q2_new = self.critic(states, new_actions)
        q_new = torch.min(q1_new, q2_new)

        actor_loss = (self.alpha * log_probs - q_new).mean()

        self.actor_optimizer.zero_grad()
        actor_loss.backward()
        self.actor_optimizer.step()

        # Update alpha (temperature parameter)
        if self.auto_alpha:
            alpha_loss = -(
                self.log_alpha * (log_probs + self.target_entropy).detach()
            ).mean()

            self.alpha_optimizer.zero_grad()
            alpha_loss.backward()
            self.alpha_optimizer.step()

            self.alpha = self.log_alpha.exp().item()

        # Soft update target network
        self._soft_update()

        return {
            "critic_loss": critic_loss.item(),
            "actor_loss": actor_loss.item(),
            "alpha": self.alpha,
        }

    def _soft_update(self):
        """Soft update target network parameters"""
        for target_param, param in zip(
            self.critic_target.parameters(), self.critic.parameters()
        ):
            target_param.data.copy_(
                target_param.data * (1.0 - self.tau) + param.data * self.tau
            )

    def save(self, filepath: str):
        """Save agent"""
        torch.save(
            {
                "actor": self.actor.state_dict(),
                "critic": self.critic.state_dict(),
                "critic_target": self.critic_target.state_dict(),
                "actor_optimizer": self.actor_optimizer.state_dict(),
                "critic_optimizer": self.critic_optimizer.state_dict(),
                "alpha": self.alpha,
            },
            filepath,
        )
        logger.info(f"Agent saved to {filepath}")

    def load(self, filepath: str):
        """Load agent"""
        checkpoint = torch.load(filepath, map_location=self.device)

        self.actor.load_state_dict(checkpoint["actor"])
        self.critic.load_state_dict(checkpoint["critic"])
        self.critic_target.load_state_dict(checkpoint["critic_target"])
        self.actor_optimizer.load_state_dict(checkpoint["actor_optimizer"])
        self.critic_optimizer.load_state_dict(checkpoint["critic_optimizer"])
        self.alpha = checkpoint["alpha"]

        logger.info(f"Agent loaded from {filepath}")
