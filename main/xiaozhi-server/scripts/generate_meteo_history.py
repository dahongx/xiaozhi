"""
气象历史数据生成器
生成最近30天的模拟气象数据，每小时一条记录
模拟真实的气象变化趋势（温度有昼夜波动）
"""
import sys
import os
import random
import math
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugins_func.functions.get_meteo_data import save_meteo_data, init_database


def simulate_temperature(hour, base_temp=20):
    """
    模拟温度的昼夜变化
    - 凌晨4-6点最低
    - 下午2-4点最高
    - 使用正弦波模拟
    """
    # 正弦波：最低点在凌晨5点，最高点在下午3点
    phase = (hour - 5) / 24 * 2 * math.pi
    variation = 8 * math.sin(phase)  # 温差约16度
    noise = random.uniform(-2, 2)  # 随机波动
    return round(base_temp + variation + noise, 1)


def simulate_humidity(hour):
    """
    模拟湿度的昼夜变化
    - 早晨湿度较高
    - 下午湿度较低
    """
    phase = (hour - 6) / 24 * 2 * math.pi
    variation = -15 * math.sin(phase)  # 湿度变化
    base = 60
    noise = random.uniform(-5, 5)
    humidity = base + variation + noise
    return round(max(30, min(95, humidity)), 1)  # 限制在30-95%


def simulate_pressure():
    """模拟气压（相对稳定，小幅波动）"""
    base = 1013
    variation = random.uniform(-10, 10)
    return round(base + variation, 1)


def simulate_wind_speed(hour):
    """
    模拟风速
    - 白天风速较大
    - 夜间风速较小
    """
    if 6 <= hour <= 18:
        # 白天
        return round(random.uniform(2, 8), 1)
    else:
        # 夜间
        return round(random.uniform(0.5, 4), 1)


def simulate_wind_direction():
    """模拟风向（0-360度）"""
    # 常见风向：北(0)、东(90)、南(180)、西(270)
    common_directions = [0, 45, 90, 135, 180, 225, 270, 315]
    base = random.choice(common_directions)
    variation = random.uniform(-20, 20)
    direction = (base + variation) % 360
    return round(direction, 0)


def simulate_precipitation(hour):
    """
    模拟降水量
    - 大部分时间无降水
    - 偶尔有降水
    """
    if random.random() < 0.9:  # 90%的时间无降水
        return 0.0
    else:
        return round(random.uniform(0.1, 5.0), 1)


def simulate_visibility():
    """模拟能见度"""
    # 大部分时间能见度良好
    if random.random() < 0.8:
        return 30000  # 30km
    else:
        return random.randint(5000, 20000)


def simulate_uv_index(hour):
    """
    模拟紫外线强度
    - 夜间为0
    - 中午最强
    """
    if hour < 6 or hour > 18:
        return 0.0
    else:
        # 使用正弦波模拟，中午12点最强
        phase = (hour - 6) / 12 * math.pi
        intensity = 20 * math.sin(phase)
        noise = random.uniform(-2, 2)
        return round(max(0, intensity + noise), 2)


def generate_hourly_data(obs_time, base_temp=20):
    """生成某个时间点的完整气象数据"""
    hour = obs_time.hour
    
    return {
        "station_id": "SH001",
        "obs_time": obs_time.strftime("%Y-%m-%d %H:%M:%S"),
        "elements": {
            "TEMPA": {"value": simulate_temperature(hour, base_temp), "qc_code": 0},
            "HUMIA": {"value": simulate_humidity(hour), "qc_code": 0},
            "PRESA": {"value": simulate_pressure(), "qc_code": 0},
            "WSPDA": {"value": simulate_wind_speed(hour), "qc_code": 0},
            "WDIRA": {"value": simulate_wind_direction(), "qc_code": 0},
            "PRECA": {"value": simulate_precipitation(hour), "qc_code": 0},
            "VISIA": {"value": simulate_visibility(), "qc_code": 0},
            "UVRAA": {"value": simulate_uv_index(hour), "qc_code": 0},
        }
    }


def generate_history_data(days=30):
    """
    生成历史数据
    
    Args:
        days: 生成多少天的历史数据
    """
    print("=" * 60)
    print("气象历史数据生成器")
    print("=" * 60)
    
    # 初始化数据库
    init_database()
    print("✓ 数据库初始化完成")
    
    # 计算起始时间（从days天前的整点开始）
    end_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(days=days)
    
    print(f"✓ 开始生成数据：{start_time.strftime('%Y-%m-%d %H:%M')} 到 {end_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"✓ 总计：{days} 天 × 24 小时 = {days * 24} 条记录")
    print()
    
    # 生成数据
    total_records = 0
    current_time = start_time
    
    # 基础温度随季节变化（这里简化处理）
    base_temp = 15  # 12月的基础温度
    
    while current_time <= end_time:
        # 生成该小时的数据
        data = generate_hourly_data(current_time, base_temp)
        save_meteo_data(data)
        
        total_records += 1
        
        # 每天显示一次进度
        if current_time.hour == 0:
            print(f"  [{current_time.strftime('%Y-%m-%d')}] 已生成 {total_records} 条记录")
        
        # 下一个小时
        current_time += timedelta(hours=1)
    
    print()
    print("=" * 60)
    print(f"✓ 数据生成完成！共生成 {total_records} 条记录")
    print("=" * 60)
    print()
    print("示例查询：")
    print("  - '现在温度多少？'")
    print("  - '昨天下午3点的温度是多少？'")
    print("  - '今天早上的湿度？'")
    print("  - '12月10号中午的风速？'")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="生成气象历史数据")
    parser.add_argument("--days", type=int, default=30, help="生成多少天的历史数据（默认30天）")
    
    args = parser.parse_args()
    
    generate_history_data(args.days)

