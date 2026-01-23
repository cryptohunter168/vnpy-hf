"""
新闻驱动交易策略
支持多种执行模式的新闻驱动策略
"""

from typing import Optional, List
from datetime import datetime, timedelta

from vnpy.trader.constant import Direction, Offset, OrderType
from vnpy.trader.object import OrderData, TradeData, TickData, BarData
from vnpy.app.cta_strategy.template import CtaTemplate
from vnpy.trader.event import EVENT_NEWS, EVENT_NEWS_ANALYSIS, EVENT_TRADE_COMMAND

from .config import (
    ExecutionConfig, ExecutionMode,
    NewsProcessingConfig, NewsProcessingMode, ScheduleType,
    IncrementalModeConfig, CurrentRankModeConfig, DailySummaryModeConfig
)
from .sentiment_analyzer import NewsAnalyzer, get_analyzer
from .news_engine import News_Engine
from .news_storage import StorageManager
from .news_matcher import (
    NewsMatcher, IncrementalNewsMatcher,
    CurrentRankNewsMatcher, DailySummaryNewsMatcher
)
from .scheduler import NewsScheduler, FixedTimeScheduler, IntervalScheduler


class NewsTradingStrategy(CtaTemplate):
    """新闻驱动交易策略

    支持的执行模式:
    1. DIRECT: 直接执行 - 分析后立即执行交易
    2. LARK_APPROVAL: 飞书审批 - 推送到飞书，等待人工审批后执行
    3. HYBRID: 混合模式 - 小仓位直接执行，大仓位飞书审批
    4. MANUAL: 仅通知 - 只推送分析结果，不自动执行
    """

    author = "vn.py team"

    # 策略参数
    execution_mode: str = "direct"           # 执行模式
    news_processing_mode: str = "incremental" # 新闻处理模式

    sentiment_threshold: float = 0.6         # 情感阈值
    confidence_threshold: float = 0.7        # 置信度阈值
    trade_volume: float = 1.0               # 交易数量
    max_single_order: float = 50000.0        # 单笔最大金额
    max_daily_orders: int = 10               # 每日最大交易次数
    news_valid_time: int = 300              # 新闻有效时间（秒）
    enable_lark_push: bool = True          # 启用飞书推送

    # 增量模式参数
    incremental_keywords: str = ""          # 增量模式关键词，逗号分隔
    incremental_max_cache: int = 1000       # 增量模式最大缓存数

    # 当前榜单模式参数
    rank_threshold: int = 10                # 榜单模式排名阈值
    rank_min_sources: int = 2               # 榜单模式最少源数
    rank_platforms: str = ""                # 榜单模式平台过滤，逗号分隔

    # 当日汇总模式参数
    summary_keywords: str = ""              # 汇总模式关键词，逗号分隔
    summary_schedule_times: str = "09:00,15:00,21:00"  # 汇总模式推送时间点
    summary_schedule_type: str = "fixed_time"         # 定时类型
    summary_schedule_interval: int = 3600             # 汇总模式推送间隔（秒）

    # SQLite 配置
    db_path: str = "vnpy_news_trading.db"   # SQLite 数据库文件路径

    # 飞书配置
    lark_app_id: str = ""                  # 飞书应用ID
    lark_app_secret: str = ""              # 飞书应用Secret
    lark_chat_id: str = ""                 # 飞书群聊ID
    lark_approval_timeout: int = 300         # 审批超时时间（秒）

    # 分析器配置
    analyzer_type: str = "snownlp"          # 分析器类型 (keyword/snownlp/bert)

    # 策略变量
    last_news_time: Optional[datetime] = None   # 最后新闻时间
    last_sentiment: float = 0.0                # 最后情感分数
    today_order_count: int = 0                  # 今日交易次数

    parameters = [
        "execution_mode",
        "news_processing_mode",
        "sentiment_threshold",
        "confidence_threshold",
        "trade_volume",
        "max_single_order",
        "max_daily_orders",
        "news_valid_time",
        "enable_lark_push",
        "lark_app_id",
        "lark_app_secret",
        "lark_chat_id",
        "lark_approval_timeout",
        "analyzer_type",
        "incremental_keywords",
        "incremental_max_cache",
        "rank_threshold",
        "rank_min_sources",
        "rank_platforms",
        "summary_keywords",
        "summary_schedule_times",
        "summary_schedule_type",
        "summary_schedule_interval",
        "db_path",
    ]

    variables = [
        "last_news_time",
        "last_sentiment",
        "today_order_count",
    ]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """构造函数"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        # 1. 创建执行配置
        self.config = self._create_config()

        # 2. 创建新闻处理配置
        self.news_config = self._create_news_config()

        # 3. 初始化 SQLite 存储管理器
        self.storage_manager = StorageManager(self.db_path)

        # 4. 初始化匹配器
        self.matcher = self._create_matcher()

        # 5. 初始化调度器（仅汇总模式需要）
        self.scheduler: Optional[NewsScheduler] = None
        if self.news_config.mode == NewsProcessingMode.DAILY_SUMMARY:
            self.scheduler = self._create_scheduler()

        # 6. 分析器（保持原有）
        self.analyzer = get_analyzer(
            config={
                "sentiment_threshold": self.sentiment_threshold,
                "confidence_threshold": self.confidence_threshold,
                "known_symbols": [self.vt_symbol],
            },
            analyzer_type=self.analyzer_type
        )

        # 7. 执行引擎（稍后在 on_init 中初始化）
        self.execution_engine: Optional[News_Engine] = None

    def _create_news_config(self) -> NewsProcessingConfig:
        """创建新闻处理配置"""
        mode = NewsProcessingMode(self.news_processing_mode)

        # 解析关键词列表
        incremental_keywords = [k.strip() for k in self.incremental_keywords.split(",") if k.strip()]
        summary_keywords = [k.strip() for k in self.summary_keywords.split(",") if k.strip()]
        rank_platforms = [p.strip() for p in self.rank_platforms.split(",") if p.strip()]

        # 解析定时配置
        schedule_times = [t.strip() for t in self.summary_schedule_times.split(",") if t.strip()]

        return NewsProcessingConfig(
            mode=mode,
            incremental_config=IncrementalModeConfig(
                keywords=incremental_keywords,
                max_cache_size=self.incremental_max_cache
            ),
            current_rank_config=CurrentRankModeConfig(
                rank_threshold=self.rank_threshold,
                min_sources=self.rank_min_sources,
                platforms=rank_platforms
            ),
            daily_summary_config=DailySummaryModeConfig(
                keywords=summary_keywords,
                schedule_type=ScheduleType(self.summary_schedule_type),
                schedule_times=schedule_times,
                schedule_interval=self.summary_schedule_interval
            )
        )

    def _create_matcher(self) -> NewsMatcher:
        """创建新闻匹配器"""
        mode = self.news_config.mode

        if mode == NewsProcessingMode.INCREMENTAL:
            return IncrementalNewsMatcher(self.news_config)
        elif mode == NewsProcessingMode.CURRENT_RANK:
            try:
                from . import core
                return CurrentRankNewsMatcher(self.news_config, core)
            except ImportError:
                self.write_log("警告: 无法导入core模块，使用增量匹配器")
                return IncrementalNewsMatcher(self.news_config)
        elif mode == NewsProcessingMode.DAILY_SUMMARY:
            return DailySummaryNewsMatcher(self.news_config)
        else:
            raise ValueError(f"未知的处理模式: {mode}")

    def _create_scheduler(self) -> NewsScheduler:
        """创建定时调度器"""
        summary_config = self.news_config.daily_summary_config

        if summary_config.schedule_type == ScheduleType.FIXED_TIME:
            return FixedTimeScheduler(
                callback=self._on_summary_scheduled,
                event_engine=self.event_engine,
                schedule_times=summary_config.schedule_times
            )
        else:
            return IntervalScheduler(
                callback=self._on_summary_scheduled,
                event_engine=self.event_engine,
                interval_seconds=summary_config.schedule_interval
            )

    def _create_config(self) -> ExecutionConfig:
        """创建执行配置"""
        return ExecutionConfig(
            mode=ExecutionMode(self.execution_mode),
            lark_app_id=self.lark_app_id,
            lark_app_secret=self.lark_app_secret,
            lark_chat_id=self.lark_chat_id,
            lark_approval_timeout=self.lark_approval_timeout,
            max_single_order=self.max_single_order,
            max_daily_orders=self.max_daily_orders,
            sentiment_threshold=self.sentiment_threshold,
            confidence_threshold=self.confidence_threshold,
            enable_lark_push=self.enable_lark_push,
            news_valid_time=self.news_valid_time,
        )

    def on_init(self):
        """策略初始化"""
        self.write_log(f"新闻驱动交易策略初始化 (模式: {self.news_processing_mode})")

        # 订阅新闻事件
        self.event_engine.register(EVENT_NEWS, self.on_news_event)
        self.event_engine.register(EVENT_NEWS_ANALYSIS, self.on_analysis_event)
        self.event_engine.register(EVENT_TRADE_COMMAND, self.on_trade_command_event)

        # 初始化执行引擎
        if self.cta_engine.main_engine:
            self.execution_engine = News_Engine(
                main_engine=self.cta_engine.main_engine,
                config=self.config
            )
            self.write_log("执行引擎初始化成功")

        # 启动调度器（如果需要）
        if self.scheduler:
            self.scheduler.start()
            self.write_log("定时调度器已启动")

    def on_start(self):
        """策略启动"""
        self.write_log("新闻驱动交易策略启动")

        # 重置每日计数
        self._reset_daily_count()

    def on_stop(self):
        """策略停止"""
        self.write_log("新闻驱动交易策略停止")

        # 停止调度器
        if self.scheduler:
            self.scheduler.stop()
            self.write_log("定时调度器已停止")

        # 关闭数据库连接
        if self.storage_manager:
            self.storage_manager.close()
            self.write_log("数据库连接已关闭")

        # 取消事件订阅
        self.event_engine.unregister(EVENT_NEWS, self.on_news_event)
        self.event_engine.unregister(EVENT_NEWS_ANALYSIS, self.on_analysis_event)
        self.event_engine.unregister(EVENT_TRADE_COMMAND, self.on_trade_command_event)

    def on_news_event(self, event):
        """处理新闻事件（重构后的路由函数）"""
        news_data = event.data
        news_id = news_data.get("news_id", "")

        if not news_id:
            return

        # 根据模式分发处理
        mode = self.news_config.mode

        if mode == NewsProcessingMode.INCREMENTAL:
            self._process_incremental_news(news_data)
        elif mode == NewsProcessingMode.CURRENT_RANK:
            self._process_current_rank_news(news_data)
        elif mode == NewsProcessingMode.DAILY_SUMMARY:
            self._process_daily_summary_news(news_data)

    def _process_incremental_news(self, news_data: dict):
        """处理增量模式新闻"""
        # 1. 匹配
        if not self.matcher.match(news_data):
            return

        # 2. 存储到数据库（自动去重）
        is_new = self.storage_manager.news_storage.add_news(
            NewsProcessingMode.INCREMENTAL,
            news_data
        )

        if not is_new:
            return  # 已处理过

        self.write_log(f"[增量模式] 收到新闻: {news_data.get('title', '')}")

        # 3. 立即分析
        self._analyze_news(news_data)

    def _process_current_rank_news(self, news_data: dict):
        """处理当前榜单模式新闻"""
        # 1. 匹配
        if not self.matcher.match(news_data):
            return

        # 2. 存储到数据库（自动去重）
        is_new = self.storage_manager.news_storage.add_news(
            NewsProcessingMode.CURRENT_RANK,
            news_data
        )

        if not is_new:
            return

        self.write_log(f"[榜单模式] 收到新闻: {news_data.get('title', '')}")

        # 3. 立即分析
        self._analyze_news(news_data)

    def _process_daily_summary_news(self, news_data: dict):
        """处理当日汇总模式新闻"""
        # 1. 匹配
        if not self.matcher.match(news_data):
            return

        # 2. 存储到数据库（自动去重）
        is_new = self.storage_manager.news_storage.add_news(
            NewsProcessingMode.DAILY_SUMMARY,
            news_data
        )

        if not is_new:
            return  # 已收集过

        self.write_log(f"[汇总模式] 收集新闻: {news_data.get('title', '')}")

        # 3. 检查是否应该触发批量分析
        if self._should_trigger_summary():
            self._on_summary_scheduled()

    def _should_trigger_summary(self) -> bool:
        """判断是否应该触发汇总分析"""
        summary_config = self.news_config.daily_summary_config
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        if summary_config.schedule_type == ScheduleType.FIXED_TIME:
            # 固定时间点触发
            return current_time in summary_config.schedule_times
        else:
            # 间隔模式：使用内存记录
            if not hasattr(self, '_last_summary_time'):
                self._last_summary_time = None

            if self._last_summary_time is None:
                self._last_summary_time = now
                return True

            elapsed = (now - self._last_summary_time).total_seconds()
            if elapsed >= summary_config.schedule_interval:
                self._last_summary_time = now
                return True

        return False

    def _on_summary_scheduled(self):
        """定时触发汇总分析"""
        # 从数据库获取所有未分析的汇总模式新闻
        all_news = self.storage_manager.news_storage.get_news_by_mode(
            NewsProcessingMode.DAILY_SUMMARY,
            limit=None  # 获取所有
        )

        if not all_news:
            self.write_log("[汇总模式] 无待分析新闻")
            return

        self.write_log(f"[汇总模式] 定时分析 {len(all_news)} 条新闻")

        # 批量分析
        for news_doc in all_news:
            # 从数据库文档中提取原始新闻数据
            news_data = news_doc.get("raw_data", news_doc)
            self._analyze_news(news_data)

        # 清空已分析的汇总模式新闻
        self.storage_manager.news_storage.clear_mode(NewsProcessingMode.DAILY_SUMMARY)
        self.write_log("[汇总模式] 已清空缓存")

    def _analyze_news(self, news_data: dict):
        """分析新闻"""
        try:
            # 执行分析
            analysis = self.analyzer.analyze_news(news_data)

            # 更新策略变量
            self.last_news_time = analysis["analysis_time"]
            self.last_sentiment = analysis["sentiment"]

            self.write_log(f"分析结果: 情感={analysis['sentiment']:.2f}, "
                          f"标签={analysis['sentiment_label']}, "
                          f"信号={analysis['trade_signal']}")

            # 保存分析结果到数据库
            self.storage_manager.analysis_storage.save_analysis(analysis)

            # 发送分析事件
            from vnpy.event import Event
            event = Event(EVENT_NEWS_ANALYSIS, analysis)
            self.event_engine.put(event)

            # 执行分析结果
            if self.execution_engine:
                self.execution_engine.execute_analysis(analysis, news_data)

        except Exception as e:
            self.write_log(f"分析新闻失败: {e}")

    def on_analysis_event(self, event):
        """处理分析结果事件（可用于记录、风控等）"""
        analysis = event.data
        # 可以在这里添加额外的处理逻辑
        pass

    def on_trade_command_event(self, event):
        """处理交易指令事件（用于手动触发交易）"""
        command = event.data

        if self.execution_engine:
            if command.get("action") == "approve":
                self.execution_engine.approve_command(command["command_id"])
            elif command.get("action") == "reject":
                self.execution_engine.reject_command(command["command_id"], command.get("reason", ""))

    def on_tick(self, tick: TickData):
        """Tick数据回调"""
        # 检查新闻是否过期
        if self.last_news_time:
            time_diff = (datetime.now() - self.last_news_time).total_seconds()
            if time_diff > self.news_valid_time:
                self.write_log("新闻信号已过期")
                self.last_news_time = None
                self.last_sentiment = 0.0

        # 可以在这里添加基于市场的风控逻辑
        # 例如：检查价格波动、成交量等

    def on_bar(self, bar: BarData):
        """K线数据回调"""
        # 可以在这里添加基于K线的分析
        pass

    def on_order(self, order: OrderData):
        """订单回调"""
        self.write_log(f"订单更新: {order.vt_orderid}, 状态={order.status}")

        # 更新交易计数
        if order.status.value in ["已成交", "部分成交"]:
            if order.traded > 0 and order.traded == order.volume:
                self.today_order_count += 1

    def on_trade(self, trade: TradeData):
        """成交回调"""
        self.write_log(f"成交回报: {trade.vt_tradeid}, "
                      f"{trade.vt_symbol}, "
                      f"{trade.direction.value}, "
                      f"{trade.price}, {trade.volume}")

    def buy(self, price: float, volume: float, stop: bool = False, lock: bool = False):
        """买入"""
        return super().buy(price, volume, stop, lock)

    def sell(self, price: float, volume: float, stop: bool = False, lock: bool = False):
        """卖出"""
        return super().sell(price, volume, stop, lock)

    def short(self, price: float, volume: float, stop: bool = False, lock: bool = False):
        """卖空"""
        return super().short(price, volume, stop, lock)

    def cover(self, price: float, volume: float, stop: bool = False, lock: bool = False):
        """回补"""
        return super().cover(price, volume, stop, lock)

    def cancel_order(self, vt_orderid: str):
        """撤单"""
        return super().cancel_order(vt_orderid)

    def _reset_daily_count(self):
        """重置每日计数"""
        self.today_order_count = 0


class MultiSymbolNewsStrategy(NewsTradingStrategy):
    """多品种新闻策略

    支持同时监控多个品种，根据新闻选择目标品种交易
    """

    # 策略参数
    target_symbols: str = "BTC,ETH,BNB"    # 目标品种列表（逗号分隔）

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        # 解析目标品种
        self.target_symbols_list = [
            s.strip() for s in self.target_symbols.split(",")
        ]

        # 更新分析器的已知品种
        self.analyzer.known_symbols = self.target_symbols_list

    def on_news_event(self, event):
        """处理新闻事件"""
        news_data = event.data
        news_id = news_data.get("news_id", "")

        # 检查是否已处理
        if news_id in self.processed_news_ids:
            return

        self.write_log(f"收到新闻: {news_data.get('title', '')}")

        # 添加到缓存
        self.processed_news_ids.add(news_id)

        # 分析新闻
        self._analyze_news(news_data)

    def _analyze_news(self, news_data: dict):
        """分析新闻"""
        try:
            # 执行分析
            analysis = self.analyzer.analyze_news(news_data)

            # 更新策略变量
            self.last_news_time = analysis["analysis_time"]
            self.last_sentiment = analysis["sentiment"]

            target_symbols = analysis.get("target_symbols", [])

            self.write_log(f"分析结果: 情感={analysis['sentiment']:.2f}, "
                          f"标签={analysis['sentiment_label']}, "
                          f"信号={analysis['trade_signal']}, "
                          f"目标={target_symbols}")

            # 发送分析事件
            from vnpy.event import Event
            event = Event(EVENT_NEWS_ANALYSIS, analysis)
            self.event_engine.put(event)

            # 只处理目标品种中的信号
            if analysis["trade_signal"] == "HOLD":
                return

            # 过滤目标品种
            filtered_symbols = [s for s in target_symbols if s in self.target_symbols_list]

            if not filtered_symbols:
                self.write_log("没有匹配的目标品种")
                return

            # 更新分析结果中的目标品种
            analysis["target_symbols"] = filtered_symbols

            # 执行分析结果
            if self.execution_engine:
                self.execution_engine.execute_analysis(analysis, news_data)

        except Exception as e:
            self.write_log(f"分析新闻失败: {e}")

    parameters = NewsTradingStrategy.parameters + ["target_symbols"]
