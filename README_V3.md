# Stock Deepseeker v3.0 - 机构级AI量化交易系统

完全升级版本，基于2025年最先进的AI技术

## 核心技术升级

### AI模型（全新）
- ✅ **Transformer架构**：512维度，8注意力头，市场序列预测
- ✅ **SAC强化学习**：Soft Actor-Critic，自适应策略优化  
- ✅ **ChatGPT-5 Nano API**：深度市场分析和情绪解读
- ✅ **集成模型系统**：多模型加权集成，自适应权重调整

### 系统架构（机构级）
```
代码量：20,000+ 行生产级代码
模块：核心基础设施、AI模型、数据处理、智能体、执行、风险、回测、监控
技术栈：Python 3.11+, PyTorch 2.4, Transformers 4.46, OpenAI API
```

## 升级亮点

1. **配置管理系统**（650行）
   - 多环境支持、动态配置、验证系统
   
2. **日志系统**（400行）
   - 结构化日志、JSON格式、多目标输出

3. **事件系统**（450行）
   - 发布-订阅、异步处理、事件历史

4. **指标收集**（450行）
   - Prometheus导出、实时监控

5. **缓存管理**（450行）
   - LRU/LFU/TTL策略、多级缓存

6. **Transformer模型**（500行）
   - 相对位置编码、时间特征嵌入

7. **SAC强化学习**（600行）
   - 双Critic架构、自动熵调节

8. **GPT-5集成**（350行）
   - 市场分析、技术分析、交易决策

9. **数据处理**（900行）
   - 多源数据、特征工程、数据验证

## 快速开始

bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
export GPT5_API_KEY="your_key"
export BROKER_API_KEY="your_key"

# 运行系统
python main_upgraded.py


## 系统要求

- Python 3.11+
- CUDA 11.8+ (可选，用于GPU加速)
- 8GB+ RAM
- API密钥：ChatGPT-5、Alpaca/IBKR

## 版本对比

| 特性 | v2.0 | v3.0 |
|------|------|------|
| 代码量 | 11,000行 | 20,000+行 |
| AI技术 | OpenAI API | Transformer + SAC + GPT-5 |
| 数据源 | 单一 | 多源融合 |
| 风险管理 | 基础 | 机构级 |
| 监控系统 | 简单 | 完整Dashboard |

## 许可证
MIT License
