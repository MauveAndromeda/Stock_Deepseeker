"""
Correlation and covariance matrix management.

Monitors correlation changes and systemic risk.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform
from loguru import logger


@dataclass
class CorrelationMetrics:
    """Correlation analysis metrics."""
    average_correlation: float
    median_correlation: float
    max_correlation: float
    min_correlation: float
    correlation_dispersion: float
    eigenvalue_ratio: float  # Largest eigenvalue / trace
    effective_dimension: int  # Number of significant eigenvalues
    timestamp: datetime


class CorrelationManager:
    """
    Manages correlation and covariance matrices.
    
    Monitors correlation changes that indicate regime shifts
    or systemic risk.
    """
    
    def __init__(
        self,
        lookback_window: int = 60,  # Days for correlation calculation
        ewma_lambda: float = 0.94,  # EWMA decay for covariance
        min_eigenvalue: float = 0.01  # Min eigenvalue to count
    ):
        """Initialize correlation manager."""
        self.lookback_window = lookback_window
        self.ewma_lambda = ewma_lambda
        self.min_eigenvalue = min_eigenvalue
        
        # Historical matrices
        self.correlation_history: List[pd.DataFrame] = []
        self.covariance_history: List[pd.DataFrame] = []
        self.metrics_history: List[CorrelationMetrics] = []
        
        logger.info("Initialized CorrelationManager")
    
    def update(
        self,
        returns: pd.DataFrame,  # columns = symbols
        use_ewma: bool = True
    ) -> CorrelationMetrics:
        """
        Update correlation and covariance matrices.
        
        Args:
            returns: Returns data (rows=dates, cols=symbols)
            use_ewma: Use exponentially weighted moving average
            
        Returns:
            CorrelationMetrics
        """
        if len(returns) < self.lookback_window:
            logger.warning(f"Insufficient data for correlation: {len(returns)} < {self.lookback_window}")
            return self._empty_metrics()
        
        # Calculate covariance matrix
        if use_ewma:
            cov_matrix = self._calculate_ewma_covariance(returns)
        else:
            cov_matrix = returns.cov()
        
        # Calculate correlation matrix
        corr_matrix = self._covariance_to_correlation(cov_matrix)
        
        # Store matrices
        self.correlation_history.append(corr_matrix)
        self.covariance_history.append(cov_matrix)
        
        # Calculate metrics
        metrics = self._calculate_metrics(corr_matrix, cov_matrix)
        self.metrics_history.append(metrics)
        
        logger.info(
            f"Correlation update: Avg={metrics.average_correlation:.3f}, "
            f"Max={metrics.max_correlation:.3f}"
        )
        
        return metrics
    
    def _calculate_ewma_covariance(
        self,
        returns: pd.DataFrame
    ) -> pd.DataFrame:
        """Calculate exponentially weighted covariance."""
        # Use pandas ewm
        ewma_cov = returns.ewm(
            span=self.lookback_window,
            min_periods=self.lookback_window
        ).cov()
        
        # Get latest covariance matrix
        latest_date = returns.index[-1]
        cov_matrix = ewma_cov.loc[latest_date]
        
        return cov_matrix
    
    def _covariance_to_correlation(
        self,
        cov_matrix: pd.DataFrame
    ) -> pd.DataFrame:
        """Convert covariance to correlation matrix."""
        std_devs = np.sqrt(np.diag(cov_matrix))
        std_matrix = np.outer(std_devs, std_devs)
        
        # Avoid division by zero
        std_matrix[std_matrix == 0] = 1
        
        corr_matrix = cov_matrix / std_matrix
        
        # Ensure correlation bounds [-1, 1]
        corr_matrix = corr_matrix.clip(-1, 1)
        
        return pd.DataFrame(
            corr_matrix,
            index=cov_matrix.index,
            columns=cov_matrix.columns
        )
    
    def _calculate_metrics(
        self,
        corr_matrix: pd.DataFrame,
        cov_matrix: pd.DataFrame
    ) -> CorrelationMetrics:
        """Calculate correlation metrics."""
        # Get upper triangle (exclude diagonal)
        n = len(corr_matrix)
        mask = np.triu(np.ones((n, n)), k=1).astype(bool)
        correlations = corr_matrix.values[mask]
        
        # Basic statistics
        avg_corr = correlations.mean()
        median_corr = np.median(correlations)
        max_corr = correlations.max()
        min_corr = correlations.min()
        dispersion = correlations.std()
        
        # Eigenvalue analysis
        eigenvalues = np.linalg.eigvalsh(cov_matrix.values)
        eigenvalues = eigenvalues[eigenvalues > 0]  # Keep positive
        
        # Eigenvalue concentration
        if len(eigenvalues) > 0:
            eigenvalue_ratio = eigenvalues[-1] / eigenvalues.sum()
            effective_dim = np.sum(eigenvalues > self.min_eigenvalue)
        else:
            eigenvalue_ratio = 0
            effective_dim = 0
        
        return CorrelationMetrics(
            average_correlation=avg_corr,
            median_correlation=median_corr,
            max_correlation=max_corr,
            min_correlation=min_corr,
            correlation_dispersion=dispersion,
            eigenvalue_ratio=eigenvalue_ratio,
            effective_dimension=int(effective_dim),
            timestamp=datetime.now()
        )
    
    def detect_correlation_spike(
        self,
        threshold: float = 0.05
    ) -> Optional[Dict]:
        """
        Detect sudden correlation increases (flight to quality).
        
        Args:
            threshold: Minimum correlation increase to trigger alert
            
        Returns:
            Alert dict if spike detected, None otherwise
        """
        if len(self.metrics_history) < 2:
            return None
        
        current = self.metrics_history[-1]
        previous = self.metrics_history[-2]
        
        correlation_change = current.average_correlation - previous.average_correlation
        
        if correlation_change > threshold:
            return {
                'type': 'correlation_spike',
                'current_correlation': current.average_correlation,
                'previous_correlation': previous.average_correlation,
                'change': correlation_change,
                'timestamp': current.timestamp
            }
        
        return None
    
    def get_diversification_ratio(
        self,
        weights: pd.Series  # Portfolio weights
    ) -> float:
        """
        Calculate diversification ratio.
        
        DR = (weighted avg volatility) / (portfolio volatility)
        Higher = better diversification
        
        Args:
            weights: Portfolio weights (symbol -> weight)
            
        Returns:
            Diversification ratio
        """
        if len(self.covariance_history) == 0:
            return 1.0
        
        cov_matrix = self.covariance_history[-1]
        
        # Align weights with covariance matrix
        aligned_weights = weights.reindex(cov_matrix.index, fill_value=0)
        
        # Individual volatilities
        individual_vols = np.sqrt(np.diag(cov_matrix))
        
        # Weighted average volatility
        weighted_avg_vol = np.sum(np.abs(aligned_weights.values) * individual_vols)
        
        # Portfolio volatility
        portfolio_var = np.dot(aligned_weights.values, np.dot(cov_matrix.values, aligned_weights.values))
        portfolio_vol = np.sqrt(portfolio_var)
        
        if portfolio_vol > 0:
            diversification_ratio = weighted_avg_vol / portfolio_vol
        else:
            diversification_ratio = 1.0
        
        return diversification_ratio
    
    def get_correlation_clusters(
        self,
        n_clusters: int = 5
    ) -> Dict[int, List[str]]:
        """
        Identify correlation-based asset clusters.
        
        Uses hierarchical clustering on correlation matrix.
        
        Args:
            n_clusters: Number of clusters to form
            
        Returns:
            Dict mapping cluster_id -> list of symbols
        """
        if len(self.correlation_history) == 0:
            return {}
        
        corr_matrix = self.correlation_history[-1]
        
        # Convert correlation to distance
        distance_matrix = 1 - corr_matrix.abs()
        
        # Hierarchical clustering
        condensed_dist = squareform(distance_matrix.values, checks=False)
        linkage = hierarchy.linkage(condensed_dist, method='ward')
        
        # Cut tree
        clusters = hierarchy.fcluster(linkage, n_clusters, criterion='maxclust')
        
        # Map clusters to symbols
        cluster_map = {}
        for symbol, cluster_id in zip(corr_matrix.index, clusters):
            if cluster_id not in cluster_map:
                cluster_map[cluster_id] = []
            cluster_map[cluster_id].append(symbol)
        
        return cluster_map
    
    def get_principal_components(
        self,
        n_components: int = 5
    ) -> pd.DataFrame:
        """
        Get principal components of covariance matrix.
        
        Args:
            n_components: Number of components to return
            
        Returns:
            DataFrame with principal component loadings
        """
        if len(self.covariance_history) == 0:
            return pd.DataFrame()
        
        cov_matrix = self.covariance_history[-1]
        
        # Eigenvalue decomposition
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix.values)
        
        # Sort by eigenvalue (descending)
        idx = eigenvalues.argsort()[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        
        # Get top n components
        top_components = eigenvectors[:, :n_components]
        
        # Create DataFrame
        pc_df = pd.DataFrame(
            top_components,
            index=cov_matrix.index,
            columns=[f'PC{i+1}' for i in range(n_components)]
        )
        
        # Add variance explained
        variance_explained = eigenvalues[:n_components] / eigenvalues.sum()
        pc_df.loc['variance_explained'] = variance_explained
        
        return pc_df
    
    def get_risk_contribution(
        self,
        weights: pd.Series
    ) -> pd.Series:
        """
        Calculate marginal risk contribution of each position.
        
        MRC_i = (∂σ_p / ∂w_i) = (Σw · ∂Σ/∂w_i) / σ_p
        
        Args:
            weights: Portfolio weights
            
        Returns:
            Series of marginal risk contributions
        """
        if len(self.covariance_history) == 0:
            return pd.Series()
        
        cov_matrix = self.covariance_history[-1]
        
        # Align weights
        aligned_weights = weights.reindex(cov_matrix.index, fill_value=0)
        
        # Portfolio variance
        portfolio_var = np.dot(aligned_weights.values, np.dot(cov_matrix.values, aligned_weights.values))
        portfolio_vol = np.sqrt(portfolio_var)
        
        if portfolio_vol == 0:
            return pd.Series(0, index=weights.index)
        
        # Marginal risk contribution
        marginal_contrib = np.dot(cov_matrix.values, aligned_weights.values) / portfolio_vol
        
        # Total risk contribution (MRC * weight)
        risk_contrib = marginal_contrib * aligned_weights.values
        
        return pd.Series(risk_contrib, index=cov_matrix.index)
    
    def _empty_metrics(self) -> CorrelationMetrics:
        """Return empty metrics."""
        return CorrelationMetrics(
            average_correlation=0,
            median_correlation=0,
            max_correlation=0,
            min_correlation=0,
            correlation_dispersion=0,
            eigenvalue_ratio=0,
            effective_dimension=0,
            timestamp=datetime.now()
        )
