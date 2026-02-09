"""
统一配置管理模块
集中管理所有新闻交易策略的配置
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


class NewsTradingConfig:
    """新闻交易策略配置管理"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: 配置文件路径，默认为 app/cta_news_trading/config/news_trading_config.json
        """
        if config_path is None:
            # 默认配置文件路径：vnpy/app/cta_news_trading/config/
            config_dir = Path(__file__).parent / "config"
            config_path = config_dir / "news_trading_config.json"

        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not self.config_path.exists():
            # 如果配置文件不存在，创建默认配置
            default_config = self._get_default_config()
            self._save_config(default_config)
            print(f"[INFO] 创建默认配置文件: {self.config_path}")
            return default_config

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"[INFO] 加载配置文件: {self.config_path}")
        return config

    def _save_config(self, config: Dict[str, Any]):
        """保存配置到文件"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "strategy": {
                "class_name": "NewsTradingStrategy",
                "strategy_name": "news_strategy_manual",
                "vt_symbol": "BTCUSDT.BINANCE",
                "setting": {
                    # 执行模式: manual(仅通知), direct(直接执行), lark_approval(飞书审批), hybrid(混合模式)
                    "execution_mode": "manual",

                    # 交易参数
                    "sentiment_threshold": 0.6,
                    "confidence_threshold": 0.7,
                    "trade_volume": 0.01,
                    "max_single_order": 50000.0,
                    "max_daily_orders": 10,
                    "news_valid_time": 300,

                    # 飞书配置
                    "enable_lark_push": True,
                    # Webhook 方式（推荐，更简单）
                    "lark_webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/a97ae0ac-e449-44bd-9bfb-de4b6acd31ba",
                    # 应用方式（可选，如果不用 webhook 可以配置这个）
                    "lark_app_id": "",
                    "lark_app_secret": "",
                    "lark_chat_id": "",
                    "lark_approval_timeout": 300,

                    # 分析器配置
                    "analyzer_type": "keyword",  # keyword/snownlp/bert

                    # 新闻处理模式
                    "news_processing_mode": "incremental",  # incremental/current_rank/daily_summary

                    # 增量模式参数
                    "incremental_keywords": "比特币,以太坊,BTC,ETH,加密货币,数字货币,区块链",
                    "incremental_max_cache": 100,

                    # 排名模式参数
                    "rank_threshold": 5,
                    "rank_min_sources": 2,
                    "rank_platforms": "sina,163,eastmoney",

                    # 汇总模式参数
                    "summary_keywords": "",
                    "summary_schedule_type": "interval",  # interval/fixed_time
                    "summary_schedule_times": "09:00,18:00",
                    "summary_schedule_interval": 3600,

                    # 数据库配置
                    "db_path": "vntrade/vnp_news_trading.db",
                }
            },
            "news_sources": {
                "fetch_interval": 60,
                "sources": [
                    {
                        "type": "api",
                        "name": "全部热点新闻",
                        "site_id": "newsnow",
                        "url": "https://newsnow.busiyi.world/api/s?id=all&latest"
                    }
                ]
            },
            "gateway": {
                # 交易网关配置（用于实际交易）
                "gateway_name": "BINANCE",
                "api_key": "",
                "api_secret": "",
                "proxy_host": "",
                "proxy_port": 0,
            }
        }

    def get_strategy_setting(self) -> Dict[str, Any]:
        """获取策略配置"""
        return self.config["strategy"]["setting"]

    def get_strategy_config(self) -> Dict[str, Any]:
        """获取完整策略配置（包含 class_name, strategy_name, vt_symbol）"""
        return self.config["strategy"]

    def get_news_config(self) -> Dict[str, Any]:
        """获取新闻源配置"""
        return {
            "fetch_interval": self.config["news_sources"]["fetch_interval"],
            "news_sources": self.config["news_sources"]["sources"]
        }

    def get_gateway_config(self) -> Dict[str, Any]:
        """获取交易网关配置"""
        return self.config["gateway"]

    def update_strategy_setting(self, setting: Dict[str, Any]):
        """更新策略配置"""
        self.config["strategy"]["setting"].update(setting)
        self._save_config(self.config)
        print(f"[INFO] 配置已保存到: {self.config_path}")

    def get_webhook_url(self) -> str:
        """获取飞书 Webhook URL"""
        return self.config["strategy"]["setting"].get("lark_webhook_url", "")

    def get_execution_mode(self) -> str:
        """获取执行模式"""
        return self.config["strategy"]["setting"].get("execution_mode", "manual")

    def is_lark_push_enabled(self) -> bool:
        """是否启用飞书推送"""
        return self.config["strategy"]["setting"].get("enable_lark_push", True)


# 创建全局配置实例
_global_config: Optional[NewsTradingConfig] = None


def get_config(config_path: Optional[str] = None) -> NewsTradingConfig:
    """获取全局配置实例（单例模式）"""
    global _global_config
    if _global_config is None:
        _global_config = NewsTradingConfig(config_path)
    return _global_config


def reload_config(config_path: Optional[str] = None) -> NewsTradingConfig:
    """重新加载配置"""
    global _global_config
    _global_config = NewsTradingConfig(config_path)
    return _global_config
