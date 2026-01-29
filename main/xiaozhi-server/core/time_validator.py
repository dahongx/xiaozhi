"""
时间防篡改模块（纯离线版本）
多重机制检测系统时间是否被篡改

检测方法：
1. 记录最后验证时间 - 时间不应该倒退
2. 累计运行时间 - 独立于系统时间
3. 文件时间戳参考 - 检查系统关键文件时间
4. 单调时钟 - 使用 time.monotonic()
5. 最大时间水位线 - 记录历史最大时间戳
"""

import os
import sys
import json
import time
import hashlib
import platform
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

# 时间状态文件（加密存储）
TIME_STATE_FILE = ".time_state"

# 允许的时间误差（秒）
TIME_TOLERANCE = 300  # 5分钟容差


class TimeValidator:
    """时间防篡改验证器（纯离线）"""
    
    def __init__(self, state_dir: Optional[str] = None, machine_id: str = ""):
        """
        初始化时间验证器
        
        Args:
            state_dir: 状态文件存储目录
            machine_id: 机器码，用于加密密钥派生
        """
        self.state_dir = Path(state_dir) if state_dir else Path(__file__).parent.parent
        self.state_file = self.state_dir / TIME_STATE_FILE
        self.machine_id = machine_id or self._get_default_machine_id()
        self._encryption_key = None
        self._session_start_monotonic = time.monotonic()
        self._session_start_time = time.time()
    
    def _get_default_machine_id(self) -> str:
        """获取默认机器标识"""
        import uuid
        return hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()[:32]
    
    def _get_encryption_key(self) -> bytes:
        """基于机器码生成加密密钥"""
        if self._encryption_key:
            return self._encryption_key
        
        salt = b"xiaozhi_time_validator_salt"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.machine_id.encode()))
        self._encryption_key = key
        return key
    
    def _encrypt_state(self, data: dict) -> str:
        """加密状态数据"""
        key = self._get_encryption_key()
        f = Fernet(key)
        json_data = json.dumps(data).encode()
        encrypted = f.encrypt(json_data)
        return base64.b64encode(encrypted).decode()
    
    def _decrypt_state(self, encrypted_data: str) -> Optional[dict]:
        """解密状态数据"""
        key = self._get_encryption_key()
        f = Fernet(key)
        try:
            encrypted = base64.b64decode(encrypted_data.encode())
            decrypted = f.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception:
            return None
    
    def _load_state(self) -> Optional[dict]:
        """加载时间状态"""
        if not self.state_file.exists():
            return None
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                encrypted = f.read().strip()
            return self._decrypt_state(encrypted)
        except Exception:
            return None
    
    def _save_state(self, state: dict):
        """保存时间状态"""
        encrypted = self._encrypt_state(state)
        
        # 如果文件存在，先移除隐藏/只读属性
        if os.path.exists(self.state_file):
            try:
                if platform.system() == 'Windows':
                    import ctypes
                    # 移除隐藏和只读属性 (设置为普通属性 0x80 = NORMAL)
                    ctypes.windll.kernel32.SetFileAttributesW(str(self.state_file), 0x80)
                else:
                    os.chmod(self.state_file, 0o644)
            except:
                pass
        
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                f.write(encrypted)
        except PermissionError:
            # 如果仍然失败，尝试删除后重新创建
            try:
                os.remove(self.state_file)
                with open(self.state_file, 'w', encoding='utf-8') as f:
                    f.write(encrypted)
            except:
                pass  # 静默失败，不影响程序运行
        
        # Windows 下设置隐藏属性
        if platform.system() == 'Windows':
            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(str(self.state_file), 2)
            except:
                pass
    
    def _get_reference_timestamps(self) -> list:
        """
        获取系统参考时间戳
        使用系统关键文件的修改时间作为时间参考
        """
        reference_files = []
        
        if platform.system() == 'Windows':
            # Windows 系统文件
            candidates = [
                os.environ.get('WINDIR', 'C:\\Windows') + '\\System32\\config\\SAM',
                os.environ.get('WINDIR', 'C:\\Windows') + '\\System32\\config\\SYSTEM',
                os.environ.get('PROGRAMDATA', 'C:\\ProgramData'),
                os.environ.get('APPDATA', ''),
            ]
        else:
            # Linux/Mac 系统文件
            candidates = [
                '/var/log/lastlog',
                '/var/log/wtmp',
                '/etc/passwd',
                str(Path.home() / '.bashrc'),
            ]
        
        for path in candidates:
            if path and os.path.exists(path):
                try:
                    stat = os.stat(path)
                    reference_files.append({
                        'path': path,
                        'mtime': stat.st_mtime,
                        'ctime': stat.st_ctime
                    })
                except:
                    pass
        
        return reference_files
    
    def validate_time(self) -> Tuple[bool, str]:
        """
        验证系统时间是否被篡改（纯离线检测）
        
        Returns:
            Tuple[bool, str]: (是否有效, 消息)
        """
        current_time = time.time()
        current_monotonic = time.monotonic()
        
        # 加载之前的状态
        state = self._load_state()
        
        if state is None:
            # 首次运行，创建初始状态
            new_state = {
                'last_check_time': current_time,
                'last_monotonic': current_monotonic,
                'total_runtime': 0,
                'check_count': 1,
                'reference_files': self._get_reference_timestamps(),
                'created_time': current_time,
                'max_time_watermark': current_time,  # 最大时间水位线
            }
            self._save_state(new_state)
            return True, "时间验证初始化完成"
        
        issues = []
        
        # ========== 检测1: 时间倒退检测 ==========
        last_check_time = state.get('last_check_time', 0)
        if current_time < last_check_time - TIME_TOLERANCE:
            time_diff = last_check_time - current_time
            issues.append(f"系统时间倒退了 {time_diff:.0f} 秒")
        
        # ========== 检测2: 最大时间水位线检测 ==========
        # 记录历史上见过的最大时间，时间不应该低于这个水位线
        max_time_watermark = state.get('max_time_watermark', 0)
        if current_time < max_time_watermark - TIME_TOLERANCE:
            time_diff = max_time_watermark - current_time
            issues.append(f"系统时间低于历史水位线 {time_diff:.0f} 秒")
        
        # 更新水位线（只升不降）
        new_watermark = max(max_time_watermark, current_time)
        
        # ========== 检测3: 单调时钟 vs 系统时钟 ==========
        # 计算自会话开始以来的单调时间差
        monotonic_elapsed = current_monotonic - self._session_start_monotonic
        expected_time = self._session_start_time + monotonic_elapsed
        
        # 如果系统时间和预期时间差距太大（运行期间修改了时间）
        time_drift = abs(current_time - expected_time)
        if time_drift > TIME_TOLERANCE and monotonic_elapsed > 60:  # 运行超过1分钟后才检测
            issues.append(f"运行期间系统时间被修改，偏差 {time_drift:.0f} 秒")
        
        # ========== 检测4: 累计运行时间检测 ==========
        total_runtime = state.get('total_runtime', 0)
        created_time = state.get('created_time', current_time)
        expected_max_time = current_time - created_time
        
        # 如果累计运行时间超过了理论最大值，说明时间被回拨过
        if total_runtime > expected_max_time + 3600:  # 允许1小时误差
            issues.append("累计运行时间超过理论最大值，时间可能被回拨")
        
        # ========== 检测5: 文件时间戳参考 ==========
        old_references = state.get('reference_files', [])
        new_references = self._get_reference_timestamps()
        
        for old_ref in old_references:
            for new_ref in new_references:
                if old_ref['path'] == new_ref['path']:
                    # 文件修改时间不应该变早（除非时间被回拨）
                    if new_ref['mtime'] < old_ref['mtime'] - TIME_TOLERANCE:
                        issues.append("系统文件时间戳异常，时间可能被回拨")
                        break
        
        # 更新状态
        session_runtime = current_monotonic - self._session_start_monotonic
        new_state = {
            'last_check_time': current_time,
            'last_monotonic': current_monotonic,
            'total_runtime': total_runtime + max(0, session_runtime),
            'check_count': state.get('check_count', 0) + 1,
            'reference_files': new_references if new_references else old_references,
            'created_time': created_time,
            'max_time_watermark': new_watermark,
        }
        self._save_state(new_state)
        
        # 重置会话起点
        self._session_start_monotonic = current_monotonic
        self._session_start_time = current_time
        
        if issues:
            return False, "检测到时间异常: " + "; ".join(issues)
        
        return True, "时间验证通过"
    
    def reset(self):
        """重置时间状态（仅用于开发测试）"""
        if self.state_file.exists():
            os.remove(self.state_file)


# 便捷函数
def validate_system_time(machine_id: str = "") -> Tuple[bool, str]:
    """
    验证系统时间的便捷函数
    
    Returns:
        Tuple[bool, str]: (是否有效, 消息)
    """
    validator = TimeValidator(machine_id=machine_id)
    return validator.validate_time()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="时间防篡改验证工具（离线版）")
    parser.add_argument("--validate", action="store_true", help="验证系统时间")
    parser.add_argument("--reset", action="store_true", help="重置时间状态")
    
    args = parser.parse_args()
    
    validator = TimeValidator()
    
    if args.reset:
        validator.reset()
        print("时间状态已重置")
    else:
        valid, message = validator.validate_time()
        print(f"{'✓' if valid else '✗'} {message}")
