"""
新闻交易策略执行模式配置
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List


class ExecutionMode(Enum):
    """策略执行模式"""

    DIRECT = "direct"          # 直接执行：分析后立即执行交易
    LARK_APPROVAL = "lark"     # 飞书审批：推送到飞书，等待人工审批后执行
    HYBRID = "hybrid"          # 混合模式：小仓位直接执行，大仓位飞书审批
    MANUAL = "manual"          # 仅通知：只推送分析结果，不自动执行


class NewsProcessingMode(Enum):
    """新闻处理模式"""

    INCREMENTAL = "incremental"      # 增量模式：只关注新增新闻
    CURRENT_RANK = "current_rank"    # 当前榜单模式：从当前榜单匹配新闻
    DAILY_SUMMARY = "daily_summary"  # 当日汇总模式：定时批量分析


class ScheduleType(Enum):
    """定时类型"""

    FIXED_TIME = "fixed_time"        # 固定时间点 (如: "09:00", "15:30")
    INTERVAL = "interval"            # 定时间隔 (如: 3600秒)


@dataclass
class IncrementalModeConfig:
    """增量模式配置"""
    keywords: List[str] = field(default_factory=list)  # 匹配关键词
    max_cache_size: int = 1000       # 最大缓存数量
    cache_expire_hours: int = 24     # 缓存过期时间(小时)


@dataclass
class CurrentRankModeConfig:
    """当前榜单模式配置"""
    rank_threshold: int = 10         # 榜单排名阈值
    min_sources: int = 2             # 最少出现源数
    platforms: List[str] = field(default_factory=list)  # 平台过滤
    max_cache_size: int = 1000


@dataclass
class DailySummaryModeConfig:
    """当日汇总模式配置"""
    keywords: List[str] = field(default_factory=list)
    collection_start_time: str = "00:00"   # 开始收集时间
    collection_end_time: str = "23:59"     # 结束收集时间

    # 定时推送配置
    schedule_type: ScheduleType = ScheduleType.FIXED_TIME
    schedule_times: List[str] = field(default_factory=lambda: ["09:00", "15:00", "21:00"])
    schedule_interval: int = 3600  # 秒，仅当schedule_type=INTERVAL时使用

    max_daily_news: int = 500      # 每日最多收集新闻数


@dataclass
class NewsProcessingConfig:
    """新闻处理配置"""
    mode: NewsProcessingMode = NewsProcessingMode.INCREMENTAL

    # 三种模式的配置
    incremental_config: IncrementalModeConfig = field(default_factory=IncrementalModeConfig)
    current_rank_config: CurrentRankModeConfig = field(default_factory=CurrentRankModeConfig)
    daily_summary_config: DailySummaryModeConfig = field(default_factory=DailySummaryModeConfig)

    # 通用配置
    enable_duplicate_detection: bool = True  # 启用去重
    cache_cleanup_interval: int = 3600       # 缓存清理间隔(秒)


class Priority(Enum):
    """指令优先级"""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


@dataclass
class ExecutionConfig:
    """执行配置"""

    mode: ExecutionMode = ExecutionMode.DIRECT

    # 飞书审批模式配置
    lark_app_id: str = ""           # 飞书应用ID
    lark_app_secret: str = ""       # 飞书应用Secret
    lark_chat_id: str = ""          # 飞书群聊ID
    lark_bot_name: str = "交易机器人" # 飞书机器人名称

    # 混合模式配置
    direct_threshold: float = 10000.0   # 直接执行的资金阈值
    lark_approval_timeout: int = 300    # 飞书审批超时时间（秒）

    # 风险控制配置
    max_single_order: float = 50000.0   # 单笔最大交易金额
    max_daily_orders: int = 10          # 每日最大交易次数
    sentiment_threshold: float = 0.6    # 情感阈值（超过此值才触发交易）
    confidence_threshold: float = 0.7   # 置信度阈值

    # 消息推送配置
    enable_lark_push: bool = True      # 是否推送飞书消息
    enable_wechat_push: bool = False   # 是否推送微信消息
    enable_dingtalk_push: bool = False # 是否推送钉钉消息

    # 其他配置
    news_valid_time: int = 300         # 新闻有效时间（秒）
    symbol_whitelist: list = field(default_factory=list)  # 品种白名单
    symbol_blacklist: list = field(default_factory=list)  # 品种黑名单

    # 新闻处理配置
    news_processing_config: NewsProcessingConfig = field(default_factory=NewsProcessingConfig)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "mode": self.mode.value,
            "lark_app_id": self.lark_app_id,
            "lark_app_secret": self.lark_app_secret,
            "lark_chat_id": self.lark_chat_id,
            "lark_bot_name": self.lark_bot_name,
            "direct_threshold": self.direct_threshold,
            "lark_approval_timeout": self.lark_approval_timeout,
            "max_single_order": self.max_single_order,
            "max_daily_orders": self.max_daily_orders,
            "sentiment_threshold": self.sentiment_threshold,
            "confidence_threshold": self.confidence_threshold,
            "enable_lark_push": self.enable_lark_push,
            "enable_wechat_push": self.enable_wechat_push,
            "enable_dingtalk_push": self.enable_dingtalk_push,
            "news_valid_time": self.news_valid_time,
            "symbol_whitelist": self.symbol_whitelist,
            "symbol_blacklist": self.symbol_blacklist,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionConfig":
        """从字典创建配置"""
        if isinstance(data.get("mode"), str):
            data["mode"] = ExecutionMode(data["mode"])
        return cls(**data)

    def should_use_direct_execution(self, amount: float) -> bool:
        """判断是否应该直接执行"""
        if self.mode == ExecutionMode.DIRECT:
            return True
        elif self.mode == ExecutionMode.LARK_APPROVAL:
            return False
        elif self.mode == ExecutionMode.MANUAL:
            return False
        elif self.mode == ExecutionMode.HYBRID:
            return amount <= self.direct_threshold
        return False
