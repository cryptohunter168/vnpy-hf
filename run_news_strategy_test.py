"""
新闻驱动交易策略 - 三种模式测试脚本
支持增量模式、榜单模式、汇总模式

注意：此脚本不依赖 CTA 策略引擎，直接创建策略实例进行测试
"""

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.gateway.binance import BinanceGateway

# 保留新闻网关（完整功能）
from vnpy.app.news_trading.news_gateway import NewsGateway
from vnpy.app.news_trading.strategy import NewsTradingStrategy


def run_strategy_test(mode: str = "incremental"):
    """
    运行新闻策略测试（不依赖 CTA 引擎）

    Args:
        mode: 新闻处理模式
            - "incremental": 增量模式（立即分析）
            - "current_rank": 当前榜单模式（榜单匹配）
            - "daily_summary": 当日汇总模式（定时批量分析）
    """

    print("=" * 80)
    print(f"新闻驱动交易策略 - {mode.upper()} 模式测试")
    print("=" * 80)

    # 1. 创建事件引擎
    print("\n[1/7] 创建事件引擎...")
    event_engine = EventEngine()
    event_engine.start()
    print("    ✓ 事件引擎已启动")

    # 2. 创建主引擎（可选，用于交易网关）
    print("[2/7] 创建主引擎...")
    main_engine = MainEngine(event_engine)

    # 3. 添加 Binance 网关（可选）
    print("[3/7] 添加Binance交易网关...")
    try:
        main_engine.add_gateway(BinanceGateway)
        print("    ✓ Binance网关已添加")
    except Exception as e:
        print(f"    ! Binance网关添加失败（非必需）: {e}")

    # 4. 配置并启动新闻网关（保留完整功能）
    print("[4/7] 配置新闻网关...")
    news_config = {
        "fetch_interval": 60,  # 每60秒获取一次新闻
        "news_sources": [
            {
                "type": "mock",  # 使用模拟新闻源测试
                "name": "模拟新闻源",
            },
            # 也可以添加真实新闻源
            # {
            #     "type": "rss",
            #     "name": "新浪财经",
            #     "url": "http://finance.sina.com.cn/roll/finance.d.html"
            # }
        ]
    }

    # 创建并启动新闻网关
    news_gateway = None
    try:
        news_gateway = NewsGateway(event_engine, news_config)
        news_gateway.start()
        print("    ✓ 新闻网关已启动")
        print(f"    新闻源数量: {len(news_config['news_sources'])}")
    except Exception as e:
        print(f"    ✗ 新闻网关启动失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 5. 配置策略参数
    print(f"[5/7] 配置策略参数（{mode}模式）...")
    setting = {
        "vt_symbol": "BTCUSDT.BINANCE",
        "execution_mode": "manual",  # 仅通知模式

        # 新闻处理模式
        "news_processing_mode": mode,
        "incremental_keywords": "比特币,区块链,BTC,加密货币",
        "incremental_max_cache": 1000,

        # 分析器配置
        "sentiment_threshold": 0.6,
        "confidence_threshold": 0.7,
        "analyzer_type": "keyword",  # 使用关键词分析器

        # SQLite配置
        "db_path": f"vnpy_news_trading_{mode}.db",
    }

    # 根据模式调整配置
    if mode == "current_rank":
        setting.update({
            "rank_threshold": 10,
            "rank_min_sources": 2,
            "rank_platforms": "",
        })
    elif mode == "daily_summary":
        setting.update({
            "summary_keywords": "财经,市场,交易",
            "summary_schedule_times": "09:00,15:00,21:00",
            "summary_schedule_type": "fixed_time",
        })

    print("    ✓ 参数配置完成")

    # 6. 手动创建策略实例（不通过 CTA 引擎）
    print("[6/7] 创建并初始化策略...")
    try:
        strategy = create_strategy_directly(event_engine, setting)
        print("    ✓ 策略已创建并初始化")
    except Exception as e:
        print(f"    ✗ 策略创建失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 7. 运行系统
    print("[7/7] 系统运行中...")
    print("\n" + "=" * 80)
    print(f"✓ 系统已启动 - {mode.upper()} 模式")
    print("=" * 80)
    print(f"数据库文件: vnpy_news_trading_{mode}.db")
    print(f"新闻网关: {'✓ 运行中' if news_gateway else '✗ 未启动'}")
    print("\n功能说明:")
    if mode == "incremental":
        print("  • 实时接收新闻 → 关键词匹配 → 立即分析")
        print("  • 数据保留24小时")
    elif mode == "current_rank":
        print("  • 实时接收新闻 → 榜单匹配 + 排名过滤 → 立即分析")
        print("  • 数据保留7天")
    elif mode == "daily_summary":
        print("  • 收集匹配的新闻 → 定时批量分析 (09:00, 15:00, 21:00)")
        print("  • 数据保留30天")
    print("=" * 80)
    print("\n按 Ctrl+C 停止系统\n")

    # 运行主循环
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n正在停止系统...")
        try:
            # 停止新闻网关
            if news_gateway:
                news_gateway.stop()
                print("✓ 新闻网关已停止")

            # 停止策略
            strategy.on_stop()
            print("✓ 策略已停止")

            # 停止事件引擎
            event_engine.stop()
            print("✓ 事件引擎已停止")
            print("\n✓ 系统已完全停止")

        except Exception as e:
            print(f"✗ 停止时发生错误: {e}")


def create_strategy_directly(event_engine, setting):
    """直接创建策略实例，不通过 CTA 引擎"""

    class MockCtaEngine:
        """模拟 CTA 引擎"""
        def __init__(self, event_engine):
            self.event_engine = event_engine
            self.main_engine = None

        def write_log(self, msg):
            """输出策略日志"""
            print(f"    [策略] {msg}")

    # 创建模拟引擎
    cta_engine = MockCtaEngine(event_engine)

    # 直接创建策略实例
    strategy = NewsTradingStrategy(
        cta_engine,
        f"news_strategy_{setting['news_processing_mode']}",
        setting["vt_symbol"],
        setting
    )

    # 手动设置事件引擎（策略会用到）
    strategy.event_engine = event_engine

    # 手动调用初始化
    strategy.on_init()

    # 手动调用启动
    strategy.on_start()

    return strategy


if __name__ == "__main__":
    import sys

    # 从命令行参数获取模式
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        print("使用方法:")
        print("  python run_news_strategy_test.py incremental   # 增量模式")
        print("  python run_news_strategy_test.py current_rank # 榜单模式")
        print("  python run_news_strategy_test.py daily_summary # 汇总模式")
        print("\n默认使用增量模式...")
        mode = "incremental"

    # 验证模式
    valid_modes = ["incremental", "current_rank", "daily_summary"]
    if mode not in valid_modes:
        print(f"错误: 无效的模式 '{mode}'")
        print(f"有效模式: {', '.join(valid_modes)}")
        sys.exit(1)

    try:
        run_strategy_test(mode)
    except Exception as e:
        print(f"\n运行错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)



if __name__ == "__main__":
    import sys

    # 从命令行参数获取模式
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        print("使用方法:")
        print("  python run_news_strategy_test.py incremental   # 增量模式")
        print("  python run_news_strategy_test.py current_rank # 榜单模式")
        print("  python run_news_strategy_test.py daily_summary # 汇总模式")
        print("\n默认使用增量模式...")
        mode = "incremental"

    # 验证模式
    valid_modes = ["incremental", "current_rank", "daily_summary"]
    if mode not in valid_modes:
        print(f"错误: 无效的模式 '{mode}'")
        print(f"有效模式: {', '.join(valid_modes)}")
        sys.exit(1)

    try:
        run_strategy_test(mode)
    except Exception as e:
        print(f"\n运行错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
