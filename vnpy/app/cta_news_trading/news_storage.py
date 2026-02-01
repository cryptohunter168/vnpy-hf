"""
新闻存储管理模块
使用 SQLite 存储新闻缓存和分析结果
"""

import sqlite3
import json
from typing import List, Optional
from datetime import datetime
from contextlib import contextmanager

from .config import NewsProcessingMode


def _json_serializer(obj):
    """JSON 序列化器，处理 datetime 等特殊类型"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class NewsDatabase:
    """新闻数据库管理器"""

    def __init__(self, db_path: str = "vnpy_news_trading.db"):
        """
        Args:
            db_path: SQLite 数据库文件路径
        """
        self.db_path = db_path
        self.conn = None

        # 初始化数据库
        self._connect()
        self._create_tables()
        self._create_indexes()

    def _connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        # 使用行工厂，返回字典格式
        self.conn.row_factory = sqlite3.Row

    @contextmanager
    def get_cursor(self):
        """获取数据库游标（上下文管理器）"""
        cursor = self.conn.cursor()
        try:
            yield cursor
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e

    def _create_tables(self):
        """创建表"""
        with self.get_cursor() as cursor:
            # 增量模式新闻表（24小时过期）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS incremental_news (
                    news_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT,
                    source TEXT,
                    url TEXT,
                    news_time TIMESTAMP,
                    added_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    rank_info TEXT,  -- JSON 格式
                    raw_data TEXT    -- JSON 格式，存储原始数据
                )
            """)

            # 当前榜单模式新闻表（7天过期）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS current_rank_news (
                    news_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT,
                    source TEXT,
                    url TEXT,
                    news_time TIMESTAMP,
                    added_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    rank_info TEXT,
                    raw_data TEXT
                )
            """)

            # 当日汇总模式新闻表（30天过期）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_summary_news (
                    news_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT,
                    source TEXT,
                    url TEXT,
                    news_time TIMESTAMP,
                    added_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    rank_info TEXT,
                    raw_data TEXT
                )
            """)

            # 分析历史表（不过期）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    news_id TEXT NOT NULL,
                    sentiment REAL NOT NULL,
                    confidence REAL NOT NULL,
                    sentiment_label TEXT NOT NULL,
                    relevant_symbols TEXT,  -- JSON 数组
                    keywords TEXT,          -- JSON 数组
                    trade_signal TEXT NOT NULL,
                    target_symbols TEXT,    -- JSON 数组
                    analysis_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    raw_analysis TEXT       -- JSON 格式
                )
            """)

    def _create_indexes(self):
        """创建索引"""
        with self.get_cursor() as cursor:
            # 时间索引（用于查询和过期清理）
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_incremental_added_time
                ON incremental_news(added_time)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_current_rank_added_time
                ON current_rank_news(added_time)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_summary_added_time
                ON daily_summary_news(added_time)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analysis_time
                ON analysis_history(analysis_time DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analysis_news_id
                ON analysis_history(news_id)
            """)

    def cleanup_expired(self):
        """清理过期数据"""
        with self.get_cursor() as cursor:
            # 增量模式：24小时
            cursor.execute("""
                DELETE FROM incremental_news
                WHERE datetime(added_time) < datetime('now', '-24 hours')
            """)

            # 榜单模式：7天
            cursor.execute("""
                DELETE FROM current_rank_news
                WHERE datetime(added_time) < datetime('now', '-7 days')
            """)

            # 汇总模式：30天
            cursor.execute("""
                DELETE FROM daily_summary_news
                WHERE datetime(added_time) < datetime('now', '-30 days')
            """)

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()


