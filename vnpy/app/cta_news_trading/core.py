# coding=utf-8
"""
TrendRadar - 热点新闻监控与分析工具

模块结构：
1. 导入和常量定义
2. 配置管理
3. 工具函数
4. 推送记录管理
5. 数据获取
6. 数据处理与解析
7. 统计与分析
8. 报告生成
9. Webhook 通知
10. 主分析器
"""

# ============================================================================
# 第一部分：导入和常量定义
# ============================================================================

# 标准库
import json
import os
import random
import re
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union

# 第三方库
import pytz
import requests
import yaml

# 版本号
VERSION = "2.1.0"


# ============================================================================
# 第二部分：配置管理
# ============================================================================

def _build_silent_push_config(notification_config: Dict) -> Dict:
    """构建静默推送配置"""
    silent_push = notification_config.get("silent_push", {})
    time_range = silent_push.get("time_range", {})

    return {
        "ENABLED": silent_push.get("enabled", False),
        "TIME_RANGE": {
            "START": time_range.get("start", "08:00"),
            "END": time_range.get("end", "22:00"),
        },
        "MAX_PUSH_COUNT": silent_push.get("max_push_count", 0),
        "RECORD_RETENTION_DAYS": silent_push.get("push_record_retention_days", 7),
    }


def _build_webhook_config(notification_config: Dict) -> Dict:
    """构建 Webhook 配置，环境变量优先"""
    webhooks = notification_config.get("webhooks", {})

    config = {
        "FEISHU_WEBHOOK_URL": (
            os.environ.get("FEISHU_WEBHOOK_URL", "").strip()
            or webhooks.get("feishu_url", "")
        ),
        "DINGTALK_WEBHOOK_URL": (
            os.environ.get("DINGTALK_WEBHOOK_URL", "").strip()
            or webhooks.get("dingtalk_url", "")
        ),
        "WEWORK_WEBHOOK_URL": (
            os.environ.get("WEWORK_WEBHOOK_URL", "").strip()
            or webhooks.get("wework_url", "")
        ),
        "TELEGRAM_BOT_TOKEN": (
            os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
            or webhooks.get("telegram_bot_token", "")
        ),
        "TELEGRAM_CHAT_ID": (
            os.environ.get("TELEGRAM_CHAT_ID", "").strip()
            or webhooks.get("telegram_chat_id", "")
        ),
    }

    return config


def _print_webhook_sources(config: Dict) -> None:
    """输出 Webhook 配置来源信息"""
    webhook_sources = []

    webhook_mappings = [
        ("FEISHU_WEBHOOK_URL", "FEISHU_WEBHOOK_URL", "飞书"),
        ("DINGTALK_WEBHOOK_URL", "DINGTALK_WEBHOOK_URL", "钉钉"),
        ("WEWORK_WEBHOOK_URL", "WEWORK_WEBHOOK_URL", "企业微信"),
    ]

    for config_key, env_key, name in webhook_mappings:
        if config[config_key]:
            source = "环境变量" if os.environ.get(env_key) else "配置文件"
            webhook_sources.append(f"{name}({source})")

    # Telegram 特殊处理
    if config["TELEGRAM_BOT_TOKEN"] and config["TELEGRAM_CHAT_ID"]:
        token_source = "环境变量" if os.environ.get("TELEGRAM_BOT_TOKEN") else "配置文件"
        chat_source = "环境变量" if os.environ.get("TELEGRAM_CHAT_ID") else "配置文件"
        webhook_sources.append(f"Telegram({token_source}/{chat_source})")

    if webhook_sources:
        print(f"Webhook 配置来源: {', '.join(webhook_sources)}")
    else:
        print("未配置任何 Webhook")


def load_config() -> Dict:
    """加载配置文件"""
    config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")

    if not Path(config_path).exists():
        raise FileNotFoundError(f"配置文件 {config_path} 不存在")

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    print(f"配置文件加载成功: {config_path}")

    notification = config_data.get("notification", {})

    # 构建主配置
    config = {
        # 应用配置
        "VERSION_CHECK_URL": config_data["app"]["version_check_url"],
        "SHOW_VERSION_UPDATE": config_data["app"]["show_version_update"],

        # 爬虫配置
        "REQUEST_INTERVAL": config_data["crawler"]["request_interval"],
        "USE_PROXY": config_data["crawler"]["use_proxy"],
        "DEFAULT_PROXY": config_data["crawler"]["default_proxy"],
        "ENABLE_CRAWLER": config_data["crawler"]["enable_crawler"],

        # 报告配置
        "REPORT_MODE": config_data["report"]["mode"],
        "RANK_THRESHOLD": config_data["report"]["rank_threshold"],

        # 通知配置
        "ENABLE_NOTIFICATION": notification["enable_notification"],
        "MESSAGE_BATCH_SIZE": notification["message_batch_size"],
        "BATCH_SEND_INTERVAL": notification["batch_send_interval"],
        "FEISHU_MESSAGE_SEPARATOR": notification["feishu_message_separator"],
        "SILENT_PUSH": _build_silent_push_config(notification),

        # 权重配置
        "WEIGHT_CONFIG": {
            "RANK_WEIGHT": config_data["weight"]["rank_weight"],
            "FREQUENCY_WEIGHT": config_data["weight"]["frequency_weight"],
            "HOTNESS_WEIGHT": config_data["weight"]["hotness_weight"],
        },

        # 平台配置
        "PLATFORMS": config_data["platforms"],

        # 情绪分析配置
        "SENTIMENT_ANALYSIS": config_data.get("sentiment_analysis", {
            "enabled": False,
            "api_base": "https://api.deepseek.com/v1",
            "api_key": "",
            "model": "deepseek-chat",
            "max_news_per_batch": 10,
            "cache_hours": 24,
        }),

        # 股票分析配置
        "STOCK_ANALYSIS": config_data.get("stock_analysis", {
            "enabled": False,
            "config_file": "config/stock_keywords.yaml",
        }),
    }

    # 添加 Webhook 配置
    webhook_config = _build_webhook_config(notification)
    config.update(webhook_config)

    # 输出配置来源
    _print_webhook_sources(config)

    return config


# 加载全局配置
print("正在加载配置...")
CONFIG = load_config()
print(f"TrendRadar v{VERSION} 配置加载完成")
print(f"监控平台数量: {len(CONFIG['PLATFORMS'])}")


# ============================================================================
# 第三部分：工具函数
# ============================================================================

def get_beijing_time() -> datetime:
    """获取北京时间"""
    return datetime.now(pytz.timezone("Asia/Shanghai"))


def format_date_folder() -> str:
    """格式化日期文件夹名称"""
    return get_beijing_time().strftime("%Y年%m月%d日")


def format_time_filename() -> str:
    """格式化时间文件名"""
    return get_beijing_time().strftime("%H时%M分")


def clean_title(title: str) -> str:
    """清理标题中的特殊字符"""
    if not isinstance(title, str):
        title = str(title)
    cleaned = title.replace("\n", " ").replace("\r", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def ensure_directory_exists(directory: str) -> None:
    """确保目录存在"""
    Path(directory).mkdir(parents=True, exist_ok=True)


def get_output_path(subfolder: str, filename: str) -> str:
    """获取输出路径"""
    date_folder = format_date_folder()
    output_dir = Path("output") / date_folder / subfolder
    ensure_directory_exists(str(output_dir))
    return str(output_dir / filename)


def html_escape(text: str) -> str:
    """HTML 转义"""
    if not isinstance(text, str):
        text = str(text)

    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def is_first_crawl_today() -> bool:
    """检测是否是当天第一次爬取"""
    date_folder = format_date_folder()
    txt_dir = Path("output") / date_folder / "txt"

    if not txt_dir.exists():
        return True

    files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])
    return len(files) <= 1


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """解析版本号字符串"""
    try:
        parts = version_str.strip().split(".")
        if len(parts) != 3:
            raise ValueError("版本号格式不正确")
        return int(parts[0]), int(parts[1]), int(parts[2])
    except Exception:
        return 0, 0, 0


