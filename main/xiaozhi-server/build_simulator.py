#!/usr/bin/env python3
"""
气象数据模拟器 - PyInstaller 打包脚本
将 meteo_data_simulator.py 打包成独立 EXE
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# 项目根目录
PROJECT_DIR = Path(__file__).parent.absolute()
SCRIPTS_DIR = PROJECT_DIR / "scripts"
OUTPUT_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build_simulator"
SPEC_FILE = PROJECT_DIR / "weather-simulator.spec"

# 模拟器入口文件
SIMULATOR_SCRIPT = SCRIPTS_DIR / "meteo_data_simulator.py"


def check_pyinstaller():
    """检查 PyInstaller 是否安装"""
    try:
        import PyInstaller
        print(f"✓ PyInstaller 已安装: {PyInstaller.__version__}")
        return True
    except ImportError:
        return False


def install_pyinstaller():
    """安装 PyInstaller"""
    print("正在安装 PyInstaller...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    print("✓ PyInstaller 安装完成")


def clean_build():
    """清理之前的构建（只清理模拟器相关目录）"""
    # 只清理 weather-simulator 子目录，不影响其他程序
    simulator_output = OUTPUT_DIR / "weather-simulator"
    if simulator_output.exists():
        print(f"清理目录: {simulator_output}")
        shutil.rmtree(simulator_output)
    
    if BUILD_DIR.exists():
        print(f"清理目录: {BUILD_DIR}")
        shutil.rmtree(BUILD_DIR)
    
    if SPEC_FILE.exists():
        SPEC_FILE.unlink()


def create_spec_file():
    """创建 PyInstaller spec 文件"""
    
    # 只需要 data 目录（数据库）
    data_dir = PROJECT_DIR / "data"
    
    # 隐藏导入 - 只需要基本模块
    hidden_imports = [
        "sqlite3",
        "datetime",
        "argparse",
        "math",
        "random",
        "time",
        "encodings",
        "encodings.utf_8",
        "encodings.gbk",
        "encodings.ascii",
    ]
    
    hidden_imports_str = ",\n        ".join([f"'{h}'" for h in hidden_imports])
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for weather-simulator

block_cipher = None

a = Analysis(
    [r'{SIMULATOR_SCRIPT}'],
    pathex=[r'{PROJECT_DIR}', r'{SCRIPTS_DIR}'],
    binaries=[],
    datas=[
        (r'{data_dir}', 'data'),
    ],
    hiddenimports=[
        {hidden_imports_str}
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'IPython',
        'notebook',
        'jupyter',
        'torch',
        'torchaudio',
        'numpy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='weather-simulator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='weather-simulator',
)
'''
    
    with open(SPEC_FILE, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"✓ 已创建 spec 文件: {SPEC_FILE}")


def build_exe():
    """使用 PyInstaller 编译"""
    print("\n" + "="*60)
    print("开始编译气象数据模拟器...")
    print("="*60 + "\n")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        f"--distpath={OUTPUT_DIR}",
        f"--workpath={BUILD_DIR}",
        str(SPEC_FILE),
    ]
    
    print("编译命令:", " ".join(cmd[:5]) + " ...")
    print()
    
    try:
        subprocess.run(cmd, check=True, cwd=PROJECT_DIR)
        print("\n" + "="*60)
        print("✓ 编译成功!")
        print("="*60)
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ 编译失败: {e}")
        return False


def create_batch_scripts():
    """创建启动/停止批处理脚本"""
    
    # 一键启动脚本
    start_all = '''@echo off
chcp 65001 >nul
title XiaoZhi Server - 启动全部服务

echo ============================================================
echo           XiaoZhi Server - 启动全部服务
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/2] 启动气象数据模拟器...
start "" /MIN "weather-simulator\\weather-simulator.exe" --daemon
timeout /t 2 /nobreak >nul
echo       ✓ 气象数据模拟器已启动

echo.
echo [2/2] 启动主服务...
start "" "xiaozhi-server\\xiaozhi-server.exe"
echo       ✓ 主服务已启动

echo.
echo ============================================================
echo 全部服务已启动!
echo ============================================================
echo.
echo 按任意键退出此窗口 (服务将继续运行)...
pause >nul
'''
    
    # 一键停止脚本
    stop_all = '''@echo off
chcp 65001 >nul
title XiaoZhi Server - 停止全部服务

echo ============================================================
echo           XiaoZhi Server - 停止全部服务
echo ============================================================
echo.

echo 正在停止所有服务...

taskkill /F /IM xiaozhi-server.exe 2>nul
if %errorlevel%==0 (
    echo ✓ 已停止 xiaozhi-server
) else (
    echo - xiaozhi-server 未运行
)

taskkill /F /IM weather-simulator.exe 2>nul
if %errorlevel%==0 (
    echo ✓ 已停止 weather-simulator
) else (
    echo - weather-simulator 未运行
)

echo.
echo ============================================================
echo 全部服务已停止!
echo ============================================================
pause
'''
    
    # 仅启动主服务
    start_main = '''@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 启动 XiaoZhi Server...
start "" "xiaozhi-server\\xiaozhi-server.exe"
'''
    
    # 仅启动模拟器
    start_simulator = '''@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 启动气象数据模拟器 (后台运行)...
start "" /MIN "weather-simulator\\weather-simulator.exe" --daemon
echo 模拟器已在后台启动
pause
'''
    
    with open(OUTPUT_DIR / "启动全部服务.bat", "w", encoding="utf-8") as f:
        f.write(start_all)
    
    with open(OUTPUT_DIR / "停止全部服务.bat", "w", encoding="utf-8") as f:
        f.write(stop_all)
    
    with open(OUTPUT_DIR / "仅启动主服务.bat", "w", encoding="utf-8") as f:
        f.write(start_main)
    
    with open(OUTPUT_DIR / "仅启动模拟器.bat", "w", encoding="utf-8") as f:
        f.write(start_simulator)
    
    print("✓ 已创建启动/停止脚本")


def create_readme():
    """创建说明文件"""
    readme_content = """# XiaoZhi Server 独立部署包

