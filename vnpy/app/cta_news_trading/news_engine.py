"""
新闻交易引擎
负责根据分析结果和配置执行交易
"""

import time
import uuid
import threading
from typing import Dict, Callable, Optional, List
from datetime import datetime, timedelta

from .config import ExecutionConfig, ExecutionMode
from .lark_client import LarkClient


class TradeCommand:
    """交易指令"""

    def __init__(self, command_type: str, symbol: str, exchange,
                 direction, offset, price: float, volume: float,
                 source: str = "NEWS", priority: int = 0, reason: str = ""):
        self.command_id = str(uuid.uuid4())
        self.command_type = command_type  # BUY/SELL/CANCEL_ALL
        self.symbol = symbol
        self.exchange = exchange
        self.direction = direction
        self.offset = offset
        self.price = price
        self.volume = volume
        self.source = source
        self.priority = priority
        self.reason = reason
        self.created_time = datetime.now()
        self.expire_time = None
        self.status = "pending"  # pending/approved/rejected/executed/expired

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "command_id": self.command_id,
            "command_type": self.command_type,
            "symbol": self.symbol,
            "exchange": self.exchange.value if self.exchange else "",
            "direction": self.direction.value if self.direction else "",
            "offset": self.offset.value if self.offset else "",
            "price": self.price,
            "volume": self.volume,
            "source": self.source,
            "priority": self.priority,
            "reason": self.reason,
            "created_time": self.created_time,
            "status": self.status,
        }


