"""
Strategy Optimizer
Optimizes strategy parameters using various methods
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor
from loguru import logger
import optuna


@dataclass
class OptimizationResult:
    """Result of optimization"""
    best_params: Dict
    best_score: float
    all_trials: List[Dict]
    optimization_time: float


class StrategyOptimizer:
    """Optimizes trading strategy parameters"""

    def __init__(self, objective_metric: str = 'sharpe_ratio'):
        """
        Args:
            objective_metric: Metric to optimize (sharpe_ratio, total_return, etc.)
        """
        self.objective_metric = objective_metric
        logger.info(f"Strategy optimizer initialized with metric: {objective_metric}")

    def grid_search(
        self,
        strategy_class,
        param_grid: Dict,
        data: pd.DataFrame,
        n_jobs: int = 4
    ) -> OptimizationResult:
        """
        Grid search optimization
        
        Args:
            strategy_class: Strategy class to optimize
            param_grid: Dict of parameter names -> list of values
            data: Historical data for backtesting
            n_jobs: Number of parallel jobs
            
        Returns:
            OptimizationResult
        """
        import time
        import itertools
        
        start_time = time.time()
        logger.info(f"Starting grid search with {len(param_grid)} parameters")
        
        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(itertools.product(*param_values))
        
        logger.info(f"Testing {len(combinations)} parameter combinations")
        
        # Test each combination
        results = []
        best_score = -np.inf
        best_params = None
        
        def evaluate_params(params):
            """Evaluate single parameter set"""
            param_dict = dict(zip(param_names, params))
            
            try:
                # Create strategy with these params
                # (This is simplified - in production would run full backtest)
                score = self._evaluate_strategy(strategy_class, param_dict, data)
                
                return {
                    'params': param_dict,
                    'score': score
                }
            except Exception as e:
                logger.error(f"Error evaluating {param_dict}: {e}")
                return {
                    'params': param_dict,
                    'score': -np.inf
                }
        
        # Parallel evaluation
        with ProcessPoolExecutor(max_workers=n_jobs) as executor:
            results = list(executor.map(evaluate_params, combinations))
        
        # Find best
        for result in results:
            if result['score'] > best_score:
                best_score = result['score']
                best_params = result['params']
        
        optimization_time = time.time() - start_time
        
        logger.info(f"Grid search complete in {optimization_time:.2f}s")
        logger.info(f"Best score: {best_score:.4f}")
        logger.info(f"Best params: {best_params}")
        
        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            all_trials=results,
            optimization_time=optimization_time
        )

    def random_search(
        self,
        strategy_class,
        param_distributions: Dict,
        n_iterations: int = 100,
        data: pd.DataFrame = None
    ) -> OptimizationResult:
        """
        Random search optimization
        
        Args:
            strategy_class: Strategy class
            param_distributions: Dict of parameter -> (min, max) or list
            n_iterations: Number of iterations
            data: Historical data
            
        Returns:
            OptimizationResult
        """
        import time
        
        start_time = time.time()
        logger.info(f"Starting random search with {n_iterations} iterations")
        
        results = []
        best_score = -np.inf
        best_params = None
        
        for i in range(n_iterations):
            # Sample random parameters
            params = {}
            for param_name, distribution in param_distributions.items():
                if isinstance(distribution, tuple):
                    # Uniform sampling from range
                    params[param_name] = np.random.uniform(distribution[0], distribution[1])
                elif isinstance(distribution, list):
                    # Random choice from list
                    params[param_name] = np.random.choice(distribution)
            
            # Evaluate
            score = self._evaluate_strategy(strategy_class, params, data)
            
            results.append({
                'params': params,
                'score': score
            })
            
            if score > best_score:
                best_score = score
                best_params = params
            
            if (i + 1) % 10 == 0:
                logger.info(f"Iteration {i+1}/{n_iterations}, Best score: {best_score:.4f}")
        
        optimization_time = time.time() - start_time
        
        logger.info(f"Random search complete in {optimization_time:.2f}s")
        
        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            all_trials=results,
            optimization_time=optimization_time
        )

    def bayesian_optimization(
        self,
        strategy_class,
        param_space: Dict,
        n_trials: int = 100,
        data: pd.DataFrame = None
    ) -> OptimizationResult:
        """
        Bayesian optimization using Optuna
        
        Args:
            strategy_class: Strategy class
            param_space: Dict of parameter definitions
            n_trials: Number of trials
            data: Historical data
            
        Returns:
            OptimizationResult
        """
        import time
        
        start_time = time.time()
        logger.info(f"Starting Bayesian optimization with {n_trials} trials")
        
        def objective(trial):
            """Optuna objective function"""
            params = {}
            
            for param_name, param_def in param_space.items():
                if param_def['type'] == 'float':
                    params[param_name] = trial.suggest_float(
                        param_name,
                        param_def['low'],
                        param_def['high']
                    )
                elif param_def['type'] == 'int':
                    params[param_name] = trial.suggest_int(
                        param_name,
                        param_def['low'],
                        param_def['high']
                    )
                elif param_def['type'] == 'categorical':
                    params[param_name] = trial.suggest_categorical(
                        param_name,
                        param_def['choices']
                    )
            
            score = self._evaluate_strategy(strategy_class, params, data)
            return score
        
        # Create study
        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=n_trials)
        
        # Get results
        best_params = study.best_params
        best_score = study.best_value
        
        all_trials = [
            {
                'params': trial.params,
                'score': trial.value
            }
            for trial in study.trials
        ]
        
        optimization_time = time.time() - start_time
        
        logger.info(f"Bayesian optimization complete in {optimization_time:.2f}s")
        logger.info(f"Best score: {best_score:.4f}")
        logger.info(f"Best params: {best_params}")
        
        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            all_trials=all_trials,
            optimization_time=optimization_time
        )

    def genetic_algorithm(
        self,
        strategy_class,
        param_ranges: Dict,
        population_size: int = 50,
        n_generations: int = 20,
        mutation_rate: float = 0.1,
        data: pd.DataFrame = None
    ) -> OptimizationResult:
        """
        Genetic algorithm optimization
        
        Args:
            strategy_class: Strategy class
            param_ranges: Dict of parameter -> (min, max)
            population_size: Size of population
            n_generations: Number of generations
            mutation_rate: Mutation rate
            data: Historical data
            
        Returns:
            OptimizationResult
        """
        import time
        
        start_time = time.time()
        logger.info(f"Starting genetic algorithm: pop={population_size}, gen={n_generations}")
        
        param_names = list(param_ranges.keys())
        
        # Initialize population
        population = []
        for _ in range(population_size):
            individual = {}
            for param_name, (min_val, max_val) in param_ranges.items():
                individual[param_name] = np.random.uniform(min_val, max_val)
            population.append(individual)
        
        all_trials = []
        best_score = -np.inf
        best_params = None
        
        for generation in range(n_generations):
            # Evaluate fitness
            fitness_scores = []
            for individual in population:
                score = self._evaluate_strategy(strategy_class, individual, data)
                fitness_scores.append(score)
                
                all_trials.append({
                    'params': individual.copy(),
                    'score': score
                })
                
                if score > best_score:
                    best_score = score
                    best_params = individual.copy()
            
            # Selection (tournament selection)
            new_population = []
            for _ in range(population_size):
                # Select parents
                tournament_size = 3
                tournament_idx = np.random.choice(population_size, tournament_size, replace=False)
                tournament_fitness = [fitness_scores[i] for i in tournament_idx]
                winner_idx = tournament_idx[np.argmax(tournament_fitness)]
                parent = population[winner_idx]
                
                # Create offspring (with mutation)
                offspring = {}
                for param_name, value in parent.items():
                    if np.random.random() < mutation_rate:
                        # Mutate
                        min_val, max_val = param_ranges[param_name]
                        mutation = np.random.uniform(-0.1 * (max_val - min_val), 0.1 * (max_val - min_val))
                        offspring[param_name] = np.clip(value + mutation, min_val, max_val)
                    else:
                        offspring[param_name] = value
                
                new_population.append(offspring)
            
            population = new_population
            
            logger.info(f"Generation {generation+1}/{n_generations}, Best score: {best_score:.4f}")
        
        optimization_time = time.time() - start_time
        
        logger.info(f"Genetic algorithm complete in {optimization_time:.2f}s")
        
        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            all_trials=all_trials,
            optimization_time=optimization_time
        )

    def walk_forward_optimization(
        self,
        strategy_class,
        param_grid: Dict,
        data: pd.DataFrame,
        train_size: int = 252,
        test_size: int = 63,
        step_size: int = 21
    ) -> List[Dict]:
        """
        Walk-forward optimization
        
        Args:
            strategy_class: Strategy class
            param_grid: Parameter grid
            data: Historical data
            train_size: Training window size (days)
            test_size: Test window size (days)
            step_size: Step size between windows
            
        Returns:
            List of results for each window
        """
        logger.info("Starting walk-forward optimization")
        
        results = []
        
        for start_idx in range(0, len(data) - train_size - test_size, step_size):
            # Split data
            train_end = start_idx + train_size
            test_end = train_end + test_size
            
            train_data = data.iloc[start_idx:train_end]
            test_data = data.iloc[train_end:test_end]
            
            # Optimize on training data
            opt_result = self.grid_search(
                strategy_class,
                param_grid,
                train_data,
                n_jobs=1
            )
            
            # Test on out-of-sample data
            test_score = self._evaluate_strategy(
                strategy_class,
                opt_result.best_params,
                test_data
            )
            
            results.append({
                'train_period': (train_data.index[0], train_data.index[-1]),
                'test_period': (test_data.index[0], test_data.index[-1]),
                'best_params': opt_result.best_params,
                'train_score': opt_result.best_score,
                'test_score': test_score
            })
            
            logger.info(f"Window {len(results)}: Train={opt_result.best_score:.4f}, Test={test_score:.4f}")
        
        return results

    def _evaluate_strategy(
        self,
        strategy_class,
        params: Dict,
        data: pd.DataFrame
    ) -> float:
        """
        Evaluate strategy with given parameters
        
        Args:
            strategy_class: Strategy class
            params: Parameters
            data: Data for evaluation
            
        Returns:
            Score (higher is better)
        """
        # This is a simplified evaluation
        # In production, would run full backtest
        
        try:
            # Create strategy config with params
            from src.trading.strategy.base import StrategyConfig
            
            config = StrategyConfig(
                name="test_strategy",
                **params
            )
            
            # Create strategy instance
            strategy = strategy_class(config)
            
            # Simulate trades (simplified)
            equity = [10000]
            
            for i in range(len(data) - 1):
                df_slice = data.iloc[:i+1]
                
                # Generate signal
                signal = strategy.analyze(df_slice, "TEST")
                
                # Simulate return based on signal
                actual_return = (data.iloc[i+1]['close'] / data.iloc[i]['close'] - 1)
                
                if signal.action == 'buy':
                    portfolio_return = actual_return * signal.strength
                elif signal.action == 'sell':
                    portfolio_return = -actual_return * signal.strength
                else:
                    portfolio_return = 0
                
                equity.append(equity[-1] * (1 + portfolio_return))
            
            # Calculate metric
            equity_array = np.array(equity)
            returns = np.diff(equity_array) / equity_array[:-1]
            
            if self.objective_metric == 'sharpe_ratio':
                if len(returns) > 1 and np.std(returns) > 0:
                    score = np.mean(returns) / np.std(returns) * np.sqrt(252)
                else:
                    score = 0
            elif self.objective_metric == 'total_return':
                score = (equity[-1] / equity[0] - 1) * 100
            elif self.objective_metric == 'calmar_ratio':
                total_return = equity[-1] / equity[0] - 1
                running_max = np.maximum.accumulate(equity_array)
                drawdown = (equity_array - running_max) / running_max
                max_dd = abs(np.min(drawdown))
                score = total_return / max_dd if max_dd > 0 else 0
            else:
                score = 0
            
            return score
            
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return -np.inf
