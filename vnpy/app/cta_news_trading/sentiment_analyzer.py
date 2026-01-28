"""
AI情感分析模块
支持多种情感分析方式
"""

import re
import json
from typing import List, Dict, Tuple
from datetime import datetime

try:
    import jieba
    import jieba.analyse
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

try:
    from snownlp import SnowNLP
    SNOWNLP_AVAILABLE = True
except ImportError:
    SNOWNLP_AVAILABLE = False

try:
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


class SentimentAnalyzer:
    """情感分析器基类"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.load_keywords()

    def load_keywords(self):
        """加载情感关键词"""
        # 正面关键词
        self.positive_keywords = [
            "上涨", "大涨", "利好", "突破", "创新高", "强势",
            "增长", "盈利", "回购", "分红", "业绩增长", "超预期",
            "上涨", "飙升", "暴涨", "领涨", "强势", "反弹",
            "复苏", "企稳", "利好", "积极", "乐观"
        ]

        # 负面关键词
        self.negative_keywords = [
            "下跌", "大跌", "利空", "破位", "创新低", "弱势",
            "亏损", "减持", "停牌", "退市", "业绩下滑", "不及预期",
            "下跌", "暴跌", "跳水", "领跌", "弱势", "回调",
            "衰退", "下跌", "利空", "消极", "悲观", "风险",
            "减持", "质押", "违约", "欺诈", "调查", "处罚"
        ]

        # 行业/概念关键词映射到股票代码
        self.symbol_keywords = self.config.get("symbol_keywords", {})

        # 扩展自定义关键词
        if self.config.get("custom_positive_keywords"):
            self.positive_keywords.extend(self.config["custom_positive_keywords"])
        if self.config.get("custom_negative_keywords"):
            self.negative_keywords.extend(self.config["custom_negative_keywords"])
        if self.config.get("custom_symbol_keywords"):
            self.symbol_keywords.update(self.config["custom_symbol_keywords"])

    def analyze(self, text: str) -> Dict:
        """分析文本情感

        Args:
            text: 待分析文本

        Returns:
            分析结果字典:
            {
                "sentiment": float,      # 情感分数 (-1 ~ 1)
                "confidence": float,     # 置信度 (0 ~ 1)
                "sentiment_label": str,  # 标签 (正面/负面/中性)
                "keywords": list,        # 提取的关键词
            }
        """
        raise NotImplementedError

    def extract_keywords(self, text: str, top_k: int = 10) -> List[str]:
        """提取关键词"""
        if JIEBA_AVAILABLE:
            keywords = jieba.analyse.extract_tags(text, topK=top_k, withWeight=False)
            return keywords
        else:
            # 简单分词
            words = re.findall(r'[\u4e00-\u9fa5]{2,}', text)
            return words[:top_k]

    def extract_symbols(self, text: str, known_symbols: List[str] = None) -> List[str]:
        """从文本中提取相关交易品种"""
        relevant_symbols = []

        if known_symbols:
            # 直接匹配品种代码
            for symbol in known_symbols:
                if symbol in text:
                    relevant_symbols.append(symbol)

        # 通过关键词映射提取
        for keyword, symbols in self.symbol_keywords.items():
            if keyword in text:
                relevant_symbols.extend(symbols)

        # 提取股票代码（格式：600xxx, 000xxx, 300xxx, 688xxx等）
        stock_pattern = r'\b(600|000|002|300|301|601|603|605|688|430)\d{3}\b'
        stocks = re.findall(stock_pattern, text)
        relevant_symbols.extend(stocks)

        # 提取数字货币代码（BTC, ETH等）
        crypto_pattern = r'\b(BTC|ETH|BNB|SOL|ADA|DOGE|XRP|DOT|LINK|UNI)\b'
        cryptos = re.findall(crypto_pattern, text, re.IGNORECASE)
        relevant_symbols.extend([c.upper() for c in cryptos])

        return list(set(relevant_symbols))

    def generate_summary(self, title: str, content: str) -> str:
        """生成摘要"""
        # 简单摘要：取标题+前100字
        summary = title
        if content:
            summary = f"{title}\n{content[:100]}..."
        return summary


class KeywordSentimentAnalyzer(SentimentAnalyzer):
    """基于关键词的情感分析器"""

    def analyze(self, text: str) -> Dict:
        """基于关键词进行情感分析"""
        positive_count = 0
        negative_count = 0

        # 统计关键词出现次数
        for keyword in self.positive_keywords:
            count = text.count(keyword)
            if count > 0:
                positive_count += count

        for keyword in self.negative_keywords:
            count = text.count(keyword)
            if count > 0:
                negative_count += count

        # 计算情感分数
        total_count = positive_count + negative_count
        if total_count == 0:
            sentiment = 0.0
            sentiment_label = "中性"
            confidence = 0.3
        else:
            sentiment = (positive_count - negative_count) / (positive_count + negative_count + 1)
            confidence = min(0.5 + total_count * 0.1, 0.9)

            if sentiment > 0.3:
                sentiment_label = "正面"
            elif sentiment < -0.3:
                sentiment_label = "负面"
            else:
                sentiment_label = "中性"

        # 提取关键词
        keywords = self.extract_keywords(text, top_k=10)

        return {
            "sentiment": round(sentiment, 2),
            "confidence": round(confidence, 2),
            "sentiment_label": sentiment_label,
            "keywords": keywords,
        }


class SnowNLPSentimentAnalyzer(SentimentAnalyzer):
    """基于SnowNLP的情感分析器"""

    def analyze(self, text: str) -> Dict:
        """使用SnowNLP进行情感分析"""
        if not SNOWNLP_AVAILABLE:
            return KeywordSentimentAnalyzer(self.config).analyze(text)

        try:
            s = SnowNLP(text)
            sentiment = s.sentiments

            # SnowNLP返回0-1之间，映射到-1到1
            sentiment = (sentiment - 0.5) * 2

            if sentiment > 0.3:
                sentiment_label = "正面"
            elif sentiment < -0.3:
                sentiment_label = "负面"
            else:
                sentiment_label = "中性"

            confidence = abs(sentiment) * 0.5 + 0.5
            keywords = self.extract_keywords(text, top_k=10)

            return {
                "sentiment": round(sentiment, 2),
                "confidence": round(confidence, 2),
                "sentiment_label": sentiment_label,
                "keywords": keywords,
            }
        except Exception as e:
            print(f"SnowNLP分析失败: {e}")
            return KeywordSentimentAnalyzer(self.config).analyze(text)


class BERTSentimentAnalyzer(SentimentAnalyzer):
    """基于BERT的情感分析器"""

    def __init__(self, config: dict = None, model_name: str = "bert-base-chinese"):
        super().__init__(config)
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self._load_model()

    def _load_model(self):
        """加载BERT模型"""
        if not TRANSFORMERS_AVAILABLE:
            return

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self.model.eval()
        except Exception as e:
            print(f"加载BERT模型失败: {e}")
            self.model = None
            self.tokenizer = None

    def analyze(self, text: str) -> Dict:
        """使用BERT进行情感分析"""
        if not self.model or not self.tokenizer:
            return SnowNLPSentimentAnalyzer(self.config).analyze(text)

        try:
            # 截断文本到512token
            inputs = self.tokenizer(text[:512], return_tensors="pt", truncation=True)

            with torch.no_grad():
                outputs = self.model(**inputs)
                predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
                positive_score = predictions[0][1].item()  # 假设label 1是正面

            sentiment = (positive_score - 0.5) * 2

            if sentiment > 0.3:
                sentiment_label = "正面"
            elif sentiment < -0.3:
                sentiment_label = "负面"
            else:
                sentiment_label = "中性"

            confidence = abs(sentiment) * 0.5 + 0.5
            keywords = self.extract_keywords(text, top_k=10)

            return {
                "sentiment": round(sentiment, 2),
                "confidence": round(confidence, 2),
                "sentiment_label": sentiment_label,
                "keywords": keywords,
            }
        except Exception as e:
            print(f"BERT分析失败: {e}")
            return SnowNLPSentimentAnalyzer(self.config).analyze(text)


class NewsAnalyzer:
    """新闻分析器 - 综合分析新闻并生成交易信号"""

    def __init__(self, config: dict = None, analyzer_type: str = "snownlp"):
        """
        Args:
            config: 配置字典
            analyzer_type: 分析器类型 (keyword/snownlp/bert)
        """
        self.config = config or {}
        self.analyzer_type = analyzer_type

        # 选择情感分析器
        if analyzer_type == "bert":
            self.sentiment_analyzer = BERTSentimentAnalyzer(config)
        elif analyzer_type == "snownlp":
            self.sentiment_analyzer = SnowNLPSentimentAnalyzer(config)
        else:
            self.sentiment_analyzer = KeywordSentimentAnalyzer(config)

        # 配置
        self.sentiment_threshold = self.config.get("sentiment_threshold", 0.6)
        self.confidence_threshold = self.config.get("confidence_threshold", 0.7)
        self.known_symbols = self.config.get("known_symbols", [])

    def analyze_news(self, news_data: dict) -> dict:
        """分析新闻数据

        Args:
            news_data: 新闻数据字典

        Returns:
            分析结果字典
        """
        title = news_data.get("title", "")
        content = news_data.get("content", "")
        news_id = news_data.get("news_id", "")

        # 组合文本进行分析
        text = f"{title}\n{content}"

        # 情感分析
        sentiment_result = self.sentiment_analyzer.analyze(text)

        # 提取相关品种
        relevant_symbols = self.sentiment_analyzer.extract_symbols(text, self.known_symbols)

        # 生成交易信号
        trade_signal = "HOLD"
        target_symbols = []

        sentiment = sentiment_result["sentiment"]
        confidence = sentiment_result["confidence"]

        if (abs(sentiment) >= self.sentiment_threshold and
            confidence >= self.confidence_threshold):

            if sentiment > 0:
                trade_signal = "BUY"
                target_symbols = relevant_symbols
            elif sentiment < 0:
                trade_signal = "SELL"
                target_symbols = relevant_symbols

        # 生成摘要
        summary = self.sentiment_analyzer.generate_summary(title, content)

        return {
            "news_id": news_id,
            "sentiment": sentiment_result["sentiment"],
            "confidence": sentiment_result["confidence"],
            "sentiment_label": sentiment_result["sentiment_label"],
            "relevant_symbols": relevant_symbols,
            "keywords": sentiment_result["keywords"],
            "summary": summary,
            "trade_signal": trade_signal,
            "target_symbols": target_symbols,
            "analysis_time": datetime.now(),
        }


def get_analyzer(config: dict = None, analyzer_type: str = "snownlp") -> NewsAnalyzer:
    """获取新闻分析器实例

    Args:
        config: 配置字典
        analyzer_type: 分析器类型

    Returns:
        NewsAnalyzer实例
    """
    return NewsAnalyzer(config, analyzer_type)
