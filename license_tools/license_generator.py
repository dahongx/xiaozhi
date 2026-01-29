#!/usr/bin/env python3
"""
许可证生成工具 - 管理员专用（独立版本）
此文件夹包含私钥，请妥善保管，切勿分发给用户！

依赖安装：
    pip install cryptography

使用方法：
1. 首次运行生成密钥对：
    python license_generator.py --init
    
2. 将生成的公钥复制到客户端程序的 trial_license.py 中的 PUBLIC_KEY_PEM 变量

3. 生成许可证：
    # 生成7天试用许可证（绑定机器）
    python license_generator.py --generate --machine-id abc123... --days 7
    
    # 生成30天通用许可证（任意机器可用）
    python license_generator.py --generate --days 30 --licensee "Company A"
    
    # 生成永久企业许可证
    python license_generator.py --generate --days 0 --type enterprise --licensee "VIP客户"

4. 将生成的 license.lic 文件发送给用户
"""

import os
import sys
import json
import base64
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import time

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print("错误：缺少 cryptography 库")
    print("请运行：pip install cryptography")
    sys.exit(1)

# 密钥文件路径（相对于脚本所在目录）
SCRIPT_DIR = Path(__file__).parent
KEYS_DIR = SCRIPT_DIR / "keys"
PRIVATE_KEY_FILE = KEYS_DIR / "private_key.pem"
PUBLIC_KEY_FILE = KEYS_DIR / "public_key.pem"

# 许可证输出目录
OUTPUT_DIR = SCRIPT_DIR / "licenses"