def check_version_update(
    current_version: str,
    version_url: str,
    proxy_url: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """检查版本更新"""
    try:
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/plain, */*",
            "Cache-Control": "no-cache",
        }

        response = requests.get(
            version_url, proxies=proxies, headers=headers, timeout=10
        )
        response.raise_for_status()

        remote_version = response.text.strip()
        print(f"当前版本: {current_version}, 远程版本: {remote_version}")

        current_tuple = parse_version(current_version)
        remote_tuple = parse_version(remote_version)

        need_update = current_tuple < remote_tuple
        return need_update, remote_version if need_update else None

    except Exception as e:
        print(f"版本检查失败: {e}")
        return False, None


# ============================================================================
# 第四部分：推送记录管理
# ============================================================================

class PushRecordManager:
    """推送记录管理器 - 管理每日推送状态和记录清理"""

    def __init__(self):
        self.record_dir = Path("output") / ".push_records"
        self._ensure_record_dir()
        self._cleanup_old_records()

    def _ensure_record_dir(self) -> None:
        """确保记录目录存在"""
        self.record_dir.mkdir(parents=True, exist_ok=True)

    def _get_today_record_file(self) -> Path:
        """获取今天的记录文件路径"""
        today = get_beijing_time().strftime("%Y%m%d")
        return self.record_dir / f"push_record_{today}.json"

    def _cleanup_old_records(self) -> None:
        """清理过期的推送记录"""
        retention_days = CONFIG["SILENT_PUSH"]["RECORD_RETENTION_DAYS"]
        current_time = get_beijing_time()

        for record_file in self.record_dir.glob("push_record_*.json"):
            try:
                date_str = record_file.stem.replace("push_record_", "")
                file_date = datetime.strptime(date_str, "%Y%m%d")
                file_date = pytz.timezone("Asia/Shanghai").localize(file_date)

                if (current_time - file_date).days > retention_days:
                    record_file.unlink()
                    print(f"清理过期推送记录: {record_file.name}")
            except Exception as e:
                print(f"清理记录文件失败 {record_file}: {e}")

    def get_push_count(self) -> int:
        """获取今天的推送次数"""
        record_file = self._get_today_record_file()

        if not record_file.exists():
            return 0

        try:
            with open(record_file, "r", encoding="utf-8") as f:
                record = json.load(f)
            return record.get("push_count", 0)
        except Exception as e:
            print(f"读取推送记录失败: {e}")
            return 0

    def can_push(self, max_count: int) -> bool:
        """检查是否可以推送（未达到最大次数限制）"""
        if max_count <= 0:
            return True  # 0 表示不限制
        return self.get_push_count() < max_count

    def record_push(self, report_type: str) -> None:
        """记录推送"""
        record_file = self._get_today_record_file()
        now = get_beijing_time()

        # 读取现有记录
        current_count = self.get_push_count()
        push_history = []

        if record_file.exists():
            try:
                with open(record_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                push_history = existing.get("push_history", [])
            except Exception:
                pass

        # 添加新的推送记录
        push_history.append({
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "report_type": report_type,
        })

        record = {
            "push_count": current_count + 1,
            "last_push_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "push_history": push_history,
        }

        try:
            with open(record_file, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
            print(f"推送记录已保存: {report_type} at {now.strftime('%H:%M:%S')} (第 {current_count + 1} 次)")
        except Exception as e:
            print(f"保存推送记录失败: {e}")

    def is_in_time_range(self, start_time: str, end_time: str) -> bool:
        """检查当前时间是否在指定时间范围内"""
        current_time = get_beijing_time().strftime("%H:%M")
        return start_time <= current_time <= end_time


# ============================================================================
# 第五部分：数据获取
# ============================================================================

class DataFetcher:
    """数据获取器 - 负责从 API 获取热点数据"""

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }

    API_BASE_URL = "https://newsnow.busiyi.world/api/s"

    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url
        self.proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    def fetch_data(
        self,
        id_info: Union[str, Tuple[str, str]],
        max_retries: int = 2,
        min_retry_wait: int = 3,
        max_retry_wait: int = 5,
    ) -> Tuple[Optional[str], str, str]:
        """获取指定 ID 数据，支持重试"""
        id_value, alias = self._parse_id_info(id_info)
        url = f"{self.API_BASE_URL}?id={id_value}&latest"

        for retry in range(max_retries + 1):
            try:
                response = requests.get(
                    url,
                    proxies=self.proxies,
                    headers=self.DEFAULT_HEADERS,
                    timeout=10
                )
                response.raise_for_status()

                data = json.loads(response.text)
                status = data.get("status", "未知")

                if status not in ["success", "cache"]:
                    raise ValueError(f"响应状态异常: {status}")

                status_info = "最新数据" if status == "success" else "缓存数据"
                print(f"获取 {id_value} 成功（{status_info}）")
                return response.text, id_value, alias

            except Exception as e:
                if retry < max_retries:
                    wait_time = self._calculate_retry_wait(
                        retry, min_retry_wait, max_retry_wait
                    )
                    print(f"请求 {id_value} 失败: {e}. {wait_time:.2f}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"请求 {id_value} 失败: {e}")
                    return None, id_value, alias

        return None, id_value, alias

    def crawl_websites(
        self,
        ids_list: List[Union[str, Tuple[str, str]]],
        request_interval: int = CONFIG["REQUEST_INTERVAL"],
    ) -> Tuple[Dict, Dict, List]:
        """爬取多个网站数据"""
        results = {}
        id_to_name = {}
        failed_ids = []

        for i, id_info in enumerate(ids_list):
            id_value, name = self._parse_id_info(id_info)
            id_to_name[id_value] = name

            response, _, _ = self.fetch_data(id_info)

            if response:
                self._process_response(response, id_value, results, failed_ids)
            else:
                failed_ids.append(id_value)

            # 请求间隔
            if i < len(ids_list) - 1:
                self._wait_between_requests(request_interval)

        print(f"成功: {list(results.keys())}, 失败: {failed_ids}")
        return results, id_to_name, failed_ids

    @staticmethod
    def _parse_id_info(id_info: Union[str, Tuple[str, str]]) -> Tuple[str, str]:
        """解析 ID 信息"""
        if isinstance(id_info, tuple):
            return id_info[0], id_info[1]
        return id_info, id_info

    @staticmethod
    def _calculate_retry_wait(retry: int, min_wait: int, max_wait: int) -> float:
        """计算重试等待时间"""
        base_wait = random.uniform(min_wait, max_wait)
        additional_wait = retry * random.uniform(1, 2)
        return base_wait + additional_wait

    @staticmethod
    def _wait_between_requests(interval: int) -> None:
        """请求间等待"""
        actual_interval = interval + random.randint(-10, 20)
        actual_interval = max(50, actual_interval)
        time.sleep(actual_interval / 1000)

    def _process_response(
        self,
        response: str,
        id_value: str,
        results: Dict,
        failed_ids: List
    ) -> None:
        """处理 API 响应"""
        try:
            data = json.loads(response)
            results[id_value] = {}

            for index, item in enumerate(data.get("items", []), 1):
                title = item["title"]
                url = item.get("url", "")
                mobile_url = item.get("mobileUrl", "")

                if title in results[id_value]:
                    results[id_value][title]["ranks"].append(index)
                else:
                    results[id_value][title] = {
                        "ranks": [index],
                        "url": url,
                        "mobileUrl": mobile_url,
                    }
        except json.JSONDecodeError:
            print(f"解析 {id_value} 响应失败")
            failed_ids.append(id_value)
        except Exception as e:
            print(f"处理 {id_value} 数据出错: {e}")
            failed_ids.append(id_value)


# ============================================================================
# 第六部分：数据处理与解析
# ============================================================================

def save_titles_to_file(results: Dict, id_to_name: Dict, failed_ids: List) -> str:
    """保存标题到文件"""
    file_path = get_output_path("txt", f"{format_time_filename()}.txt")

    with open(file_path, "w", encoding="utf-8") as f:
        for id_value, title_data in results.items():
            # 写入平台标识
            name = id_to_name.get(id_value)
            if name and name != id_value:
                f.write(f"{id_value} | {name}\n")
            else:
                f.write(f"{id_value}\n")

            # 按排名排序并写入标题
            sorted_titles = _sort_titles_by_rank(title_data)
            for rank, cleaned_title, url, mobile_url in sorted_titles:
                line = f"{rank}. {cleaned_title}"
                if url:
                    line += f" [URL:{url}]"
                if mobile_url:
                    line += f" [MOBILE:{mobile_url}]"
                f.write(line + "\n")

            f.write("\n")

        # 写入失败 ID
        if failed_ids:
            f.write("==== 以下ID请求失败 ====\n")
            for id_value in failed_ids:
                f.write(f"{id_value}\n")

    return file_path


def _sort_titles_by_rank(title_data: Dict) -> List[Tuple]:
    """按排名排序标题"""
    sorted_titles = []

    for title, info in title_data.items():
        cleaned_title = clean_title(title)

        if isinstance(info, dict):
            ranks = info.get("ranks", [])
            url = info.get("url", "")
            mobile_url = info.get("mobileUrl", "")
        else:
            ranks = info if isinstance(info, list) else []
            url = ""
            mobile_url = ""

        rank = ranks[0] if ranks else 1
        sorted_titles.append((rank, cleaned_title, url, mobile_url))

    sorted_titles.sort(key=lambda x: x[0])
    return sorted_titles


def load_frequency_words(
    frequency_file: Optional[str] = None,
) -> Tuple[List[Dict], List[str]]:
    """加载频率词配置"""
    if frequency_file is None:
        frequency_file = os.environ.get(
            "FREQUENCY_WORDS_PATH", "config/frequency_words.txt"
        )

    frequency_path = Path(frequency_file)
    if not frequency_path.exists():
        raise FileNotFoundError(f"频率词文件 {frequency_file} 不存在")

    with open(frequency_path, "r", encoding="utf-8") as f:
        content = f.read()

    word_groups = [group.strip() for group in content.split("\n\n") if group.strip()]

    processed_groups = []
    filter_words = []

    for group in word_groups:
        group_data = _parse_word_group(group, filter_words)
        if group_data:
            processed_groups.append(group_data)

    return processed_groups, filter_words


def _parse_word_group(group: str, filter_words: List[str]) -> Optional[Dict]:
    """解析单个词组"""
    words = [word.strip() for word in group.split("\n") if word.strip()]

    group_required_words = []
    group_normal_words = []

    for word in words:
        if word.startswith("!"):
            filter_words.append(word[1:])
        elif word.startswith("+"):
            group_required_words.append(word[1:])
        else:
            group_normal_words.append(word)

    if not group_required_words and not group_normal_words:
        return None

    group_key = (
        " ".join(group_normal_words)
        if group_normal_words
        else " ".join(group_required_words)
    )

    return {
        "required": group_required_words,
        "normal": group_normal_words,
        "group_key": group_key,
    }


def parse_file_titles(file_path: Path) -> Tuple[Dict, Dict]:
    """解析单个 txt 文件的标题数据"""
    titles_by_id = {}
    id_to_name = {}

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        sections = content.split("\n\n")

    for section in sections:
        if not section.strip() or "==== 以下ID请求失败 ====" in section:
            continue

        lines = section.strip().split("\n")
        if len(lines) < 2:
            continue

        # 解析头部
        source_id, name = _parse_section_header(lines[0])
        id_to_name[source_id] = name
        titles_by_id[source_id] = {}

        # 解析标题行
        for line in lines[1:]:
            if line.strip():
                title_data = _parse_title_line(line)
                if title_data:
                    title, data = title_data
                    titles_by_id[source_id][title] = data

    return titles_by_id, id_to_name


def _parse_section_header(header_line: str) -> Tuple[str, str]:
    """解析节头部"""
    header_line = header_line.strip()
    if " | " in header_line:
        parts = header_line.split(" | ", 1)
        return parts[0].strip(), parts[1].strip()
    return header_line, header_line


def _parse_title_line(line: str) -> Optional[Tuple[str, Dict]]:
    """解析标题行"""
    try:
        title_part = line.strip()
        rank = None

        # 提取排名
        if ". " in title_part and title_part.split(". ")[0].isdigit():
            rank_str, title_part = title_part.split(". ", 1)
            rank = int(rank_str)

        # 提取 MOBILE URL
        mobile_url = ""
        if " [MOBILE:" in title_part:
            title_part, mobile_part = title_part.rsplit(" [MOBILE:", 1)
            if mobile_part.endswith("]"):
                mobile_url = mobile_part[:-1]

        # 提取 URL
        url = ""
        if " [URL:" in title_part:
            title_part, url_part = title_part.rsplit(" [URL:", 1)
            if url_part.endswith("]"):
                url = url_part[:-1]

        title = clean_title(title_part.strip())

        return title, {
            "ranks": [rank] if rank is not None else [1],
            "url": url,
            "mobileUrl": mobile_url,
        }
    except Exception as e:
        print(f"解析标题行出错: {line}, 错误: {e}")
        return None


def read_all_today_titles(
    current_platform_ids: Optional[List[str]] = None,
) -> Tuple[Dict, Dict, Dict]:
    """读取当天所有标题文件"""
    date_folder = format_date_folder()
    txt_dir = Path("output") / date_folder / "txt"

    if not txt_dir.exists():
        return {}, {}, {}

    all_results = {}
    final_id_to_name = {}
    title_info = {}

    files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])

    for file_path in files:
        time_info = file_path.stem
        titles_by_id, file_id_to_name = parse_file_titles(file_path)

        # 按当前平台过滤
        if current_platform_ids is not None:
            titles_by_id, file_id_to_name = _filter_by_platform(
                titles_by_id, file_id_to_name, current_platform_ids
            )

        final_id_to_name.update(file_id_to_name)

        for source_id, title_data in titles_by_id.items():
            _merge_source_data(
                source_id, title_data, time_info, all_results, title_info
            )

    return all_results, final_id_to_name, title_info


def _filter_by_platform(
    titles_by_id: Dict,
    id_to_name: Dict,
    platform_ids: List[str]
) -> Tuple[Dict, Dict]:
    """按平台 ID 过滤数据"""
    filtered_titles = {
        sid: data for sid, data in titles_by_id.items() if sid in platform_ids
    }
    filtered_names = {
        sid: name for sid, name in id_to_name.items() if sid in platform_ids
    }
    return filtered_titles, filtered_names


def _merge_source_data(
    source_id: str,
    title_data: Dict,
    time_info: str,
    all_results: Dict,
    title_info: Dict,
) -> None:
    """合并来源数据"""
    if source_id not in all_results:
        all_results[source_id] = title_data
        title_info[source_id] = {}

        for title, data in title_data.items():
            title_info[source_id][title] = {
                "first_time": time_info,
                "last_time": time_info,
                "count": 1,
                **data,
            }
    else:
        for title, data in title_data.items():
            if title not in all_results[source_id]:
                all_results[source_id][title] = data
                title_info[source_id][title] = {
                    "first_time": time_info,
                    "last_time": time_info,
                    "count": 1,
                    **data,
                }
            else:
                _update_existing_title(
                    all_results[source_id][title],
                    title_info[source_id][title],
                    data,
                    time_info,
                )


def _update_existing_title(
    existing: Dict,
    info: Dict,
    new_data: Dict,
    time_info: str
) -> None:
    """更新已存在的标题数据"""
    # 合并排名
    new_ranks = new_data.get("ranks", [])
    merged_ranks = existing.get("ranks", []).copy()
    for rank in new_ranks:
        if rank not in merged_ranks:
            merged_ranks.append(rank)

    existing["ranks"] = merged_ranks
    existing["url"] = existing.get("url") or new_data.get("url", "")
    existing["mobileUrl"] = existing.get("mobileUrl") or new_data.get("mobileUrl", "")

    info["last_time"] = time_info
    info["ranks"] = merged_ranks
    info["count"] += 1
    info["url"] = info.get("url") or new_data.get("url", "")
    info["mobileUrl"] = info.get("mobileUrl") or new_data.get("mobileUrl", "")


def detect_latest_new_titles(current_platform_ids: Optional[List[str]] = None) -> Dict:
    """检测当日最新批次的新增标题"""
    date_folder = format_date_folder()
    txt_dir = Path("output") / date_folder / "txt"

    if not txt_dir.exists():
        return {}

    files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])
    if len(files) < 2:
        return {}

    # 解析最新文件
    latest_file = files[-1]
    latest_titles, _ = parse_file_titles(latest_file)

    if current_platform_ids is not None:
        latest_titles, _ = _filter_by_platform(latest_titles, {}, current_platform_ids)

    # 汇总历史标题
    historical_titles = _collect_historical_titles(files[:-1], current_platform_ids)

    # 找出新增标题
    return _find_new_titles(latest_titles, historical_titles)


def _collect_historical_titles(
    files: List[Path],
    platform_ids: Optional[List[str]]
) -> Dict[str, set]:
    """收集历史标题"""
    historical_titles = {}

    for file_path in files:
        historical_data, _ = parse_file_titles(file_path)

        if platform_ids is not None:
            historical_data, _ = _filter_by_platform(historical_data, {}, platform_ids)

        for source_id, titles_data in historical_data.items():
            if source_id not in historical_titles:
                historical_titles[source_id] = set()
            historical_titles[source_id].update(titles_data.keys())

    return historical_titles


def _find_new_titles(latest_titles: Dict, historical_titles: Dict) -> Dict:
    """找出新增标题"""
    new_titles = {}

    for source_id, source_titles in latest_titles.items():
        historical_set = historical_titles.get(source_id, set())
        source_new = {
            title: data
            for title, data in source_titles.items()
            if title not in historical_set
        }
        if source_new:
            new_titles[source_id] = source_new

    return new_titles


# ============================================================================
# 第七部分：统计与分析
# ============================================================================

def calculate_news_weight(
    title_data: Dict,
    rank_threshold: int = CONFIG["RANK_THRESHOLD"]
) -> float:
    """计算新闻权重，用于排序"""
    ranks = title_data.get("ranks", [])
    if not ranks:
        return 0.0

    count = title_data.get("count", len(ranks))
    weight_config = CONFIG["WEIGHT_CONFIG"]

    # 排名权重
    rank_scores = [11 - min(rank, 10) for rank in ranks]
    rank_weight = sum(rank_scores) / len(ranks)

    # 频次权重
    frequency_weight = min(count, 10) * 10

    # 热度加成
    high_rank_count = sum(1 for rank in ranks if rank <= rank_threshold)
    hotness_weight = (high_rank_count / len(ranks)) * 100

    total_weight = (
        rank_weight * weight_config["RANK_WEIGHT"]
        + frequency_weight * weight_config["FREQUENCY_WEIGHT"]
        + hotness_weight * weight_config["HOTNESS_WEIGHT"]
    )

    return total_weight


def matches_word_groups(
    title: str,
    word_groups: List[Dict],
    filter_words: List[str]
) -> bool:
    """检查标题是否匹配词组规则"""
    if not word_groups:
        return True

    title_lower = title.lower()

    # 过滤词检查
    if any(fw.lower() in title_lower for fw in filter_words):
        return False

    # 词组匹配检查
    for group in word_groups:
        required = group["required"]
        normal = group["normal"]

        # 必须词检查
        if required and not all(rw.lower() in title_lower for rw in required):
            continue

        # 普通词检查
        if normal and not any(nw.lower() in title_lower for nw in normal):
            continue

        return True

    return False


def format_time_display(first_time: str, last_time: str) -> str:
    """格式化时间显示"""
    if not first_time:
        return ""
    if first_time == last_time or not last_time:
        return first_time
    return f"[{first_time} ~ {last_time}]"


def format_rank_display(
    ranks: List[int],
    rank_threshold: int,
    format_type: str
) -> str:
    """统一的排名格式化方法"""
    if not ranks:
        return ""

    unique_ranks = sorted(set(ranks))
    min_rank, max_rank = unique_ranks[0], unique_ranks[-1]

    # 格式化标记
    highlights = {
        "html": ("<font color='red'><strong>", "</strong></font>"),
        "telegram": ("<b>", "</b>"),
    }
    default_highlight = ("**", "**")
    start, end = highlights.get(format_type, default_highlight)

    # 构建显示文本
    rank_text = f"[{min_rank}]" if min_rank == max_rank else f"[{min_rank} - {max_rank}]"

    if min_rank <= rank_threshold:
        return f"{start}{rank_text}{end}"
    return rank_text


def count_word_frequency(
    results: Dict,
    word_groups: List[Dict],
    filter_words: List[str],
    id_to_name: Dict,
    title_info: Optional[Dict] = None,
    rank_threshold: int = CONFIG["RANK_THRESHOLD"],
    new_titles: Optional[Dict] = None,
    mode: str = "daily",
) -> Tuple[List[Dict], int]:
    """统计词频，支持必须词、频率词、过滤词"""
    # 处理空词组情况
    if not word_groups:
        print("频率词配置为空，将显示所有新闻")
        word_groups = [{"required": [], "normal": [], "group_key": "全部新闻"}]
        filter_words = []

    is_first_today = is_first_crawl_today()
    title_info = title_info or {}
    new_titles = new_titles or {}

    # 确定处理数据和模式
    results_to_process, all_news_are_new = _prepare_results_for_mode(
        results, new_titles, title_info, mode, is_first_today
    )

    # 初始化统计
    word_stats = {group["group_key"]: {"count": 0, "titles": {}} for group in word_groups}
    total_titles = 0
    processed_titles = {}
    matched_new_count = 0

    # 统计处理
    for source_id, titles_data in results_to_process.items():
        total_titles += len(titles_data)
        processed_titles.setdefault(source_id, {})

        for title, title_data in titles_data.items():
            if title in processed_titles.get(source_id, {}):
                continue

            if not matches_word_groups(title, word_groups, filter_words):
                continue

            if (mode == "incremental" and all_news_are_new) or (mode == "current" and is_first_today):
                matched_new_count += 1

            # 处理匹配的标题
            _process_matched_title(
                title, title_data, source_id, word_groups, word_stats,
                title_info, new_titles, id_to_name, rank_threshold,
                all_news_are_new, mode, processed_titles
            )

    # 输出统计信息
    _print_mode_statistics(
        mode, is_first_today, results, new_titles, word_groups,
        matched_new_count, word_stats, results_to_process
    )

    # 构建并排序结果
    return _build_stats_result(word_stats, total_titles, rank_threshold)


def _prepare_results_for_mode(
    results: Dict,
    new_titles: Dict,
    title_info: Dict,
    mode: str,
    is_first_today: bool
) -> Tuple[Dict, bool]:
    """根据模式准备处理数据"""
    if mode == "incremental":
        if is_first_today:
            return results, True
        return new_titles if new_titles else {}, True

    if mode == "current" and title_info:
        latest_time = _find_latest_time(title_info)
        if latest_time:
            filtered = _filter_by_latest_time(results, title_info, latest_time)
            count = sum(len(titles) for titles in filtered.values())
            print(f"当前榜单模式：最新时间 {latest_time}，筛选出 {count} 条当前榜单新闻")
            return filtered, False

    if mode == "daily":
        total = sum(len(titles) for titles in results.values())
        print(f"当日汇总模式：处理 {total} 条新闻")

    return results, False


def _find_latest_time(title_info: Dict) -> Optional[str]:
    """查找最新时间"""
    latest_time = None
    for source_titles in title_info.values():
        for data in source_titles.values():
            last_time = data.get("last_time", "")
            if last_time and (latest_time is None or last_time > latest_time):
                latest_time = last_time
    return latest_time


def _filter_by_latest_time(
    results: Dict,
    title_info: Dict,
    latest_time: str
) -> Dict:
    """按最新时间过滤结果"""
    filtered = {}
    for source_id, source_titles in results.items():
        if source_id not in title_info:
            continue
        source_filtered = {
            title: data
            for title, data in source_titles.items()
            if title in title_info[source_id]
            and title_info[source_id][title].get("last_time") == latest_time
        }
        if source_filtered:
            filtered[source_id] = source_filtered
    return filtered


def _process_matched_title(
    title: str,
    title_data: Dict,
    source_id: str,
    word_groups: List[Dict],
    word_stats: Dict,
    title_info: Dict,
    new_titles: Dict,
    id_to_name: Dict,
    rank_threshold: int,
    all_news_are_new: bool,
    mode: str,
    processed_titles: Dict
) -> None:
    """处理匹配的标题"""
    title_lower = title.lower()
    is_all_news_mode = len(word_groups) == 1 and word_groups[0]["group_key"] == "全部新闻"

    for group in word_groups:
        if not is_all_news_mode:
            required = group["required"]
            normal = group["normal"]

            if required and not all(rw.lower() in title_lower for rw in required):
                continue
            if normal and not any(nw.lower() in title_lower for nw in normal):
                continue

        group_key = group["group_key"]
        word_stats[group_key]["count"] += 1
        word_stats[group_key]["titles"].setdefault(source_id, [])

        # 构建标题信息
        entry = _build_title_entry(
            title, title_data, source_id, title_info, new_titles,
            id_to_name, rank_threshold, all_news_are_new, mode
        )
        word_stats[group_key]["titles"][source_id].append(entry)

        processed_titles.setdefault(source_id, {})[title] = True
        break


def _build_title_entry(
    title: str,
    title_data: Dict,
    source_id: str,
    title_info: Dict,
    new_titles: Dict,
    id_to_name: Dict,
    rank_threshold: int,
    all_news_are_new: bool,
    mode: str
) -> Dict:
    """构建标题条目"""
    source_ranks = title_data.get("ranks", [])
    source_url = title_data.get("url", "")
    source_mobile_url = title_data.get("mobileUrl", "")

    # 获取历史信息
    first_time = last_time = ""
    count_info = 1
    ranks = source_ranks or []
    url = source_url
    mobile_url = source_mobile_url

    if title_info and source_id in title_info and title in title_info[source_id]:
        info = title_info[source_id][title]
        first_time = info.get("first_time", "")
        last_time = info.get("last_time", "")
        count_info = info.get("count", 1)
        if info.get("ranks"):
            ranks = info["ranks"]
        url = info.get("url", source_url)
        mobile_url = info.get("mobileUrl", source_mobile_url)

    if not ranks:
        ranks = [99]

    # 判断是否新增
    is_new = all_news_are_new or (
        new_titles and source_id in new_titles and title in new_titles[source_id]
    )

    return {
        "title": title,
        "source_name": id_to_name.get(source_id, source_id),
        "first_time": first_time,
        "last_time": last_time,
        "time_display": format_time_display(first_time, last_time),
        "count": count_info,
        "ranks": ranks,
        "rank_threshold": rank_threshold,
        "url": url,
        "mobileUrl": mobile_url,
        "is_new": is_new,
    }


def _print_mode_statistics(
    mode: str,
    is_first_today: bool,
    results: Dict,
    new_titles: Dict,
    word_groups: List[Dict],
    matched_new_count: int,
    word_stats: Dict,
    results_to_process: Dict
) -> None:
    """输出模式统计信息"""
    is_all_news = len(word_groups) == 1 and word_groups[0]["group_key"] == "全部新闻"

    if mode == "incremental":
        if is_first_today:
            total = sum(len(titles) for titles in results.values())
            status = "全部显示" if is_all_news else "频率词匹配"
            print(f"增量模式：当天第一次爬取，{total} 条新闻中有 {matched_new_count} 条{status}")
        elif new_titles:
            total_new = sum(len(titles) for titles in new_titles.values())
            status = "全部显示" if is_all_news else "匹配频率词"
            print(f"增量模式：{total_new} 条新增新闻中，有 {matched_new_count} 条{status}")
            if matched_new_count == 0 and not is_all_news:
                print("增量模式：没有新增新闻匹配频率词，将不会发送通知")
        else:
            print("增量模式：未检测到新增新闻")

    elif mode == "current":
        total = sum(len(titles) for titles in results_to_process.values())
        if is_first_today:
            status = "全部显示" if is_all_news else "频率词匹配"
            print(f"当前榜单模式：当天第一次爬取，{total} 条当前榜单新闻中有 {matched_new_count} 条{status}")
        else:
            matched = sum(stat["count"] for stat in word_stats.values())
            status = "全部显示" if is_all_news else "频率词匹配"
            print(f"当前榜单模式：{total} 条当前榜单新闻中有 {matched} 条{status}")


def _build_stats_result(
    word_stats: Dict,
    total_titles: int,
    rank_threshold: int
) -> Tuple[List[Dict], int]:
    """构建统计结果"""
    stats = []

    for group_key, data in word_stats.items():
        all_titles = []
        for title_list in data["titles"].values():
            all_titles.extend(title_list)

        # 按权重排序
        sorted_titles = sorted(
            all_titles,
            key=lambda x: (
                -calculate_news_weight(x, rank_threshold),
                min(x["ranks"]) if x["ranks"] else 999,
                -x["count"],
            ),
        )

        stats.append({
            "word": group_key,
            "count": data["count"],
            "titles": sorted_titles,
            "percentage": round(data["count"] / total_titles * 100, 2) if total_titles > 0 else 0,
        })

    stats.sort(key=lambda x: x["count"], reverse=True)
    return stats, total_titles


# ============================================================================
# 第八部分：报告生成
# ============================================================================

def prepare_report_data(
    stats: List[Dict],
    failed_ids: Optional[List] = None,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    mode: str = "daily",
) -> Dict:
    """准备报告数据"""
    hide_new_section = mode == "incremental"
    processed_new_titles = []

    if not hide_new_section and new_titles and id_to_name:
        processed_new_titles = _process_new_titles_for_report(new_titles, id_to_name)

    processed_stats = _process_stats_for_report(stats)

    return {
        "stats": processed_stats,
        "new_titles": processed_new_titles,
        "failed_ids": failed_ids or [],
        "total_new_count": sum(len(src["titles"]) for src in processed_new_titles),
    }


def _process_new_titles_for_report(new_titles: Dict, id_to_name: Dict) -> List[Dict]:
    """处理新增标题用于报告"""
    word_groups, filter_words = load_frequency_words()
    processed = []

    for source_id, titles_data in new_titles.items():
        filtered = {
            t: d for t, d in titles_data.items()
            if matches_word_groups(t, word_groups, filter_words)
        }

        if not filtered:
            continue

        source_name = id_to_name.get(source_id, source_id)
        source_titles = [
            {
                "title": title,
                "source_name": source_name,
                "time_display": "",
                "count": 1,
                "ranks": data.get("ranks", []),
                "rank_threshold": CONFIG["RANK_THRESHOLD"],
                "url": data.get("url", ""),
                "mobile_url": data.get("mobileUrl", ""),
                "is_new": True,
            }
            for title, data in filtered.items()
        ]

        processed.append({
            "source_id": source_id,
            "source_name": source_name,
            "titles": source_titles,
        })

    return processed


def _process_stats_for_report(stats: List[Dict]) -> List[Dict]:
    """处理统计数据用于报告"""
    processed = []

    for stat in stats:
        if stat["count"] <= 0:
            continue

        titles = [
            {
                "title": td["title"],
                "source_name": td["source_name"],
                "time_display": td["time_display"],
                "count": td["count"],
                "ranks": td["ranks"],
                "rank_threshold": td["rank_threshold"],
                "url": td.get("url", ""),
                "mobile_url": td.get("mobileUrl", ""),
                "is_new": td.get("is_new", False),
            }
            for td in stat["titles"]
        ]

        processed.append({
            "word": stat["word"],
            "count": stat["count"],
            "percentage": stat.get("percentage", 0),
            "titles": titles,
        })

    return processed


def format_title_for_platform(
    platform: str,
    title_data: Dict,
    show_source: bool = True
) -> str:
    """统一的标题格式化方法"""
    rank_display = format_rank_display(
        title_data["ranks"], title_data["rank_threshold"], platform
    )
    link_url = title_data.get("mobile_url") or title_data.get("url", "")
    cleaned_title = clean_title(title_data["title"])
    title_prefix = "🆕 " if title_data.get("is_new") else ""

    # 格式化标题链接
    if platform == "telegram":
        if link_url:
            formatted = f'<a href="{link_url}">{html_escape(cleaned_title)}</a>'
        else:
            formatted = html_escape(cleaned_title)
    elif platform == "html":
        escaped_title = html_escape(cleaned_title)
        if link_url:
            escaped_url = html_escape(link_url)
            formatted = f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
        else:
            formatted = f'<span class="no-link">{escaped_title}</span>'
    else:
        formatted = f"[{cleaned_title}]({link_url})" if link_url else cleaned_title

    # 构建结果
    source_prefix = f"[{title_data['source_name']}] " if show_source else ""
    result = f"{source_prefix}{title_prefix}{formatted}"

    if rank_display:
        result += f" {rank_display}"

    # 时间和次数
    time_sep = " <code>-" if platform == "telegram" else " -"
    time_end = "</code>" if platform == "telegram" else ""

    if title_data.get("time_display"):
        result += f"{time_sep} {title_data['time_display']}{time_end}"

    if title_data.get("count", 1) > 1:
        if platform == "telegram":
            result += f" <code>({title_data['count']}次)</code>"
        else:
            result += f" ({title_data['count']}次)"

    return result


def generate_html_report(
    stats: List[Dict],
    total_titles: int,
    failed_ids: Optional[List] = None,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    mode: str = "daily",
    is_daily_summary: bool = False,
    sentiment_summary: Optional[Dict] = None,
    stock_analysis: Optional[List[Dict]] = None,
) -> str:
    """生成 HTML 报告"""
    # 确定文件名
    if is_daily_summary:
        filename_map = {
            "current": "当前榜单汇总.html",
            "incremental": "当日增量.html",
        }
        filename = filename_map.get(mode, "当日汇总.html")
    else:
        filename = f"{format_time_filename()}.html"

    file_path = get_output_path("html", filename)
    report_data = prepare_report_data(stats, failed_ids, new_titles, id_to_name, mode)
    # 添加新的分析数据
    report_data["sentiment_summary"] = sentiment_summary
    report_data["stock_analysis"] = stock_analysis or []
    html_content = _render_html_content(report_data, total_titles, is_daily_summary, mode)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    if is_daily_summary:
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html_content)

    return file_path


def _render_html_content(
    report_data: Dict,
    total_titles: int,
    is_daily_summary: bool,
    mode: str
) -> str:
    """渲染 HTML 内容"""
    now = get_beijing_time()
    hot_news_count = sum(len(stat["titles"]) for stat in report_data["stats"])

    # 报告类型显示
    if is_daily_summary:
        report_type_map = {"current": "当前榜单", "incremental": "增量模式"}
        report_type = report_type_map.get(mode, "当日汇总")
    else:
        report_type = "实时分析"

    html = _get_html_template()
    html = html.replace("{{REPORT_TYPE}}", report_type)
    html = html.replace("{{TOTAL_TITLES}}", str(total_titles))
    html = html.replace("{{HOT_NEWS_COUNT}}", str(hot_news_count))
    html = html.replace("{{GENERATE_TIME}}", now.strftime("%m-%d %H:%M"))

    # 渲染内容部分
    content_html = ""

    # 失败 ID
    if report_data["failed_ids"]:
        content_html += _render_html_error_section(report_data["failed_ids"])

    # 情绪分析摘要
    if report_data.get("sentiment_summary"):
        content_html += _render_html_sentiment_section(report_data["sentiment_summary"])

    # 板块分析
    if report_data.get("stock_analysis"):
        content_html += _render_html_stock_section(report_data["stock_analysis"])

    # 统计数据
    if report_data["stats"]:
        content_html += _render_html_stats_section(report_data["stats"])

    # 新增新闻
    if report_data["new_titles"]:
        content_html += _render_html_new_section(report_data)

    html = html.replace("{{CONTENT}}", content_html)
    return html


def _get_html_template() -> str:
    """获取 HTML 模板"""
    return '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>热点新闻分析</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; margin: 0; padding: 16px; background: #fafafa; color: #333; line-height: 1.5; }
        .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 16px rgba(0,0,0,0.06); }
        .header { background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); color: white; padding: 32px 24px; text-align: center; }
        .header-title { font-size: 22px; font-weight: 700; margin: 0 0 20px 0; }
        .header-info { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; font-size: 14px; opacity: 0.95; }
        .info-item { text-align: center; }
        .info-label { display: block; font-size: 12px; opacity: 0.8; margin-bottom: 4px; }
        .info-value { font-weight: 600; font-size: 16px; }
        .content { padding: 24px; }
        /* 分析卡片样式 */
        .analysis-section { margin-bottom: 24px; padding: 20px; background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-radius: 12px; border: 1px solid #e2e8f0; }
        .analysis-title { font-size: 16px; font-weight: 600; color: #1e293b; margin: 0 0 16px 0; display: flex; align-items: center; gap: 8px; }
        .analysis-title .icon { font-size: 18px; }
        /* 情绪分析 */
        .sentiment-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
        .sentiment-card { padding: 16px; border-radius: 8px; text-align: center; }
        .sentiment-card.positive { background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%); }
        .sentiment-card.negative { background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%); }
        .sentiment-card.neutral { background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%); }
        .sentiment-value { font-size: 24px; font-weight: 700; margin-bottom: 4px; }
        .sentiment-card.positive .sentiment-value { color: #16a34a; }
        .sentiment-card.negative .sentiment-value { color: #dc2626; }
        .sentiment-card.neutral .sentiment-value { color: #6b7280; }
        .sentiment-label { font-size: 12px; color: #64748b; }
        .sentiment-pct { font-size: 11px; color: #94a3b8; margin-top: 2px; }
        /* 板块分析 */
        .stock-list { display: flex; flex-direction: column; gap: 12px; }
        .stock-item-wrapper { background: white; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; }
        .stock-item { display: flex; align-items: center; gap: 12px; padding: 12px; }
        .stock-trend { width: 40px; height: 40px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; }
        .stock-trend.bullish { background: #dcfce7; }
        .stock-trend.bearish { background: #fee2e2; }
        .stock-trend.neutral { background: #f3f4f6; }
        .stock-info { flex: 1; min-width: 0; }
        .stock-name { font-size: 14px; font-weight: 600; color: #1e293b; }
        .stock-meta { font-size: 11px; color: #64748b; margin-top: 2px; }
        .stock-badge { padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
        .stock-badge.bullish { background: #dcfce7; color: #16a34a; }
        .stock-badge.bearish { background: #fee2e2; color: #dc2626; }
        .stock-badge.neutral { background: #f3f4f6; color: #6b7280; }
        .stock-news-list { padding: 8px 12px 12px 12px; border-top: 1px solid #f1f5f9; background: #fafbfc; }
        .stock-news-item { font-size: 12px; color: #475569; padding: 4px 0; line-height: 1.4; display: flex; align-items: flex-start; gap: 4px; }
        .stock-news-source { color: #94a3b8; font-size: 11px; white-space: nowrap; }
        /* 原有样式 */
        .word-group { margin-bottom: 40px; }
        .word-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; padding-bottom: 8px; border-bottom: 1px solid #f0f0f0; }
        .word-info { display: flex; align-items: center; gap: 12px; }
        .word-name { font-size: 17px; font-weight: 600; color: #1a1a1a; }
        .word-count { color: #666; font-size: 13px; font-weight: 500; }
        .word-count.hot { color: #dc2626; font-weight: 600; }
        .word-count.warm { color: #ea580c; font-weight: 600; }
        .word-index { color: #999; font-size: 12px; }
        .news-item { margin-bottom: 20px; padding: 16px 0; border-bottom: 1px solid #f5f5f5; position: relative; display: flex; gap: 12px; align-items: center; }
        .news-item:last-child { border-bottom: none; }
        .news-item.new::after { content: "NEW"; position: absolute; top: 12px; right: 0; background: #fbbf24; color: #92400e; font-size: 9px; font-weight: 700; padding: 3px 6px; border-radius: 4px; }
        .news-number { color: #999; font-size: 13px; font-weight: 600; min-width: 20px; text-align: center; flex-shrink: 0; background: #f8f9fa; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; align-self: flex-start; margin-top: 8px; }
        .news-content { flex: 1; min-width: 0; padding-right: 40px; }
        .news-item.new .news-content { padding-right: 50px; }
        .news-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
        .source-name { color: #666; font-size: 12px; font-weight: 500; }
        .rank-num { color: #fff; background: #6b7280; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 10px; min-width: 18px; text-align: center; }
        .rank-num.top { background: #dc2626; }
        .rank-num.high { background: #ea580c; }
        .time-info { color: #999; font-size: 11px; }
        .count-info { color: #059669; font-size: 11px; font-weight: 500; }
        .news-title { font-size: 15px; line-height: 1.4; color: #1a1a1a; margin: 0; }
        .news-link { color: #2563eb; text-decoration: none; }
        .news-link:hover { text-decoration: underline; }
        .news-link:visited { color: #7c3aed; }
        .new-section { margin-top: 40px; padding-top: 24px; border-top: 2px solid #f0f0f0; }
        .new-section-title { color: #1a1a1a; font-size: 16px; font-weight: 600; margin: 0 0 20px 0; }
        .new-source-group { margin-bottom: 24px; }
        .new-source-title { color: #666; font-size: 13px; font-weight: 500; margin: 0 0 12px 0; padding-bottom: 6px; border-bottom: 1px solid #f5f5f5; }
        .new-item { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #f9f9f9; }
        .new-item:last-child { border-bottom: none; }
        .new-item-number { color: #999; font-size: 12px; font-weight: 600; min-width: 18px; text-align: center; flex-shrink: 0; background: #f8f9fa; border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; }
        .new-item-rank { color: #fff; background: #6b7280; font-size: 10px; font-weight: 700; padding: 3px 6px; border-radius: 8px; min-width: 20px; text-align: center; flex-shrink: 0; }
        .new-item-rank.top { background: #dc2626; }
        .new-item-rank.high { background: #ea580c; }
        .new-item-content { flex: 1; min-width: 0; }
        .new-item-title { font-size: 14px; line-height: 1.4; color: #1a1a1a; margin: 0; }
        .error-section { background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 16px; margin-bottom: 24px; }
        .error-title { color: #dc2626; font-size: 14px; font-weight: 600; margin: 0 0 8px 0; }
        .error-list { list-style: none; padding: 0; margin: 0; }
        .error-item { color: #991b1b; font-size: 13px; padding: 2px 0; font-family: 'SF Mono', Consolas, monospace; }
        @media (max-width: 480px) { body { padding: 12px; } .header { padding: 24px 20px; } .content { padding: 20px; } .header-info { grid-template-columns: 1fr; gap: 12px; } .sentiment-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-title">热点新闻分析</div>
            <div class="header-info">
                <div class="info-item"><span class="info-label">报告类型</span><span class="info-value">{{REPORT_TYPE}}</span></div>
                <div class="info-item"><span class="info-label">新闻总数</span><span class="info-value">{{TOTAL_TITLES}} 条</span></div>
                <div class="info-item"><span class="info-label">热点新闻</span><span class="info-value">{{HOT_NEWS_COUNT}} 条</span></div>
                <div class="info-item"><span class="info-label">生成时间</span><span class="info-value">{{GENERATE_TIME}}</span></div>
            </div>
        </div>
        <div class="content">{{CONTENT}}</div>
    </div>
</body>
</html>'''


def _render_html_sentiment_section(sentiment_summary: Dict) -> str:
    """渲染情绪分析区域"""
    if not sentiment_summary or sentiment_summary.get("total", 0) == 0:
        return ""

    positive = sentiment_summary.get("positive", 0)
    negative = sentiment_summary.get("negative", 0)
    neutral = sentiment_summary.get("neutral", 0)
    positive_pct = sentiment_summary.get("positive_pct", 0)
    negative_pct = sentiment_summary.get("negative_pct", 0)

    return f'''<div class="analysis-section">
        <div class="analysis-title"><span class="icon">📊</span>情绪分析</div>
        <div class="sentiment-grid">
            <div class="sentiment-card positive">
                <div class="sentiment-value">{positive}</div>
                <div class="sentiment-label">正面/利好</div>
                <div class="sentiment-pct">{positive_pct}%</div>
            </div>
            <div class="sentiment-card negative">
                <div class="sentiment-value">{negative}</div>
                <div class="sentiment-label">负面/利空</div>
                <div class="sentiment-pct">{negative_pct}%</div>
            </div>
            <div class="sentiment-card neutral">
                <div class="sentiment-value">{neutral}</div>
                <div class="sentiment-label">中性</div>
                <div class="sentiment-pct">{round(100 - positive_pct - negative_pct, 1)}%</div>
            </div>
        </div>
    </div>'''


def _render_html_stock_section(stock_analysis: List[Dict]) -> str:
    """渲染板块分析区域"""
    if not stock_analysis:
        return ""

    items_html = ""
    for stock in stock_analysis[:5]:  # 只显示提及次数前 5 的板块
        trend = stock.get("trend", "neutral")
        trend_cn = stock.get("trend_cn", "中性")
        icon = "📈" if trend == "bullish" else ("📉" if trend == "bearish" else "➖")

        # 渲染关联的新闻列表
        news_list = stock.get("news", [])
        news_html = ""
        if news_list:
            news_items = ""
            for news in news_list[:5]:  # 每个板块最多显示 5 条关联新闻
                news_title = html_escape(news.get("title", "")[:50])
                if len(news.get("title", "")) > 50:
                    news_title += "..."
                sentiment = news.get("sentiment", "neutral")
                sentiment_icon = "🟢" if sentiment == "positive" else ("🔴" if sentiment == "negative" else "⚪")
                source = html_escape(news.get("source_name", ""))
                news_items += f'<div class="stock-news-item">{sentiment_icon} <span class="stock-news-source">[{source}]</span> {news_title}</div>'
            news_html = f'<div class="stock-news-list">{news_items}</div>'

        items_html += f'''<div class="stock-item-wrapper">
            <div class="stock-item">
                <div class="stock-trend {trend}">{icon}</div>
                <div class="stock-info">
                    <div class="stock-name">{html_escape(stock.get("name", ""))}</div>
                    <div class="stock-meta">提及 {stock.get("count", 0)} 次 · 正面 {stock.get("positive_ratio", 0)}%</div>
                </div>
                <div class="stock-badge {trend}">{trend_cn}</div>
            </div>{news_html}
        </div>'''

    return f'''<div class="analysis-section">
        <div class="analysis-title"><span class="icon">📈</span>板块关联分析</div>
        <div class="stock-list">{items_html}</div>
    </div>'''


def _render_html_error_section(failed_ids: List) -> str:
    """渲染错误部分"""
    items = "".join(f'<li class="error-item">{html_escape(id_val)}</li>' for id_val in failed_ids)
    return f'''<div class="error-section">
        <div class="error-title">⚠️ 请求失败的平台</div>
        <ul class="error-list">{items}</ul>
    </div>'''


def _render_html_stats_section(stats: List[Dict]) -> str:
    """渲染统计部分"""
    html = ""
    total_count = len(stats)

    for i, stat in enumerate(stats, 1):
        count = stat["count"]
        count_class = "hot" if count >= 10 else ("warm" if count >= 5 else "")

        html += f'''<div class="word-group">
            <div class="word-header">
                <div class="word-info">
                    <div class="word-name">{html_escape(stat["word"])}</div>
                    <div class="word-count {count_class}">{count} 条</div>
                </div>
                <div class="word-index">{i}/{total_count}</div>
            </div>'''

        for j, title_data in enumerate(stat["titles"], 1):
            html += _render_html_news_item(j, title_data)

        html += "</div>"

    return html


def _render_html_news_item(index: int, title_data: Dict) -> str:
    """渲染新闻条目"""
    is_new = title_data.get("is_new", False)
    new_class = "new" if is_new else ""

    ranks = title_data.get("ranks", [])
    rank_html = ""
    if ranks:
        min_rank, max_rank = min(ranks), max(ranks)
        rank_threshold = title_data.get("rank_threshold", 10)
        rank_class = "top" if min_rank <= 3 else ("high" if min_rank <= rank_threshold else "")
        rank_text = str(min_rank) if min_rank == max_rank else f"{min_rank}-{max_rank}"
        rank_html = f'<span class="rank-num {rank_class}">{rank_text}</span>'

    time_html = ""
    if title_data.get("time_display"):
        simplified = title_data["time_display"].replace(" ~ ", "~").replace("[", "").replace("]", "")
        time_html = f'<span class="time-info">{html_escape(simplified)}</span>'

    count_html = ""
    if title_data.get("count", 1) > 1:
        count_html = f'<span class="count-info">{title_data["count"]}次</span>'

    link_url = title_data.get("mobile_url") or title_data.get("url", "")
    escaped_title = html_escape(title_data["title"])

    if link_url:
        title_html = f'<a href="{html_escape(link_url)}" target="_blank" class="news-link">{escaped_title}</a>'
    else:
        title_html = escaped_title

    return f'''<div class="news-item {new_class}">
        <div class="news-number">{index}</div>
        <div class="news-content">
            <div class="news-header">
                <span class="source-name">{html_escape(title_data["source_name"])}</span>
                {rank_html}{time_html}{count_html}
            </div>
            <div class="news-title">{title_html}</div>
        </div>
    </div>'''


def _render_html_new_section(report_data: Dict) -> str:
    """渲染新增新闻部分"""
    html = f'''<div class="new-section">
        <div class="new-section-title">本次新增热点 (共 {report_data["total_new_count"]} 条)</div>'''

    for source_data in report_data["new_titles"]:
        html += f'''<div class="new-source-group">
            <div class="new-source-title">{html_escape(source_data["source_name"])} · {len(source_data["titles"])}条</div>'''

        for idx, title_data in enumerate(source_data["titles"], 1):
            ranks = title_data.get("ranks", [])

            rank_class = ""
            if ranks:
                min_rank = min(ranks)
                rank_class = "top" if min_rank <= 3 else ("high" if min_rank <= title_data.get("rank_threshold", 10) else "")
                rank_text = str(ranks[0]) if len(ranks) == 1 else f"{min(ranks)}-{max(ranks)}"
            else:
                rank_text = "?"

            link_url = title_data.get("mobile_url") or title_data.get("url", "")
            escaped_title = html_escape(title_data["title"])

            title_html = f'<a href="{html_escape(link_url)}" target="_blank" class="news-link">{escaped_title}</a>' if link_url else escaped_title

            html += f'''<div class="new-item">
                <div class="new-item-number">{idx}</div>
                <div class="new-item-rank {rank_class}">{rank_text}</div>
                <div class="new-item-content"><div class="new-item-title">{title_html}</div></div>
            </div>'''

        html += "</div>"

    html += "</div>"
    return html


# ============================================================================
# 第九部分：Webhook 通知
# ============================================================================

def render_feishu_content(
    report_data: Dict,
    update_info: Optional[Dict] = None,
    mode: str = "daily"
) -> str:
    """渲染飞书内容"""
    text = ""

    # 添加分析摘要（如果存在）
    analysis_summary = report_data.get("analysis_summary")
    if analysis_summary:
        # 情绪分析摘要
        sentiment = analysis_summary.get("sentiment_summary")
        if sentiment and sentiment.get("total", 0) > 0:
            text += "📊 **情绪分析**\n"
            text += f"  正面: {sentiment['positive']} ({sentiment['positive_pct']}%)  |  "
            text += f"负面: {sentiment['negative']} ({sentiment['negative_pct']}%)  |  "
            text += f"中性: {sentiment['neutral']}\n\n"

        # 板块分析摘要
        stocks = analysis_summary.get("stock_analysis", [])
        if stocks:
            text += "📈 **热门板块**\n  "
            stock_texts = []
            for s in stocks[:5]:  # 最多显示 5 个板块
                trend_icon = "🔺" if s["trend"] == "bullish" else ("🔻" if s["trend"] == "bearish" else "➖")
                stock_texts.append(f"{s['name']}{trend_icon}")
            text += "  |  ".join(stock_texts) + "\n\n"

        text += f"{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n"

    if report_data["stats"]:
        text += "📊 **热点词汇统计**\n\n"
        total = len(report_data["stats"])

        for i, stat in enumerate(report_data["stats"]):
            icon = "🔥" if stat["count"] >= 10 else ("📈" if stat["count"] >= 5 else "📌")
            text += f"{icon} [{i+1}/{total}] **{stat['word']}** : {stat['count']}条\n\n"

            for j, td in enumerate(stat["titles"], 1):
                formatted = format_title_for_platform("feishu", td, show_source=True)
                text += f"  {j}. {formatted}\n"
                if j < len(stat["titles"]):
                    text += "\n"

            if i < len(report_data["stats"]) - 1:
                text += f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n"

    if not text:
        mode_text_map = {
            "incremental": "增量模式下暂无新增匹配的热点词汇",
            "current": "当前榜单模式下暂无匹配的热点词汇",
        }
        text = f"📭 {mode_text_map.get(mode, '暂无匹配的热点词汇')}\n\n"

    # 新增新闻
    if report_data["new_titles"]:
        if "暂无匹配" not in text:
            text += f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n"
        text += f"🆕 **本次新增热点新闻** (共 {report_data['total_new_count']} 条)\n\n"

        for src in report_data["new_titles"]:
            text += f"**{src['source_name']}** ({len(src['titles'])} 条):\n"
            for j, td in enumerate(src["titles"], 1):
                td_copy = {**td, "is_new": False}
                formatted = format_title_for_platform("feishu", td_copy, show_source=False)
                text += f"  {j}. {formatted}\n"
            text += "\n"

    # 失败 ID
    if report_data["failed_ids"]:
        if "暂无匹配" not in text:
            text += f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n"
        text += "⚠️ **数据获取失败的平台：**\n\n"
        for id_val in report_data["failed_ids"]:
            text += f"  • <font color='red'>{id_val}</font>\n"

    now = get_beijing_time()
    text += f"\n\n更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"

    if update_info:
        text += f"\n TrendRadar 发现新版本 {update_info['remote_version']}，当前 {update_info['current_version']}"

    return text


def render_dingtalk_content(
    report_data: Dict,
    update_info: Optional[Dict] = None,
    mode: str = "daily"
) -> str:
    """渲染钉钉内容"""
    total_titles = sum(len(s["titles"]) for s in report_data["stats"] if s["count"] > 0)
    now = get_beijing_time()

    text = f"**总新闻数：** {total_titles}\n\n"
    text += f"**时间：** {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    text += f"**类型：** 热点分析报告\n\n---\n\n"

    if report_data["stats"]:
        text += "📊 **热点词汇统计**\n\n"
        total = len(report_data["stats"])

        for i, stat in enumerate(report_data["stats"]):
            icon = "🔥" if stat["count"] >= 10 else ("📈" if stat["count"] >= 5 else "📌")
            text += f"{icon} [{i+1}/{total}] **{stat['word']}** : **{stat['count']}** 条\n\n"

            for j, td in enumerate(stat["titles"], 1):
                formatted = format_title_for_platform("dingtalk", td, show_source=True)
                text += f"  {j}. {formatted}\n"
                if j < len(stat["titles"]):
                    text += "\n"

            if i < len(report_data["stats"]) - 1:
                text += "\n---\n\n"
    else:
        mode_text_map = {
            "incremental": "增量模式下暂无新增匹配的热点词汇",
            "current": "当前榜单模式下暂无匹配的热点词汇",
        }
        text += f"📭 {mode_text_map.get(mode, '暂无匹配的热点词汇')}\n\n"

    # 新增新闻和失败 ID（同飞书逻辑）
    if report_data["new_titles"]:
        if "暂无匹配" not in text:
            text += "\n---\n\n"
        text += f"🆕 **本次新增热点新闻** (共 {report_data['total_new_count']} 条)\n\n"
        for src in report_data["new_titles"]:
            text += f"**{src['source_name']}** ({len(src['titles'])} 条):\n\n"
            for j, td in enumerate(src["titles"], 1):
                td_copy = {**td, "is_new": False}
                formatted = format_title_for_platform("dingtalk", td_copy, show_source=False)
                text += f"  {j}. {formatted}\n"
            text += "\n"

    if report_data["failed_ids"]:
        if "暂无匹配" not in text:
            text += "\n---\n\n"
        text += "⚠️ **数据获取失败的平台：**\n\n"
        for id_val in report_data["failed_ids"]:
            text += f"  • **{id_val}**\n"

    text += f"\n\n> 更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"
    if update_info:
        text += f"\n> TrendRadar 发现新版本 **{update_info['remote_version']}**，当前 **{update_info['current_version']}**"

    return text


def split_content_into_batches(
    report_data: Dict,
    format_type: str,
    update_info: Optional[Dict] = None,
    max_bytes: int = CONFIG["MESSAGE_BATCH_SIZE"],
    mode: str = "daily",
) -> List[str]:
    """分批处理消息内容"""
    batches = []
    now = get_beijing_time()
    total_titles = sum(len(s["titles"]) for s in report_data["stats"] if s["count"] > 0)

    # 头部和尾部
    if format_type == "wework":
        header = f"**总新闻数：** {total_titles}\n\n\n\n"
        footer = f"\n\n\n> 更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"
        if update_info:
            footer += f"\n> TrendRadar 发现新版本 **{update_info['remote_version']}**，当前 **{update_info['current_version']}**"
        separator = "\n\n\n\n"
        stats_header = "📊 **热点词汇统计**\n\n"
    else:  # telegram
        header = f"总新闻数： {total_titles}\n\n"
        footer = f"\n\n更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"
        if update_info:
            footer += f"\nTrendRadar 发现新版本 {update_info['remote_version']}，当前 {update_info['current_version']}"
        separator = "\n\n"
        stats_header = "📊 热点词汇统计\n\n"

    # 空内容处理
    if not report_data["stats"] and not report_data["new_titles"] and not report_data["failed_ids"]:
        mode_text_map = {
            "incremental": "增量模式下暂无新增匹配的热点词汇",
            "current": "当前榜单模式下暂无匹配的热点词汇",
        }
        return [header + f"📭 {mode_text_map.get(mode, '暂无匹配的热点词汇')}\n\n" + footer]

    current_batch = header
    has_content = False

    def can_add(content: str) -> bool:
        test = current_batch + content
        return len(test.encode("utf-8")) + len(footer.encode("utf-8")) < max_bytes

    def flush_batch():
        nonlocal current_batch, has_content
        if has_content:
            batches.append(current_batch + footer)
        current_batch = header
        has_content = False

    # 处理统计数据
    if report_data["stats"]:
        if can_add(stats_header):
            current_batch += stats_header
            has_content = True
        else:
            flush_batch()
            current_batch += stats_header
            has_content = True

        total = len(report_data["stats"])
        for i, stat in enumerate(report_data["stats"]):
            # 词组标题
            icon = "🔥" if stat["count"] >= 10 else ("📈" if stat["count"] >= 5 else "📌")
            if format_type == "wework":
                word_header = f"{icon} [{i+1}/{total}] **{stat['word']}** : **{stat['count']}** 条\n\n"
            else:
                word_header = f"{icon} [{i+1}/{total}] {stat['word']} : {stat['count']} 条\n\n"

            # 第一条新闻
            first_line = ""
            if stat["titles"]:
                formatted = format_title_for_platform(format_type, stat["titles"][0], show_source=True)
                first_line = f"  1. {formatted}\n"
                if len(stat["titles"]) > 1:
                    first_line += "\n"

            word_with_first = word_header + first_line

            if not can_add(word_with_first):
                flush_batch()
                current_batch += stats_header + word_with_first
                has_content = True
            else:
                current_batch += word_with_first
                has_content = True

            # 剩余新闻
            for j in range(1, len(stat["titles"])):
                formatted = format_title_for_platform(format_type, stat["titles"][j], show_source=True)
                line = f"  {j+1}. {formatted}\n"
                if j < len(stat["titles"]) - 1:
                    line += "\n"

                if not can_add(line):
                    flush_batch()
                    current_batch += stats_header + word_header + line
                    has_content = True
                else:
                    current_batch += line

            # 分隔符
            if i < len(report_data["stats"]) - 1 and can_add(separator):
                current_batch += separator

    # 处理新增新闻
    if report_data["new_titles"]:
        if format_type == "wework":
            new_header = f"\n\n\n\n🆕 **本次新增热点新闻** (共 {report_data['total_new_count']} 条)\n\n"
        else:
            new_header = f"\n\n🆕 本次新增热点新闻 (共 {report_data['total_new_count']} 条)\n\n"

        if not can_add(new_header):
            flush_batch()
        current_batch += new_header
        has_content = True

        for src in report_data["new_titles"]:
            if format_type == "wework":
                src_header = f"**{src['source_name']}** ({len(src['titles'])} 条):\n\n"
            else:
                src_header = f"{src['source_name']} ({len(src['titles'])} 条):\n\n"

            first_line = ""
            if src["titles"]:
                td_copy = {**src["titles"][0], "is_new": False}
                formatted = format_title_for_platform(format_type, td_copy, show_source=False)
                first_line = f"  1. {formatted}\n"

            src_with_first = src_header + first_line
            if not can_add(src_with_first):
                flush_batch()
                current_batch += new_header + src_with_first
                has_content = True
            else:
                current_batch += src_with_first
                has_content = True

            for j in range(1, len(src["titles"])):
                td_copy = {**src["titles"][j], "is_new": False}
                formatted = format_title_for_platform(format_type, td_copy, show_source=False)
                line = f"  {j+1}. {formatted}\n"

                if not can_add(line):
                    flush_batch()
                    current_batch += new_header + src_header + line
                    has_content = True
                else:
                    current_batch += line

            current_batch += "\n"

    # 处理失败 ID
    if report_data["failed_ids"]:
        if format_type == "wework":
            failed_header = "\n\n\n\n⚠️ **数据获取失败的平台：**\n\n"
        else:
            failed_header = "\n\n⚠️ 数据获取失败的平台：\n\n"

        if not can_add(failed_header):
            flush_batch()
        current_batch += failed_header
        has_content = True

        for id_val in report_data["failed_ids"]:
            line = f"  • {id_val}\n"
            if not can_add(line):
                flush_batch()
                current_batch += failed_header + line
                has_content = True
            else:
                current_batch += line

    # 最后批次
    if has_content:
        batches.append(current_batch + footer)

    return batches


def send_to_webhooks(
    stats: List[Dict],
    failed_ids: Optional[List] = None,
    report_type: str = "当日汇总",
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    analysis_summary: Optional[Dict] = None,
) -> Dict[str, bool]:
    """发送数据到多个 webhook 平台"""
    results = {}

    # 静默推送检查
    if CONFIG["SILENT_PUSH"]["ENABLED"]:
        push_manager = PushRecordManager()
        start = CONFIG["SILENT_PUSH"]["TIME_RANGE"]["START"]
        end = CONFIG["SILENT_PUSH"]["TIME_RANGE"]["END"]
        max_count = CONFIG["SILENT_PUSH"]["MAX_PUSH_COUNT"]

        if not push_manager.is_in_time_range(start, end):
            now = get_beijing_time()
            print(f"静默模式：当前时间 {now.strftime('%H:%M')} 不在推送时间范围 {start}-{end} 内，跳过推送")
            return results

        if not push_manager.can_push(max_count):
            current_count = push_manager.get_push_count()
            print(f"静默模式：今天已推送 {current_count} 次，已达到最大推送次数 {max_count}，跳过本次推送")
            return results

        current_count = push_manager.get_push_count()
        if max_count > 0:
            print(f"静默模式：今天第 {current_count + 1}/{max_count} 次推送")
        else:
            print(f"静默模式：今天第 {current_count + 1} 次推送（不限次数）")

    report_data = prepare_report_data(stats, failed_ids, new_titles, id_to_name, mode)
    # 添加分析摘要到报告数据
    if analysis_summary:
        report_data["analysis_summary"] = analysis_summary
    update_info_to_send = update_info if CONFIG["SHOW_VERSION_UPDATE"] else None
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    # 发送到各平台
    if CONFIG["FEISHU_WEBHOOK_URL"]:
        results["feishu"] = _send_to_feishu(
            CONFIG["FEISHU_WEBHOOK_URL"], report_data, report_type,
            update_info_to_send, proxies, mode
        )

    if CONFIG["DINGTALK_WEBHOOK_URL"]:
        results["dingtalk"] = _send_to_dingtalk(
            CONFIG["DINGTALK_WEBHOOK_URL"], report_data, report_type,
            update_info_to_send, proxies, mode
        )

    if CONFIG["WEWORK_WEBHOOK_URL"]:
        results["wework"] = _send_to_wework(
            CONFIG["WEWORK_WEBHOOK_URL"], report_data, report_type,
            update_info_to_send, proxies, mode
        )

    if CONFIG["TELEGRAM_BOT_TOKEN"] and CONFIG["TELEGRAM_CHAT_ID"]:
        results["telegram"] = _send_to_telegram(
            CONFIG["TELEGRAM_BOT_TOKEN"], CONFIG["TELEGRAM_CHAT_ID"],
            report_data, report_type, update_info_to_send, proxies, mode
        )

    if not results:
        print("未配置任何 webhook URL，跳过通知发送")

    # 记录推送
    if CONFIG["SILENT_PUSH"]["ENABLED"] and any(results.values()):
        PushRecordManager().record_push(report_type)

    return results


def _send_to_feishu(
    url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict],
    proxies: Optional[Dict],
    mode: str
) -> bool:
    """发送到飞书（使用卡片消息支持超链接）"""
    content = render_feishu_content(report_data, update_info, mode)
    total = sum(len(s["titles"]) for s in report_data["stats"] if s["count"] > 0)
    now = get_beijing_time()

    # 使用 interactive 卡片消息格式，支持 Markdown 超链接
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📊 TrendRadar 热点分析 - {report_type}"
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": content
                    }
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"新闻数: {total} | 时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"
                        }
                    ]
                }
            ]
        }
    }

    return _send_webhook_request(url, payload, proxies, "飞书", report_type)


def _send_to_dingtalk(
    url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict],
    proxies: Optional[Dict],
    mode: str
) -> bool:
    """发送到钉钉"""
    content = render_dingtalk_content(report_data, update_info, mode)

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": f"TrendRadar 热点分析报告 - {report_type}",
            "text": content,
        },
    }

    return _send_webhook_request(url, payload, proxies, "钉钉", report_type, check_errcode=True)


def _send_to_wework(
    url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict],
    proxies: Optional[Dict],
    mode: str
) -> bool:
    """发送到企业微信（分批）"""
    batches = split_content_into_batches(report_data, "wework", update_info, mode=mode)
    return _send_batched_webhook(url, batches, proxies, "企业微信", report_type)


def _send_to_telegram(
    token: str,
    chat_id: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict],
    proxies: Optional[Dict],
    mode: str
) -> bool:
    """发送到 Telegram（分批）"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    batches = split_content_into_batches(report_data, "telegram", update_info, mode=mode)

    print(f"Telegram 消息分为 {len(batches)} 批次发送 [{report_type}]")

    for i, content in enumerate(batches, 1):
        batch_size = len(content.encode("utf-8"))
        print(f"发送 Telegram 第 {i}/{len(batches)} 批次，大小：{batch_size} 字节 [{report_type}]")

        if len(batches) > 1:
            content = f"<b>[第 {i}/{len(batches)} 批次]</b>\n\n" + content

        payload = {
            "chat_id": chat_id,
            "text": content,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            resp = requests.post(url, json=payload, proxies=proxies, timeout=30)
            if resp.status_code == 200 and resp.json().get("ok"):
                print(f"Telegram 第 {i}/{len(batches)} 批次发送成功 [{report_type}]")
                if i < len(batches):
                    time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
            else:
                error = resp.json().get("description", "未知错误")
                print(f"Telegram 第 {i}/{len(batches)} 批次发送失败 [{report_type}]，错误：{error}")
                return False
        except Exception as e:
            print(f"Telegram 第 {i}/{len(batches)} 批次发送出错 [{report_type}]：{e}")
            return False

    print(f"Telegram 所有 {len(batches)} 批次发送完成 [{report_type}]")
    return True


def _send_webhook_request(
    url: str,
    payload: Dict,
    proxies: Optional[Dict],
    platform: str,
    report_type: str,
    check_errcode: bool = False
) -> bool:
    """发送 webhook 请求"""
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            proxies=proxies,
            timeout=30
        )

        if resp.status_code == 200:
            if check_errcode:
                result = resp.json()
                if result.get("errcode") == 0:
                    print(f"{platform}通知发送成功 [{report_type}]")
                    return True
                print(f"{platform}通知发送失败 [{report_type}]，错误：{result.get('errmsg')}")
                return False
            print(f"{platform}通知发送成功 [{report_type}]")
            return True

        print(f"{platform}通知发送失败 [{report_type}]，状态码：{resp.status_code}")
        return False
    except Exception as e:
        print(f"{platform}通知发送出错 [{report_type}]：{e}")
        return False


def _send_batched_webhook(
    url: str,
    batches: List[str],
    proxies: Optional[Dict],
    platform: str,
    report_type: str
) -> bool:
    """发送分批 webhook"""
    print(f"{platform}消息分为 {len(batches)} 批次发送 [{report_type}]")

    for i, content in enumerate(batches, 1):
        batch_size = len(content.encode("utf-8"))
        print(f"发送{platform}第 {i}/{len(batches)} 批次，大小：{batch_size} 字节 [{report_type}]")

        if len(batches) > 1:
            content = f"**[第 {i}/{len(batches)} 批次]**\n\n" + content

        payload = {"msgtype": "markdown", "markdown": {"content": content}}

        try:
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                proxies=proxies,
                timeout=30
            )

            if resp.status_code == 200 and resp.json().get("errcode") == 0:
                print(f"{platform}第 {i}/{len(batches)} 批次发送成功 [{report_type}]")
                if i < len(batches):
                    time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
            else:
                error = resp.json().get("errmsg", "未知错误")
                print(f"{platform}第 {i}/{len(batches)} 批次发送失败 [{report_type}]，错误：{error}")
                return False
        except Exception as e:
            print(f"{platform}第 {i}/{len(batches)} 批次发送出错 [{report_type}]：{e}")
            return False

    print(f"{platform}所有 {len(batches)} 批次发送完成 [{report_type}]")
    return True


# ============================================================================
# 第十部分：情绪分析模块
# ============================================================================

class SentimentAnalyzer:
    """AI 情绪分析器 - 使用 OpenAI 兼容 API 分析新闻情绪"""

    SYSTEM_PROMPT = """你是一个专业的新闻情绪分析师。请分析以下新闻标题的情绪倾向。

对于每条新闻，请判断其情绪是：
- positive（正面/利好）：积极的、乐观的、有利的消息
- negative（负面/利空）：消极的、悲观的、不利的消息
- neutral（中性）：客观陈述、无明显倾向

请以 JSON 格式返回结果，格式如下：
[
  {"index": 1, "sentiment": "positive", "score": 0.8, "reason": "简短理由"},
  {"index": 2, "sentiment": "negative", "score": 0.7, "reason": "简短理由"}
]

注意：
1. score 范围 0-1，表示情绪强度
2. reason 用一句话解释判断理由
3. 只返回 JSON，不要其他内容"""

    def __init__(self, config: Dict):
        self.enabled = config.get("enabled", False)
        self.api_base = config.get("api_base", "https://api.deepseek.com/v1")
        self.api_key = os.environ.get("SENTIMENT_API_KEY") or config.get("api_key", "")
        self.model = config.get("model", "deepseek-chat")
        self.max_batch = config.get("max_news_per_batch", 10)
        self.cache_hours = config.get("cache_hours", 24)
        self._cache = {}
        self._cache_file = Path("output") / ".sentiment_cache.json"
        self._load_cache()

    def _load_cache(self) -> None:
        """加载情绪分析缓存"""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                # 清理过期缓存
                current_time = time.time()
                self._cache = {
                    k: v for k, v in cache_data.items()
                    if current_time - v.get("timestamp", 0) < self.cache_hours * 3600
                }
            except Exception as e:
                print(f"加载情绪缓存失败: {e}")
                self._cache = {}

    def _save_cache(self) -> None:
        """保存情绪分析缓存"""
        try:
            ensure_directory_exists("output")
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存情绪缓存失败: {e}")

    def analyze_batch(self, news_list: List[Dict]) -> List[Dict]:
        """批量分析新闻情绪"""
        if not self.enabled or not self.api_key:
            print("情绪分析未启用或未配置 API Key")
            return [{"title": n.get("title", ""), "sentiment": "neutral", "score": 0.5, "reason": "未分析"} for n in news_list]

        results = []
        uncached_news = []
        uncached_indices = []

        # 检查缓存
        for i, news in enumerate(news_list):
            title = news.get("title", "")
            cache_key = title[:100]  # 使用标题前 100 字符作为缓存键
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                results.append({
                    "title": title,
                    "sentiment": cached["sentiment"],
                    "score": cached["score"],
                    "reason": cached.get("reason", ""),
                    "cached": True
                })
            else:
                results.append(None)
                uncached_news.append(news)
                uncached_indices.append(i)

        # 分批调用 API 分析未缓存的新闻
        if uncached_news:
            print(f"情绪分析：{len(uncached_news)} 条新闻需要分析（{len(news_list) - len(uncached_news)} 条已缓存）")
            for batch_start in range(0, len(uncached_news), self.max_batch):
                batch = uncached_news[batch_start:batch_start + self.max_batch]
                batch_results = self._analyze_batch_api(batch)

                for j, result in enumerate(batch_results):
                    original_idx = uncached_indices[batch_start + j]
                    results[original_idx] = result
                    # 缓存结果
                    cache_key = result["title"][:100]
                    self._cache[cache_key] = {
                        "sentiment": result["sentiment"],
                        "score": result["score"],
                        "reason": result.get("reason", ""),
                        "timestamp": time.time()
                    }

                # 批次间延迟
                if batch_start + self.max_batch < len(uncached_news):
                    time.sleep(1)

            self._save_cache()

        return results

    def _analyze_batch_api(self, batch: List[Dict]) -> List[Dict]:
        """调用 API 分析一批新闻"""
        # 构建用户提示
        user_prompt = "请分析以下新闻标题的情绪：\n\n"
        for i, news in enumerate(batch, 1):
            user_prompt += f"{i}. {news.get('title', '')}\n"

        try:
            response = requests.post(
                f"{self.api_base.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # 解析 JSON 响应
            # 尝试提取 JSON 部分
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                sentiment_list = json.loads(json_match.group())
                results = []
                for i, news in enumerate(batch):
                    # 找到对应的分析结果
                    sentiment_data = next(
                        (s for s in sentiment_list if s.get("index") == i + 1),
                        {"sentiment": "neutral", "score": 0.5, "reason": "解析失败"}
                    )
                    results.append({
                        "title": news.get("title", ""),
                        "sentiment": sentiment_data.get("sentiment", "neutral"),
                        "score": sentiment_data.get("score", 0.5),
                        "reason": sentiment_data.get("reason", "")
                    })
                return results

        except Exception as e:
            print(f"情绪分析 API 调用失败: {e}")

        # 失败时返回中性结果
        return [{"title": n.get("title", ""), "sentiment": "neutral", "score": 0.5, "reason": "API 调用失败"} for n in batch]

    def get_sentiment_summary(self, results: List[Dict]) -> Dict:
        """获取情绪分析摘要"""
        if not results:
            return {"positive": 0, "negative": 0, "neutral": 0, "total": 0, "overall": "neutral"}

        counts = {"positive": 0, "negative": 0, "neutral": 0}
        for r in results:
            sentiment = r.get("sentiment", "neutral")
            if sentiment in counts:
                counts[sentiment] += 1

        total = len(results)
        overall = max(counts, key=counts.get) if total > 0 else "neutral"

        return {
            "positive": counts["positive"],
            "negative": counts["negative"],
            "neutral": counts["neutral"],
            "total": total,
            "overall": overall,
            "positive_pct": round(counts["positive"] / total * 100, 1) if total > 0 else 0,
            "negative_pct": round(counts["negative"] / total * 100, 1) if total > 0 else 0,
        }


# ============================================================================
# 第十一部分：股票关联分析模块
# ============================================================================

class StockAnalyzer:
    """股票关联分析器 - 根据新闻内容识别关联股票"""

    def __init__(self, config: Dict):
        self.enabled = config.get("enabled", True)
        config_file = config.get("config_file", "config/stock_keywords.yaml")
        self.stock_mappings = self._load_mappings(config_file)

    def _load_mappings(self, config_file: str) -> List[Dict]:
        """加载股票-关键词映射"""
        config_path = Path(config_file)
        if not config_path.exists():
            print(f"股票配置文件不存在: {config_file}")
            return []

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data.get("stocks", [])
        except Exception as e:
            print(f"加载股票配置失败: {e}")
            return []

    def analyze(self, news_list: List[Dict], sentiment_results: Optional[List[Dict]] = None) -> Dict:
        """分析新闻关联的股票"""
        if not self.enabled or not self.stock_mappings:
            return {}

        # 创建标题到情绪的映射
        sentiment_map = {}
        if sentiment_results:
            for sr in sentiment_results:
                sentiment_map[sr.get("title", "")] = sr

        stock_data = {}

        for news in news_list:
            title = news.get("title", "")
            title_lower = title.lower()

            # 获取该新闻的情绪
            news_sentiment = sentiment_map.get(title, {})

            for stock in self.stock_mappings:
                stock_name = stock.get("name", "")
                keywords = stock.get("keywords", [])

                # 检查是否匹配任一关键词
                matched = any(kw.lower() in title_lower for kw in keywords)

                if matched:
                    if stock_name not in stock_data:
                        stock_data[stock_name] = {
                            "name": stock_name,
                            "code": stock.get("code", ""),
                            "market": stock.get("market", ""),
                            "count": 0,
                            "news": [],
                            "sentiments": {"positive": 0, "negative": 0, "neutral": 0},
                        }

                    stock_data[stock_name]["count"] += 1
                    stock_data[stock_name]["news"].append({
                        "title": title,
                        "sentiment": news_sentiment.get("sentiment", "neutral"),
                        "score": news_sentiment.get("score", 0.5),
                        "source_name": news.get("source_name", ""),
                    })

                    # 统计情绪
                    sentiment = news_sentiment.get("sentiment", "neutral")
                    if sentiment in stock_data[stock_name]["sentiments"]:
                        stock_data[stock_name]["sentiments"][sentiment] += 1

        return stock_data

    def get_bullish_stocks(self, stock_data: Dict, min_count: int = 2) -> List[Dict]:
        """获取利好股票列表"""
        bullish_stocks = []

        for stock_name, data in stock_data.items():
            if data["count"] < min_count:
                continue

            sentiments = data["sentiments"]
            total = sum(sentiments.values())

            if total == 0:
                continue

            # 计算情绪倾向
            positive_ratio = sentiments["positive"] / total
            negative_ratio = sentiments["negative"] / total

            # 判断利好/利空
            if positive_ratio > 0.5:
                trend = "bullish"
                trend_cn = "利好"
            elif negative_ratio > 0.5:
                trend = "bearish"
                trend_cn = "利空"
            else:
                trend = "neutral"
                trend_cn = "中性"

            bullish_stocks.append({
                "name": stock_name,
                "code": data["code"],
                "market": data["market"],
                "count": data["count"],
                "trend": trend,
                "trend_cn": trend_cn,
                "positive_ratio": round(positive_ratio * 100, 1),
                "negative_ratio": round(negative_ratio * 100, 1),
                "news": data["news"][:5],  # 只保留前 5 条新闻
            })

        # 按提及次数排序
        bullish_stocks.sort(key=lambda x: (-x["count"], -x["positive_ratio"]))
        return bullish_stocks


# ============================================================================
# 第十三部分：主分析器
# ============================================================================

class NewsAnalyzer:
    """新闻分析器 - 核心分析引擎"""

    # 模式策略配置
    MODE_STRATEGIES = {
        "incremental": {
            "mode_name": "增量模式",
            "description": "增量模式（只关注新增新闻，无新增时不推送）",
            "realtime_report_type": "实时增量",
            "summary_report_type": "当日汇总",
            "should_send_realtime": True,
            "should_generate_summary": True,
            "summary_mode": "daily",
        },
        "current": {
            "mode_name": "当前榜单模式",
            "description": "当前榜单模式（当前榜单匹配新闻 + 新增新闻区域 + 按时推送）",
            "realtime_report_type": "实时当前榜单",
            "summary_report_type": "当前榜单汇总",
            "should_send_realtime": True,
            "should_generate_summary": True,
            "summary_mode": "current",
        },
        "daily": {
            "mode_name": "当日汇总模式",
            "description": "当日汇总模式（所有匹配新闻 + 新增新闻区域 + 按时推送）",
            "realtime_report_type": "",
            "summary_report_type": "当日汇总",
            "should_send_realtime": False,
            "should_generate_summary": True,
            "summary_mode": "daily",
        },
    }

    def __init__(self):
        self.request_interval = CONFIG["REQUEST_INTERVAL"]
        self.report_mode = CONFIG["REPORT_MODE"]
        self.rank_threshold = CONFIG["RANK_THRESHOLD"]
        self.is_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
        self.is_docker = self._detect_docker()
        self.update_info = None
        self.proxy_url = self._setup_proxy()
        self.data_fetcher = DataFetcher(self.proxy_url)

        # 初始化新的分析模块
        self.sentiment_analyzer = SentimentAnalyzer(CONFIG.get("SENTIMENT_ANALYSIS", {}))
        self.stock_analyzer = StockAnalyzer(CONFIG.get("STOCK_ANALYSIS", {}))

        if self.is_github_actions:
            self._check_version()

    def _detect_docker(self) -> bool:
        """检测 Docker 环境"""
        if os.environ.get("DOCKER_CONTAINER") == "true":
            return True
        return os.path.exists("/.dockerenv")

    def _setup_proxy(self) -> Optional[str]:
        """设置代理"""
        if self.is_github_actions:
            print("GitHub Actions 环境，不使用代理")
            return None

        if CONFIG["USE_PROXY"]:
            print("本地环境，使用代理")
            return CONFIG["DEFAULT_PROXY"]

        print("本地环境，未启用代理")
        return None

    def _check_version(self) -> None:
        """检查版本更新"""
        try:
            need_update, remote_version = check_version_update(
                VERSION, CONFIG["VERSION_CHECK_URL"], self.proxy_url
            )

            if need_update and remote_version:
                self.update_info = {
                    "current_version": VERSION,
                    "remote_version": remote_version,
                }
                print(f"发现新版本: {remote_version} (当前: {VERSION})")
            else:
                print("版本检查完成，当前为最新版本")
        except Exception as e:
            print(f"版本检查出错: {e}")

    def _get_mode_strategy(self) -> Dict:
        """获取当前模式策略"""
        return self.MODE_STRATEGIES.get(self.report_mode, self.MODE_STRATEGIES["daily"])

    def _has_webhook(self) -> bool:
        """检查是否配置了 webhook"""
        return any([
            CONFIG["FEISHU_WEBHOOK_URL"],
            CONFIG["DINGTALK_WEBHOOK_URL"],
            CONFIG["WEWORK_WEBHOOK_URL"],
            CONFIG["TELEGRAM_BOT_TOKEN"] and CONFIG["TELEGRAM_CHAT_ID"],
        ])

    def _has_valid_content(self, stats: List[Dict], new_titles: Optional[Dict] = None) -> bool:
        """检查是否有有效内容"""
        if self.report_mode in ["incremental", "current"]:
            return any(s["count"] > 0 for s in stats)

        has_matched = any(s["count"] > 0 for s in stats)
        has_new = bool(new_titles and any(len(t) > 0 for t in new_titles.values()))
        return has_matched or has_new

    def _load_analysis_data(self) -> Optional[Tuple]:
        """加载分析数据"""
        try:
            platform_ids = [p["id"] for p in CONFIG["PLATFORMS"]]
            print(f"当前监控平台: {platform_ids}")

            all_results, id_to_name, title_info = read_all_today_titles(platform_ids)

            if not all_results:
                print("没有找到当天的数据")
                return None

            total = sum(len(t) for t in all_results.values())
            print(f"读取到 {total} 个标题（已按当前监控平台过滤）")

            new_titles = detect_latest_new_titles(platform_ids)
            word_groups, filter_words = load_frequency_words()

            return all_results, id_to_name, title_info, new_titles, word_groups, filter_words
        except Exception as e:
            print(f"数据加载失败: {e}")
            return None

    def _run_analysis(
        self,
        data: Dict,
        mode: str,
        title_info: Dict,
        new_titles: Dict,
        word_groups: List[Dict],
        filter_words: List[str],
        id_to_name: Dict,
        failed_ids: Optional[List] = None,
        is_daily_summary: bool = False,
    ) -> Tuple[List[Dict], str]:
        """运行分析流水线"""
        stats, total = count_word_frequency(
            data, word_groups, filter_words, id_to_name,
            title_info, self.rank_threshold, new_titles, mode=mode
        )

        # 收集所有匹配的新闻用于分析
        all_matched_news = []
        for stat in stats:
            for title_data in stat.get("titles", []):
                all_matched_news.append({
                    "title": title_data.get("title", ""),
                    "source_name": title_data.get("source_name", ""),
                    "url": title_data.get("url", ""),
                })

        # 情绪分析
        sentiment_results = []
        sentiment_summary = None
        if all_matched_news and self.sentiment_analyzer.enabled:
            print(f"开始情绪分析 ({len(all_matched_news)} 条新闻)...")
            sentiment_results = self.sentiment_analyzer.analyze_batch(all_matched_news)
            sentiment_summary = self.sentiment_analyzer.get_sentiment_summary(sentiment_results)
            print(f"情绪分析完成: 正面 {sentiment_summary['positive']}, 负面 {sentiment_summary['negative']}, 中性 {sentiment_summary['neutral']}")

        # 股票板块分析
        stock_analysis = []
        if all_matched_news and self.stock_analyzer.enabled:
            print("开始板块关联分析...")
            stock_data = self.stock_analyzer.analyze(all_matched_news, sentiment_results)
            stock_analysis = self.stock_analyzer.get_bullish_stocks(stock_data, min_count=1)
            print(f"板块分析完成: 关联 {len(stock_analysis)} 个板块")

        # 生成 HTML 报告（包含新的分析结果）
        html_file = generate_html_report(
            stats, total, failed_ids, new_titles, id_to_name,
            mode, is_daily_summary,
            sentiment_summary=sentiment_summary,
            stock_analysis=stock_analysis,
        )

        # 保存分析结果供消息推送使用
        self._last_analysis_results = {
            "sentiment_summary": sentiment_summary,
            "stock_analysis": stock_analysis,
        }

        return stats, html_file

    def _send_notification(
        self,
        stats: List[Dict],
        report_type: str,
        mode: str,
        failed_ids: Optional[List] = None,
        new_titles: Optional[Dict] = None,
        id_to_name: Optional[Dict] = None,
    ) -> bool:
        """发送通知"""
        has_webhook = self._has_webhook()

        # 获取分析结果
        analysis_summary = getattr(self, '_last_analysis_results', None)

        if CONFIG["ENABLE_NOTIFICATION"] and has_webhook and self._has_valid_content(stats, new_titles):
            send_to_webhooks(
                stats, failed_ids or [], report_type, new_titles,
                id_to_name, self.update_info, self.proxy_url, mode,
                analysis_summary=analysis_summary
            )
            return True

        if CONFIG["ENABLE_NOTIFICATION"] and not has_webhook:
            print("⚠️ 警告：通知功能已启用但未配置 webhook URL，将跳过通知发送")
        elif not CONFIG["ENABLE_NOTIFICATION"]:
            print(f"跳过{report_type}通知：通知功能已禁用")
        elif not self._has_valid_content(stats, new_titles):
            strategy = self._get_mode_strategy()
            print(f"跳过通知：{strategy['mode_name']}下未检测到匹配的新闻")

        return False

    def _generate_summary(self, mode: str, send_notification: bool = False) -> Optional[str]:
        """生成汇总报告"""
        summary_type = "当前榜单汇总" if mode == "current" else "当日汇总"
        print(f"生成{summary_type}{'报告' if send_notification else 'HTML'}...")

        data = self._load_analysis_data()
        if not data:
            return None

        all_results, id_to_name, title_info, new_titles, word_groups, filter_words = data

        stats, html_file = self._run_analysis(
            all_results, mode, title_info, new_titles,
            word_groups, filter_words, id_to_name, is_daily_summary=True
        )

        print(f"{summary_type}{'报告' if send_notification else 'HTML'}已生成: {html_file}")

        if send_notification:
            strategy = self._get_mode_strategy()
            self._send_notification(
                stats, strategy["summary_report_type"], mode,
                new_titles=new_titles, id_to_name=id_to_name
            )

        return html_file

    def run(self) -> None:
        """执行分析流程"""
        try:
            self._init_and_check()
            strategy = self._get_mode_strategy()
            results, id_to_name, failed_ids = self._crawl()
            self._execute_strategy(strategy, results, id_to_name, failed_ids)
        except Exception as e:
            print(f"分析流程执行出错: {e}")
            raise

    def _init_and_check(self) -> None:
        """初始化和检查配置"""
        now = get_beijing_time()
        print(f"当前北京时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        if not CONFIG["ENABLE_CRAWLER"]:
            print("爬虫功能已禁用（ENABLE_CRAWLER=False），程序退出")
            return

        has_webhook = self._has_webhook()
        if not CONFIG["ENABLE_NOTIFICATION"]:
            print("通知功能已禁用（ENABLE_NOTIFICATION=False），将只进行数据抓取")
        elif not has_webhook:
            print("未配置任何 webhook URL，将只进行数据抓取，不发送通知")
        else:
            print("通知功能已启用，将发送 webhook 通知")

        strategy = self._get_mode_strategy()
        print(f"报告模式: {self.report_mode}")
        print(f"运行模式: {strategy['description']}")

    def _crawl(self) -> Tuple[Dict, Dict, List]:
        """执行爬取"""
        ids = [
            (p["id"], p["name"]) if "name" in p else p["id"]
            for p in CONFIG["PLATFORMS"]
        ]

        print(f"配置的监控平台: {[p.get('name', p['id']) for p in CONFIG['PLATFORMS']]}")
        print(f"开始爬取数据，请求间隔 {self.request_interval} 毫秒")
        ensure_directory_exists("output")

        results, id_to_name, failed_ids = self.data_fetcher.crawl_websites(
            ids, self.request_interval
        )

        title_file = save_titles_to_file(results, id_to_name, failed_ids)
        print(f"标题已保存到: {title_file}")

        return results, id_to_name, failed_ids

    def _execute_strategy(
        self,
        strategy: Dict,
        results: Dict,
        id_to_name: Dict,
        failed_ids: List
    ) -> None:
        """执行模式策略"""
        platform_ids = [p["id"] for p in CONFIG["PLATFORMS"]]
        new_titles = detect_latest_new_titles(platform_ids)
        word_groups, filter_words = load_frequency_words()

        # current 模式使用完整历史数据
        if self.report_mode == "current":
            data = self._load_analysis_data()
            if data:
                all_results, hist_id_to_name, hist_title_info, hist_new_titles, _, _ = data
                print(f"current 模式：使用过滤后的历史数据，包含平台：{list(all_results.keys())}")

                stats, html_file = self._run_analysis(
                    all_results, self.report_mode, hist_title_info, hist_new_titles,
                    word_groups, filter_words, hist_id_to_name, failed_ids
                )

                print(f"HTML 报告已生成: {html_file}")

                if strategy["should_send_realtime"]:
                    combined_names = {**hist_id_to_name, **id_to_name}
                    self._send_notification(
                        stats, strategy["realtime_report_type"], self.report_mode,
                        failed_ids, hist_new_titles, combined_names
                    )
            else:
                raise RuntimeError("数据一致性检查失败：保存后立即读取失败")
        else:
            # 其他模式
            time_info = format_time_filename()
            title_info = self._build_title_info(results, time_info)

            stats, html_file = self._run_analysis(
                results, self.report_mode, title_info, new_titles,
                word_groups, filter_words, id_to_name, failed_ids
            )

            print(f"HTML 报告已生成: {html_file}")

            if strategy["should_send_realtime"]:
                self._send_notification(
                    stats, strategy["realtime_report_type"], self.report_mode,
                    failed_ids, new_titles, id_to_name
                )

        # 生成汇总
        summary_html = None
        if strategy["should_generate_summary"]:
            send_notif = not strategy["should_send_realtime"]
            summary_html = self._generate_summary(strategy["summary_mode"], send_notif)

        # 打开浏览器
        self._open_browser(html_file, summary_html)

    def _build_title_info(self, results: Dict, time_info: str) -> Dict:
        """构建标题信息"""
        title_info = {}
        for source_id, titles_data in results.items():
            title_info[source_id] = {}
            for title, data in titles_data.items():
                title_info[source_id][title] = {
                    "first_time": time_info,
                    "last_time": time_info,
                    "count": 1,
                    **data,
                }
        return title_info

    def _open_browser(self, html_file: str, summary_html: Optional[str]) -> None:
        """打开浏览器"""
        should_open = not self.is_github_actions and not self.is_docker

        if should_open and html_file:
            target = summary_html or html_file
            file_url = "file://" + str(Path(target).resolve())
            print(f"正在打开{'汇总报告' if summary_html else 'HTML 报告'}: {file_url}")
            webbrowser.open(file_url)
        elif self.is_docker and html_file:
            target = summary_html or html_file
            print(f"{'汇总报告' if summary_html else 'HTML 报告'}已生成（Docker 环境）: {target}")


# ============================================================================
# 入口点
# ============================================================================

def main():
    """程序入口"""
    try:
        analyzer = NewsAnalyzer()
        analyzer.run()
    except FileNotFoundError as e:
        print(f"❌ 配置文件错误: {e}")
        print("\n请确保以下文件存在:")
        print("  • config/config.yaml")
        print("  • config/frequency_words.txt")
        print("\n参考项目文档进行正确配置")
    except Exception as e:
        print(f"❌ 程序运行错误: {e}")
        raise


if __name__ == "__main__":
    main()
