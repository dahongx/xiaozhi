#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
气象数据模拟发送器
持续运行，每小时自动生成模拟气象数据并存入数据库
- 自动补全缺失的历史数据
- 智能模拟真实气象变化趋势
- 自动清理30天前的旧数据
"""
import sys
import os
import random
import math
import time
import argparse
import sqlite3
from datetime import datetime, timedelta


def get_db_path():
    """获取数据库路径，支持开发环境和打包环境"""
    # 检查是否是打包后的环境
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后，使用 EXE 所在目录的上级 data 目录（共享）
        exe_dir = os.path.dirname(sys.executable)
        parent_dir = os.path.dirname(exe_dir)
        shared_db = os.path.join(parent_dir, "data", "meteo_data.db")
        # 确保目录存在
        os.makedirs(os.path.dirname(shared_db), exist_ok=True)
        return shared_db
    else:
        # 开发环境
        return os.path.join(os.path.dirname(__file__), "..", "data", "meteo_data.db")


# 数据库路径
DB_PATH = get_db_path()


# 判断是否打包环境，避免导入复杂依赖
if getattr(sys, 'frozen', False):
    # 打包环境：使用简化版本，不依赖主项目模块
    def save_meteo_data(data: dict):
        """保存气象数据到数据库（简化版）
        
        Args:
            data: 包含以下字段的字典:
                - station_id: 站点ID
                - obs_time: 观测时间 (datetime 或字符串)
                - elements: 气象要素字典，格式为 {element_code: {"value": ..., "qc_code": ...}}
        """
        station_id = data.get('station_id', 'LOCAL')
        obs_time = data.get('obs_time')
        elements = data.get('elements', {})
        
        # 如果是 datetime 对象，转换为字符串
        if hasattr(obs_time, 'strftime'):
            obs_time = obs_time.strftime('%Y-%m-%d %H:%M:%S')
        
        with sqlite3.connect(DB_PATH) as conn:
            # 遍历每个气象要素并保存
            for element_code, element_data in elements.items():
                value = element_data.get('value')
                qc_code = element_data.get('qc_code', 0)
                
                conn.execute("""
                    INSERT OR REPLACE INTO meteo_data 
                    (station_id, obs_time, element_code, value, qc_code) 
                    VALUES (?, ?, ?, ?, ?)
                """, (station_id, obs_time, element_code, value, qc_code))
            conn.commit()
    
    def init_database():
        """初始化数据库（简化版）"""
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS meteo_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    station_id TEXT DEFAULT 'LOCAL',
                    obs_time TEXT NOT NULL,
                    element_code TEXT NOT NULL,
                    value REAL,
                    qc_code INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(station_id, obs_time, element_code)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_time ON meteo_data(obs_time)")
            conn.commit()
        print(f"✓ 数据库已初始化: {DB_PATH}")
else:
    # 开发环境：添加项目路径并使用完整版本
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from plugins_func.functions.get_meteo_data import save_meteo_data, init_database

# 数据保留天数
RETENTION_DAYS = 30

# 日志文件路径 - 支持打包环境
def get_log_dir():
    """获取日志目录"""
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        parent_dir = os.path.dirname(exe_dir)
        return os.path.join(parent_dir, "logs")
    else:
        return os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs")

LOG_DIR = get_log_dir()
LOG_FILE = os.path.join(LOG_DIR, "simulator.log")
ERR_FILE = os.path.join(LOG_DIR, "simulator_err.log")

# 全局日志文件句柄
_log_file = None
_err_file = None


def setup_logging(daemon_mode=False):
    """设置日志输出"""
    global _log_file, _err_file

    if daemon_mode:
        # 守护进程模式：输出到文件
        os.makedirs(LOG_DIR, exist_ok=True)
        _log_file = open(LOG_FILE, 'a', encoding='utf-8', buffering=1)  # 行缓冲
        _err_file = open(ERR_FILE, 'a', encoding='utf-8', buffering=1)
        sys.stdout = _log_file
        sys.stderr = _err_file
    else:
        # 单次运行模式：输出到控制台
        if sys.platform == 'win32':
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def cleanup_logging():
    """清理日志文件句柄"""
    global _log_file, _err_file
    if _log_file:
        _log_file.close()
    if _err_file:
        _err_file.close()


def get_latest_data_time():
    """获取数据库中最新的数据时间"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                SELECT obs_time 
                FROM meteo_data 
                WHERE obs_time LIKE '____-__-__ __:__:__'
                ORDER BY obs_time DESC 
                LIMIT 1
            """)
            result = cursor.fetchone()
            if result:
                return datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"⚠️  获取最新数据时间失败: {e}")
    return None


def get_previous_hour_data():
    """获取上一小时的数据（用于连续变化）"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                SELECT element_code, value
                FROM meteo_data 
                WHERE obs_time LIKE '____-__-__ __:__:__'
                ORDER BY obs_time DESC 
                LIMIT 8
            """)
            results = cursor.fetchall()
            if results:
                return {code: value for code, value in results}
    except Exception as e:
        print(f"⚠️  获取上一小时数据失败: {e}")
    return None


def simulate_temperature(hour, previous_temp=None, base_temp=15):
    """
    模拟温度
    - 如果有上一小时数据，在其基础上小幅变化
    - 否则使用昼夜周期模拟
    """
    if previous_temp is not None:
        # 基于上一小时温度变化 ±2度
        change = random.uniform(-2, 2)
        # 添加昼夜趋势：白天升温，夜间降温
        if 6 <= hour <= 14:
            change += random.uniform(0, 0.5)  # 白天倾向升温
        elif 18 <= hour <= 23 or 0 <= hour <= 5:
            change -= random.uniform(0, 0.5)  # 夜间倾向降温
        
        new_temp = previous_temp + change
        return round(max(0, min(40, new_temp)), 1)  # 限制在0-40度
    else:
        # 首次运行，使用正弦波模拟昼夜变化
        phase = (hour - 5) / 24 * 2 * math.pi
        variation = 8 * math.sin(phase)
        noise = random.uniform(-2, 2)
        return round(base_temp + variation + noise, 1)


def simulate_humidity(hour, previous_humidity=None):
    """模拟湿度"""
    if previous_humidity is not None:
        change = random.uniform(-5, 5)
        new_humidity = previous_humidity + change
        return round(max(30, min(95, new_humidity)), 1)
    else:
        phase = (hour - 6) / 24 * 2 * math.pi
        variation = -15 * math.sin(phase)
        base = 60
        noise = random.uniform(-5, 5)
        humidity = base + variation + noise
        return round(max(30, min(95, humidity)), 1)


def simulate_pressure(previous_pressure=None):
    """模拟气压"""
    if previous_pressure is not None:
        change = random.uniform(-2, 2)
        new_pressure = previous_pressure + change
        return round(max(990, min(1030, new_pressure)), 1)
    else:
        base = 1013
        variation = random.uniform(-10, 10)
        return round(base + variation, 1)


def simulate_wind_speed(hour, previous_wind=None):
    """模拟风速"""
    if previous_wind is not None:
        change = random.uniform(-1, 1)
        new_wind = previous_wind + change
        return round(max(0, min(20, new_wind)), 1)
    else:
        if 6 <= hour <= 18:
            return round(random.uniform(2, 8), 1)
        else:
            return round(random.uniform(0.5, 4), 1)


def simulate_wind_direction(previous_direction=None):
    """模拟风向"""
    if previous_direction is not None:
        change = random.uniform(-30, 30)
        new_direction = (previous_direction + change) % 360
        return round(new_direction, 0)
    else:
        common_directions = [0, 45, 90, 135, 180, 225, 270, 315]
        base = random.choice(common_directions)
        variation = random.uniform(-20, 20)
        direction = (base + variation) % 360
        return round(direction, 0)


def simulate_precipitation(hour):
    """模拟降水量"""
    if random.random() < 0.9:
        return 0.0
    else:
        return round(random.uniform(0.1, 5.0), 1)


def simulate_visibility():
    """模拟能见度"""
    if random.random() < 0.8:
        return 30000
    else:
        return random.randint(5000, 20000)


def simulate_uv_index(hour):
    """模拟紫外线强度"""
    if hour < 6 or hour > 18:
        return 0.0
    else:
        phase = (hour - 6) / 12 * math.pi
        intensity = 20 * math.sin(phase)
        noise = random.uniform(-2, 2)
        return round(max(0, intensity + noise), 2)


def generate_data_for_time(obs_time, previous_data=None):
    """
    生成指定时间的气象数据

    Args:
        obs_time: 观测时间
        previous_data: 上一小时的数据（用于连续变化）

    Returns:
        数据字典
    """
    hour = obs_time.hour

    # 如果有上一小时数据，基于它进行变化
    prev_temp = previous_data.get("TEMPA") if previous_data else None
    prev_humidity = previous_data.get("HUMIA") if previous_data else None
    prev_pressure = previous_data.get("PRESA") if previous_data else None
    prev_wind = previous_data.get("WSPDA") if previous_data else None
    prev_direction = previous_data.get("WDIRA") if previous_data else None

    return {
        "station_id": "SH001",
        "obs_time": obs_time.strftime("%Y-%m-%d %H:%M:%S"),
        "elements": {
            "TEMPA": {"value": simulate_temperature(hour, prev_temp), "qc_code": 0},
            "HUMIA": {"value": simulate_humidity(hour, prev_humidity), "qc_code": 0},
            "PRESA": {"value": simulate_pressure(prev_pressure), "qc_code": 0},
            "WSPDA": {"value": simulate_wind_speed(hour, prev_wind), "qc_code": 0},
            "WDIRA": {"value": simulate_wind_direction(prev_direction), "qc_code": 0},
            "PRECA": {"value": simulate_precipitation(hour), "qc_code": 0},
            "VISIA": {"value": simulate_visibility(), "qc_code": 0},
            "UVRAA": {"value": simulate_uv_index(hour), "qc_code": 0},
        }
    }


def fill_missing_data(start_time, end_time):
    """
    补全缺失的历史数据

    Args:
        start_time: 开始时间（不包含）
        end_time: 结束时间（包含）
    """
    print(f"\n📊 开始补全数据：{start_time.strftime('%Y-%m-%d %H:%M')} 到 {end_time.strftime('%Y-%m-%d %H:%M')}")

    current_time = start_time + timedelta(hours=1)
    count = 0

    while current_time <= end_time:
        # 获取上一小时数据（用于连续变化）
        previous_data = get_previous_hour_data()

        # 生成数据
        data = generate_data_for_time(current_time, previous_data)
        save_meteo_data(data)

        count += 1
        if count % 24 == 0:
            print(f"  ✓ 已补全 {count} 小时数据（当前：{current_time.strftime('%Y-%m-%d %H:%M')}）")

        current_time += timedelta(hours=1)

    print(f"✅ 补全完成！共补全 {count} 小时数据\n")
    return count


def cleanup_old_data(days=RETENTION_DAYS):
    """
    清理旧数据，只保留最近N天

    Args:
        days: 保留天数
    """
    cutoff_time = datetime.now() - timedelta(days=days)
    cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:%M:%S")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                DELETE FROM meteo_data
                WHERE obs_time < ? AND obs_time LIKE '____-__-__ __:__:__'
            """, (cutoff_str,))
            deleted = cursor.rowcount

            if deleted > 0:
                print(f"🗑️  清理旧数据：删除 {deleted} 条记录（{days}天前的数据）")

            return deleted
    except Exception as e:
        print(f"⚠️  清理旧数据失败: {e}")
        return 0


