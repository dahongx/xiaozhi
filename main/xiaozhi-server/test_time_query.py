"""
测试时间查询功能
验证时间解析和数据查询是否正常工作
"""
import sys
import os
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from plugins_func.functions.get_meteo_data import (
    parse_time_expression,
    get_element_by_time,
    get_latest_element,
    init_database
)


def test_time_parsing():
    """测试时间解析功能"""
    print("=" * 60)
    print("测试时间解析功能")
    print("=" * 60)
    
    test_cases = [
        "现在",
        "今天",
        "昨天",
        "前天",
        "3小时前",
        "昨天下午3点",
        "今天早上8点",
        "12月10号中午",
        "上周一",
    ]
    
    for text in test_cases:
        parsed = parse_time_expression(text)
        if parsed:
            print(f"✓ '{text}' → {parsed.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"✗ '{text}' → 解析失败")
    
    print()


def test_data_query():
    """测试数据查询功能"""
    print("=" * 60)
    print("测试数据查询功能")
    print("=" * 60)
    
    init_database()
    
    # 测试1：查询最新数据
    print("\n1. 查询最新温度数据：")
    data = get_latest_element("TEMPA")
    if data:
        print(f"   ✓ 温度: {data['value']}℃")
        print(f"   ✓ 观测时间: {data['obs_time']}")
    else:
        print("   ✗ 无数据")
    
    # 测试2：查询昨天的数据
    print("\n2. 查询昨天的温度数据：")
    yesterday = datetime.now() - timedelta(days=1)
    data = get_element_by_time("TEMPA", yesterday, tolerance_hours=2)
    if data:
        print(f"   ✓ 温度: {data['value']}℃")
        print(f"   ✓ 观测时间: {data['obs_time']}")
        print(f"   ✓ 时间差: {data['time_diff_hours']:.2f}小时")
    else:
        print("   ✗ 无数据")
    
    # 测试3：查询3小时前的数据
    print("\n3. 查询3小时前的湿度数据：")
    three_hours_ago = datetime.now() - timedelta(hours=3)
    data = get_element_by_time("HUMIA", three_hours_ago, tolerance_hours=1)
    if data:
        print(f"   ✓ 湿度: {data['value']}%")
        print(f"   ✓ 观测时间: {data['obs_time']}")
        print(f"   ✓ 时间差: {data['time_diff_hours']:.2f}小时")
    else:
        print("   ✗ 无数据")
    
    print()


def test_full_query():
    """测试完整的查询流程（模拟用户输入）"""
    print("=" * 60)
    print("测试完整查询流程")
    print("=" * 60)
    
    test_queries = [
        ("现在温度多少？", "温度", "现在"),
        ("昨天下午3点的温度是多少？", "温度", "昨天下午3点"),
        ("今天早上的湿度？", "湿度", "今天早上"),
        ("3小时前的风速？", "风速", "3小时前"),
    ]
    
    for query, element, time_text in test_queries:
        print(f"\n用户问: {query}")
        
        # 解析时间
        target_time = parse_time_expression(time_text)
        if not target_time:
            print(f"  ✗ 时间解析失败")
            continue
        
        print(f"  → 解析时间: {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 映射要素
        element_map = {
            "温度": "TEMPA",
            "湿度": "HUMIA",
            "风速": "WSPDA",
        }
        element_code = element_map.get(element)
        
        # 查询数据
        if "现在" in time_text or "当前" in time_text:
            data = get_latest_element(element_code)
        else:
            data = get_element_by_time(element_code, target_time, tolerance_hours=2)
        
        if data:
            print(f"  ✓ 结果: {data['value']} (观测时间: {data['obs_time']})")
        else:
            print(f"  ✗ 无数据")
    
    print()


if __name__ == "__main__":
    print("\n")
    print("🧪 气象数据时间查询功能测试")
    print()
    
    # 测试1：时间解析
    test_time_parsing()
    
    # 测试2：数据查询
    test_data_query()
    
    # 测试3：完整流程
    test_full_query()
    
    print("=" * 60)
    print("✓ 测试完成")
    print("=" * 60)
    print()
    print("提示：如果看到很多'无数据'，请先运行数据生成脚本：")
    print("  python scripts/generate_meteo_history.py --days 30")
    print()