class NewsStorage:
    """新闻存储管理器"""

    def __init__(self, db: NewsDatabase):
        self.db = db

    def add_news(self, mode: NewsProcessingMode, news_data: dict) -> bool:
        """添加新闻到数据库

        Args:
            mode: 处理模式
            news_data: 新闻数据

        Returns:
            是否新增（False表示已存在）
        """
        table_name = self._get_table_name(mode)
        news_id = news_data.get("news_id")

        if not news_id:
            return False

        try:
            with self.db.get_cursor() as cursor:
                cursor.execute(f"""
                    INSERT INTO {table_name}
                    (news_id, title, content, source, url, news_time, rank_info, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    news_id,
                    news_data.get("title", ""),
                    news_data.get("content", ""),
                    news_data.get("source", ""),
                    news_data.get("url", ""),
                    news_data.get("news_time"),
                    json.dumps(news_data.get("rank_info", {}), ensure_ascii=False, default=_json_serializer),
                    json.dumps(news_data, ensure_ascii=False, default=_json_serializer)
                ))
                return True
        except sqlite3.IntegrityError:
            # 主键冲突，已存在
            return False
        except Exception as e:
            print(f"插入新闻失败: {e}")
            return False

    def get_news_by_mode(self, mode: NewsProcessingMode,
                        limit: int = None,
                        start_time: datetime = None,
                        end_time: datetime = None) -> List[dict]:
        """获取指定模式的新闻

        Args:
            mode: 处理模式
            limit: 最大返回数量
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            新闻列表
        """
        table_name = self._get_table_name(mode)

        query = f"SELECT * FROM {table_name}"
        params = []

        # 时间过滤
        conditions = []
        if start_time:
            conditions.append("datetime(added_time) >= ?")
            params.append(start_time.strftime("%Y-%m-%d %H:%M:%S"))
        if end_time:
            conditions.append("datetime(added_time) <= ?")
            params.append(end_time.strftime("%Y-%m-%d %H:%M:%S"))

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY added_time DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with self.db.get_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        # 转换为字典列表
        results = []
        for row in rows:
            news_dict = dict(row)
            # 解析 JSON 字段
            if news_dict.get("rank_info"):
                news_dict["rank_info"] = json.loads(news_dict["rank_info"])
            if news_dict.get("raw_data"):
                news_dict["raw_data"] = json.loads(news_dict["raw_data"])
            results.append(news_dict)

        return results

    def get_news_by_id(self, news_id: str) -> Optional[dict]:
        """根据新闻ID获取新闻（跨模式查询）"""
        tables = ["incremental_news", "current_rank_news", "daily_summary_news"]

        for table in tables:
            with self.db.get_cursor() as cursor:
                cursor.execute(f"""
                    SELECT * FROM {table} WHERE news_id = ?
                """, (news_id,))
                row = cursor.fetchone()

                if row:
                    news_dict = dict(row)
                    # 解析 JSON 字段
                    if news_dict.get("rank_info"):
                        news_dict["rank_info"] = json.loads(news_dict["rank_info"])
                    if news_dict.get("raw_data"):
                        news_dict["raw_data"] = json.loads(news_dict["raw_data"])
                    return news_dict

        return None

    def clear_mode(self, mode: NewsProcessingMode):
        """清空指定模式的新闻"""
        table_name = self._get_table_name(mode)

        with self.db.get_cursor() as cursor:
            cursor.execute(f"DELETE FROM {table_name}")

    def _get_table_name(self, mode: NewsProcessingMode) -> str:
        """获取模式对应的表名"""
        if mode == NewsProcessingMode.INCREMENTAL:
            return "incremental_news"
        elif mode == NewsProcessingMode.CURRENT_RANK:
            return "current_rank_news"
        elif mode == NewsProcessingMode.DAILY_SUMMARY:
            return "daily_summary_news"
        else:
            raise ValueError(f"未知的处理模式: {mode}")


class AnalysisStorage:
    """分析结果存储管理器"""

    def __init__(self, db: NewsDatabase):
        self.db = db

    def save_analysis(self, analysis_result: dict) -> bool:
        """保存分析结果"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO analysis_history
                    (news_id, sentiment, confidence, sentiment_label,
                     relevant_symbols, keywords, trade_signal, target_symbols, raw_analysis)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    analysis_result.get("news_id"),
                    analysis_result.get("sentiment"),
                    analysis_result.get("confidence"),
                    analysis_result.get("sentiment_label"),
                    json.dumps(analysis_result.get("relevant_symbols", []), ensure_ascii=False),
                    json.dumps(analysis_result.get("keywords", []), ensure_ascii=False),
                    analysis_result.get("trade_signal"),
                    json.dumps(analysis_result.get("target_symbols", []), ensure_ascii=False),
                    json.dumps(analysis_result, ensure_ascii=False, default=_json_serializer)
                ))
                return True
        except Exception as e:
            print(f"保存分析结果失败: {e}")
            return False

    def get_analysis_history(self, news_id: str = None,
                           start_time: datetime = None,
                           end_time: datetime = None,
                           limit: int = 100) -> List[dict]:
        """获取分析历史"""
        query = "SELECT * FROM analysis_history"
        params = []

        conditions = []
        if news_id:
            conditions.append("news_id = ?")
            params.append(news_id)
        if start_time:
            conditions.append("datetime(analysis_time) >= ?")
            params.append(start_time.strftime("%Y-%m-%d %H:%M:%S"))
        if end_time:
            conditions.append("datetime(analysis_time) <= ?")
            params.append(end_time.strftime("%Y-%m-%d %H:%M:%S"))

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY analysis_time DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with self.db.get_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        results = []
        for row in rows:
            result_dict = dict(row)
            # 解析 JSON 字段
            for json_field in ["relevant_symbols", "keywords", "target_symbols", "raw_analysis"]:
                if result_dict.get(json_field):
                    result_dict[json_field] = json.loads(result_dict[json_field])
            results.append(result_dict)

        return results

    def get_statistics(self, start_time: datetime = None,
                      end_time: datetime = None) -> dict:
        """获取统计分析"""
        query = """
            SELECT
                COUNT(*) as total_count,
                SUM(CASE WHEN sentiment > 0 THEN 1 ELSE 0 END) as positive_count,
                SUM(CASE WHEN sentiment < 0 THEN 1 ELSE 0 END) as negative_count,
                SUM(CASE WHEN sentiment = 0 THEN 1 ELSE 0 END) as neutral_count,
                AVG(sentiment) as avg_sentiment,
                SUM(CASE WHEN trade_signal = 'BUY' THEN 1 ELSE 0 END) as buy_signals,
                SUM(CASE WHEN trade_signal = 'SELL' THEN 1 ELSE 0 END) as sell_signals
            FROM analysis_history
        """
        params = []

        # 时间过滤
        if start_time or end_time:
            conditions = []
            if start_time:
                conditions.append("datetime(analysis_time) >= ?")
                params.append(start_time.strftime("%Y-%m-%d %H:%M:%S"))
            if end_time:
                conditions.append("datetime(analysis_time) <= ?")
                params.append(end_time.strftime("%Y-%m-%d %H:%M:%S"))

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        with self.db.get_cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()

        if row:
            return dict(row)
        else:
            return {
                "total_count": 0,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "avg_sentiment": 0,
                "buy_signals": 0,
                "sell_signals": 0
            }


class StorageManager:
    """统一的存储管理器"""

    def __init__(self, db_path: str = "vnpy_news_trading.db"):
        self.database = NewsDatabase(db_path)
        self.news_storage = NewsStorage(self.database)
        self.analysis_storage = AnalysisStorage(self.database)

    def close(self):
        """关闭连接"""
        self.database.close()

    @classmethod
    def from_config(cls, config: dict) -> "StorageManager":
        """从配置创建管理器"""
        return cls(
            db_path=config.get("db_path", "vnpy_news_trading.db")
        )
