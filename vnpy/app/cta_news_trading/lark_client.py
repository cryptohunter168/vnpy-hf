"""
飞书消息推送模块
"""

import json
import requests
import time
import hmac
import hashlib
import base64
import threading
from typing import Dict, List
from datetime import datetime

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class LarkClient:
    """飞书客户端"""

    def __init__(self, app_id: str, app_secret: str, bot_name: str = "交易机器人"):
        """
        Args:
            app_id: 飞书应用ID
            app_secret: 飞书应用Secret
            bot_name: 机器人名称
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.bot_name = bot_name
        self.access_token = ""
        self.token_expire_time = 0
        self.lock = threading.Lock()

    def _get_access_token(self) -> str:
        """获取access_token"""
        if self.access_token and time.time() < self.token_expire_time:
            return self.access_token

        with self.lock:
            # 双重检查
            if self.access_token and time.time() < self.token_expire_time:
                return self.access_token

            if not REQUESTS_AVAILABLE:
                print("缺少requests库，无法获取飞书access_token")
                return ""

            url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
            data = {
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }

            try:
                response = requests.post(url, json=data, timeout=10)
                result = response.json()

                if result.get("code") == 0:
                    self.access_token = result.get("app_access_token")
                    self.token_expire_time = time.time() + result.get("expire", 3600) - 60
                    return self.access_token
                else:
                    print(f"获取access_token失败: {result}")
                    return ""
            except Exception as e:
                print(f"获取access_token异常: {e}")
                return ""

    def _request(self, method: str, path: str, data: dict = None,
                 params: dict = None, **kwargs) -> dict:
        """发送请求

        Args:
            method: 请求方法 (GET/POST)
            path: 请求路径
            data: 请求数据
            params: 请求参数
            **kwargs: 其他参数

        Returns:
            响应数据字典
        """
        if not REQUESTS_AVAILABLE:
            print("缺少requests库")
            return {}

        token = self._get_access_token()
        if not token:
            return {}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        url = f"https://open.feishu.cn{path}"

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params,
                                       timeout=10, **kwargs)
            else:
                response = requests.post(url, headers=headers, json=data,
                                        params=params, timeout=10, **kwargs)

            result = response.json()

            if result.get("code") == 0:
                return result.get("data", {})
            else:
                print(f"请求失败: {result}")
                return {}
        except Exception as e:
            print(f"请求异常: {e}")
            return {}

    def send_text_message(self, chat_id: str, content: str) -> bool:
        """发送文本消息

        Args:
            chat_id: 群聊ID或用户ID
            content: 消息内容

        Returns:
            是否发送成功
        """
        url = "/open-apis/message/v4/send"
        data = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": {
                "text": content
            },
            "receive_id_type": "chat_id"
        }

        result = self._request("POST", url, data=data)
        return bool(result)

    def send_card_message(self, chat_id: str, card: dict) -> bool:
        """发送卡片消息

        Args:
            chat_id: 群聊ID或用户ID
            card: 卡片内容

        Returns:
            是否发送成功
        """
        url = "/open-apis/message/v4/send"
        data = {
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": card,
            "receive_id_type": "chat_id"
        }

        result = self._request("POST", url, data=data)
        return bool(result)

    def send_news_analysis(self, chat_id: str, analysis: dict) -> bool:
        """发送新闻分析结果

        Args:
            chat_id: 群聊ID
            analysis: 分析结果

        Returns:
            是否发送成功
        """
        # 构建卡片
        sentiment_emoji = {
            "正面": "📈",
            "负面": "📉",
            "中性": "😐"
        }

        signal_emoji = {
            "BUY": "🟢",
            "SELL": "🔴",
            "HOLD": "⚪"
        }

        sentiment_label = analysis.get("sentiment_label", "中性")
        sentiment_score = analysis.get("sentiment", 0)
        confidence = analysis.get("confidence", 0)
        trade_signal = analysis.get("trade_signal", "HOLD")
        target_symbols = analysis.get("target_symbols", [])
        keywords = analysis.get("keywords", [])
        summary = analysis.get("summary", "")

        # 构建内容元素
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**情感倾向:** {sentiment_emoji.get(sentiment_label, '')} {sentiment_label} ({sentiment_score:.2f})"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**置信度:** {confidence:.2%}"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**交易信号:** {signal_emoji.get(trade_signal, '')} {trade_signal}"
                }
            },
        ]

        if target_symbols:
            symbols_str = "、".join(target_symbols)
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**相关品种:** {symbols_str}"
                }
            })

        if keywords:
            keywords_str = "、".join(keywords[:5])
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**关键词:** {keywords_str}"
                }
            })

        if summary:
            elements.append({
                "tag": "hr"
            })
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**摘要:** {summary}"
                }
            })

        card = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📰 新闻分析结果"
                }
            },
            "elements": elements
        }

        return self.send_card_message(chat_id, card)

    def send_trade_request(self, chat_id: str, command: dict, timeout: int = 300) -> bool:
        """发送交易请求（带审批按钮）

        Args:
            chat_id: 群聊ID
            command: 交易指令
            timeout: 审批超时时间（秒）

        Returns:
            是否发送成功
        """
        command_id = command.get("command_id", "")
        symbol = command.get("symbol", "")
        direction = command.get("direction", "")
        price = command.get("price", 0)
        volume = command.get("volume", 0)
        reason = command.get("reason", "")

        # 构建交互式卡片
        direction_emoji = {
            "LONG": "📈",
            "SHORT": "📉"
        }

        card = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "⚠️ 交易请求审批"
                },
                "template": "red"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**品种:** {symbol}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**方向:** {direction_emoji.get(direction, '')} {direction}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**价格:** {price}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**数量:** {volume}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**理由:** {reason}"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "✅ 同意"
                            },
                            "type": "primary",
                            "value": {
                                "action": "approve",
                                "command_id": command_id
                            }
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "❌ 拒绝"
                            },
                            "type": "danger",
                            "value": {
                                "action": "reject",
                                "command_id": command_id
                            }
                        }
                    ]
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"_请在{timeout}秒内做出决定_"
                    }
                }
            ]
        }

        return self.send_card_message(chat_id, card)

    def send_trade_result(self, chat_id: str, command_id: str,
                         success: bool, message: str = "") -> bool:
        """发送交易执行结果

        Args:
            chat_id: 群聊ID
            command_id: 指令ID
            success: 是否成功
            message: 结果消息

        Returns:
            是否发送成功
        """
        status_emoji = "✅" if success else "❌"
        status_text = "执行成功" if success else "执行失败"

        card = {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{status_emoji} 交易结果"
                },
                "template": "green" if success else "red"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**指令ID:** {command_id}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**状态:** {status_text}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**详情:** {message}"
                    }
                }
            ]
        }

        return self.send_card_message(chat_id, card)


class LarkWebhookClient:
    """飞书Webhook客户端（使用webhook地址发送消息）"""

    def __init__(self, webhook_url: str):
        """
        Args:
            webhook_url: 飞书webhook地址
        """
        self.webhook_url = webhook_url

    def send_message(self, content: str, msg_type: str = "text") -> bool:
        """发送消息

        Args:
            content: 消息内容
            msg_type: 消息类型 (text/post/interactive)

        Returns:
            是否发送成功
        """
        if not REQUESTS_AVAILABLE:
            print("缺少requests库")
            return False

        data = {
            "msg_type": msg_type,
        }

        if msg_type == "text":
            data["content"] = {"text": content}
        elif msg_type == "post":
            data["content"] = {
                "post": {
                    "zh_cn": {
                        "title": "",
                        "content": [[{"tag": "text", "text": content}]]
                    }
                }
            }
        elif msg_type == "interactive":
            data["content"] = content

        try:
            print(f"[DEBUG] 发送飞书Webhook消息: {self.webhook_url}")
            print(f"[DEBUG] 消息类型: {msg_type}")
            print(f"[DEBUG] 请求数据: {data}")

            response = requests.post(self.webhook_url, json=data, timeout=10)
            result = response.json()

            print(f"[DEBUG] 响应状态码: {response.status_code}")
            print(f"[DEBUG] 响应内容: {result}")

            # 检查不同的成功字段
            code = result.get("code", result.get("StatusCode", -1))
            if code == 0:
                print(f"[DEBUG] 飞书消息发送成功")
                return True
            else:
                print(f"[ERROR] 飞书消息发送失败, code={code}, msg={result.get('msg', 'unknown')}")
                return False
        except Exception as e:
            print(f"[ERROR] 发送飞书消息异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    def send_text_message(self, chat_id: str, content: str) -> bool:
        """发送文本消息（兼容LarkClient接口）

        Args:
            chat_id: 群聊ID（webhook模式下忽略此参数）
            content: 消息内容

        Returns:
            是否发送成功
        """
        return self.send_message(content, msg_type="text")

    def send_card_message(self, chat_id: str, card: dict) -> bool:
        """发送卡片消息（兼容LarkClient接口）

        Args:
            chat_id: 群聊ID（webhook模式下忽略此参数）
            card: 卡片内容

        Returns:
            是否发送成功
        """
        return self.send_message(card, msg_type="interactive")

    def send_news_analysis(self, chat_id: str, analysis: dict) -> bool:
        """发送新闻分析结果（兼容LarkClient接口）

        Args:
            chat_id: 群聊ID（webhook模式下忽略此参数）
            analysis: 分析结果

        Returns:
            是否发送成功
        """
        # 构建卡片
        sentiment_emoji = {
            "正面": "📈",
            "负面": "📉",
            "中性": "😐"
        }

        signal_emoji = {
            "BUY": "🟢",
            "SELL": "🔴",
            "HOLD": "⚪"
        }

        sentiment_label = analysis.get("sentiment_label", "中性")
        sentiment_score = analysis.get("sentiment", 0)
        confidence = analysis.get("confidence", 0)
        trade_signal = analysis.get("trade_signal", "HOLD")
        target_symbols = analysis.get("target_symbols", [])
        keywords = analysis.get("keywords", [])
        summary = analysis.get("summary", "")

        # 构建内容元素
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**情感倾向:** {sentiment_emoji.get(sentiment_label, '')} {sentiment_label} ({sentiment_score:.2f})"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**置信度:** {confidence:.2%}"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**交易信号:** {signal_emoji.get(trade_signal, '')} {trade_signal}"
                }
            },
        ]

        if target_symbols:
            symbols_str = "、".join(target_symbols)
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**相关品种:** {symbols_str}"
                }
            })

        if keywords:
            keywords_str = "、".join(keywords[:5])
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**关键词:** {keywords_str}"
                }
            })

        if summary:
            elements.append({
                "tag": "hr"
            })
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**摘要:** {summary}"
                }
            })

        card = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📰 新闻分析结果"
                }
            },
            "elements": elements
        }

        return self.send_card_message(chat_id, card)

    def send_trade_request(self, chat_id: str, command: dict, timeout: int = 300) -> bool:
        """发送交易请求（兼容LarkClient接口，webhook模式不支持按钮）

        Args:
            chat_id: 群聊ID（webhook模式下忽略此参数）
            command: 交易指令
            timeout: 审批超时时间（秒）

        Returns:
            是否发送成功
        """
        # Webhook模式不支持交互式按钮，发送文本消息
        command_id = command.get("command_id", "")
        symbol = command.get("symbol", "")
        direction = command.get("direction", "")
        price = command.get("price", 0)
        volume = command.get("volume", 0)
        reason = command.get("reason", "")

        direction_emoji = {
            "LONG": "📈",
            "SHORT": "📉"
        }

        content = f"""⚠️ 交易请求（Webhook模式不支持审批）

