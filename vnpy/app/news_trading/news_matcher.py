"""
新闻匹配器模块
实现三种模式的新闻匹配逻辑
"""

from typing import Optional
from .config import NewsProcessingConfig, NewsProcessingMode


class NewsMatcher:
    """新闻匹配器基类"""

    def __init__(self, config: NewsProcessingConfig):
        self.config = config

    def match(self, news_data: dict) -> bool:
        """判断新闻是否匹配"""
        raise NotImplementedError


class IncrementalNewsMatcher(NewsMatcher):
    """增量模式匹配器"""

    def match(self, news_data: dict) -> bool:
        """增量模式：只要包含关键词即匹配"""
        config = self.config.incremental_config

        if not config.keywords:
            return True

        text = f"{news_data.get('title', '')} {news_data.get('content', '')}"
        return any(keyword in text for keyword in config.keywords)


class CurrentRankNewsMatcher(NewsMatcher):
    """当前榜单模式匹配器"""

    def __init__(self, config: NewsProcessingConfig, core_module=None):
        super().__init__(config)
        self.core_module = core_module

    def match(self, news_data: dict) -> bool:
        """当前榜单模式：从榜单中匹配"""
        config = self.config.current_rank_config

        # 1. 检查是否在当前榜单中
        if not self._is_in_current_rank(news_data):
            return False

        # 2. 检查排名
        rank_info = news_data.get("rank_info", {})
        min_rank = rank_info.get("min_rank", 999)
        if min_rank > config.rank_threshold:
            return False

        # 3. 检查源数量
        source_count = rank_info.get("count", 0)
        if source_count < config.min_sources:
            return False

        # 4. 检查平台过滤
        if config.platforms:
            platforms = rank_info.get("platforms", [])
            if not any(p in config.platforms for p in platforms):
                return False

        return True

    def _is_in_current_rank(self, news_data: dict) -> bool:
        """检查是否在当前榜单中"""
        # 调用 core.py 中的 detect_latest_new_titles()
        # 然后检查新闻标题是否在其中
        if self.core_module is None:
            return False

        try:
            current_titles = self.core_module.detect_latest_new_titles(
                current_platform_ids=self.config.current_rank_config.platforms
            )

            title = news_data.get("title", "")
            for source_titles in current_titles.values():
                if title in source_titles:
                    return True

            return False
        except Exception as e:
            print(f"检查榜单失败: {e}")
            return False


class DailySummaryNewsMatcher(NewsMatcher):
    """当日汇总模式匹配器"""

    def match(self, news_data: dict) -> bool:
        """当日汇总模式：匹配关键词"""
        config = self.config.daily_summary_config

        if not config.keywords:
            return True

        text = f"{news_data.get('title', '')} {news_data.get('content', '')}"
        return any(keyword in text for keyword in config.keywords)
