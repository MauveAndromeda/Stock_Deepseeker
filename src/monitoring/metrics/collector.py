"""
Metrics Collector
Collects and exports metrics for monitoring
"""

from typing import Dict, List
from datetime import datetime
from collections import deque
from loguru import logger
import time

class MetricsCollector:
    """Collects system and trading metrics"""

    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        
        # Time series metrics
        self.portfolio_values = deque(maxlen=max_history)
        self.returns = deque(maxlen=max_history)
        self.cycle_times = deque(maxlen=max_history)
        self.trade_counts = deque(maxlen=max_history)
        
        # Counters
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.api_calls = 0
        self.api_errors = 0
        
        # Timestamps
        self.start_time = datetime.now()
        self.last_update = datetime.now()
        
        logger.info("Metrics collector initialized")

    def record_portfolio_value(self, value: float):
        """Record portfolio value"""
        self.portfolio_values.append({
            'timestamp': datetime.now(),
            'value': value
        })
        self.last_update = datetime.now()

    def record_return(self, ret: float):
        """Record return"""
        self.returns.append({
            'timestamp': datetime.now(),
            'return': ret
        })

    def record_cycle_time(self, duration: float):
        """Record trading cycle duration"""
        self.cycle_times.append({
            'timestamp': datetime.now(),
            'duration': duration
        })

    def record_trade(self, success: bool = True):
        """Record trade execution"""
        self.total_trades += 1
        if success:
            self.successful_trades += 1
        else:
            self.failed_trades += 1
        
        self.trade_counts.append({
            'timestamp': datetime.now(),
            'success': success
        })

    def record_api_call(self, success: bool = True):
        """Record API call"""
        self.api_calls += 1
        if not success:
            self.api_errors += 1

    def get_metrics(self) -> Dict:
        """Get current metrics snapshot"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        # Calculate averages
        avg_cycle_time = sum(c['duration'] for c in self.cycle_times) / len(self.cycle_times) if self.cycle_times else 0
        
        # Success rates
        trade_success_rate = self.successful_trades / self.total_trades if self.total_trades > 0 else 0
        api_success_rate = (self.api_calls - self.api_errors) / self.api_calls if self.api_calls > 0 else 1
        
        return {
            'uptime_seconds': uptime,
            'total_trades': self.total_trades,
            'successful_trades': self.successful_trades,
            'failed_trades': self.failed_trades,
            'trade_success_rate': trade_success_rate,
            'api_calls': self.api_calls,
            'api_errors': self.api_errors,
            'api_success_rate': api_success_rate,
            'avg_cycle_time': avg_cycle_time,
            'last_update': self.last_update.isoformat()
        }

    def get_performance_summary(self) -> Dict:
        """Get performance summary"""
        if not self.portfolio_values:
            return {}
        
        values = [v['value'] for v in self.portfolio_values]
        initial_value = values[0]
        current_value = values[-1]
        
        total_return = (current_value / initial_value - 1) * 100
        
        import numpy as np
        returns_array = np.array([r['return'] for r in self.returns]) if self.returns else np.array([])
        
        if len(returns_array) > 1:
            sharpe = np.mean(returns_array) / np.std(returns_array) * np.sqrt(252)
        else:
            sharpe = 0
        
        return {
            'initial_value': initial_value,
            'current_value': current_value,
            'total_return_pct': total_return,
            'sharpe_ratio': sharpe,
            'num_data_points': len(self.portfolio_values)
        }

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        metrics = self.get_metrics()
        
        output = []
        output.append(f"# HELP trading_uptime_seconds System uptime")
        output.append(f"# TYPE trading_uptime_seconds gauge")
        output.append(f"trading_uptime_seconds {metrics['uptime_seconds']}")
        
        output.append(f"# HELP trading_total_trades Total number of trades")
        output.append(f"# TYPE trading_total_trades counter")
        output.append(f"trading_total_trades {metrics['total_trades']}")
        
        output.append(f"# HELP trading_success_rate Trade success rate")
        output.append(f"# TYPE trading_success_rate gauge")
        output.append(f"trading_success_rate {metrics['trade_success_rate']}")
        
        return '\n'.join(output)

    def reset(self):
        """Reset all metrics"""
        self.portfolio_values.clear()
        self.returns.clear()
        self.cycle_times.clear()
        self.trade_counts.clear()
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.api_calls = 0
        self.api_errors = 0
        self.start_time = datetime.now()
        logger.info("Metrics reset")
