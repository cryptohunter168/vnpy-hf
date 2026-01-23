# 新闻网关使用指南

## 概述

新闻网关（`NewsGateway`）已经重构，参考 `core.py` 中的 `DataFetcher` 实现，增强了以下功能：

1. **支持多种新闻源类型**：RSS、API、NewsNow API、Mock
2. **自动重试机制**：网络失败时自动重试
3. **灵活的解析方式**：支持 JSON、XML/RSS 格式
4. **代理支持**：支持 HTTP/HTTPS 代理
5. **超时控制**：可配置请求超时时间

## 新闻源类型

### 1. RSS 新闻源 (`RSSNewsSource`)

**特点**：
- 支持标准 RSS/Atom 格式
- 支持自定义 JSON 格式（如 NewsNow API）
- 自动检测响应类型并选择合适的解析器
- 可选择使用 `feedparser` 或 `requests` 解析

**配置示例**：

```python
{
    "type": "rss",
    "name": "新浪财经",
    "url": "http://finance.sina.com.cn/roll/finance.d.html",
    "use_feedparser": True,    # 使用 feedparser（默认 True）
    "max_retries": 2,           # 最大重试次数（默认 2）
    "timeout": 10,              # 超时时间（默认 10 秒）
    "proxy_url": None           # 代理 URL（可选）
}
```

**支持的解析方式**：

1. **feedparser 模式**（`use_feedparser=True`）
   - 使用 `feedparser` 库解析标准 RSS
   - 支持多种 RSS 格式
   - 自动处理命名空间

2. **requests 模式**（`use_feedparser=False`）
   - 使用 `requests` 获取内容
   - 自动检测响应类型：
     - `Content-Type: application/json` → JSON 解析
     - 其他 → XML/RSS 解析
   - 支持 XML 命名空间

**支持的数据格式**：

```javascript
// JSON 格式
{
  "items": [
    {
      "title": "新闻标题",
      "url": "https://...",
      "description": "新闻描述",
      "pubDate": "2024-01-19T10:30:00Z"
    }
  ]
}

// RSS/XML 格式
<rss>
  <channel>
    <item>
      <title>新闻标题</title>
      <link>https://...</link>
      <description>新闻描述</description>
      <pubDate>Mon, 19 Jan 2024 10:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
```

### 2. NewsNow API 新闻源 (`NewsNowAPISource`)

**特点**：
- 专门用于 `newsnow.busiyi.world/api/s`
- 参考 `core.py` 的 `DataFetcher` 实现
- 支持站点 ID 查询
- 区分最新数据和缓存数据
- 移动端 URL 优先

**配置示例**：

```python
# 方式一：使用站点 ID
{
    "type": "newsnow_api",
    "name": "NewsNow-新浪",
    "url": "https://newsnow.busiyi.world/api/s",  # 可选，默认使用官方 API
    "site_id": "sina",                               # 站点 ID
    "max_retries": 2,
    "min_retry_wait": 3,    # 最小重试等待时间（秒）
    "max_retry_wait": 5,    # 最大重试等待时间（秒）
    "timeout": 10,
    "proxy_url": None
}

# 方式二：直接使用 URL（已有完整参数）
{
    "type": "newsnow_api",
    "name": "NewsNow-API",
    "url": "https://newsnow.busiyi.world/api/s?id=all&latest"
}
```

**常用站点 ID**：

```python
# 常见站点 ID 列表
SITE_IDS = {
    "sina": "新浪财经",
    "163": "网易财经",
    "eastmoney": "东方财富",
    "10jqka": "同花顺",
    "wallstreetcn": "华尔街见闻",
    "jinrongjie": "金融界",
    "stockstar": "证券之星",
    # ... 更多站点
}
```

**API 响应格式**：

```javascript
{
  "status": "success",  // 或 "cache"
  "items": [
    {
      "title": "新闻标题",
      "url": "https://...",
      "mobileUrl": "https://m...",  // 移动端 URL
      "time": 1705660200             // Unix 时间戳（秒）
    }
  ]
}
```

### 3. 通用 API 新闻源 (`APINewsSource`)

