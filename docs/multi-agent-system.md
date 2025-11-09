# Multi-Agent Trading System

**Research-grade implementation (Under Development)**

A complete multi-agent system integrating LangChain, LangGraph, and quantitative backtesting.

## ⚠️ Development Status

This is a research-grade system under active development:
- ✅ Core architecture implemented and tested
- ✅ Integrated with backtest engine (no lookahead bias)
- ✅ Mock mode works offline (no API keys needed)
- ⚠️ LLM mode requires API keys and incurs costs
- ❌ Not production-ready
- ❌ Performance not yet validated on real markets

## Architecture

### 1. MU (Model Unified) Layer

`src/ai/model_unified.py`

Unified interface for multiple LLM providers:
- OpenAI (GPT-4o, GPT-4o-mini)
- Anthropic (Claude 3.5 Sonnet)
- DeepSeek (future)
- Local models (future)

Features:
- Rate limiting
- Automatic retry with exponential backoff
- Cost tracking
- Model routing based on task requirements
- Fallback mechanism

### 2. Enhanced Agent System

`src/agents/enhanced_base.py`

LLM-powered trading agents with distinct personalities:
- **MomentumChaserAgent**: Aggressive, follows trends
- **ValueSeekerAgent**: Patient, seeks undervalued stocks
- **TechnicalTraderAgent**: Systematic, relies on indicators
- **QuantitativeAgent**: Data-driven, factor-based

Each agent:
- Uses LangChain prompt templates
- Maintains conversation memory
- Provides structured JSON output
- Tracks performance

### 3. LangGraph Workflow

`src/agents/langgraph_workflow.py`

Multi-round expert discussion using graph-based workflow:

```
┌─────────────────┐
│ Sentiment       │
│ Analyst         │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Institutional   │
│ Analyst         │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Risk Manager    │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Market Timer    │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Chairman        │
│ (Synthesizer)   │
└────────┬────────┘
         ▼
    Check Rounds
         ▼
   Continue/End
```

Features:
- Configurable discussion rounds
- Early termination on strong consensus
- Full discussion history tracking
- State management across rounds

### 4. Backtest Integration

`src/agents/backtest_integration.py`

Seamless integration with the backtest engine:
- **No lookahead bias**: Signals generated at T, executed at T+1
- **Async/sync bridge**: Handles event loop complexity
- **Multi-agent consensus**: Votes or expert panel synthesis
- **Performance tracking**: Decision history and statistics

## Usage

### Quick Start (Mock Mode)

No API keys needed:

```bash
python run_multi_agent_backtest.py --mock
```

This uses rule-based mock agents to demonstrate the system without LLM calls.

### Full System (LLM Mode)

Requires API keys:

```bash
# Set API keys
export OPENAI_API_KEY="your-key"
# or
export ANTHROPIC_API_KEY="your-key"

# Run with LLM agents
python run_multi_agent_backtest.py --use-llm
```

### Advanced Options

```bash
# Multiple symbols
python run_multi_agent_backtest.py --mock --symbols AAPL MSFT GOOGL

# Custom date range
python run_multi_agent_backtest.py --mock --start 2023-01-01 --end 2024-12-31

# Custom capital
python run_multi_agent_backtest.py --mock --capital 50000
```

## Configuration

### Model Tiers

Control cost vs. performance:

```python
from src.ai.model_unified import ModelTier

# Fast and cheap
ModelTier.FAST  # e.g., gpt-4o-mini

# Balanced
ModelTier.BALANCED  # e.g., gpt-4o

# Premium quality
ModelTier.PREMIUM  # e.g., claude-3-5-sonnet
```

### Agent Parameters

```python
agent = MomentumChaserAgent(
    agent_id="momentum_1",
    agent_type=AgentType.MOMENTUM_CHASER,
    initial_capital=100000,
    risk_tolerance=0.7,  # 0-1
    model_tier=ModelTier.FAST,
    use_memory=True  # Remember previous decisions
)
```

### Strategy Configuration

```python
strategy = MultiAgentStrategy(
    name="MyStrategy",
    agents=[agent1, agent2, agent3],
    use_expert_panel=True,  # Enable LangGraph workflow
    expert_panel_rounds=2,  # Discussion rounds
    consensus_threshold=0.6,  # Minimum agreement ratio
    min_confidence=0.65  # Minimum confidence to act
)
```

## Testing

