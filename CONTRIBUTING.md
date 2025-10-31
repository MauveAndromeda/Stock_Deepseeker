# Contributing to Stock DeepSeeker

Thank you for your interest in contributing to Stock DeepSeeker!

## Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL with TimescaleDB
- Redis
- Docker (optional)

### Installation

```bash
git clone https://github.com/MauveAndromeda/Stock_Deepseeker.git
cd Stock_Deepseeker

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your API keys

# Initialize database
python scripts/setup/init_database.py
```

## Project Structure

```
Stock_Deepseeker/
├── src/                    # Main source code
│   ├── data/              # Data collection and processing
│   ├── features/          # Feature engineering
│   ├── models/            # AI models (Transformer, SAC)
│   ├── trading/           # Trading strategies and execution
│   ├── risk/              # Risk management
│   ├── portfolio/         # Portfolio management
│   ├── backtesting/       # Backtesting engine
│   ├── monitoring/        # Monitoring and metrics
│   ├── api/               # External API integrations
│   └── utils/             # Utility functions
├── tests/                 # Unit and integration tests
├── scripts/               # Setup and deployment scripts
├── config/                # Configuration files
├── docs/                  # Documentation
└── notebooks/             # Jupyter notebooks for research
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Follow PEP 8 style guidelines
- Add type hints to all functions
- Write docstrings for all public APIs
- Add logging for important operations

### 3. Write Tests

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=src tests/
```

### 4. Lint and Format

```bash
# Format code
black src/ tests/

# Lint
flake8 src/ tests/
pylint src/

# Type check
mypy src/
```

### 5. Commit Changes

```bash
git add .
git commit -m "feat: add new feature"
```

Use conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance tasks

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

## Code Guidelines

### Python Style

- Use Black for formatting (line length: 88)
- Follow PEP 8
- Use type hints
- Write comprehensive docstrings

### Example Function

```python
def calculate_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252,
) -> float:
    """
    Calculate annualized Sharpe ratio.

    Args:
        returns: Array of returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year

    Returns:
        Annualized Sharpe ratio

    Raises:
        ValueError: If returns array is empty

    Examples:
        >>> returns = np.array([0.01, 0.02, -0.01, 0.03])
        >>> sharpe = calculate_sharpe_ratio(returns)
        >>> print(f"Sharpe: {sharpe:.2f}")
    """
    if len(returns) == 0:
        raise ValueError("Returns array cannot be empty")

    excess_returns = returns - (risk_free_rate / periods_per_year)
    
    if np.std(excess_returns) == 0:
        return 0.0

    sharpe = np.mean(excess_returns) / np.std(excess_returns)
    return sharpe * np.sqrt(periods_per_year)
```

### Testing Guidelines

- Write unit tests for all new functions
- Aim for >80% code coverage
- Use pytest fixtures for common test data
- Test edge cases and error conditions

### Example Test

```python
def test_calculate_sharpe_ratio():
    """Test Sharpe ratio calculation"""
    # Positive returns
    returns = np.array([0.01, 0.02, 0.01, 0.03])
    sharpe = calculate_sharpe_ratio(returns)
    assert sharpe > 0

    # Zero returns
    returns = np.zeros(100)
    sharpe = calculate_sharpe_ratio(returns)
    assert sharpe == 0

    # Empty array
    with pytest.raises(ValueError):
        calculate_sharpe_ratio(np.array([]))
```

## Adding New Features

### New Data Source

1. Create collector in `src/data/collectors/`
2. Implement data fetching and parsing
3. Add caching for API calls
4. Write tests
5. Update documentation

### New Trading Strategy

1. Inherit from `BaseStrategy` in `src/trading/strategy/base.py`
2. Implement required methods:
   - `analyze()`
   - `should_enter()`
   - `should_exit()`
3. Add strategy tests
4. Document strategy logic

### New AI Model

1. Create model in appropriate `src/models/` subdirectory
2. Implement training pipeline
3. Add model serialization/deserialization
4. Write inference code
5. Add evaluation metrics

## Performance Considerations

- Use vectorized operations (NumPy, Pandas)
- Cache expensive computations
- Use async for I/O operations
- Profile code with `cProfile` for bottlenecks
- Consider using Numba for hot loops

## Security

- Never commit API keys or secrets
- Use environment variables for sensitive data
- Validate all external inputs
- Use prepared statements for database queries
- Implement rate limiting for API calls

## Documentation

- Update README.md for major changes
- Add docstrings to all public APIs
- Create notebooks for complex features
- Update CHANGELOG.md

## Questions?

- Open an issue for bugs
- Start a discussion for features
- Join our Discord/Slack (link)

Thank you for contributing! 🚀
