"""
测试脚本：向数据库插入气象测试数据
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from plugins_func.functions.get_meteo_data import (
    init_database, parse_meteo_string, save_meteo_data, get_latest_element, METEO_DICT, QC_CODE
)

# 测试数据（你提供的样本数据）
test_data_string = "SH001DATADICK,V202401,SH001,YISMO00,N01,OB,20251125144200,ACRAA,669,0,ACRAB,1.30,0,ACRAA_mmmax,671,0,ACRAA_mmmin,666,0,ACRAA_mmstd,1.4318,0,TIMEC,202511251429,0,EVAPA,/,/,EVAPB,/,/,TEMPA,12.5,0,TEMPA_mmstd,0.0580,0,HUMIA,45,0,PRESA,1013.2,0,WSPDA,3.5,0,WDIRA,180,0"

def main():
    print("=" * 50)
    print("气象数据测试工具")
    print("=" * 50)
    
    # 初始化数据库
    print("\n1. 初始化数据库...")
    init_database()
    print("   ✓ 数据库初始化完成")
    
    # 解析测试数据
    print("\n2. 解析测试数据...")
    parsed = parse_meteo_string(test_data_string)
    print(f"   站点ID: {parsed.get('station_id')}")
    print(f"   观测时间: {parsed.get('obs_time')}")
    print(f"   解析到 {len(parsed.get('elements', {}))} 个气象要素:")
    for code, elem in parsed.get("elements", {}).items():
        name = METEO_DICT.get(code, {}).get("name", code)
        unit = METEO_DICT.get(code, {}).get("unit", "")
        qc = QC_CODE.get(elem["qc_code"], "未知")
        print(f"      - {name}({code}): {elem['value']} {unit}, 质控: {qc}")
    
    # 保存到数据库
    print("\n3. 保存到数据库...")
    save_meteo_data(parsed)
    print("   ✓ 数据保存完成")
    
    # 查询验证
    print("\n4. 验证查询...")
    for code in ["TEMPA", "HUMIA", "PRESA", "WSPDA", "WDIRA"]:
        result = get_latest_element(code)
        if result:
            name = METEO_DICT.get(code, {}).get("name", code)
            unit = METEO_DICT.get(code, {}).get("unit", "")
            qc = QC_CODE.get(result["qc_code"], "未知")
            print(f"   ✓ {name}: {result['value']} {unit}, 状态: {qc}")
        else:
            print(f"   ✗ {code}: 无数据")
    
    print("\n" + "=" * 50)
    print("测试完成！现在可以启动服务并语音查询：")
    print('  "现在温度多少？"')
    print('  "湿度多少？"')
    print('  "风速多少？"')
    print("=" * 50)

if __name__ == "__main__":
    main()

