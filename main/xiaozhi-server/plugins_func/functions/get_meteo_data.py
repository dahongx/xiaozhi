"""
气象数据查询插件 - 离线版
用于查询本地气象监测设备的实时数据
支持时间查询：昨天、今天、具体时间点等
"""
import sqlite3
import os
import threading
from datetime import datetime, timedelta
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

# 尝试导入dateparser，如果没有则使用简单的时间解析
try:
    import dateparser
    HAS_DATEPARSER = True
except ImportError:
    HAS_DATEPARSER = False
    print("警告: 未安装dateparser库，时间解析功能受限。建议安装: pip install dateparser")

TAG = __name__
logger = setup_logging()

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "meteo_data.db")

# 气象要素中英文映射
METEO_DICT = {
    "TEMPA": {"name": "温度", "unit": "℃"},
    "TEMPB": {"name": "温度B", "unit": "℃"},
    "HUMIA": {"name": "湿度", "unit": "%"},
    "PRESA": {"name": "气压", "unit": "hPa"},
    "WSPDA": {"name": "风速", "unit": "m/s"},
    "WDIRA": {"name": "风向", "unit": "°"},
    "PRECA": {"name": "降水量", "unit": "mm"},
    "VISIA": {"name": "能见度", "unit": "m"},
    "UVRAA": {"name": "紫外线强度", "unit": "W/m²"},
    "ACRAA": {"name": "辐射A", "unit": "W/m²"},
    "LERAA": {"name": "长波辐射", "unit": "W/m²"},
    "SDRAA": {"name": "散射辐射", "unit": "W/m²"},
    "SGRAA": {"name": "总辐射", "unit": "W/m²"},
    "STEMB": {"name": "土壤温度", "unit": "℃"},
}

# 质控码说明
QC_CODE = {
    0: "正常",
    1: "可疑",
    2: "错误",
    9: "缺测",
}

# 线程锁
_db_lock = threading.Lock()


def init_database():
    """初始化数据库"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meteo_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id TEXT,
                element_code TEXT,
                value REAL,
                qc_code INTEGER,
                obs_time TEXT,
                update_time TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_element ON meteo_data(element_code)")
        conn.commit()


def parse_meteo_string(data_string: str) -> dict:
    """解析气象数据字符串"""
    parts = data_string.split(",")
    if len(parts) < 7:
        return {}
    
    station_id = parts[2]  # SH001
    obs_time = parts[6]    # 20251125144200
    
    result = {"station_id": station_id, "obs_time": obs_time, "elements": {}}
    
    # 从第7个元素开始，每3个一组 [名称, 值, 质控码]
    i = 7
    while i + 2 < len(parts):
        code = parts[i]
        value = parts[i + 1]
        qc = parts[i + 2]
        
        if code in METEO_DICT and value != "/" and value != "":
            try:
                result["elements"][code] = {
                    "value": float(value),
                    "qc_code": int(qc) if qc.isdigit() else 0
                }
            except ValueError:
                pass
        i += 3
    
    return result


def save_meteo_data(data: dict):
    """保存气象数据到数据库"""
    with _db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for code, elem in data.get("elements", {}).items():
                # 使用 REPLACE 更新最新数据
                conn.execute("""
                    INSERT OR REPLACE INTO meteo_data 
                    (station_id, element_code, value, qc_code, obs_time, update_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (data["station_id"], code, elem["value"], elem["qc_code"], 
                      data["obs_time"], now))
            conn.commit()


