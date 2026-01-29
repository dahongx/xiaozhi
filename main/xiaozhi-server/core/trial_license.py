"""
试用期许可证验证模块 - 非对称加密版本
使用 RSA 数字签名，确保 license 无法被伪造

安全特性：
1. RSA-2048 非对称加密签名
2. 机器码绑定，防止 license 复制
3. 时间戳校验，防止系统时间回拨
4. 多重时间防篡改检测
5. 代码混淆兼容（可配合 PyArmor 使用）
"""

import os
import sys
import json
import hashlib
import base64
import platform
import uuid
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

# 导入时间防篡改模块
from core.time_validator import TimeValidator, validate_system_time

# ============================================================
# 公钥配置 - 此公钥用于验证 license 签名
# 私钥保存在 license_generator.py 中，仅管理员持有
# ============================================================
# 首次运行时会自动生成密钥对，请将生成的公钥粘贴到这里
PUBLIC_KEY_PEM = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA8IH6in2tcRo0XLXmZR9J
Lz12g7K1Ku/f9e8hSNziMfrG1fwd1bkzEWJ5JSRakQCnO6UKgtgw8mt2Yomcbwnf
jaN0A27agt+UkexGcMPcHSnMUF+I15NW60TM66wQBmuyG2ipUCKiuf5a6Zo+K9AG
SrgeE4p1eiUgw7Ys0qZUviaioNmPj4utjFhfjh/aMbA0oGrNQr+89iLcrGtfeO6y
BAQ2SJarvX6C4VI6XfcOLKGMRJ/TvqxGA/t/8uIm6CfYG6lIHRQDPUwCPUMjVe0k
TSfH+LTrO9+rdo32zJL3uVKMVdS8NM4hTsoXWUq6dkpRlFwnIIfAwYFKZfVcehJE
zwIDAQAB
-----END PUBLIC KEY-----
""".strip()

# 许可证文件名
LICENSE_FILE = "license.lic"

# 是否启用严格时间验证（检测到时间篡改时拒绝运行）
STRICT_TIME_VALIDATION = True


class LicenseError(Exception):
    """许可证异常基类"""
    pass


class LicenseNotFound(LicenseError):
    """未找到许可证文件"""
    pass


class LicenseExpired(LicenseError):
    """许可证已过期"""
    pass


class LicenseInvalid(LicenseError):
    """许可证无效（签名错误或机器码不匹配）"""
    pass


class LicenseVerifier:
    """许可证验证器 - 仅验证，不生成"""
    
    def __init__(self, license_dir: Optional[str] = None):
        """
        初始化验证器
        
        Args:
            license_dir: license 文件所在目录，默认为程序目录
        """
        self.license_dir = Path(license_dir) if license_dir else Path(__file__).parent.parent
        self.license_file = self.license_dir / LICENSE_FILE
        self._machine_id = None
        self._public_key = None
    
    def _get_public_key(self):
        """加载公钥"""
        if self._public_key:
            return self._public_key
        
        if "REPLACE_WITH_YOUR_PUBLIC_KEY" in PUBLIC_KEY_PEM:
            raise LicenseError(
                "公钥未配置！请先运行 license_generator.py 生成密钥对，"
                "然后将公钥粘贴到 trial_license.py 的 PUBLIC_KEY_PEM 中"
            )
        
        self._public_key = serialization.load_pem_public_key(
            PUBLIC_KEY_PEM.encode(),
            backend=default_backend()
        )
        return self._public_key
    
    def get_machine_id(self) -> str:
        """
        获取机器唯一标识符
        组合多个硬件特征生成稳定的机器码
        """
        if self._machine_id:
            return self._machine_id
        
        features = []
        
        # 1. 平台信息
        features.append(platform.system())
        features.append(platform.machine())
        
        # 2. MAC 地址
        try:
            mac = uuid.getnode()
            features.append(str(mac))
        except:
            pass
        
        # 3. 处理器信息
        features.append(platform.processor())
        
        # 4. 主机名
        features.append(platform.node())
        
        # 5. 用户目录
        features.append(str(Path.home()))
        
        # 6. 磁盘序列号（Windows）
        if platform.system() == 'Windows':
            try:
                import subprocess
                result = subprocess.run(
                    ['wmic', 'diskdrive', 'get', 'serialnumber'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    lines = [l.strip() for l in result.stdout.split('\n') if l.strip() and l.strip() != 'SerialNumber']
                    if lines:
                        features.append(lines[0])
            except:
                pass
        
        # 组合并哈希生成 32 字符机器码
        combined = "|".join(features)
        self._machine_id = hashlib.sha256(combined.encode()).hexdigest()[:32]
        
        return self._machine_id
    
    def _verify_signature(self, data: dict, signature: str) -> bool:
        """验证数字签名"""
        public_key = self._get_public_key()
        
        # 重建签名数据
        sign_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
        
        try:
            signature_bytes = base64.b64decode(signature)
            public_key.verify(
                signature_bytes,
                sign_data.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except InvalidSignature:
            return False
        except Exception as e:
            raise LicenseInvalid(f"签名验证失败: {e}")
    
    def _load_license(self) -> dict:
        """加载并解析 license 文件"""
        if not self.license_file.exists():
            raise LicenseNotFound(
                f"未找到许可证文件: {self.license_file}\n"
                "请联系管理员获取有效的 license.lic 文件"
            )
        
        try:
            with open(self.license_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # 解码 base64
            decoded = base64.b64decode(content).decode('utf-8')
            license_data = json.loads(decoded)
            
            return license_data
        except json.JSONDecodeError:
            raise LicenseInvalid("许可证格式错误")
        except Exception as e:
            raise LicenseInvalid(f"无法读取许可证: {e}")
    
    def verify(self) -> Tuple[bool, int, str]:
        """
        验证许可证
        
        Returns:
            Tuple[bool, int, str]: (是否有效, 剩余天数, 消息)
        
        Raises:
            LicenseNotFound: 未找到许可证文件
            LicenseInvalid: 许可证无效
            LicenseExpired: 许可证已过期
        """
        license_data = self._load_license()
        
        # 提取数据和签名
        data = license_data.get("data", {})
        signature = license_data.get("signature", "")
        
        if not data or not signature:
            raise LicenseInvalid("许可证结构不完整")
        
        # 1. 验证签名
        if not self._verify_signature(data, signature):
            raise LicenseInvalid("许可证签名验证失败，可能被篡改")
        
        # 2. 验证机器码（如果 license 中指定了机器码）
        license_machine_id = data.get("machine_id", "")
        if license_machine_id and license_machine_id != "*":  # * 表示通用 license
            if license_machine_id != self.get_machine_id():
                raise LicenseInvalid(
                    f"许可证与当前机器不匹配\n"
                    f"许可证机器码: {license_machine_id[:8]}...\n"
                    f"当前机器码:   {self.get_machine_id()[:8]}..."
                )
        
        # 3. 多重时间防篡改检测
        time_validator = TimeValidator(
            state_dir=self.license_dir,
            machine_id=self.get_machine_id()
        )
        time_valid, time_message = time_validator.validate_time()
        
        if not time_valid and STRICT_TIME_VALIDATION:
            raise LicenseInvalid(f"时间验证失败: {time_message}")
        
        # 4. 基础时间戳检查（防止时间回拨到 license 签发之前）
        issue_timestamp = data.get("issue_timestamp", 0)
        current_time = time.time()
        
        # 如果当前时间比签发时间早太多（超过1小时），说明时间被回拨
        if current_time < issue_timestamp - 3600:
            raise LicenseInvalid("检测到系统时间异常，请校准系统时间")
        
        # 5. 检查过期时间
        expiry_date_str = data.get("expiry_date", "")
        if expiry_date_str:
            expiry_date = datetime.fromisoformat(expiry_date_str)
            now = datetime.now()
            
            if now > expiry_date:
                raise LicenseExpired(
                    f"许可证已于 {expiry_date.strftime('%Y-%m-%d %H:%M')} 过期\n"
                    "请联系管理员续期"
                )
            
            remaining = expiry_date - now
            remaining_days = remaining.days
            
            return True, remaining_days, f"许可证有效，剩余 {remaining_days} 天"
        
        # 无过期时间 = 永久有效
        return True, 9999, "许可证有效（永久）"
    
    def get_license_info(self) -> Dict[str, Any]:
        """获取许可证详细信息"""
        try:
            license_data = self._load_license()
            data = license_data.get("data", {})
            
            expiry_date_str = data.get("expiry_date", "")
            if expiry_date_str:
                expiry_date = datetime.fromisoformat(expiry_date_str)
                remaining = expiry_date - datetime.now()
                is_expired = datetime.now() > expiry_date
            else:
                expiry_date = None
                remaining = timedelta(days=9999)
                is_expired = False
            
            return {
                "status": "已过期" if is_expired else "有效",
                "license_type": data.get("license_type", "trial"),
                "licensee": data.get("licensee", "未知"),
                "machine_id": data.get("machine_id", "*")[:8] + "..." if data.get("machine_id") else "通用",
                "issue_date": data.get("issue_date", "未知"),
                "expiry_date": expiry_date.strftime('%Y-%m-%d %H:%M:%S') if expiry_date else "永久",
                "remaining_days": max(0, remaining.days),
                "is_expired": is_expired,
                "features": data.get("features", [])
            }
        except LicenseNotFound:
            return {"status": "未激活", "error": "未找到许可证文件"}
        except Exception as e:
            return {"status": "错误", "error": str(e)}


def check_license(exit_on_error: bool = True, show_info: bool = True) -> bool:
    """
    检查许可证的便捷函数
    
    Args:
        exit_on_error: 验证失败时是否退出程序
        show_info: 是否显示许可证信息
        
    Returns:
        bool: 是否验证通过
    """
    verifier = LicenseVerifier()
    
    try:
        valid, remaining_days, message = verifier.verify()
        
        if show_info:
            print(f"✓ {message}")
            
            # 剩余时间少于3天时发出警告
            if remaining_days <= 3:
                print(f"⚠ 警告：许可证即将到期，请联系管理员续期")
        
        return True
        
    except LicenseNotFound as e:
        print(f"✗ 许可证未找到")
        print(f"  {e}")
        print(f"\n当前机器码: {verifier.get_machine_id()}")
        print("请将机器码发送给管理员以获取许可证")
        
    except LicenseExpired as e:
        print(f"✗ 许可证已过期")
        print(f"  {e}")
        
    except LicenseInvalid as e:
        print(f"✗ 许可证无效")
        print(f"  {e}")
        
    except LicenseError as e:
        print(f"✗ 许可证错误: {e}")
    
    if exit_on_error:
        sys.exit(1)
    
    return False


def get_machine_id() -> str:
    """获取当前机器码的便捷函数"""
    return LicenseVerifier().get_machine_id()


# 命令行工具
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="许可证验证工具")
    parser.add_argument("--info", action="store_true", help="显示许可证信息")
    parser.add_argument("--verify", action="store_true", help="验证许可证")
    parser.add_argument("--machine-id", action="store_true", help="显示机器码")
    
    args = parser.parse_args()
    
    verifier = LicenseVerifier()
    
    if args.machine_id:
        print(f"当前机器码: {verifier.get_machine_id()}")
        print("\n请将此机器码发送给管理员以获取许可证")
    elif args.info:
        info = verifier.get_license_info()
        print("=" * 50)
        print("许可证信息")
        print("=" * 50)
        for key, value in info.items():
            print(f"  {key}: {value}")
        print("=" * 50)
    else:
        check_license(exit_on_error=False)