**特点**：
- 支持通用 REST API
- 需要 API 密钥
- 可自定义请求参数

**配置示例**：

```python
{
    "type": "api",
    "name": "NewsAPI",
    "url": "https://newsapi.org/v2/top-headlines",
    "api_key": "your_api_key_here",
    "params": {                           # 自定义参数
        "country": "cn",
        "category": "business",
        "pageSize": 20
    }
}
```

### 4. Mock 新闻源 (`MockNewsSource`)

**特点**：
- 返回模拟新闻，用于测试
- 循环返回预定义的新闻列表

**配置示例**：

```python
{
    "type": "mock",
    "name": "Mock"
}
```

## 完整配置示例

### 示例 1：使用 NewsNow API（推荐）

```python
news_config = {
    "fetch_interval": 60,  # 每 60 秒获取一次
    "news_sources": [
        {
            "type": "newsnow_api",
            "name": "新浪财经热点",
            "site_id": "sina"
        },
        {
            "type": "newsnow_api",
            "name": "网易财经热点",
            "site_id": "163"
        },
        {
            "type": "newsnow_api",
            "name": "全部热点",
            "url": "https://newsnow.busiyi.world/api/s?id=all&latest"
        }
    ]
}
```

### 示例 2：混合使用多种新闻源

```python
news_config = {
    "fetch_interval": 60,
    "news_sources": [
        # NewsNow API（热点）
        {
            "type": "newsnow_api",
            "name": "NewsNow",
            "site_id": "sina"
        },
        # 标准 RSS
        {
            "type": "rss",
            "name": "东方财富RSS",
            "url": "http://www.eastmoney.com/api/rss/finance.xml",
            "use_feedparser": True
        },
        # 自定义 JSON API
        {
            "type": "rss",
            "name": "自定义API",
            "url": "https://your-api.com/news",
            "use_feedparser": False  # 使用 requests 解析
        },
        # Mock（测试用）
        {
            "type": "mock",
            "name": "测试源"
        }
    ]
}
```

### 示例 3：使用代理和自定义重试

```python
news_config = {
    "fetch_interval": 120,
    "news_sources": [
        {
            "type": "newsnow_api",
            "name": "NewsNow",
            "site_id": "sina",
            "max_retries": 3,          # 增加重试次数
            "min_retry_wait": 5,       # 增加等待时间
            "max_retry_wait": 10,
            "timeout": 15,             # 增加超时时间
            "proxy_url": "http://127.0.0.1:7890"  # 使用代理
        }
    ]
}
```

## 使用方式

### 方式一：直接创建新闻网关

```python
from vnpy.event import EventEngine
from vnpy.app.news_trading.news_gateway import get_news_gateway

# 创建事件引擎
event_engine = EventEngine()
event_engine.start()

# 配置新闻网关
news_config = {
    "fetch_interval": 60,
    "news_sources": [
        {
            "type": "newsnow_api",
            "name": "NewsNow",
            "site_id": "sina"
        }
    ]
}

# 创建新闻网关
news_gateway = get_news_gateway(event_engine, news_config)

# 设置回调（可选）
def news_callback(news_list):
    print(f"收到 {len(news_list)} 条新闻")

news_gateway.set_callback(news_callback)

# 启动新闻采集
news_gateway.connect()

# 系统将自动定时采集新闻并发送事件
```

### 方式二：在策略中使用

```python
from vnpy.app.news_trading.strategy import NewsTradingStrategy

# 策略会自动订阅 EVENT_NEWS 事件
setting = {
    "vt_symbol": "BTCUSDT.BINANCE",
    "execution_mode": "manual",
    "sentiment_threshold": 0.6,
    "analyzer_type": "snownlp"
}

# 添加策略后，新闻会自动触发策略的 on_news_event()
cta_engine.add_strategy(NewsTradingStrategy, "news_strategy", setting)
```

## 重试机制

参考 `core.py` 的 `DataFetcher` 实现：

