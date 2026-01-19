"""
新闻交易策略执行模式配置
"""

from enum import Enum
from dataclasses import dataclass, field


class ExecutionMode(Enum):
    """策略执行模式"""

    DIRECT = "direct"          # 直接执行：分析后立即执行交易
    LARK_APPROVAL = "lark"     # 飞书审批：推送到飞书，等待人工审批后执行
    HYBRID = "hybrid"          # 混合模式：小仓位直接执行，大仓位飞书审批
    MANUAL = "manual"           # 仅通知：只推送分析结果，不自动执行


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
