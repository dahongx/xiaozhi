"""
气象数据接收器
用于接收和解析气象监测设备发送的数据，并存入数据库

使用方法:
1. 模拟测试数据: python meteo_data_receiver.py --test
2. 从串口接收:    python meteo_data_receiver.py --port COM3
3. 从文件读取:    python meteo_data_receiver.py --file data.txt
"""
import sys
import os
import argparse
import time

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugins_func.functions.get_meteo_data import parse_meteo_string, save_meteo_data, get_latest_element, init_database


def test_with_sample_data():
    """使用示例数据测试"""
    sample_data = """SH001DATADICK,V202401,SH001,YISMO00,N01,OB,20251125144200,ACRAA,669,0,ACRAB,1.30,0,ACRAA_mmmax,671,0,ACRAA_mmmin,666,0,ACRAA_mmstd,1.4318,0,TIMEC,202511251429,0,EVAPA,/,/,EVAPB,/,/,TEMPA,/,/,TEMPA_mmstd,/,/,TEMPA,/,/,TEMPA_mmstd,/,/,TEMPA,/,/,TEMPA_mmstd,/,/,TEMPA,12.5,0,TEMPA_mmstd,0.0580,0,HUMIA,/,/,HUMIA_mmstd,/,/,LERAA,397,0,LERAB,1.05,0,LERAA_mmmax,398,0,LERAA_mmmin,395,0,LERAA_mmstd,0.9214,0,TIMEC,202511251429,0,LSRAA,265,0,LSRAB,0.48,0,LSRAA_mmmax,266,0,LSRAA_mmmin,265,0,LSRAA_mmstd,0.4422,0,TIMEC,202511251429,0,PRECA,/,/,PRECA_p0accu,/,/,PRECA,0.0,0,PRECA_p0accu,0.0,0,PRECA,/,/,PRECA_p0accu,/,/,PRESA,/,/,PRESA_mmstd,/,/,SDRAA,601,0,SDRAB,1.11,0,SDRAA_mmmax,601,0,SDRAA_mmmin,600,0,SDRAA_mmstd,0.5000,0,TIMEC,202511251429,0,SGRAA,357,0,SGRAB,0.70,0,SGRAA_mmmax,358,0,SGRAA_mmmin,356,0,SGRAA_mmstd,0.7024,0,TIMEC,202511251429,0,SRRAA,106,0,SRRAB,0.20,0,SRRAA_mmmax,106,0,SRRAA_mmmin,106,0,SRRAA_mmstd,0.0000,0,TIMEC,202511251429,0,SSRAA,138,0,SSRAB,0.26,0,SSRAA_mmmax,139,0,SSRAA_mmmin,138,0,SSRAA_mmstd,0.4230,0,TIMEC,202511251429,0,STEMB,23.2,0,STEMB_mmstd,0.0441,0,STEMA,/,/,STEMB,/,/,STEMC,/,/,STEMD,/,/,STEME,/,/,STEMF,/,/,STEMG,/,/,STEMH,/,/,STEMI,/,/,STEMJ,/,/,UVRAA,16.17,0,UVRAE,0.032,0,UVRAA_mmmax,16.23,0,UVRAA_mmmin,16.11,0,UVRAA_mmstd,0.0342,0,TIMEC,202511251429,0,UVRAB,0.30,0,UVRAF,0.001,0,UVRAB_mmmax,0.30,0,UVRAB_mmmin,0.30,0,UVRAB_mmstd,0.0000,0,TIMEC,202511251429,0,VISIA,30000,0,VISIB,30000,0,WSPDA,/,/,WSPDB,/,/,WSPDC,/,/,WSPDD,/,/,WSPDE,/,/,WDIRA,/,/,WDIRB,/,/,WDIRC,/,/,WDIRD,/,/,WDIRE,/,/,WSPDA,3.0,0,WDIRA,253,0,WSPDB,3.2,0,WDIRB,240,0,WSPDC,3.0,0,WDIRC,231,0,WSPDD,2.9,0,WDIRD,241,0,WSPDE,3.9,0,WDIRE,240,0,TEMPB,13.6,0,WEATA,/,/,RDSDA,/,/,WEATA,00,9,SNOWA,/,/,PMPMA,/,/,PMPMB,/,/,PMPMC,/,/,PMPMD,/,/,CLODA,/,/,CLODC,/,/,CLODE,/,/,CLODF,/,/,CLODH,/,/,CLODI,/,/,CLODJ,/,/,z,0,6479,ED"""
    
    print("=" * 60)
    print("气象数据接收器 - 测试模式")
    print("=" * 60)
    
    # 初始化数据库
    init_database()
    print("✓ 数据库初始化完成")
    
    # 解析数据
    parsed = parse_meteo_string(sample_data)
    print(f"✓ 解析完成，站点: {parsed.get('station_id')}, 观测时间: {parsed.get('obs_time')}")
    print(f"✓ 解析到 {len(parsed.get('elements', {}))} 个有效要素")
    
    # 保存到数据库
    save_meteo_data(parsed)
    print("✓ 数据已保存到数据库")
    
    # 查询验证
    print("\n--- 数据验证 ---")
    test_elements = ["TEMPA", "WSPDA", "VISIA", "UVRAA"]
    for code in test_elements:
        data = get_latest_element(code)
        if data:
            print(f"  {code}: {data['value']} (质控码: {data['qc_code']})")
        else:
            print(f"  {code}: 无数据")
    
    print("\n✓ 测试完成！现在可以通过语音查询气象数据了")
    print("  示例：'现在温度多少？' -> '当前温度为 12.5 ℃，数据状态：正常'")


def receive_from_serial(port, baudrate=9600):
    """从串口接收数据"""
    try:
        import serial
    except ImportError:
        print("请先安装 pyserial: pip install pyserial")
        return
    
    print(f"正在监听串口 {port}，波特率 {baudrate}...")
    init_database()
    
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        while True:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line and line.startswith("SH"):
                parsed = parse_meteo_string(line)
                if parsed.get("elements"):
                    save_meteo_data(parsed)
                    print(f"[{time.strftime('%H:%M:%S')}] 收到数据，{len(parsed['elements'])} 个要素")
    except KeyboardInterrupt:
        print("\n已停止接收")
    except Exception as e:
        print(f"串口错误: {e}")


def receive_from_file(filepath):
    """从文件读取数据（用于测试或回放）"""
    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        return
    
    init_database()
    print(f"从文件读取数据: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and line.startswith("SH"):
                parsed = parse_meteo_string(line)
                if parsed.get("elements"):
                    save_meteo_data(parsed)
                    print(f"已处理: {parsed.get('station_id')} - {len(parsed['elements'])} 个要素")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="气象数据接收器")
    parser.add_argument("--test", action="store_true", help="使用示例数据测试")
    parser.add_argument("--port", type=str, help="串口端口，如 COM3 或 /dev/ttyUSB0")
    parser.add_argument("--baudrate", type=int, default=9600, help="串口波特率")
    parser.add_argument("--file", type=str, help="从文件读取数据")
    
    args = parser.parse_args()
    
    if args.test:
        test_with_sample_data()
    elif args.port:
        receive_from_serial(args.port, args.baudrate)
    elif args.file:
        receive_from_file(args.file)
    else:
        parser.print_help()
        print("\n示例:")
        print("  python meteo_data_receiver.py --test           # 测试模式")
        print("  python meteo_data_receiver.py --port COM3      # 串口接收")
        print("  python meteo_data_receiver.py --file data.txt  # 文件读取")

