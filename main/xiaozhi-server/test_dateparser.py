"""
测试 dateparser 的中文解析能力
"""
import dateparser
from datetime import datetime

print("=" * 60)
print("测试 dateparser 中文时间解析")
print("=" * 60)
print()

test_cases = [
    "现在",
    "今天",
    "昨天",
    "前天",
    "3小时前",
    "昨天下午3点",
    "昨天下午三点",
    "昨天15点",
    "今天早上8点",
    "今天早上八点",
    "今天8点",
    "12月10号中午",
    "12月10日中午",
    "12月10号12点",
    "上周一",
    "上星期一",
]

for text in test_cases:
    # 测试不同的配置
    parsed1 = dateparser.parse(
        text,
        languages=['zh'],
        settings={
            'TIMEZONE': 'Asia/Shanghai',
            'RETURN_AS_TIMEZONE_AWARE': False,
            'PREFER_DATES_FROM': 'past'
        }
    )
    
    parsed2 = dateparser.parse(
        text,
        languages=['zh', 'en'],
        settings={
            'TIMEZONE': 'Asia/Shanghai',
            'RETURN_AS_TIMEZONE_AWARE': False,
            'PREFER_DATES_FROM': 'past',
            'RELATIVE_BASE': datetime.now()
        }
    )
    
    print(f"'{text}'")
    if parsed1:
        print(f"  配置1: {parsed1.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"  配置1: ❌ 解析失败")
    
    if parsed2:
        print(f"  配置2: {parsed2.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"  配置2: ❌ 解析失败")
    print()

