"""
气象数据查询插件 - 离线版
用于查询本地气象监测设备的实时数据
"""
import sqlite3
import os
import threading
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

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


# Function Call 描述
GET_METEO_DATA_DESC = {
    "type": "function",
    "function": {
        "name": "get_meteo_data",
        "description": "查询气象监测站的实时数据，如温度、湿度、风速、气压等。用户问温度多少、湿度多少、风速多少时调用此函数。",
        "parameters": {
            "type": "object",
            "properties": {
                "element": {
                    "type": "string",
                    "description": "要查询的气象要素，可选：温度、湿度、气压、风速、风向、降水量、能见度、紫外线",
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
def get_meteo_data(conn, element: str):
    """查询气象数据的主函数"""
    # 将用户输入映射到要素代码
    element_code = None
    for key, code in USER_INPUT_MAP.items():
        if key in element:
            element_code = code
            break

    if not element_code:
        msg = "抱歉，不支持查询" + element + "，目前支持查询：温度、湿度、气压、风速、风向、降水量、能见度、紫外线"
        return ActionResponse(Action.RESPONSE, msg, msg)

    # 获取最新数据
    data = get_latest_element(element_code)

    if not data:
        elem_name = METEO_DICT[element_code]['name']
        msg = "暂无" + elem_name + "数据，请确认数据采集程序是否正常运行"
        return ActionResponse(Action.RESPONSE, msg, msg)

    # 构建回复
    elem_info = METEO_DICT[element_code]
    qc_status = QC_CODE.get(data["qc_code"], "未知")

    response = f"当前{elem_info['name']}为 {data['value']} {elem_info['unit']}，数据状态：{qc_status}"

    return ActionResponse(Action.RESPONSE, response, response)


# 初始化数据库
init_database()