def get_latest_element(element_code: str) -> dict:
    """获取最新的某个气象要素数据"""
    init_database()
    with _db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                SELECT value, qc_code, obs_time, update_time
                FROM meteo_data
                WHERE element_code = ?
                ORDER BY update_time DESC LIMIT 1
            """, (element_code,))
            row = cursor.fetchone()
            if row:
                return {"value": row[0], "qc_code": row[1], "obs_time": row[2], "update_time": row[3]}
    return None


def get_element_by_time(element_code: str, target_time: datetime, tolerance_hours=1) -> dict:
    """
    获取指定时间点的气象要素数据

    Args:
        element_code: 要素代码
        target_time: 目标时间
        tolerance_hours: 容差时间（小时），在目标时间前后tolerance_hours小时内查找最接近的数据

    Returns:
        数据字典或None
    """
    init_database()
    with _db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            # 计算时间范围
            time_start = (target_time - timedelta(hours=tolerance_hours)).strftime("%Y-%m-%d %H:%M:%S")
            time_end = (target_time + timedelta(hours=tolerance_hours)).strftime("%Y-%m-%d %H:%M:%S")
            target_time_str = target_time.strftime("%Y-%m-%d %H:%M:%S")

            # 查找时间范围内最接近的数据
            cursor = conn.execute("""
                SELECT value, qc_code, obs_time, update_time,
                       ABS(JULIANDAY(obs_time) - JULIANDAY(?)) as time_diff
                FROM meteo_data
                WHERE element_code = ?
                  AND obs_time BETWEEN ? AND ?
                ORDER BY time_diff ASC
                LIMIT 1
            """, (target_time_str, element_code, time_start, time_end))

            row = cursor.fetchone()
            if row:
                return {
                    "value": row[0],
                    "qc_code": row[1],
                    "obs_time": row[2],
                    "update_time": row[3],
                    "time_diff_hours": row[4] * 24  # 转换为小时
                }
    return None


def parse_time_expression(text: str) -> datetime:
    """
    解析时间表达式（增强版，支持复杂中文时间）

    Args:
        text: 用户输入的文本

    Returns:
        解析出的datetime对象，如果解析失败返回None
    """
    import re

    now = datetime.now()
    text = text.strip()

    # 1. 提取基准日期（今天、昨天、前天、具体日期）
    base_date = None

    # 今天/现在
    if "今天" in text or "今日" in text or "现在" in text or "当前" in text:
        base_date = now

    # 昨天
    elif "昨天" in text or "昨日" in text:
        base_date = now - timedelta(days=1)

    # 前天
    elif "前天" in text:
        base_date = now - timedelta(days=2)

    # N天前
    elif re.search(r'(\d+)\s*天前', text):
        match = re.search(r'(\d+)\s*天前', text)
        days = int(match.group(1))
        base_date = now - timedelta(days=days)

    # N小时前（直接返回）
    elif re.search(r'(\d+)\s*小时前', text):
        match = re.search(r'(\d+)\s*小时前', text)
        hours = int(match.group(1))
        return now - timedelta(hours=hours)

    # 具体日期：12月10号、12月10日、12-10
    elif re.search(r'(\d+)\s*月\s*(\d+)\s*[号日]?', text):
        match = re.search(r'(\d+)\s*月\s*(\d+)\s*[号日]?', text)
        month = int(match.group(1))
        day = int(match.group(2))
        year = now.year
        # 如果月份大于当前月份，说明是去年
        if month > now.month:
            year -= 1
        try:
            base_date = datetime(year, month, day)
        except ValueError:
            return None

    # 上周X
    elif "上周" in text or "上星期" in text:
        weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
        for cn, num in weekday_map.items():
            if cn in text:
                days_ago = (now.weekday() - num) % 7 + 7
                base_date = now - timedelta(days=days_ago)
                break
        if base_date is None:
            base_date = now - timedelta(days=7)

    # 如果没有找到基准日期，尝试用dateparser
    if base_date is None and HAS_DATEPARSER:
        parsed = dateparser.parse(
            text,
            languages=['zh'],
            settings={
                'TIMEZONE': 'Asia/Shanghai',
                'RETURN_AS_TIMEZONE_AWARE': False,
                'PREFER_DATES_FROM': 'past'
            }
        )
        if parsed:
            return parsed
        return None

    if base_date is None:
        return None

    # 2. 提取具体时间（小时）
    hour = None
    minute = 0

    # 时间段映射
    time_period_map = {
        "凌晨": 4, "早上": 8, "早晨": 8, "上午": 10,
        "中午": 12, "下午": 15, "傍晚": 18, "晚上": 20, "夜里": 22
    }

    # 先检查是否有具体小时数
    # 匹配：3点、15点、三点
    hour_match = re.search(r'(\d+)\s*[点时]', text)
    if hour_match:
        hour = int(hour_match.group(1))
        # 如果有"下午"且小时<12，需要+12
        if ("下午" in text or "晚上" in text or "傍晚" in text) and hour < 12:
            hour += 12
    else:
        # 没有具体小时，检查时间段
        for period, default_hour in time_period_map.items():
            if period in text:
                hour = default_hour
                break

    # 3. 组合日期和时间
    if hour is not None:
        try:
            result = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return result
        except ValueError:
            return None
    else:
        # 只有日期，没有具体时间，返回当天的当前时刻
        return base_date.replace(hour=now.hour, minute=now.minute, second=0, microsecond=0)


# Function Call 描述
GET_METEO_DATA_DESC = {
    "type": "function",
    "function": {
        "name": "get_meteo_data",
        "description": "查询气象监测站的数据，支持实时和历史数据查询。用户问温度、湿度、风速、气压等，或询问某个时间点的气象数据时调用此函数。",
        "parameters": {
            "type": "object",
            "properties": {
                "element": {
                    "type": "string",
                    "description": "要查询的气象要素，可选：温度、湿度、气压、风速、风向、降水量、能见度、紫外线",
                },
                "time_query": {
                    "type": "string",
                    "description": "时间查询表达式，如：现在、今天、昨天、昨天下午3点、12月10号中午等。如果不指定则查询最新数据。",
                }
            },
            "required": ["element"],
        },
    },
}

# 用户输入到要素代码的映射
USER_INPUT_MAP = {
    "温度": "TEMPA", "气温": "TEMPA", "多少度": "TEMPA",
    "湿度": "HUMIA", "相对湿度": "HUMIA",
    "气压": "PRESA", "大气压": "PRESA",
    "风速": "WSPDA", "风": "WSPDA",
    "风向": "WDIRA",
    "降水": "PRECA", "降水量": "PRECA", "雨量": "PRECA",
    "能见度": "VISIA",
    "紫外线": "UVRAA",
}


@register_function("get_meteo_data", GET_METEO_DATA_DESC, ToolType.SYSTEM_CTL)
def get_meteo_data(conn, element: str, time_query: str = None):
    """
    查询气象数据的主函数

    Args:
        conn: 连接对象
        element: 气象要素（温度、湿度等）
        time_query: 时间查询表达式（可选）
    """
    # 将用户输入映射到要素代码
    element_code = None
    for key, code in USER_INPUT_MAP.items():
        if key in element:
            element_code = code
            break

    if not element_code:
        msg = "抱歉，不支持查询" + element + "，目前支持查询：温度、湿度、气压、风速、风向、降水量、能见度、紫外线"
        return ActionResponse(Action.RESPONSE, msg, msg)

    elem_info = METEO_DICT[element_code]

    # 如果有时间查询，解析时间
    if time_query:
        logger.bind(tag=TAG).info(f"时间查询: {time_query}")

        # 解析时间表达式
        target_time = parse_time_expression(time_query)

        if target_time is None:
            # 时间解析失败，返回None让LLM处理
            logger.bind(tag=TAG).warning(f"时间解析失败: {time_query}")
            return None

        logger.bind(tag=TAG).info(f"解析时间: {target_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 查询指定时间的数据
        data = get_element_by_time(element_code, target_time, tolerance_hours=2)

        if not data:
            msg = f"抱歉，没有找到{target_time.strftime('%Y年%m月%d日 %H点')}左右的{elem_info['name']}数据"
            return ActionResponse(Action.RESPONSE, msg, msg)

        # 构建回复（包含时间信息）
        qc_status = QC_CODE.get(data["qc_code"], "未知")
        obs_time_obj = datetime.strptime(data["obs_time"], "%Y-%m-%d %H:%M:%S")
        time_desc = obs_time_obj.strftime("%Y年%m月%d日 %H点")

        response = f"{time_desc}的{elem_info['name']}为 {data['value']} {elem_info['unit']}，数据状态：{qc_status}"

    else:
        # 查询最新数据
        data = get_latest_element(element_code)

        if not data:
            elem_name = METEO_DICT[element_code]['name']
            msg = "暂无" + elem_name + "数据，请确认数据采集程序是否正常运行"
            return ActionResponse(Action.RESPONSE, msg, msg)

        # 构建回复
        qc_status = QC_CODE.get(data["qc_code"], "未知")
        response = f"当前{elem_info['name']}为 {data['value']} {elem_info['unit']}，数据状态：{qc_status}"

    return ActionResponse(Action.RESPONSE, response, response)


# 初始化数据库
init_database()