class News_Engine:
    """新闻交易引擎"""

    def __init__(self, main_engine, config: ExecutionConfig):
        """
        Args:
            main_engine: vn.py主引擎
            config: 执行配置
        """
        self.main_engine = main_engine
        self.config = config
        self.lark_client = None
        self.pending_commands: Dict[str, TradeCommand] = {}
        self.approval_requests: Dict[str, TradeCommand] = {}

        # 统计信息
        self.daily_order_count = 0
        self.last_reset_date = datetime.now().date()

        # 初始化飞书客户端
        if config.enable_lark_push and config.lark_app_id and config.lark_app_secret:
            self.lark_client = LarkClient(
                app_id=config.lark_app_id,
                app_secret=config.lark_app_secret,
                bot_name=config.lark_bot_name
            )
            print("飞书客户端已初始化")

    def _reset_daily_count(self):
        """重置每日计数"""
        today = datetime.now().date()
        if self.last_reset_date != today:
            self.daily_order_count = 0
            self.last_reset_date = today

    def execute_analysis(self, analysis: dict, news_data: dict) -> bool:
        """执行分析结果

        Args:
            analysis: 分析结果
            news_data: 新闻数据

        Returns:
            是否成功处理
        """
        try:
            # 检查阈值
            sentiment = analysis.get("sentiment", 0)
            confidence = analysis.get("confidence", 0)

            if abs(sentiment) < self.config.sentiment_threshold:
                print(f"情感分数 {sentiment} 未达到阈值 {self.config.sentiment_threshold}")
                return False

            if confidence < self.config.confidence_threshold:
                print(f"置信度 {confidence} 未达到阈值 {self.config.confidence_threshold}")
                return False

            # 推送分析结果到飞书
            if self.lark_client and self.config.enable_lark_push:
                self.lark_client.send_news_analysis(
                    self.config.lark_chat_id,
                    analysis
                )

            # 生成交易信号
            trade_signal = analysis.get("trade_signal", "HOLD")
            target_symbols = analysis.get("target_symbols", [])

            if trade_signal == "HOLD" or not target_symbols:
                print("无交易信号或目标品种")
                return True

            # 根据执行模式处理
            return self._process_trade_signal(
                trade_signal,
                target_symbols,
                analysis,
                news_data
            )

        except Exception as e:
            print(f"执行分析失败: {e}")
            return False

    def _process_trade_signal(self, signal: str, symbols: List[str],
                            analysis: dict, news_data: dict) -> bool:
        """处理交易信号

        Args:
            signal: 交易信号 (BUY/SELL)
            symbols: 目标品种列表
            analysis: 分析结果
            news_data: 新闻数据

        Returns:
            是否成功处理
        """
        for symbol in symbols:
            # 检查黑名单/白名单
            if self.config.symbol_blacklist and symbol in self.config.symbol_blacklist:
                print(f"{symbol} 在黑名单中，跳过")
                continue

            if self.config.symbol_whitelist and symbol not in self.config.symbol_whitelist:
                print(f"{symbol} 不在白名单中，跳过")
                continue

            # 获取交易所信息
            exchange = self._get_exchange_for_symbol(symbol)
            if not exchange:
                print(f"无法确定 {symbol} 的交易所")
                continue

            # 获取价格
            price = self._get_current_price(symbol, exchange)
            if price <= 0:
                print(f"无法获取 {symbol} 的当前价格")
                continue

            # 计算交易数量（根据配置调整）
            volume = self.config.get("trade_volume", 1)
            amount = price * volume

            # 生成交易指令
            from vnpy.trader.constant import Direction, Offset

            if signal == "BUY":
                direction = Direction.LONG
                offset = Offset.OPEN
                reason = f"新闻驱动买入: {news_data.get('title', '')}"
            elif signal == "SELL":
                direction = Direction.SHORT
                offset = Offset.CLOSE
                reason = f"新闻驱动卖出: {news_data.get('title', '')}"
            else:
                continue

            command = TradeCommand(
                command_type=signal,
                symbol=symbol,
                exchange=exchange,
                direction=direction,
                offset=offset,
                price=price,
                volume=volume,
                source="NEWS",
                priority=2,
                reason=reason
            )

            # 根据执行模式处理
            if self.config.should_use_direct_execution(amount):
                # 直接执行
                self._execute_command_direct(command)
            else:
                # 飞书审批
                self._request_lark_approval(command, analysis)

        return True

    def _execute_command_direct(self, command: TradeCommand) -> bool:
        """直接执行交易指令

        Args:
            command: 交易指令

        Returns:
            是否成功
        """
        try:
            # 检查每日限制
            self._reset_daily_count()
            if self.daily_order_count >= self.config.max_daily_orders:
                print(f"已达到每日最大交易次数 {self.config.max_daily_orders}")
                return False

            # 检查单笔限制
            amount = command.price * command.volume
            if amount > self.config.max_single_order:
                print(f"交易金额 {amount} 超过单笔限制 {self.config.max_single_order}")
                return False

            # 发送订单
            from vnpy.trader.object import OrderRequest, OrderType

            req = OrderRequest(
                symbol=command.symbol,
                exchange=command.exchange,
                direction=command.direction,
                offset=command.offset,
                order_type=OrderType.MARKET,  # 市价单
                volume=command.volume,
                price=command.price,
                strategy_name="NewsTrading"
            )

            vt_orderid = self.main_engine.send_order(req, self._get_gateway_name(command.exchange))
            if vt_orderid:
                command.status = "executed"
                self.daily_order_count += 1

                # 推送执行结果到飞书
                if self.lark_client:
                    self.lark_client.send_trade_result(
                        self.config.lark_chat_id,
                        command.command_id,
                        success=True,
                        message=f"订单已发送: {vt_orderid}"
                    )

                print(f"执行交易指令成功: {command.to_dict()}")
                return True
            else:
                command.status = "rejected"
                print(f"执行交易指令失败: {command.to_dict()}")
                return False

        except Exception as e:
            command.status = "rejected"
            print(f"执行交易指令异常: {e}")
            return False

    def _request_lark_approval(self, command: TradeCommand, analysis: dict):
        """请求飞书审批

        Args:
            command: 交易指令
            analysis: 分析结果
        """
        try:
            # 设置过期时间
            command.expire_time = datetime.now() + timedelta(
                seconds=self.config.lark_approval_timeout
            )

            # 发送审批请求到飞书
            if self.lark_client:
                self.lark_client.send_trade_request(
                    self.config.lark_chat_id,
                    command.to_dict(),
                    self.config.lark_approval_timeout
                )

            # 存储待审批的指令
            self.approval_requests[command.command_id] = command

            # 启动超时检查
            self._start_approval_timeout_check(command)

            print(f"请求飞书审批: {command.to_dict()}")

        except Exception as e:
            print(f"请求飞书审批失败: {e}")

    def _start_approval_timeout_check(self, command: TradeCommand):
        """启动审批超时检查"""
        def check_timeout():
            while datetime.now() < command.expire_time:
                if command.status != "pending":
                    return
                time.sleep(1)

            # 超时
            if command.status == "pending":
                command.status = "expired"
                if command.command_id in self.approval_requests:
                    del self.approval_requests[command.command_id]
                print(f"审批请求超时: {command.command_id}")

        thread = threading.Thread(target=check_timeout, daemon=True)
        thread.start()

    def approve_command(self, command_id: str) -> bool:
        """审批通过交易指令

        Args:
            command_id: 指令ID

        Returns:
            是否成功
        """
        command = self.approval_requests.get(command_id)
        if not command:
            print(f"未找到审批请求: {command_id}")
            return False

        if command.status != "pending":
            print(f"指令状态异常: {command.status}")
            return False

        command.status = "approved"
        del self.approval_requests[command_id]

        # 执行指令
        success = self._execute_command_direct(command)

        # 推送结果到飞书
        if self.lark_client:
            self.lark_client.send_trade_result(
                self.config.lark_chat_id,
                command_id,
                success=success,
                message="审批通过，已执行" if success else "执行失败"
            )

        return success

    def reject_command(self, command_id: str, reason: str = "") -> bool:
        """拒绝交易指令

        Args:
            command_id: 指令ID
            reason: 拒绝原因

        Returns:
            是否成功
        """
        command = self.approval_requests.get(command_id)
        if not command:
            print(f"未找到审批请求: {command_id}")
            return False

        command.status = "rejected"
        del self.approval_requests[command_id]

        # 推送结果到飞书
        if self.lark_client:
            self.lark_client.send_trade_result(
                self.config.lark_chat_id,
                command_id,
                success=False,
                message=f"审批拒绝: {reason}"
            )

        print(f"拒绝交易指令: {command_id}, 原因: {reason}")
        return True

    def _get_exchange_for_symbol(self, symbol: str):
        """根据品种获取交易所"""
        # 简单判断，实际应该根据配置或查询
        from vnpy.trader.constant import Exchange

        symbol = symbol.upper()

        if "BTC" in symbol or "ETH" in symbol or len(symbol) <= 6:
            return Exchange.BINANCE
        elif symbol.startswith("6") or symbol.startswith("0") or symbol.startswith("3"):
            return Exchange.SSE if symbol.startswith("6") else Exchange.SZSE
        else:
            return Exchange.SSE

    def _get_gateway_name(self, exchange):
        """根据交易所获取网关名称"""
        from vnpy.trader.constant import Exchange

        if exchange == Exchange.BINANCE:
            return "BINANCE"
        elif exchange in [Exchange.SSE, Exchange.SZSE]:
            return "SIMNOW"  # 示例
        else:
            return "BINANCE"

    def _get_current_price(self, symbol: str, exchange) -> float:
        """获取当前价格"""
        try:
            # 从主引擎获取合约
            vt_symbol = f"{symbol}.{exchange.value}"
            contract = self.main_engine.get_contract(vt_symbol)

            if contract:
                # 获取Tick数据
                tick = self.main_engine.get_tick(vt_symbol)
                if tick and tick.last_price > 0:
                    return tick.last_price

            # 如果没有Tick，返回默认值
            return 0.0
        except Exception as e:
            print(f"获取价格失败: {e}")
            return 0.0

    def get_status(self) -> dict:
        """获取新闻交易引擎状态"""
        return {
            "daily_order_count": self.daily_order_count,
            "max_daily_orders": self.config.max_daily_orders,
            "pending_commands": len(self.pending_commands),
            "approval_requests": len(self.approval_requests),
            "mode": self.config.mode.value,
        }
