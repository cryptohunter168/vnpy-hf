"""
飞书命令监听模块
接收飞书的交易指令
"""

import json
import hmac
import hashlib
import base64
from typing import Dict, Callable, Optional
from datetime import datetime

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from flask import Flask, request, jsonify
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


class LarkCommandListener:
    """飞书命令监听器"""

    def __init__(self, encrypt_key: str, bot_name: str = "交易机器人"):
        """
        Args:
            encrypt_key: 加密key（用于验证webhook签名）
            bot_name: 机器人名称
        """
        self.encrypt_key = encrypt_key
        self.bot_name = bot_name
        self.app = None
        self.command_handlers: Dict[str, Callable] = {}
        self.approval_requests: Dict[str, Dict] = {}  # 存储审批请求

        if FLASK_AVAILABLE:
            self.app = Flask(__name__)
            self._setup_routes()

    def _setup_routes(self):
        """设置路由"""
        @self.app.route('/webhook', methods=['POST'])
        def webhook():
            """接收飞书webhook"""
            data = request.get_json()

            # 验证签名
            if "timestamp" in data and "sign" in data:
                if not self._verify_signature(data["timestamp"], data["sign"]):
                    return jsonify({"code": 401, "msg": "签名验证失败"})

            # 处理不同类型的事件
            if data.get("type") == "url_verification":
                return self._handle_url_verification(data)
            elif data.get("type") == "event_callback":
                return self._handle_event_callback(data)
            elif data.get("type") == "im.message.receive_v1":
                return self._handle_message_receive(data)

            return jsonify({"code": 0, "msg": "success"})

    def _verify_signature(self, timestamp: str, sign: str) -> bool:
        """验证签名"""
        string_to_sign = f"{timestamp}\n{self.encrypt_key}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        signature = base64.b64encode(hmac_code).decode("utf-8")
        return signature == sign

    def _handle_url_verification(self, data: dict) -> dict:
        """处理URL验证"""
        return jsonify({
            "code": 0,
            "msg": "success",
            "challenge": data.get("challenge")
        })

    def _handle_event_callback(self, data: dict) -> dict:
        """处理事件回调"""
        event = data.get("event", {})

        # 处理卡片交互事件
        if event.get("type") == "card.action.trigger":
            return self._handle_card_action(event)

        return jsonify({"code": 0, "msg": "success"})

    def _handle_card_action(self, event: dict) -> dict:
        """处理卡片交互（审批按钮）"""
        action_value = event.get("action", {}).get("value", {})
        action_type = action_value.get("action")  # approve/reject
        command_id = action_value.get("command_id")

        print(f"收到卡片交互: action={action_type}, command_id={command_id}")

        # 查找对应的审批请求
        if command_id in self.approval_requests:
            request_data = self.approval_requests[command_id]

            # 调用对应的处理函数
            if action_type == "approve":
                if "on_approve" in request_data and callable(request_data["on_approve"]):
                    request_data["on_approve"](request_data["command"])
            elif action_type == "reject":
                if "on_reject" in request_data and callable(request_data["on_reject"]):
                    request_data["on_reject"](request_data["command"])

            # 清理已处理的请求
            del self.approval_requests[command_id]

        return jsonify({"code": 0, "msg": "success"})

    def _handle_message_receive(self, data: dict) -> dict:
        """处理接收消息"""
        event = data.get("event", {})
        message = event.get("message", {})
        content = message.get("content", "")

        # 解析消息内容
        try:
            if isinstance(content, str):
                content = json.loads(content)

            text = content.get("text", "").strip()
            chat_id = event.get("chat_id", "")

            print(f"收到消息: chat_id={chat_id}, text={text}")

            # 解析命令
            if text.startswith("/"):
                return self._handle_command(text, chat_id)

        except Exception as e:
            print(f"处理消息失败: {e}")

        return jsonify({"code": 0, "msg": "success"})

    def _handle_command(self, text: str, chat_id: str) -> dict:
        """处理命令"""
        parts = text.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # 查找对应的命令处理器
        if command in self.command_handlers:
            try:
                result = self.command_handlers[command](args, chat_id)
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    "code": 500,
                    "msg": f"命令执行失败: {str(e)}"
                })

        # 默认返回帮助信息
        return jsonify({
            "code": 200,
            "msg": "未知命令"
        })

    def register_command(self, command: str, handler: Callable):
        """注册命令处理器

        Args:
            command: 命令名称（如 /buy, /sell）
            handler: 处理函数，签名为 handler(args: str, chat_id: str) -> dict
        """
        self.command_handlers[command] = handler
        print(f"注册命令: {command}")

    def register_approval(self, command_id: str, command: dict,
                         on_approve: Callable, on_reject: Callable):
        """注册审批请求

        Args:
            command_id: 指令ID
            command: 交易指令
            on_approve: 同意时的回调
            on_reject: 拒绝时的回调
        """
        self.approval_requests[command_id] = {
            "command": command,
            "on_approve": on_approve,
            "on_reject": on_reject,
            "timestamp": datetime.now()
        }
        print(f"注册审批请求: {command_id}")

    def run(self, host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
        """启动Flask服务器

        Args:
            host: 监听地址
            port: 监听端口
            debug: 调试模式
        """
        if not self.app:
            print("Flask不可用，无法启动监听器")
            return

        print(f"启动飞书命令监听器: http://{host}:{port}/webhook")
        self.app.run(host=host, port=port, debug=debug, threaded=True)


class TradeCommandParser:
    """交易指令解析器"""

    @staticmethod
    def parse_command(text: str) -> Optional[dict]:
        """解析交易命令

        支持的命令格式:
        - /buy BTC 50000 0.1         # 买入BTC，价格50000，数量0.1
        - /sell ETH 3000 5           # 卖出ETH，价格3000，数量5
        - /cancel all                # 撤销所有订单
        - /cancel 123456             # 撤销指定订单

        Returns:
            解析后的指令字典，格式:
            {
                "command_type": "BUY/SELL/CANCEL_ALL/CANCEL",
                "symbol": "BTC",
                "price": 50000,
                "volume": 0.1,
                "orderid": "123456"
            }
        """
        parts = text.strip().split()

        if len(parts) < 2:
            return None

        command = parts[0].upper()

        if command == "/CANCEL":
            if len(parts) == 2 and parts[1].upper() == "ALL":
                return {
                    "command_type": "CANCEL_ALL"
                }
            elif len(parts) == 2:
                return {
                    "command_type": "CANCEL",
                    "orderid": parts[1]
                }

        elif command in ("/BUY", "/SELL"):
            if len(parts) >= 4:
                return {
                    "command_type": "BUY" if command == "/BUY" else "SELL",
                    "symbol": parts[1].upper(),
                    "price": float(parts[2]),
                    "volume": float(parts[3])
                }

        return None


# 预定义的命令处理器
def create_trade_command_handlers(main_engine, lark_client):
    """创建交易命令处理器

    Args:
        main_engine: vn.py主引擎
        lark_client: 飞书客户端

    Returns:
        命令处理器字典
    """

    def handle_buy(args: str, chat_id: str) -> dict:
        """处理买入命令"""
        try:
            command_data = TradeCommandParser.parse_command(f"/buy {args}")
            if not command_data:
                return {"code": 400, "msg": "命令格式错误，正确格式: /buy BTC 50000 0.1"}

            # 创建交易指令
            from vnpy.trader.object import OrderRequest, Direction, OrderType

            req = OrderRequest(
                symbol=command_data["symbol"],
                exchange=...,  # 需要根据symbol推断exchange
                direction=Direction.LONG,
                order_type=OrderType.LIMIT,
                volume=command_data["volume"],
                price=command_data["price"]
            )

            # 发送订单
            vt_orderid = main_engine.send_order(req, "BINANCE")  # 假设使用Binance

            return {
                "code": 200,
                "msg": f"订单已发送: {vt_orderid}",
                "orderid": vt_orderid
            }
        except Exception as e:
            return {"code": 500, "msg": str(e)}

    def handle_sell(args: str, chat_id: str) -> dict:
        """处理卖出命令"""
        try:
            command_data = TradeCommandParser.parse_command(f"/sell {args}")
            if not command_data:
                return {"code": 400, "msg": "命令格式错误，正确格式: /sell BTC 50000 0.1"}

            # 创建交易指令
            from vnpy.trader.object import OrderRequest, Direction, OrderType

            req = OrderRequest(
                symbol=command_data["symbol"],
                exchange=...,  # 需要根据symbol推断exchange
                direction=Direction.SHORT,
                order_type=OrderType.LIMIT,
                volume=command_data["volume"],
                price=command_data["price"]
            )

            # 发送订单
            vt_orderid = main_engine.send_order(req, "BINANCE")

            return {
                "code": 200,
                "msg": f"订单已发送: {vt_orderid}",
                "orderid": vt_orderid
            }
        except Exception as e:
            return {"code": 500, "msg": str(e)}

    def handle_cancel_all(args: str, chat_id: str) -> dict:
        """处理撤销所有订单命令"""
        try:
            # TODO: 实现撤销所有订单
            return {"code": 200, "msg": "撤销所有订单"}
        except Exception as e:
            return {"code": 500, "msg": str(e)}

    def handle_cancel(args: str, chat_id: str) -> dict:
        """处理撤销订单命令"""
        try:
            # TODO: 实现撤销指定订单
            return {"code": 200, "msg": f"撤销订单: {args}"}
        except Exception as e:
            return {"code": 500, "msg": str(e)}

    def handle_status(args: str, chat_id: str) -> dict:
        """处理状态查询命令"""
        try:
            # TODO: 获取账户状态
            return {"code": 200, "msg": "状态查询"}
        except Exception as e:
            return {"code": 500, "msg": str(e)}

    def handle_help(args: str, chat_id: str) -> dict:
        """处理帮助命令"""
        help_text = """
        交易机器人命令帮助:

        /buy <品种> <价格> <数量>  - 买入
        /sell <品种> <价格> <数量> - 卖出
        /cancel all              - 撤销所有订单
        /cancel <订单ID>         - 撤销指定订单
        /status                  - 查询账户状态
        /help                    - 显示帮助信息
        """
        lark_client.send_text_message(chat_id, help_text)
        return {"code": 200, "msg": "help"}

    return {
        "/buy": handle_buy,
        "/sell": handle_sell,
        "/cancel": handle_cancel,
        "/status": handle_status,
        "/help": handle_help,
    }
