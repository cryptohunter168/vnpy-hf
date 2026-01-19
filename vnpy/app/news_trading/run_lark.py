"""
新闻驱动交易策略 - 模式二：飞书审批
分析新闻后推送到飞书，等待人工审批后执行交易
"""

import threading
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.gateway.binance import BinanceGateway
from vnpy.app.cta_strategy import CtaStrategyApp

from .strategy import NewsTradingStrategy
from .news_gateway import NEWS_CONFIG_EXAMPLE
from .lark_command_listener import LarkCommandListener, create_trade_command_handlers
from .lark_client import LarkClient


def run_lark_approval_mode():
    """运行飞书审批模式"""

    print("=" * 60)
    print("新闻驱动交易策略 - 飞书审批模式")
    print("=" * 60)

    # ==================== 配置部分 ====================
    # 飞书配置（需要替换为实际配置）
    LARK_APP_ID = "your_lark_app_id"
    LARK_APP_SECRET = "your_lark_app_secret"
    LARK_CHAT_ID = "oc_xxxxxxxxxxxxxxxx"  # 群聊ID
    LARK_ENCRYPT_KEY = "your_encrypt_key"  # 用于验证webhook签名
    WEBHOOK_PORT = 5000

    # 是否使用真实配置
    USE_REAL_CONFIG = False
    # =================================================

    if not USE_REAL_CONFIG:
        print("\n警告: 当前使用演示模式，请配置实际参数后运行")
        print("需要配置的参数:")
        print("1. LARK_APP_ID: 飞书应用ID")
        print("2. LARK_APP_SECRET: 飞书应用Secret")
        print("3. LARK_CHAT_ID: 飞书群聊ID")
        print("4. LARK_ENCRYPT_KEY: 加密key（用于验证webhook）")
        print("\n在飞书开放平台获取: https://open.feishu.cn/app")
        return

    # 1. 创建事件引擎
    event_engine = EventEngine()
    event_engine.start()

    # 2. 创建主引擎
    main_engine = MainEngine(event_engine)

    # 3. 添加交易网关
    print("\n1. 添加Binance交易网关")
    main_engine.add_gateway(BinanceGateway)

    # 4. 添加CTA策略应用
    print("2. 添加CTA策略应用")
    cta_engine = CtaStrategyApp(main_engine, event_engine)

    # 5. 初始化飞书客户端
    print("3. 初始化飞书客户端")
    lark_client = LarkClient(
        app_id=LARK_APP_ID,
        app_secret=LARK_APP_SECRET,
        bot_name="交易机器人"
    )

    # 发送启动通知
    lark_client.send_text_message(LARK_CHAT_ID, "新闻交易机器人已启动 🚀")

    # 6. 初始化飞书命令监听器
    print("4. 初始化飞书命令监听器")
    command_listener = LarkCommandListener(
        encrypt_key=LARK_ENCRYPT_KEY,
        bot_name="交易机器人"
    )

    # 注册交易命令处理器
    handlers = create_trade_command_handlers(main_engine, lark_client)
    for command, handler in handlers.items():
        command_listener.register_command(command, handler)

    # 启动webhook服务器（在后台线程）
    print("5. 启动webhook服务器")
    webhook_thread = threading.Thread(
        target=command_listener.run,
        kwargs={"host": "0.0.0.0", "port": WEBHOOK_PORT},
        daemon=True
    )
    webhook_thread.start()

    # 7. 配置新闻网关
    print("6. 配置新闻网关")
    news_config = {
        "fetch_interval": 60,
        "news_sources": [
            {
                "type": "rss",
                "name": "新浪财经",
                "url": "http://finance.sina.com.cn/roll/finance.d.html"
            }
            # 可以添加更多新闻源
        ]
    }

    # 8. 初始化CTA引擎
    print("7. 初始化CTA引擎")
    cta_engine.init_engine()

    # 9. 添加策略
    print("8. 添加新闻驱动交易策略")
    setting = {
        "vt_symbol": "BTCUSDT.BINANCE",
        "execution_mode": "lark",  # 飞书审批模式
        "sentiment_threshold": 0.6,
        "confidence_threshold": 0.7,
        "trade_volume": 0.01,
        "max_single_order": 1000.0,
        "max_daily_orders": 10,
        "news_valid_time": 300,
        "enable_lark_push": True,
        "lark_app_id": LARK_APP_ID,
        "lark_app_secret": LARK_APP_SECRET,
        "lark_chat_id": LARK_CHAT_ID,
        "lark_approval_timeout": 300,  # 5分钟审批超时
        "analyzer_type": "snownlp",
    }

    cta_engine.add_strategy(NewsTradingStrategy, "news_strategy_lark", setting)

    # 10. 连接交易网关
    print("\n9. 连接交易网关")
    # 配置API密钥
    # gateway_setting = {
    #     "key": "your_binance_api_key",
    #     "secret": "your_binance_api_secret",
    #     "session_number": 3,
    #     "proxy_host": "",
    #     "proxy_port": 0,
    # }
    # main_engine.connect(gateway_setting, "BINANCE")

    print("注意：请配置API密钥")

    # 11. 启动所有策略
    print("\n10. 启动策略")
    cta_engine.start_all()

    print("\n" + "=" * 60)
    print("系统已启动")
    print(f"Webhook地址: http://your_server:{WEBHOOK_PORT}/webhook")
    print("=" * 60)
    print("\n支持飞书命令:")
    print("/buy <品种> <价格> <数量>  - 买入")
    print("/sell <品种> <价格> <数量> - 卖出")
    print("/cancel all              - 撤销所有订单")
    print("/status                  - 查询账户状态")
    print("/help                    - 显示帮助")
    print("\n按 Ctrl+C 停止")
    print("=" * 60)

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止系统...")

        # 发送停止通知
        lark_client.send_text_message(LARK_CHAT_ID, "新闻交易机器人已停止 🛑")

        cta_engine.stop_all()
        event_engine.stop()
        print("系统已停止")


if __name__ == "__main__":
    run_lark_approval_mode()