品种: {symbol}
方向: {direction_emoji.get(direction, '')} {direction}
价格: {price}
数量: {volume}
理由: {reason}
指令ID: {command_id}

注意: Webhook模式不支持交互式审批，如需执行请手动下单"""

        return self.send_message(content, msg_type="text")

    def send_trade_result(self, chat_id: str, command_id: str,
                         success: bool, message: str = "") -> bool:
        """发送交易执行结果（兼容LarkClient接口）

        Args:
            chat_id: 群聊ID（webhook模式下忽略此参数）
            command_id: 指令ID
            success: 是否成功
            message: 结果消息

        Returns:
            是否发送成功
        """
        status_emoji = "✅" if success else "❌"
        status_text = "执行成功" if success else "执行失败"

        content = f"""{status_emoji} 交易结果

指令ID: {command_id}
状态: {status_text}
详情: {message}"""

        return self.send_message(content, msg_type="text")


def verify_webhook_signature(timestamp: str, sign: str, encrypt_key: str) -> bool:
    """验证webhook签名

    Args:
        timestamp: 时间戳
        sign: 签名
        encrypt_key: 加密key

    Returns:
        是否验证通过
    """
    string_to_sign = f"{timestamp}\n{encrypt_key}"
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()
    signature = base64.b64encode(hmac_code).decode("utf-8")

    return signature == sign