Run comprehensive tests:

```bash
pytest tests/test_multi_agent_system.py -v
```

Tests cover:
- MU layer (model routing, rate limiting)
- Enhanced agents (prompt templates, memory)
- LangGraph workflow (state management, routing)
- Backtest integration (signal generation, consensus)
- End-to-end pipeline

## Performance Considerations

### Cost Management

LLM calls incur costs:
- Fast tier: ~$0.0002 per decision
- Balanced tier: ~$0.005 per decision
- Expert panel: 4-5 calls per round × rounds

For 100 decisions with expert panel (2 rounds):
- Fast agents: ~$0.02
- Expert panel: ~$0.05
- **Total: ~$0.07 per backtest run**

### Latency

- Mock mode: <1ms per decision
- LLM mode (fast tier): ~500ms per decision
- LLM mode with expert panel: ~2-3s per decision

For 100 trading days:
- Mock: ~1 second
- LLM (agents only): ~50 seconds
- LLM (with expert panel): ~5 minutes

### Optimization Tips

1. **Use mock mode for development/testing**
2. **Cache agent decisions** if running multiple backtests
3. **Disable expert panel** for faster iteration
4. **Use fast-tier models** unless quality is critical
5. **Batch similar decisions** to reduce API calls

## Limitations

### Current

1. **Not production-ready**: Research code, not battle-tested
2. **LLM non-determinism**: Results vary between runs
3. **No live trading**: Only backtesting supported
4. **Limited validation**: Needs more real-world testing
5. **API dependencies**: Requires external services

### Future Improvements

1. **Local model support**: Run offline with local LLMs
2. **Caching layer**: Reduce API costs
3. **Fine-tuned models**: Better performance for trading
4. **Real-time mode**: Support live trading
5. **Ensemble methods**: Combine multiple strategies
6. **Reinforcement learning**: Agents learn from outcomes

## Safety & Risk Management

### Built-in Protections

1. **No lookahead bias**: Enforced by architecture
2. **Position limits**: Configured in BacktestConfig
3. **Risk checks**: VaR, concentration limits
4. **Consensus requirements**: Prevent single-agent mistakes
5. **Confidence thresholds**: Only act on strong signals

### Recommended Practices

1. **Always backtest first**: Never trade without testing
2. **Start with mock mode**: Understand behavior before LLM
3. **Monitor costs**: Track API usage
4. **Set strict limits**: Maximum position sizes, stop losses
5. **Paper trading first**: Test with fake money
6. **Independent validation**: Verify results manually

## Examples

### Creating Custom Agents

```python
from src.agents.enhanced_base import LLMEnhancedAgent
from langchain_core.prompts import PromptTemplate

class ConservativeAgent(LLMEnhancedAgent):
    def _create_prompt_template(self):
        template = """
        You are an extremely conservative investor.
        Only recommend BUY when all indicators are perfect.
        Prefer HOLD in most situations.

        Market Data: {market_context}
        Your Profile: Risk Tolerance {risk_tolerance}

        {format_instructions}
        """
        return PromptTemplate.from_template(template)

    def _get_personality_traits(self):
        return "Ultra-conservative. Safety first. Low risk tolerance."
```

### Custom Expert Panel

```python
workflow = ExpertPanelWorkflow(
    max_rounds=3,  # More discussion rounds
    model_tier=ModelTier.PREMIUM  # Higher quality
)

result = await workflow.discuss(
    symbol="AAPL",
    market_data=data,
    metadata={'urgency': 'high'}
)
```

## Troubleshooting

### Common Issues

**"API key not set"**
```bash
export OPENAI_API_KEY="sk-..."
```

**"Rate limit exceeded"**
- Reduce concurrent requests
- Use slower model tier
- Add delays between calls

**"No signals generated"**
- Check confidence thresholds
- Verify agent logic
- Review decision history

**"Async errors"**
- nest-asyncio should handle this
- If issues persist, use mock mode

## Contributing

This is research code. Contributions welcome:

1. Test thoroughly
2. Document changes
3. Be honest about limitations
4. Update tests
5. Check performance impact

## References

- [LangChain Documentation](https://python.langchain.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Event-Driven Backtesting](./docs/backtest_architecture.md)
- [No Lookahead Bias](./docs/lookahead_bias.md)

## License

Research and educational use only.

---

**Built for research. Test before use. Not financial advice.**
