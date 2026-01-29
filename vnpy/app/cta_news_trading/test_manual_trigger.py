"""
测试手动触发新闻分析事件
"""

import os
os.environ['PYTHONUNBUFFERED'] = '1'

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.app.cta_strategy import CtaStrategyApp
from vnpy.app.cta_news_trading.strategy import NewsTradingStrategy
from vnpy.gateway.news.news_gateway import get_news_gateway
from vnpy.trader.event import EVENT_NEWS
import time

def test_manual_trigger():
    """手动触发新闻分析"""

    print("=" * 60)
    print("手动触发新闻分析测试")
    print("=" * 60)

    # 1. 创建引擎
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    cta_engine = main_engine.add_app(CtaStrategyApp)
    cta_engine.classes["NewsTradingStrategy"] = NewsTradingStrategy
    cta_engine.init_engine()

    # 2. 配置策略
    setting = {
        "execution_mode": "manual",
        "sentiment_threshold": 0.1,  # 降低阈值
        "confidence_threshold": 0.1,  # 降低阈值
        "enable_lark_push": True,
        "lark_webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/a97ae0ac-e449-44bd-9bfb-de4b6acd31ba",
        "analyzer_type": "keyword",  # 使用关键词分析器，更简单
    }

    # 3. 添加策略
    cta_engine.add_strategy(
        class_name="NewsTradingStrategy",
        strategy_name="test_strategy",
        vt_symbol="BTCUSDT.SSE",
        setting=setting
    )

    # 4. 初始化和启动策略
    print("\n初始化策略...")
    futures = cta_engine.init_all_strategies()
    for strategy_name, future in futures.items():
        try:
            future.result(timeout=10)
            print(f"   {strategy_name} 初始化完成")
        except Exception as e:
            print(f"   {strategy_name} 初始化失败: {e}")

    print("\n启动策略...")
    cta_engine.start_all_strategies()

    # 5. 检查策略状态
    strategy = cta_engine.strategies.get("test_strategy")
    if strategy:
        print(f"\n策略状态:")
        print(f"   execution_engine: {strategy.execution_engine}")
        if strategy.execution_engine:
            print(f"   lark_client: {strategy.execution_engine.lark_client}")

    # 6. 手动发送新闻事件
    print("\n手动发送新闻事件...")

    # 创建一个测试新闻（使用字典格式）
    news = {
        "news_id": f"test_{int(time.time())}",
        "title": "比特币大涨突破60000美元",
        "content": "比特币价格今日大幅上涨，突破60000美元关键阻力位，交易量显著增加，市场情绪乐观",
        "source": "测试来源",
        "url": "",
        "news_time": time.time()
    }

    print(f"新闻标题: {news['title']}")
    print(f"新闻内容: {news['content']}")

    # 发送新闻事件
    from vnpy.event import Event
    event = Event(EVENT_NEWS, news)
    event_engine.put(event)
    print("新闻事件已发送")

    # 7. 等待处理
    print("\n等待5秒，观察飞书是否收到消息...")
    time.sleep(5)

    # 8. 清理
    print("\n清理资源...")
    cta_engine.stop_all_strategies()
    event_engine.stop()

    print("\n测试完成")
    print("请检查飞书群聊是否收到消息")

if __name__ == "__main__":
    test_manual_trigger()
