# 新闻驱动交易策略 - 测试运行指南

## 📋 目录
1. [快速开始](#快速开始)
2. [三种模式测试](#三种模式测试)
3. [数据库查看](#数据库查看)
4. [常见问题](#常见问题)
5. [调试技巧](#调试技巧)

---

## 🚀 快速开始

### 方式一：使用新的测试脚本（推荐）

```bash
# 1. 进入项目目录
cd e:\Project\vnpy-hf

# 2. 运行增量模式测试
python run_news_strategy_test.py incremental

# 3. 运行榜单模式测试
python run_news_strategy_test.py current_rank

# 4. 运行汇总模式测试
python run_news_strategy_test.py daily_summary
```

### 方式二：使用原始脚本

```bash
python -m vnpy.app.news_trading.run_manual
```

### 方式三：Python 交互式运行

```bash
python
```

然后在 Python 交互环境中：

```python
from vnpy.app.news_trading.run_manual import run_manual_mode
run_manual_mode()
```

---

## 🧪 三种模式测试

### 1️⃣ 增量模式测试

**特点**：
- ✅ 实时接收新闻立即分析
- ✅ 关键词匹配
- ✅ 数据保留24小时

**运行命令**：
```bash
python run_news_strategy_test.py incremental
```

**预期输出**：
```
================================================================================
新闻驱动交易策略 - INCREMENTAL 模式测试
================================================================================

[1/8] 创建事件引擎...
[2/8] 创建主引擎...
[3/8] 添加Binance交易网关...
    ✓ Binance网关已添加
[4/8] 添加CTA策略应用...
[5/8] 配置新闻网关...
    ✓ 新闻网关已启动
[6/8] 初始化CTA引擎...
[7/8] 添加策略（incremental模式）...
    ✓ 策略已添加: news_strategy_incremental
[8/8] 启动策略...

================================================================================
✓ 系统已启动 - INCREMENTAL 模式
================================================================================
数据库文件: vnpy_news_trading_incremental.db
模式说明:
  • 实时接收新闻
  • 关键词匹配立即分析
  • 数据保留24小时
================================================================================

按 Ctrl+C 停止系统
```

### 2️⃣ 榜单模式测试

**特点**：
- ✅ 实时接收新闻立即分析
- ✅ 榜单匹配 + 排名过滤
- ✅ 数据保留7天

**运行命令**：
```bash
python run_news_strategy_test.py current_rank
```

### 3️⃣ 汇总模式测试

**特点**：
- ✅ 收集匹配的新闻
- ✅ 定时批量分析 (09:00, 15:00, 21:00)
- ✅ 数据保留30天

**运行命令**：
```bash
python run_news_strategy_test.py daily_summary
```

**注意**：汇总模式需要等待到达预设时间点才会批量分析，您可以修改 `summary_schedule_times` 为当前时间附近的时间进行测试。

---

## 💾 数据库查看

### 使用命令行查看

```bash
# 查看增量模式数据库
sqlite3 vnpy_news_trading_incremental.db

# SQLite 命令
.tables                    # 查看所有表
.schema incremental_news   # 查看表结构
SELECT * FROM incremental_news LIMIT 10;  # 查看前10条新闻
SELECT * FROM analysis_history ORDER BY analysis_time DESC LIMIT 10;  # 查看最近分析

# 退出
.quit
```

### 使用 Python 脚本查看

创建 `view_database.py`：

```python
"""查看新闻交易数据库"""
import sqlite3
import json

def view_database(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"\n{'='*80}")
    print(f"数据库: {db_path}")
    print(f"{'='*80}\n")

    # 查看表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("数据表:")
    for table in tables:
        print(f"  • {table[0]}")

    # 查看新闻数量
    print("\n新闻统计:")
    for table in tables:
        table_name = table[0]
        if table_name != 'analysis_history':
            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  • {table_name}: {count} 条")

    # 查看分析历史
    cursor.execute("SELECT COUNT(*) as count FROM analysis_history")
    analysis_count = cursor.fetchone()[0]
    print(f"  • analysis_history: {analysis_count} 条")

    # 查看最近的新闻
    if tables:
        first_table = tables[0][0]
        if first_table != 'analysis_history':
            print(f"\n最近5条新闻 ({first_table}):")
            cursor.execute(f"SELECT * FROM {first_table} ORDER BY added_time DESC LIMIT 5")
            rows = cursor.fetchall()
            for row in rows:
                print(f"  • {row['title'][:60]}...")
                print(f"    时间: {row['added_time']}, 来源: {row['source']}")

    # 查看统计分析
    print("\n分析统计:")
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN sentiment > 0 THEN 1 ELSE 0 END) as positive,
            SUM(CASE WHEN sentiment < 0 THEN 1 ELSE 0 END) as negative,
            AVG(sentiment) as avg_sentiment
        FROM analysis_history
    """)
    stats = cursor.fetchone()
    if stats[0] > 0:
        print(f"  • 总数: {stats[0]}")
        print(f"  • 正面: {stats[1]}")
        print(f"  • 负面: {stats[2]}")
        print(f"  • 平均情感: {stats[3]:.2f}")
    else:
        print("  暂无分析数据")

    print(f"\n{'='*80}\n")
    conn.close()

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "vnpy_news_trading_incremental.db"

    view_database(db_path)
```

运行：
```bash
python view_database.py vnpy_news_trading_incremental.db
```

### 使用图形界面工具

推荐工具：
- **DB Browser for SQLite**: https://sqlitebrowser.org/
  下载安装后直接打开 `.db` 文件即可查看

---

## ❓ 常见问题

### Q1: 运行时提示模块找不到

**错误**：
```
ModuleNotFoundError: No module named 'vnpy'
```

**解决**：
```bash
# 确保在项目根目录
cd e:\Project\vnpy-hf

# 安装项目（开发模式）
pip install -e .
```

### Q2: 数据库文件创建失败

**错误**：
```
sqlite3.OperationalError: unable to open database file
```

**解决**：
```bash
# 检查目录权限
ls -la

# 使用绝对路径
python run_news_strategy_test.py incremental
```

### Q3: 策略启动后没有反应

**可能原因**：
1. 没有配置新闻源
2. 新闻网关未启动
3. 模拟新闻源未发送新闻

**解决**：
```python
# 在 run_news_strategy_test.py 中添加测试新闻
from vnpy.event import Event
from vnpy.trader.event import EVENT_NEWS

# 发送测试新闻
test_news = {
    "news_id": "test_001",
    "title": "比特币价格突破50000美元",
    "content": "比特币今日价格突破50000美元大关，市场情绪高涨",
    "source": "测试来源",
    "url": "https://test.com/news/001",
    "news_time": datetime.now()
}
event = Event(EVENT_NEWS, test_news)
event_engine.put(event)
```

### Q4: 汇总模式不触发

**原因**：汇总模式只在设定的时间点触发

**解决**：
```python
# 修改为当前时间+1分钟
from datetime import datetime, timedelta
now = datetime.now()
next_time = (now + timedelta(minutes=1)).strftime("%H:%M")

setting = {
    # ...
    "summary_schedule_times": f"09:00,15:00,{next_time}",  # 添加当前时间+1分钟
}
```

---

## 🐛 调试技巧

### 1. 启用详细日志

```python
import logging

# 在脚本开头添加
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('news_strategy_debug.log'),
        logging.StreamHandler()
    ]
)
```

### 2. 查看策略状态

```python
# 获取策略实例
strategy = cta_engine.strategies["news_strategy_incremental"]

# 查看配置
print(f"模式: {strategy.news_processing_mode}")
print(f"数据库: {strategy.db_path}")
print(f"匹配器: {strategy.matcher.__class__.__name__}")
```

### 3. 手动触发新闻事件

```python
from vnpy.trader.event import EVENT_NEWS
from vnpy.event import Event
from datetime import datetime

# 创建测试新闻
test_news = {
    "news_id": "manual_test_001",
    "title": "测试新闻：BTC大涨",
    "content": "比特币价格大幅上涨，突破关键阻力位",
    "source": "手动测试",
    "url": "",
    "news_time": datetime.now()
}

# 发送事件
event = Event(EVENT_NEWS, test_news)
event_engine.put(event)
print("✓ 测试新闻已发送")
```

### 4. 查看数据库内容

```python
import sqlite3

conn = sqlite3.connect("vnpy_news_trading_incremental.db")
cursor = conn.cursor()

# 查看所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("数据表:", [row[0] for row in cursor.fetchall()])

# 查看新闻数量
cursor.execute("SELECT COUNT(*) FROM incremental_news")
print("增量新闻数:", cursor.fetchone()[0])

# 查看分析历史
cursor.execute("SELECT COUNT(*) FROM analysis_history")
print("分析记录数:", cursor.fetchone()[0])

conn.close()
```

---

## 📊 性能监控

### 监控脚本

创建 `monitor.py`：

```python
"""监控新闻策略运行状态"""
import sqlite3
import time
from datetime import datetime

def monitor_database(db_path: str, interval: int = 5):
    """监控数据库变化

    Args:
        db_path: 数据库路径
        interval: 检查间隔（秒）
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    last_count = 0

    try:
        while True:
            # 检查新闻数量
            cursor.execute("SELECT COUNT(*) FROM incremental_news")
            current_count = cursor.fetchone()[0]

            if current_count > last_count:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 新增新闻!")
                print(f"  总数: {last_count} → {current_count}")

                # 显示最新新闻
                cursor.execute("""
                    SELECT title, source, added_time
                    FROM incremental_news
                    ORDER BY added_time DESC
                    LIMIT 1
                """)
                row = cursor.fetchone()
                if row:
                    print(f"  标题: {row[0]}")
                    print(f"  来源: {row[1]}")
                    print(f"  时间: {row[2]}")

                last_count = current_count

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n监控停止")
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "vnpy_news_trading_incremental.db"
    monitor_database(db_path)
```

运行：
```bash
# 终端1：运行策略
python run_news_strategy_test.py incremental

# 终端2：监控数据库
python monitor.py vnpy_news_trading_incremental.db
```

---

## ✅ 测试清单

运行测试后，确认以下功能正常：

### 基础功能
- [ ] 策略成功启动
- [ ] 数据库文件成功创建
- [ ] 数据库表结构正确（4个表）
- [ ] 日志输出正常

### 增量模式
- [ ] 接收新闻立即分析
- [ ] 关键词匹配生效
- [ ] 去重功能正常
- [ ] 数据保存到数据库

### 榜单模式
- [ ] 榜单匹配功能
- [ ] 排名过滤生效
- [ ] 平台过滤生效

### 汇总模式
- [ ] 新闻收集功能
- [ ] 定时触发功能
- [ ] 批量分析功能
- [ ] 缓存清空功能

### 数据持久化
- [ ] 新闻保存到对应表
- [ ] 分析历史保存
- [ ] 统计查询功能

---

## 🎯 下一步

测试通过后，您可以：

1. **连接真实新闻源**：修改 `news_config` 配置真实的 RSS/API 源
2. **配置飞书推送**：填写真实的 `lark_app_id` 和 `lark_app_secret`
3. **连接交易接口**：配置 Binance API 进行实际交易
4. **调整策略参数**：根据实际效果优化关键词和阈值
5. **添加风控规则**：在 `execution_engine.py` 中添加自定义风控逻辑

---

**祝您测试顺利！** 🎉
