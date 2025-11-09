"""
AI模型层
包含最先进的深度学习和强化学习模型

Note: Deep learning models require torch/transformers (install with: pip install stock-deepseeker[ai])
"""

# Always available
from src.models.alpha_factors import AlphaFactorLibrary

__all__ = ["AlphaFactorLibrary"]

# Optional AI/RL dependencies
try:
    from src.models.ensemble import (
        EnsembleModel,
        ModelRegistry,
    )
    from src.models.gpt5_client import (
        GPT5Client,
        GPT5Config,
        MarketAnalyzer,
    )
    from src.models.sac import (
        SACAgent,
        SACConfig,
        TradingEnvironment,
    )
    from src.models.transformer import (
        MarketTransformer,
        TimeSeriesTransformer,
        TransformerConfig,
    )

    __all__ += [
        "EnsembleModel",
        "GPT5Client",
        "GPT5Config",
        "MarketAnalyzer",
        "MarketTransformer",
        "ModelRegistry",
        "SACAgent",
        "SACConfig",
        "TimeSeriesTransformer",
        "TradingEnvironment",
        "TransformerConfig",
    ]
except ImportError as e:
    # AI dependencies not installed
    import warnings
    warnings.warn(
        f"AI/RL models not available. Install with: pip install stock-deepseeker[ai,rl]. Error: {e}",
        ImportWarning
    )