## 目录结构

```
dist/
├── xiaozhi-server/          # 主服务程序
│   ├── xiaozhi-server.exe   # 主程序
│   └── _internal/           # 依赖文件
├── weather-simulator/       # 气象数据模拟器
│   ├── weather-simulator.exe
│   └── _internal/
├── 启动全部服务.bat          # 一键启动 (推荐)
├── 停止全部服务.bat          # 一键停止
├── 仅启动主服务.bat          # 单独启动主服务
├── 仅启动模拟器.bat          # 单独启动模拟器
├── license.lic              # 许可证文件 (必需)
└── README.txt               # 本文件
```

## 快速开始

1. 确保 `license.lic` 文件在 dist 目录下
2. 双击 `启动全部服务.bat`
3. 浏览器会自动打开测试页面

## 服务说明

### 主服务 (xiaozhi-server)
- WebSocket 端口: 8000
- HTTP API 端口: 8003
- 测试页面端口: 8006

### 气象数据模拟器 (weather-simulator)
- 每小时自动生成模拟气象数据
- 数据存储在 data/meteo_data.db
- 后台静默运行

## 注意事项

1. 首次运行需要有效的许可证文件
2. 确保端口未被占用
3. 气象模拟器会在后台持续运行
4. 使用 `停止全部服务.bat` 关闭所有服务

## 后续升级

当接入真实气象接口时，只需替换 weather-simulator 目录即可。
"""
    
    with open(OUTPUT_DIR / "README.txt", "w", encoding="utf-8") as f:
        f.write(readme_content)
    print("✓ 已创建 README.txt")


def copy_license():
    """复制许可证文件"""
    license_src = PROJECT_DIR / "license.lic"
    if license_src.exists():
        shutil.copy2(license_src, OUTPUT_DIR / "license.lic")
        print("✓ 已复制 license.lic")
    else:
        print("⚠ license.lic 不存在，请手动添加")


def copy_shared_files():
    """复制共享文件到 dist 根目录"""
    print("\n复制共享文件...")
    
    # 复制 data 目录（包含数据库）
    data_src = PROJECT_DIR / "data"
    data_dst = OUTPUT_DIR / "data"
    if data_src.exists():
        if data_dst.exists():
            # 只复制数据库文件，不覆盖整个目录
            for f in data_src.glob("*"):
                dst_file = data_dst / f.name
                if not dst_file.exists():
                    if f.is_file():
                        shutil.copy2(f, dst_file)
                    else:
                        shutil.copytree(f, dst_file)
        else:
            shutil.copytree(data_src, data_dst)
        print("✓ 已复制 data/ 目录")
    
    # 复制配置文件
    config_yaml = PROJECT_DIR / "config.yaml"
    if config_yaml.exists():
        shutil.copy2(config_yaml, OUTPUT_DIR / "config.yaml")
        print("✓ 已复制 config.yaml")
    
    # 复制 config 目录
    config_dir = PROJECT_DIR / "config"
    config_dst = OUTPUT_DIR / "config"
    if config_dir.exists() and not config_dst.exists():
        shutil.copytree(config_dir, config_dst)
        print("✓ 已复制 config/ 目录")
    
    # 创建 logs 目录
    logs_dir = OUTPUT_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)
    print("✓ 已创建 logs/ 目录")


def main():
    print("="*60)
    print("气象数据模拟器 - PyInstaller 打包工具")
    print("="*60)
    print(f"模拟器脚本: {SIMULATOR_SCRIPT}")
    print(f"输出目录: {OUTPUT_DIR}")
    print()
    
    # 检查入口文件
    if not SIMULATOR_SCRIPT.exists():
        print(f"✗ 模拟器脚本不存在: {SIMULATOR_SCRIPT}")
        sys.exit(1)
    
    # 检查/安装 PyInstaller
    if not check_pyinstaller():
        install_pyinstaller()
    
    # 清理旧构建
    clean_build()
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 创建 spec 文件
    create_spec_file()
    
    # 编译
    if build_exe():
        copy_shared_files()
        create_batch_scripts()
        create_readme()
        copy_license()
        print("\n" + "="*60)
        print(f"打包完成! 输出位置: {OUTPUT_DIR}")
        print("="*60)
    else:
        print("\n打包失败，请检查错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()
