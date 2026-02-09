"""
新闻采集网关
支持多种新闻源
"""

import time
import json
import threading
from typing import List, Callable, Optional, Dict
from datetime import datetime, timedelta

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False


class NewsSource:
    """新闻源基类"""

    def __init__(self, name: str, config: dict = None):
        """
        Args:
            name: 新闻源名称
            config: 配置字典
        """
        self.name = name
        self.config = config or {}
        self.last_fetch_time = None

    def fetch_news(self) -> List[dict]:
        """获取新闻

        Returns:
            新闻列表，每条新闻格式:
            {
                "news_id": str,
                "title": str,
                "content": str,
                "source": str,
                "url": str,
                "news_time": datetime
            }
        """
        raise NotImplementedError

    def is_available(self) -> bool:
        """检查新闻源是否可用"""
        return True


class RSSNewsSource(NewsSource):
    """RSS新闻源"""

    def __init__(self, name: str, rss_url: str, config: dict = None):
        super().__init__(name, config)
        self.rss_url = rss_url
    def fetch_news(self) -> List[dict]:
        """从RSS获取新闻"""
        if not FEEDPARSER_AVAILABLE:
            print("feedparser库不可用")
            return []

        try:
            feed = feedparser.parse(self.rss_url)
            news_list = []

            for entry in feed.entries:
                # 只获取最近24小时的新闻
                published = None
                if hasattr(entry, 'published_parsed'):
                    published = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed'):
                    published = datetime(*entry.updated_parsed[:6])

                if published and (datetime.now() - published).days > 1:
                    continue

                news = {
                    "news_id": f"{self.name}_{int(time.time())}_{entry.get('id', hash(entry.link))}",
                    "title": entry.get('title', ''),
                    "content": entry.get('description', '') or entry.get('summary', ''),
                    "source": self.name,
                    "url": entry.get('link', ''),
                    "news_time": published or datetime.now()
                }
                news_list.append(news)

            self.last_fetch_time = datetime.now()
            return news_list

        except Exception as e:
            print(f"获取RSS新闻失败: {e}")
            return []