def generate_current_hour_data():
    """生成当前整点的数据"""
    current_time = datetime.now().replace(minute=0, second=0, microsecond=0)

    # 获取上一小时数据
    previous_data = get_previous_hour_data()

    # 生成数据
    data = generate_data_for_time(current_time, previous_data)
    save_meteo_data(data)

    print(f"✅ [{current_time.strftime('%Y-%m-%d %H:%M')}] 数据已生成并保存")

    return current_time


def run_once():
    """运行一次：补全缺失数据 + 生成当前数据 + 清理旧数据"""
    setup_logging(daemon_mode=False)

    print("=" * 60)
    print("气象数据模拟发送器 - 单次运行模式")
    print("=" * 60)

    # 初始化数据库
    init_database()

    # 获取最新数据时间
    latest_time = get_latest_data_time()
    current_time = datetime.now().replace(minute=0, second=0, microsecond=0)

    if latest_time:
        print(f"📅 数据库最新数据: {latest_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"📅 当前时间: {current_time.strftime('%Y-%m-%d %H:%M')}")

        # 如果有缺失数据，补全
        if latest_time < current_time:
            fill_missing_data(latest_time, current_time)
        else:
            print("✓ 数据已是最新，无需补全\n")
    else:
        print("⚠️  数据库为空，生成当前数据")
        generate_current_hour_data()

    # 清理旧数据
    cleanup_old_data(RETENTION_DAYS)

    print("=" * 60)
    print("✅ 运行完成！")
    print("=" * 60)


def run_daemon():
    """守护进程模式：持续运行，每小时自动生成数据"""
    setup_logging(daemon_mode=True)

    print("=" * 60)
    print("气象数据模拟发送器 - 守护进程模式")
    print("=" * 60)
    print("⏰ 程序将持续运行，每小时自动生成数据")
    print("⏹️  按 Ctrl+C 停止程序")
    print("=" * 60)

    # 初始化数据库
    init_database()

    # 首次运行：补全缺失数据
    latest_time = get_latest_data_time()
    current_time = datetime.now().replace(minute=0, second=0, microsecond=0)

    if latest_time:
        print(f"\n📅 数据库最新数据: {latest_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"📅 当前时间: {current_time.strftime('%Y-%m-%d %H:%M')}")

        if latest_time < current_time:
            fill_missing_data(latest_time, current_time)
    else:
        print("\n⚠️  数据库为空，生成当前数据")
        generate_current_hour_data()

    # 清理旧数据
    cleanup_old_data(RETENTION_DAYS)

    print("\n" + "=" * 60)
    print("🔄 进入循环模式，等待下一个整点...")
    print("=" * 60 + "\n")

    try:
        while True:
            now = datetime.now()
            current_hour = now.replace(minute=0, second=0, microsecond=0)
            next_hour = current_hour + timedelta(hours=1)

            # 计算距离下一个整点的秒数
            seconds_until_next_hour = (next_hour - now).total_seconds()

            # 如果已经过了当前整点，立即生成数据
            if seconds_until_next_hour > 3600:
                print(f"⏰ [{now.strftime('%H:%M:%S')}] 生成当前整点数据...")
                generate_current_hour_data()
                cleanup_old_data(RETENTION_DAYS)

                # 重新计算等待时间
                now = datetime.now()
                current_hour = now.replace(minute=0, second=0, microsecond=0)
                next_hour = current_hour + timedelta(hours=1)
                seconds_until_next_hour = (next_hour - now).total_seconds()

            # 显示等待信息
            wait_minutes = int(seconds_until_next_hour / 60)
            print(f"⏳ [{now.strftime('%H:%M:%S')}] 等待下一个整点（{next_hour.strftime('%H:%M')}），还需 {wait_minutes} 分钟...")

            # 等待到下一个整点（提前5秒唤醒，避免错过）
            time.sleep(max(1, seconds_until_next_hour - 5))

            # 等待到整点
            while datetime.now().minute != 0:
                time.sleep(1)

            # 生成数据
            print(f"\n⏰ [{datetime.now().strftime('%H:%M:%S')}] 整点到达，开始生成数据...")
            generate_current_hour_data()

            # 每天凌晨清理一次旧数据
            if datetime.now().hour == 0:
                cleanup_old_data(RETENTION_DAYS)

            print()

    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("⏹️  程序已停止")
        print("=" * 60)
    finally:
        cleanup_logging()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="气象数据模拟发送器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行模式:
  --once      单次运行：补全缺失数据 + 生成当前数据 + 清理旧数据（适合定时任务）
  --daemon    守护进程：持续运行，每小时自动生成数据（适合后台运行）

示例:
  python meteo_data_simulator.py --once          # 单次运行
  python meteo_data_simulator.py --daemon        # 持续运行
        """
    )

    parser.add_argument(
        "--mode",
        choices=["once", "daemon"],
        default="daemon",
        help="运行模式（默认: daemon）"
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="单次运行模式（等同于 --mode once）"
    )

    parser.add_argument(
        "--daemon",
        action="store_true",
        help="守护进程模式（等同于 --mode daemon）"
    )

    args = parser.parse_args()

    # 处理参数
    if args.once:
        mode = "once"
    elif args.daemon:
        mode = "daemon"
    else:
        mode = args.mode

    # 运行
    if mode == "once":
        run_once()
    else:
        run_daemon()


if __name__ == "__main__":
    main()

