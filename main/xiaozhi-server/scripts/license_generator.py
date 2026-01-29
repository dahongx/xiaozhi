#!/usr/bin/env python3
"""
许可证生成工具 - 管理员专用
此文件包含私钥，请妥善保管，切勿分发给用户！

使用方法：
1. 首次运行生成密钥对：python license_generator.py --init
2. 将生成的公钥粘贴到 trial_license.py 中
3. 生成许可证：python license_generator.py --generate --machine-id <机器码> --days <天数>
"""

import os
import sys
import json
import base64
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

# 密钥文件路径
KEYS_DIR = Path(__file__).parent / "keys"
PRIVATE_KEY_FILE = KEYS_DIR / "private_key.pem"
PUBLIC_KEY_FILE = KEYS_DIR / "public_key.pem"

# 许可证输出目录
OUTPUT_DIR = Path(__file__).parent / "licenses"


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
            print("密钥已存在！使用 --force 强制重新生成（会使所有已发放的 license 失效）")
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
        print(f"  私钥: {PRIVATE_KEY_FILE}")
        print(f"  公钥: {PUBLIC_KEY_FILE}")
        
        print("\n" + "=" * 60)
        print("重要：请将以下公钥复制到 core/trial_license.py 的 PUBLIC_KEY_PEM 中")
        print("=" * 60)
        print(public_pem.decode())
        print("=" * 60)
        
        # 重新加载
        self._load_keys()
        return True
    
    def _sign_data(self, data: dict) -> str:
        """使用私钥对数据进行签名"""
        if not self.private_key:
            raise RuntimeError("私钥未加载，请先运行 --init 生成密钥对")
        
        # 序列化数据
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


def main():
    parser = argparse.ArgumentParser(
        description="许可证生成工具 - 管理员专用",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 初始化密钥对
  python license_generator.py --init
  
  # 生成7天试用许可证（绑定机器）
  python license_generator.py --generate --machine-id abc123... --days 7
  
  # 生成30天通用许可证（任意机器可用）
  python license_generator.py --generate --days 30 --licensee "Company A"
  
  # 生成永久企业许可证
  python license_generator.py --generate --days 0 --type enterprise --licensee "Company B"
        """
    )
    
    parser.add_argument("--init", action="store_true", help="初始化密钥对")
    parser.add_argument("--force", action="store_true", help="强制重新生成密钥对")
    parser.add_argument("--generate", action="store_true", help="生成许可证")
    parser.add_argument("--show-public-key", action="store_true", help="显示公钥")
    
    # 许可证参数
    parser.add_argument("--machine-id", type=str, default="*", 
                        help="目标机器码，* 表示通用（默认: *）")
    parser.add_argument("--days", type=int, default=7, 
                        help="有效天数，0 表示永久（默认: 7）")
    parser.add_argument("--licensee", type=str, default="Trial User", 
                        help="被授权人名称（默认: Trial User）")
    parser.add_argument("--type", type=str, default="trial",
                        choices=["trial", "standard", "enterprise"],
                        help="许可证类型（默认: trial）")
    parser.add_argument("--output", type=str, default=None,
                        help="输出文件路径（默认: 自动生成）")
    parser.add_argument("--features", type=str, nargs="+", default=None,
                        help="启用的功能列表")
    
    args = parser.parse_args()
    
    generator = LicenseGenerator()
    
    if args.init:
        generator.generate_keys(force=args.force)
        
    elif args.show_public_key:
        generator.show_public_key()
        
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
            print(f"  文件: {output}")
            print(f"  被授权人: {args.licensee}")
            print(f"  机器码: {args.machine_id}")
            print(f"  有效期: {'永久' if args.days == 0 else f'{args.days} 天'}")
            print(f"  类型: {args.type}")
            print("=" * 60)
            print("\n将生成的 license.lic 文件发送给用户，")
            print("用户需将其放置在 xiaozhi-server 目录下")
            
        except Exception as e:
            print(f"✗ 生成失败: {e}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
