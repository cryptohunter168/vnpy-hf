"""
定时调度器模块
支持固定时间点和定时间隔两种调度模式
"""

import time
import threading
from typing import List, Callable
from datetime import datetime

from .config import ScheduleType


class NewsScheduler:
    """新闻定时调度器"""

    def __init__(self, callback: Callable, event_engine):
        """
        Args:
            callback: 到期回调函数
            event_engine: vn.py事件引擎
        """
        self.callback = callback
        self.event_engine = event_engine
        self.active = False
        self.thread = None

    def start(self):
        """启动调度器"""
        if self.active:
            return

        self.active = True
        self.thread = threading.Thread(target=self._schedule_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """停止调度器"""
        self.active = False
        if self.thread:
            self.thread.join(timeout=5)

    def _schedule_loop(self):
        """调度循环"""
        while self.active:
            try:
                # 检查是否应该触发
                should_trigger = self._check_schedule()

                if should_trigger:
                    # 在主线程中执行回调（通过事件引擎）
                    try:
                        self.callback()
                    except Exception as e:
                        print(f"调度回调执行失败: {e}")

            except Exception as e:
                print(f"调度异常: {e}")

            # 每分钟检查一次
            time.sleep(60)

    def _check_schedule(self) -> bool:
        """检查是否应该触发"""
        # 由子类实现具体逻辑
        return False


class FixedTimeScheduler(NewsScheduler):
    """固定时间点调度器"""

    def __init__(self, callback: Callable, event_engine, schedule_times: List[str]):
        super().__init__(callback, event_engine)
        self.schedule_times = schedule_times
        self.last_triggered_date = None

    def _check_schedule(self) -> bool:
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_date = now.date()

        # 检查是否已触发过（避免同一天同一时间重复触发）
        if self.last_triggered_date == current_date and current_time in self.schedule_times:
            return False

        if current_time in self.schedule_times:
            self.last_triggered_date = current_date
            return True

        return False


class IntervalScheduler(NewsScheduler):
    """定时间隔调度器"""

    def __init__(self, callback: Callable, event_engine, interval_seconds: int):
        super().__init__(callback, event_engine)
        self.interval_seconds = interval_seconds
        self.last_trigger_time = None

    def _check_schedule(self) -> bool:
        now = datetime.now()

        if self.last_trigger_time is None:
            self.last_trigger_time = now
            return True

        elapsed = (now - self.last_trigger_time).total_seconds()

        if elapsed >= self.interval_seconds:
            self.last_trigger_time = now
            return True

        return False