```python
def _calculate_retry_wait(self, retry: int) -> float:
    """计算重试等待时间"""
    import random
    base_wait = random.uniform(2, 5)              # 基础等待时间
    additional_wait = retry * random.uniform(1, 2) # 额外等待时间
    return base_wait + additional_wait
```

**重试策略**：
- 第 1 次失败：等待 3-7 秒后重试
- 第 2 次失败：等待 5-9 秒后重试
- 第 3 次失败：放弃并返回空列表

## 日期时间解析

支持多种日期时间格式：

```python
"%Y-%m-%dT%H:%M:%S%z",     # 2024-01-19T10:30:00+08:00
"%Y-%m-%dT%H:%M:%SZ",       # 2024-01-19T10:30:00Z
"%Y-%m-%dT%H:%M:%S",         # 2024-01-19T10:30:00
"%Y-%m-%d %H:%M:%S",         # 2024-01-19 10:30:00
"%Y-%m-%d",                  # 2024-01-19
"%a, %d %b %Y %H:%M:%S %z",  # Mon, 19 Jan 2024 10:30:00 +0000
"%a, %d %b %Y %H:%M:%S GMT", # Mon, 19 Jan 2024 10:30:00 GMT
```

## 性能优化建议

1. **合理设置获取间隔**
   ```python
   "fetch_interval": 60  # 建议 60-300 秒
   ```

2. **使用站点 ID 而非全部热点**
   ```python
   # 好：只获取特定站点
   {"site_id": "sina"}

   # 差：获取全部热点（数据量大）
   {"site_id": "all"}
   ```

3. **启用缓存策略**
   - NewsNow API 会返回缓存数据（`status: "cache"`）
   - 可以适当增加获取间隔以利用缓存

4. **控制重试次数**
   ```python
   "max_retries": 2  # 建议 2-3 次
   ```

## 常见问题

### Q1: feedparser 和 requests 有什么区别？

**feedparser**：
- 专门解析 RSS/Atom
- 处理复杂的 XML 命名空间
- 适合标准 RSS 格式

**requests**：
- 通用 HTTP 客户端
- 支持自动检测 JSON/XML
- 适合自定义 API 或非标准格式

### Q2: 如何选择新闻源类型？

| 场景 | 推荐类型 | 配置 |
|------|---------|------|
| NewsNow 热点 | `newsnow_api` | 设置 `site_id` |
| 标准 RSS | `rss` + `use_feedparser=True` | 标准 RSS URL |
| 自定义 JSON API | `rss` + `use_feedparser=False` | API URL |
| 测试/开发 | `mock` | 无需 URL |

### Q3: 如何处理网络错误？

系统已内置重试机制：
- 自动重试 2 次（可配置）
- 随机等待时间避免被封
- 最终失败时打印日志并返回空列表

### Q4: NewsNow API 的站点 ID 在哪里获取？

可以参考 `core.py` 中的配置，或者：
1. 访问 https://newsnow.busiyi.world/
2. 查看不同站点的 ID
3. 常见 ID：`sina`, `163`, `eastmoney`, `10jqka` 等

## 迁移指南

### 从 core.py 迁移

```python
# 原来的 core.py 方式
from core import DataFetcher

fetcher = DataFetcher(proxy_url=None)
results, id_to_name, failed_ids = fetcher.crawl_websites([
    ("sina", "新浪财经"),
    ("163", "网易财经")
])

# 新的 vn.py 方式
from vnpy.app.news_trading.news_gateway import get_news_gateway

news_config = {
    "fetch_interval": 60,
    "news_sources": [
        {"type": "newsnow_api", "name": "新浪财经", "site_id": "sina"},
        {"type": "newsnow_api", "name": "网易财经", "site_id": "163"}
    ]
}

news_gateway = get_news_gateway(event_engine, news_config)
news_gateway.connect()
# 新闻会自动推送到事件引擎
```

## 总结

重构后的新闻网关：

✅ **兼容 core.py 的 DataFetcher 功能**
✅ **集成到 vn.py 的事件驱动架构**
✅ **支持多种新闻源和格式**
✅ **内置重试和错误处理**
✅ **灵活的配置选项**
✅ **易于扩展和维护**
