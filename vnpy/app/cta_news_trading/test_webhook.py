"""
测试飞书Webhook配置
"""

import json
from vnpy.app.cta_news_trading.lark_client import LarkWebhookClient

def test_webhook():
    """测试webhook是否工作"""

    # 从配置中读取webhook URL
    webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/a97ae0ac-e449-44bd-9bfb-de4b6acd31ba"

    print("=" * 60)
    print("飞书Webhook测试")
    print("=" * 60)
    print(f"Webhook URL: {webhook_url}")
    print()

    # 创建客户端
    client = LarkWebhookClient(webhook_url)

    # 测试1: 发送简单文本消息
    print("\n[测试1] 发送简单文本消息...")
    success = client.send_message("这是一条测试消息，来自vnpy新闻交易系统", msg_type="text")
    print(f"结果: {'成功' if success else '失败'}")

    # 测试2: 发送新闻分析卡片
    print("\n[测试2] 发送新闻分析卡片...")
    test_analysis = {
        "sentiment_label": "正面",
        "sentiment": 0.8,
        "confidence": 0.85,
        "trade_signal": "BUY",
        "target_symbols": ["BTCUSDT"],
        "keywords": ["比特币", "突破", "上涨"],
        "summary": "比特币价格突破60000美元关键阻力位，交易量显著增加"
    }

    success = client.send_news_analysis("", test_analysis)
    print(f"结果: {'成功' if success else '失败'}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("请检查飞书群聊是否收到消息")
    print("=" * 60)

if __name__ == "__main__":
    test_webhook()
