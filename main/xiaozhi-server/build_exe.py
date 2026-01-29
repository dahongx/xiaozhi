#!/usr/bin/env python3
"""
Nuitka 编译脚本 - 将 xiaozhi-server 打包成独立 EXE
生成的 EXE 可以在没有 Python 环境的设备上运行
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# 项目根目录
PROJECT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build_nuitka"

# 需要包含的数据目录和文件
DATA_DIRS = [
    "config",
    "data", 
    "models",
    "music",
    "plugins_func",
    "test",
    "core",  # 包含 Python 模块
]

DATA_FILES = [
    "config.yaml",
    "config_from_api.yaml",
    "agent-base-prompt.txt",
    "mcp_server_settings.json",
]

# 需要排除的文件/目录
EXCLUDE_PATTERNS = [
    "*.pyc",
    "__pycache__",
    "*.pem",  # 私钥文件
    ".time_state",
    "*.log",
    "exp/log/*",
    "tmp/*",
]


def check_nuitka():
    """检查 Nuitka 是否安装"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "nuitka", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✓ Nuitka 已安装: {result.stdout.strip()}")
            return True
    except Exception:
        pass
    return False


def install_nuitka():
    """安装 Nuitka 和相关依赖"""
    print("正在安装 Nuitka...")
    packages = [
        "nuitka",
        "ordered-set",  # Nuitka 依赖
        "zstandard",    # 压缩支持
    ]
    for pkg in packages:
        subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)
    print("✓ Nuitka 安装完成")


def clean_build():
    """清理之前的构建"""
    for d in [OUTPUT_DIR, BUILD_DIR]:
        if d.exists():
            print(f"清理目录: {d}")
            shutil.rmtree(d)
    
    # 清理 .build 目录
    build_temp = PROJECT_DIR / "app.build"
    if build_temp.exists():
        shutil.rmtree(build_temp)
    
    dist_temp = PROJECT_DIR / "app.dist"
    if dist_temp.exists():
        shutil.rmtree(dist_temp)


def build_exe():
    """使用 Nuitka 编译"""
    print("\n" + "="*60)
    print("开始 Nuitka 编译...")
    print("="*60 + "\n")
    
    # 构建 Nuitka 命令
    cmd = [
        sys.executable, "-m", "nuitka",
        
        # 基本选项
        "--standalone",                    # 独立模式，包含所有依赖
        "--onefile",                       # 打包成单个 EXE
        "--assume-yes-for-downloads",      # 自动下载依赖
        
        # Windows 特定选项
        "--windows-console-mode=attach",   # 保留控制台输出
        "--windows-icon-from-ico=",        # 可以添加图标路径
        
        # 输出设置
        f"--output-dir={OUTPUT_DIR}",
        "--output-filename=xiaozhi-server.exe",
        
        # 包含数据文件
    ]
    
    # 添加数据目录
    for data_dir in DATA_DIRS:
        src_dir = PROJECT_DIR / data_dir
        if src_dir.exists():
            cmd.append(f"--include-data-dir={src_dir}={data_dir}")
    
    # 添加数据文件
    for data_file in DATA_FILES:
        src_file = PROJECT_DIR / data_file
        if src_file.exists():
            cmd.append(f"--include-data-files={src_file}={data_file}")
    
    # 包含必要的包
    include_packages = [
        "core",
        "config",
        "plugins_func",
        "asyncio",
        "aiohttp",
        "aiohttp_cors",
        "websockets",
        "yaml",
        "ruamel.yaml",
        "loguru",
        "cryptography",
        "torch",
        "torchaudio",
        "numpy",
        "openai",
        "httpx",
        "requests",
        "silero_vad",
        "pydub",
        "edge_tts",
        "funasr",
        "sherpa_onnx",
        "mcp",
        "psutil",
        "jwt",
        "jinja2",
        "dateparser",
        "chardet",
        "aioconsole",
    ]
    
    for pkg in include_packages:
        cmd.append(f"--include-package={pkg}")
    
    # 包含隐式导入的模块
    implicit_imports = [
        "encodings",
        "codecs",
        "ssl",
        "certifi",
        "urllib3",
        "http.server",
        "webbrowser",
        "threading",
        "multiprocessing",
        "concurrent.futures",
    ]
    
    for mod in implicit_imports:
        cmd.append(f"--include-module={mod}")
    
    # 插件
    cmd.extend([
        "--enable-plugin=multiprocessing",
        "--enable-plugin=pylint-warnings",
    ])
    
    # 优化选项
    cmd.extend([
        "--lto=yes",                       # 链接时优化
        "--jobs=4",                        # 并行编译
    ])
    
    # 主入口文件
    cmd.append(str(PROJECT_DIR / "app.py"))
    
    print("编译命令:")
    print(" ".join(cmd[:10]) + " ...")
    print()
    
    # 执行编译
    try:
        subprocess.run(cmd, check=True, cwd=PROJECT_DIR)
        print("\n" + "="*60)
        print("✓ 编译成功!")
        print("="*60)
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ 编译失败: {e}")
        return False


def copy_additional_files():
    """复制额外的配置文件到输出目录"""
    print("\n复制配置文件...")
    
    exe_dir = OUTPUT_DIR
    
    # 复制 license.lic (如果存在)
    license_file = PROJECT_DIR / "license.lic"
    if license_file.exists():
        shutil.copy2(license_file, exe_dir / "license.lic")
        print(f"  ✓ 复制 license.lic")
    
    # 创建 README
    readme_content = """# XiaoZhi Server (独立版)

## 运行方法

1. 确保 license.lic 文件在同一目录下
2. 双击运行 xiaozhi-server.exe
3. 程序会自动打开测试页面

## 目录结构

- xiaozhi-server.exe  - 主程序
- license.lic         - 许可证文件 (必需)
- config.yaml         - 配置文件 (可选,会自动生成)

## 注意事项

- 首次运行需要有效的许可证文件
- 默认端口: WebSocket 8000, HTTP 8003, 测试页面 8006
- 日志文件会生成在 exp/log 目录下
"""
    
    with open(exe_dir / "README.txt", "w", encoding="utf-8") as f:
        f.write(readme_content)
    print("  ✓ 创建 README.txt")


def main():
    print("="*60)
    print("XiaoZhi Server - Nuitka 打包工具")
    print("="*60)
    print(f"项目目录: {PROJECT_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    print()
    
    # 检查/安装 Nuitka
    if not check_nuitka():
        install_nuitka()
    
    # 清理旧构建
    clean_build()
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 编译
    if build_exe():
        copy_additional_files()
        print("\n" + "="*60)
        print(f"打包完成! 输出位置: {OUTPUT_DIR}")
        print("="*60)
    else:
        print("\n打包失败，请检查错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()
