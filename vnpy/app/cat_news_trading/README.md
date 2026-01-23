# 新闻驱动交易策略

一个基于 vn.py 框架的新闻事件驱动交易系统，支持多种执行模式。

## 功能特点

- 📰 **多新闻源支持**: RSS、API、Mock（测试用）
- 🤖 **AI情感分析**: 支持关键词、SnowNLP、BERT三种分析器
- 📱 **飞书集成**: 支持消息推送、审批流程、命令交互
- ⚙️ **灵活配置**: 4种执行模式，满足不同风控需求

## 执行模式

### 模式一：直接执行 (DIRECT)
分析新闻后立即执行交易指令，无需人工干预。

**适用场景**: 高频交易、自动策略、测试环境

**配置**: `execution_mode = "direct"`

```bash
python -m vnpy.app.news_trading.run_direct
```

### 模式二：飞书审批 (LARK_APPROVAL)
分析后推送到飞书，等待人工审批后执行交易。

**适用场景**: 中等风险、需要人工确认的策略

**配置**: `execution_mode = "lark"`

```bash
python -m vnpy.app.news_trading.run_lark
```

### 模式三：混合模式 (HYBRID)
小仓位直接执行，大仓位飞书审批。

**适用场景**: 平衡效率和风控的交易

**配置**:
```python
execution_mode = "hybrid"
direct_threshold = 1000.0  # 小于1000美元直接执行
```

```bash
python -m vnpy.app.news_trading.run_hybrid
```

### 模式四：仅通知 (MANUAL)
只推送分析结果，不自动执行交易。

**适用场景**: 研究分析、策略回测、人工决策

**配置**: `execution_mode = "manual"`

```bash
python -m vnpy.app.news_trading.run_manual
```

## 安装依赖

```bash
# 基础依赖
pip install vnpy

# 新闻采集
pip install feedparser requests

# 情感分析
pip install jieba snownlp

# BERT分析器（可选）
pip install torch transformers

# 飞书集成
pip install flask requests
```

## 配置说明

### 新闻源配置

```python
news_config = {
    "fetch_interval": 60,  # 获取间隔（秒）
    "news_sources": [
        {
            "type": "rss",
            "name": "新浪财经",
            "url": "http://finance.sina.com.cn/roll/finance.d.html"
        },
        {
            "type": "api",
            "name": "NewsAPI",
            "url": "https://newsapi.org/v2/top-headlines",
            "api_key": "your_api_key",
            "params": {
                "country": "cn",
                "category": "business"
            }
        },
        {
            "type": "mock",  # 模拟新闻（用于测试）
            "name": "Mock"
        }
    ]
}
```

### 飞书配置

1. 在飞书开放平台创建应用：https://open.feishu.cn/app
2. 获取 App ID 和 App Secret
3. 创建机器人并获取 Chat ID
4. 配置 Webhook（可选）

```python
lark_config = {
    "lark_app_id": "your_app_id",
    "lark_app_secret": "your_app_secret",
    "lark_chat_id": "oc_xxxxxxxxxxxxxxxx",
    "lark_approval_timeout": 300,  # 审批超时时间（秒）
}
```

### 策略参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `execution_mode` | 执行模式 | `direct` |
| `sentiment_threshold` | 情感阈值 | `0.6` |
| `confidence_threshold` | 置信度阈值 | `0.7` |
| `trade_volume` | 交易数量 | `1.0` |
| `max_single_order` | 单笔最大金额 | `50000.0` |
| `max_daily_orders` | 每日最大交易次数 | `10` |
| `news_valid_time` | 新闻有效时间（秒） | `300` |
| `enable_lark_push` | 启用飞书推送 | `True` |
| `analyzer_type` | 分析器类型 | `snownlp` |

## 飞书命令

在飞书中支持的命令：

```
/buy <品种> <价格> <数量>  - 买入
    例如: /buy BTC 50000 0.1

/sell <品种> <价格> <数量> - 卖出
    例如: /sell BTC 50000 0.1

/cancel all              - 撤销所有订单
/cancel <订单ID>         - 撤销指定订单

/status                  - 查询账户状态
/help                    - 显示帮助信息
```

## 飞书审批流程

1. 系统检测到新闻信号
2. 分析新闻情感并生成交易建议
3. 推送卡片消息到飞书群
4. 用户点击"同意"或"拒绝"按钮
5. 系统根据审批结果执行或拒绝交易
6. 推送执行结果到飞书

## 自定义情感分析

### 关键词分析器

```python
from vnpy.app.news_trading import KeywordSentimentAnalyzer

config = {
    "custom_positive_keywords": ["利好", "上涨", "增长"],
    "custom_negative_keywords": ["利空", "下跌", "亏损"],
    "custom_symbol_keywords": {
        "比特币": ["BTC"],
        "以太坊": ["ETH"],
    }
}

analyzer = KeywordSentimentAnalyzer(config)
result = analyzer.analyze("比特币突破60000美元")
```

### SnowNLP分析器

```python
from vnpy.app.news_trading import SnowNLPSentimentAnalyzer

analyzer = SnowNLPSentimentAnalyzer(config)
result = analyzer.analyze("比特币大涨")
```

### BERT分析器（需要安装torch和transformers）

```python
from vnpy.app.news_trading import BERTSentimentAnalyzer

analyzer = BERTSentimentAnalyzer(
    config=config,
    model_name="bert-base-chinese"
)
result = analyzer.analyze("比特币大涨")
```

## 风险控制

- **情感阈值**: 只对强烈情感的新闻进行交易
- **置信度阈值**: 只对高置信度的分析结果进行交易
- **金额限制**: 单笔订单和每日交易金额限制
- **次数限制**: 每日最大交易次数
- **品种过滤**: 支持白名单和黑名单
- **时间窗口**: 新闻信号的有效时间
- **人工审批**: 支持飞书审批流程

## 文件结构

```
vnpy/app/news_trading/
├── __init__.py              # 模块导出
├── config.py                # 执行配置
├── strategy.py              # 新闻驱动策略
├── news_gateway.py           # 新闻采集网关
├── sentiment_analyzer.py    # 情感分析器
├── lark_client.py           # 飞书客户端
├── lark_command_listener.py # 飞书命令监听
├── execution_engine.py      # 执行引擎
├── run_direct.py           # 直接执行模式示例
├── run_lark.py           # 飞书审批模式示例
├── run_hybrid.py         # 混合模式示例
└── run_manual.py         # 仅通知模式示例
```

## 注意事项

1. **API密钥安全**: 不要将API密钥提交到版本控制系统
2. **风险提示**: 新闻驱动交易存在风险，建议先在模拟环境测试
3. **网络稳定**: 新闻采集和飞书推送需要稳定的网络连接
4. **时区处理**: 注意新闻时间的时区设置
5. **合规性**: 确保交易策略符合相关法规

## 常见问题

### Q: 如何添加自定义新闻源？

A: 继承 `NewsSource` 类并实现 `fetch_news` 方法。

### Q: 如何提高情感分析准确率？

A: 使用 BERT 分析器或自定义关键词词典。

### Q: 飞书Webhook如何配置？

A: 在飞书开放平台配置事件订阅，将Webhook地址设置为服务器地址。

### Q: 如何在实盘环境运行？

A: 配置真实的API密钥，选择合适的执行模式（建议先用审批模式测试）。

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。