class LicenseGenerator:
    """许可证生成器"""
    
    def __init__(self):
        self.private_key = None
        self.public_key = None
        self._load_keys()
    
    def _load_keys(self):
        """加载密钥对"""
        if PRIVATE_KEY_FILE.exists():
            with open(PRIVATE_KEY_FILE, 'rb') as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend()
                )
            self.public_key = self.private_key.public_key()
    
    def generate_keys(self, force: bool = False) -> bool:
        """
        生成 RSA 密钥对
        
        Args:
            force: 是否强制覆盖已存在的密钥
        """
        if PRIVATE_KEY_FILE.exists() and not force:
            print("=" * 60)
            print("⚠ 警告：密钥已存在！")
            print("=" * 60)
            print("重新生成密钥会使所有已发放的 license 失效！")
            print("如确定要重新生成，请使用 --force 参数")
            print("=" * 60)
            return False
        
        # 创建目录
        KEYS_DIR.mkdir(parents=True, exist_ok=True)
        
        # 生成 RSA-2048 密钥对
        print("正在生成 RSA-2048 密钥对...")
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # 保存私钥
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(PRIVATE_KEY_FILE, 'wb') as f:
            f.write(private_pem)
        
        # 保存公钥
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        with open(PUBLIC_KEY_FILE, 'wb') as f:
            f.write(public_pem)
        
        print(f"\n✓ 密钥对已生成")
        print(f"  私钥位置: {PRIVATE_KEY_FILE}")
        print(f"  公钥位置: {PUBLIC_KEY_FILE}")
        
        print("\n" + "=" * 70)
        print("重要：请将以下公钥复制到客户端 core/trial_license.py 的 PUBLIC_KEY_PEM 中")
        print("=" * 70)
        print(public_pem.decode())
        print("=" * 70)
        
        # 同时保存一份公钥到文本文件，方便复制
        public_key_txt = KEYS_DIR / "public_key_for_client.txt"
        with open(public_key_txt, 'w') as f:
            f.write("# 请将以下内容复制到客户端 core/trial_license.py 的 PUBLIC_KEY_PEM 中\n\n")
            f.write('PUBLIC_KEY_PEM = """\n')
            f.write(public_pem.decode())
            f.write('""".strip()\n')
        print(f"\n公钥也已保存到: {public_key_txt}")
        
        # 重新加载
        self._load_keys()
        return True
    
    def _sign_data(self, data: dict) -> str:
        """使用私钥对数据进行签名"""
        if not self.private_key:
            raise RuntimeError("私钥未加载，请先运行 --init 生成密钥对")
        
        # 序列化数据（按键排序确保一致性）
        sign_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
        
        # RSA-PSS 签名
        signature = self.private_key.sign(
            sign_data.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return base64.b64encode(signature).decode()
    
    def generate_license(
        self,
        machine_id: str = "*",
        days: int = 7,
        licensee: str = "Trial User",
        license_type: str = "trial",
        features: list = None,
        output_file: str = None
    ) -> str:
        """
        生成许可证
        
        Args:
            machine_id: 机器码，"*" 表示通用许可证（任意机器可用）
            days: 有效天数，0 表示永久
            licensee: 被授权人名称
            license_type: 许可证类型 (trial/standard/enterprise)
            features: 启用的功能列表
            output_file: 输出文件路径
            
        Returns:
            str: license 文件路径
        """
        if not self.private_key:
            raise RuntimeError("私钥未加载，请先运行 --init 生成密钥对")
        
        now = datetime.now()
        
        # 构建 license 数据
        data = {
            "license_type": license_type,
            "licensee": licensee,
            "machine_id": machine_id,
            "issue_date": now.strftime('%Y-%m-%d %H:%M:%S'),
            "issue_timestamp": time.time(),
            "features": features or ["basic"]
        }
        
        # 计算过期时间
        if days > 0:
            expiry_date = now + timedelta(days=days)
            data["expiry_date"] = expiry_date.isoformat()
        else:
            data["expiry_date"] = ""  # 永久
        
        # 签名
        signature = self._sign_data(data)
        
        # 构建完整 license
        license_content = {
            "data": data,
            "signature": signature
        }
        
        # 编码为 base64
        license_encoded = base64.b64encode(
            json.dumps(license_content, ensure_ascii=False).encode('utf-8')
        ).decode()
        
        # 确定输出路径
        if not output_file:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            # 生成文件名
            safe_name = "".join(c if c.isalnum() else "_" for c in licensee)
            timestamp = now.strftime('%Y%m%d_%H%M%S')
            output_file = OUTPUT_DIR / f"license_{safe_name}_{timestamp}.lic"
        else:
            output_file = Path(output_file)
        
        # 写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(license_encoded)
        
        return str(output_file)
    
    def show_public_key(self):
        """显示公钥"""
        if PUBLIC_KEY_FILE.exists():
            with open(PUBLIC_KEY_FILE, 'r') as f:
                print(f.read())
        else:
            print("公钥不存在，请先运行 --init 生成密钥对")
    
    def list_licenses(self):
        """列出已生成的许可证"""
        if not OUTPUT_DIR.exists():
            print("尚未生成任何许可证")
            return
        
        licenses = list(OUTPUT_DIR.glob("*.lic"))
        if not licenses:
            print("尚未生成任何许可证")
            return
        
        print(f"\n已生成的许可证 ({len(licenses)} 个):")
        print("-" * 80)
        
        for lic_file in sorted(licenses, key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                with open(lic_file, 'r') as f:
                    content = f.read()
                decoded = json.loads(base64.b64decode(content).decode('utf-8'))
                data = decoded.get('data', {})
                
                print(f"文件: {lic_file.name}")
                print(f"  被授权人: {data.get('licensee', 'N/A')}")
                print(f"  机器码: {data.get('machine_id', 'N/A')[:16]}...")
                print(f"  签发时间: {data.get('issue_date', 'N/A')}")
                expiry = data.get('expiry_date', '')
                print(f"  过期时间: {expiry if expiry else '永久'}")
                print(f"  类型: {data.get('license_type', 'N/A')}")
                print("-" * 80)
            except Exception as e:
                print(f"文件: {lic_file.name} (解析失败: {e})")
                print("-" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="许可证生成工具 - 管理员专用",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 初始化密钥对（首次使用必须执行）
  python license_generator.py --init
  
  # 生成7天试用许可证（绑定特定机器）
  python license_generator.py --generate --machine-id abc123def456 --days 7
  
  # 生成30天通用许可证（任意机器可用）
  python license_generator.py --generate --days 30 --licensee "公司A"
  
  # 生成永久企业许可证
  python license_generator.py --generate --days 0 --type enterprise --licensee "VIP客户"
  
  # 查看公钥（用于配置客户端）
  python license_generator.py --show-public-key
  
  # 列出已生成的许可证
  python license_generator.py --list

注意事项:
  1. 首次使用必须先执行 --init 生成密钥对
  2. 私钥文件 (keys/private_key.pem) 必须妥善保管，切勿泄露
  3. 公钥需要配置到客户端程序中
  4. machine-id 设为 * 表示通用许可证，可在任意机器使用
        """
    )
    
    parser.add_argument("--init", action="store_true", help="初始化密钥对")
    parser.add_argument("--force", action="store_true", help="强制重新生成密钥对（会使已发放的license失效）")
    parser.add_argument("--generate", action="store_true", help="生成许可证")
    parser.add_argument("--show-public-key", action="store_true", help="显示公钥")
    parser.add_argument("--list", action="store_true", help="列出已生成的许可证")
    
    # 许可证参数
    parser.add_argument("--machine-id", type=str, default="*", 
                        help="目标机器码，* 表示通用许可证（默认: *）")
    parser.add_argument("--days", type=int, default=7, 
                        help="有效天数，0 表示永久（默认: 7）")
    parser.add_argument("--licensee", type=str, default="Trial User", 
                        help="被授权人名称（默认: Trial User）")
    parser.add_argument("--type", type=str, default="trial",
                        choices=["trial", "standard", "enterprise"],
                        help="许可证类型（默认: trial）")
    parser.add_argument("--output", type=str, default=None,
                        help="输出文件路径（默认: 自动生成到 licenses 目录）")
    parser.add_argument("--features", type=str, nargs="+", default=None,
                        help="启用的功能列表（空格分隔）")
    
    args = parser.parse_args()
    
    generator = LicenseGenerator()
    
    if args.init:
        generator.generate_keys(force=args.force)
        
    elif args.show_public_key:
        generator.show_public_key()
        
    elif args.list:
        generator.list_licenses()
        
    elif args.generate:
        try:
            output = generator.generate_license(
                machine_id=args.machine_id,
                days=args.days,
                licensee=args.licensee,
                license_type=args.type,
                features=args.features,
                output_file=args.output
            )
            
            print("\n" + "=" * 60)
            print("✓ 许可证已生成")
            print("=" * 60)
            print(f"  文件位置: {output}")
            print(f"  被授权人: {args.licensee}")
            print(f"  机器码:   {args.machine_id}")
            print(f"  有效期:   {'永久' if args.days == 0 else f'{args.days} 天'}")
            print(f"  类型:     {args.type}")
            print("=" * 60)
            print("\n请将生成的 .lic 文件发送给用户")
            print("用户需将其重命名为 license.lic 并放置在程序目录下")
            
        except Exception as e:
            print(f"✗ 生成失败: {e}")
            sys.exit(1)
    else:
        parser.print_help()
        print("\n提示：首次使用请先执行 --init 初始化密钥对")


if __name__ == "__main__":
    main()