class APINewsSource(NewsSource):
    """API新闻源"""

    def __init__(self, name: str, api_url: str, api_key: str, config: dict = None):
        super().__init__(name, config)
        self.api_url = api_url
        self.api_key = api_key

    def fetch_news(self) -> List[dict]:
        """从API获取新闻"""
        if not REQUESTS_AVAILABLE:
            print("requests库不可用")
            return []

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache",
            }

            response = requests.get(self.api_url, headers=headers, timeout=10)
            response.raise_for_status()

            data_json = response.json()
            status = data_json.get("status", "error")
            if status not in ["success", "cache"]:
                print(f"API返回状态: {status}")

            news_list = []

            # 根据不同API格式解析
            articles = data_json.get("articles", data_json.get("items", data_json.get("data", [])))

            # 获取根级别的时间戳（毫秒）
            updated_time_ms = data_json.get("updatedTime", 0)
            if updated_time_ms:
                # 毫秒时间戳转换为 datetime
                from datetime import datetime
                news_time = datetime.fromtimestamp(updated_time_ms / 1000)
            else:
                news_time = datetime.now()

            for article in articles:
                news = {
                    "news_id": f"{self.name}_{int(time.time())}_{article.get('id', '')}",
                    "title": article.get("title", ""),
                    "content": article.get("description", article.get("content", "")),
                    "source": self.name,
                    "url": article.get("url", article.get("link", "")),
                    "news_time": news_time
                }
                news_list.append(news)

            self.last_fetch_time = datetime.now()
            return news_list

        except Exception as e:
            print(f"获取API新闻失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """解析日期时间字符串"""
        try:
            # 尝试常见格式
            for fmt in [
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d"
            ]:
                try:
                    return datetime.strptime(dt_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None


class MockNewsSource(NewsSource):
    """模拟新闻源（用于测试）"""

    def __init__(self, name: str = "Mock", config: dict = None):
        super().__init__(name, config)
        self.mock_news = [
            {
                "title": "BTC突破60000美元，创新高！",
                "content": "比特币价格突破60000美元大关，创下历史新高。市场情绪高涨，投资者乐观情绪浓厚。",
            },
            {
                "title": "美联储加息预期升温，美股大跌",
                "content": "受美联储加息预期影响，美股大幅下跌。科技股跌幅居前，市场避险情绪上升。",
            },
            {
                "title": "某公司业绩超预期，股价涨停",
                "content": "该公司发布业绩报告，净利润同比增长50%，远超市场预期。股价开盘即涨停。",
            },
        ]
        self.index = 0

    def fetch_news(self) -> List[dict]:
        """获取模拟新闻"""
        news_list = []
        news = self.mock_news[self.index % len(self.mock_news)]
        self.index += 1

        news_list.append({
            "news_id": f"{self.name}_{int(time.time())}_{self.index}",
            "title": news["title"],
            "content": news["content"],
            "source": self.name,
            "url": "",
            "news_time": datetime.now()
        })

        self.last_fetch_time = datetime.now()
        return news_list


class NewsGateway:
    """新闻采集网关"""

    def __init__(self, event_engine, config: dict = None):
        """
        Args:
            event_engine: vn.py事件引擎
            config: 配置字典
        """
        from vnpy.event import Event
        from vnpy.trader.event import EVENT_NEWS

        self.event_engine = event_engine
        self.config = config or {}
        self.news_sources: List[NewsSource] = []
        self.active = False
        self.fetch_interval = self.config.get("fetch_interval", 60)  # 获取间隔（秒）
        self.thread = None
        self.callback = None

        # 初始化新闻源
        self._init_news_sources()

    def _init_news_sources(self):
        """初始化新闻源"""
        sources_config = self.config.get("news_sources", [])

        for source_config in sources_config:
            source_type = source_config.get("type", "")

            if source_type == "rss":
                source = RSSNewsSource(
                    name=source_config.get("name", "RSS"),
                    rss_url=source_config.get("url"),
                    config=source_config
                )
            elif source_type == "api":
                source = APINewsSource(
                    name=source_config.get("name", "API"),
                    api_url=source_config.get("url"),
                    api_key=source_config.get("api_key"),
                    config=source_config
                )
            elif source_type == "mock":
                source = MockNewsSource(
                    name=source_config.get("name", "Mock"),
                    config=source_config
                )
            else:
                print(f"未知的新闻源类型: {source_type}")
                continue

            if source.is_available():
                self.news_sources.append(source)
                print(f"添加新闻源: {source.name}")
            else:
                print(f"新闻源不可用: {source.name}")

        # 如果没有配置新闻源，使用Mock源
        if not self.news_sources:
            print("未配置新闻源，使用模拟新闻源")
            self.news_sources.append(MockNewsSource())

    def set_callback(self, callback: Callable):
        """设置新闻回调函数

        Args:
            callback: 回调函数，签名为 callback(news_list: List[dict])
        """
        self.callback = callback

    def connect(self):
        """连接并启动新闻采集"""
        if self.active:
            print("新闻网关已在运行")
            return

        print("启动新闻采集网关")
        self.active = True
        self.thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self.thread.start()

    def close(self):
        """关闭新闻采集"""
        self.active = False
        # 不阻塞等待线程结束（daemon 线程会随主程序自动退出）
        # 如果需要等待，可以使用更短的超时时间
        # if self.thread and self.thread.is_alive():
        #     self.thread.join(timeout=0.5)
        print("新闻采集网关已关闭")

    def _fetch_loop(self):
        """新闻获取循环"""
        while self.active:
            try:
                self._fetch_news_from_all_sources()
            except Exception as e:
                print(f"获取新闻异常: {e}")

            # 等待下一次获取
            for _ in range(self.fetch_interval):
                if not self.active:
                    break
                time.sleep(1)

    def _fetch_news_from_all_sources(self):
        """从所有新闻源获取新闻"""
        all_news = []

        for source in self.news_sources:
            try:
                news_list = source.fetch_news()
                all_news.extend(news_list)
            except Exception as e:
                print(f"从 {source.name} 获取新闻失败: {e}")

        if all_news:
            print(f"获取到 {len(all_news)} 条新闻")

            # 发送事件
            from vnpy.event import Event
            from vnpy.trader.event import EVENT_NEWS

            for news_data in all_news:
                event = Event(EVENT_NEWS, news_data)
                self.event_engine.put(event)

            # 调用回调
            if self.callback:
                try:
                    self.callback(all_news)
                except Exception as e:
                    print(f"回调函数执行失败: {e}")

    def fetch_once(self) -> List[dict]:
        """手动获取一次新闻"""
        return self._fetch_news_from_all_sources()


# 新闻源配置示例
NEWS_CONFIG_EXAMPLE = {
    "fetch_interval": 60,
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
            "api_key": "your_api_key_here",
            "params": {
                "country": "cn",
                "category": "business"
            }
        },
        {
            "type": "mock",
            "name": "Mock"
        }
    ]
}


def get_news_gateway(event_engine, config: dict = None) -> NewsGateway:
    """获取新闻网关实例

    Args:
        event_engine: vn.py事件引擎
        config: 配置字典

    Returns:
        NewsGateway实例
    """
    return NewsGateway(event_engine, config)
