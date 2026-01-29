#!/usr/bin/env python3
"""
PyInstaller 编译脚本 - 将 xiaozhi-server 打包成独立 EXE
备选方案：比 Nuitka 更快，兼容性更好
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# 项目根目录
PROJECT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"
SPEC_FILE = PROJECT_DIR / "xiaozhi-server.spec"

# 需要包含的数据目录
DATA_DIRS = [
    ("config", "config"),
    ("data", "data"),
    ("models", "models"),
    ("music", "music"),
    ("plugins_func", "plugins_func"),
    ("test", "test"),
    ("core", "core"),
]

# 需要包含的数据文件
DATA_FILES = [
    ("config.yaml", "."),
    ("config_from_api.yaml", "."),
    ("agent-base-prompt.txt", "."),
    ("mcp_server_settings.json", "."),
]


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
    """清理之前的构建（只清理主服务相关目录）"""
    # 只清理 xiaozhi-server 子目录，不影响其他程序
    main_output = OUTPUT_DIR / "xiaozhi-server"
    if main_output.exists():
        print(f"清理目录: {main_output}")
        shutil.rmtree(main_output)
    
    if BUILD_DIR.exists():
        print(f"清理目录: {BUILD_DIR}")
        shutil.rmtree(BUILD_DIR)
    
    if SPEC_FILE.exists():
        SPEC_FILE.unlink()


def create_spec_file():
    """创建 PyInstaller spec 文件"""
    
    # 构建 datas 列表
    datas = []
    for src, dst in DATA_DIRS:
        src_path = PROJECT_DIR / src
        if src_path.exists():
            datas.append(f"    (r'{src_path}', '{dst}'),")
    
    for src, dst in DATA_FILES:
        src_path = PROJECT_DIR / src
        if src_path.exists():
            datas.append(f"    (r'{src_path}', '{dst}'),")
    
    # 添加第三方包的数据文件
    try:
        import funasr
        funasr_path = Path(funasr.__file__).parent
        version_file = funasr_path / "version.txt"
        if version_file.exists():
            datas.append(f"    (r'{version_file}', 'funasr'),")
            print(f"✓ 添加 funasr/version.txt")
    except ImportError:
        print("⚠ funasr 未安装，跳过")
    
    datas_str = "\n".join(datas)
    
    # 隐藏导入 - 包含 requirements.txt 中的所有依赖
    hidden_imports = [
        # 编码模块
        "encodings",
        "encodings.utf_8",
        "encodings.gbk",
        "encodings.ascii",
        "encodings.latin_1",
        "encodings.cp1252",
        
        # 核心依赖
        "aioconsole",
        "aiohttp",
        "aiohttp_cors",
        "websockets",
        "websockets.legacy",
        "websockets.legacy.server",
        "yaml",
        "ruamel.yaml",
        "loguru",
        
        # 加密
        "cryptography",
        "cryptography.fernet",
        "cryptography.hazmat.primitives.asymmetric.rsa",
        "cryptography.hazmat.primitives.asymmetric.padding",
        
        # 科学计算 - transformers/sklearn 依赖
        "scipy",
        "scipy.special",
        "scipy.optimize",
        "scipy.sparse",
        "scipy.linalg",
        "scipy.stats",
        "scipy.ndimage",
        "scipy.signal",
        "scipy.interpolate",
        "scipy.fft",
        "scipy.io",
        "scipy.io.wavfile",
        "sklearn",
        "sklearn.base",
        "sklearn.utils",
        "sklearn.utils._param_validation",
        "sklearn.utils._chunking",
        "sklearn.metrics",
        "sklearn.metrics.pairwise",
        "sklearn.cluster",
        "sklearn.neighbors",
        "sklearn.tree",
        "sklearn.linear_model",
        "sklearn.preprocessing",
        "pandas",
        "pandas.io",
        "pandas.io.formats",
        "pandas.io.formats.format",
        
        # AI/ML 相关
        "torch",
        "torchaudio",
        "numpy",
        "numpy.core",
        "numpy.linalg",
        "numpy.fft",
        "openai",
        "funasr",
        "funasr.auto",
        "funasr.auto.auto_model",
        "funasr.models",
        "funasr.models.paraformer",
        "funasr.models.paraformer.model",
        "funasr.models.sense_voice",
        "funasr.models.sense_voice.model",
        "funasr.models.sanm",
        "funasr.models.sanm.model",
        "funasr.models.e2e_asr_paraformer",
        "funasr.models.encoder",
        "funasr.models.encoder.sanm_encoder",
        "funasr.models.decoder",
        "funasr.models.decoder.sanm_decoder",
        "funasr.frontends",
        "funasr.frontends.wav_frontend",
        "funasr.utils",
        "funasr.utils.postprocess_utils",
        "funasr.utils.load_utils",
        "funasr.tokenizer",
        "funasr.download",
        "funasr.register",
        "silero_vad",
        "sherpa_onnx",
        "modelscope",
        "transformers",
        "transformers.generation",
        "transformers.generation.utils",
        "transformers.models",
        "transformers.models.auto",
        "accelerate",
        "vosk",
        "librosa",
        "librosa.core",
        "librosa.util",
        "soundfile",
        "audioread",
        "resampy",
        
        # TTS/ASR
        "edge_tts",
        "pydub",
        "opuslib_next",
        
        # 网络请求
        "httpx",
        "httpx._transports",
        "requests",
        "aiohttp",
        "socks",
        "socksio",
        
        # MCP 相关
        "mcp",
        "mcp_proxy",
        
        # 工具库
        "markitdown",
        "bs4",
        "lxml",
        "lxml.etree",
        "lxml.html",
        "psutil",
        "jwt",
        "jinja2",
        "dateparser",
        "dateparser.languages",
        "dateparser.data",
        "chardet",
        "portalocker",
        "cnlunar",
        "ormsgpack",
        "cozepy",
        "dashscope",
        "xml",
        "xml.etree",
        "xml.etree.ElementTree",
        
        # Google/百度 AI
        "google.generativeai",
        "aip",
        
        # onnxruntime
        "onnxruntime",
        "onnxruntime.capi",
        
        # 数据库
        "sqlite3",
        
        # 标准库
        "ssl",
        "certifi",
        "http.server",
        "webbrowser",
        "uuid",
        "hashlib",
        "json",
        "base64",
        "struct",
        "platform",
        "ctypes",
        "threading",
        "multiprocessing",
        "concurrent.futures",
        "asyncio",
        "signal",
        "importlib",
        "importlib.util",
        "pkgutil",
        "difflib",
        "traceback",
        "io",
        "wave",
        "random",
        "re",
        "shutil",
        "pathlib",
        "typing",
        "enum",
        "time",
        "copy",
        "functools",
        "itertools",
        "collections",
        "collections.abc",
    ]
    
    hidden_imports_str = ",\n        ".join([f"'{h}'" for h in hidden_imports])
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for xiaozhi-server

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# 收集 funasr 的所有子模块（funasr 使用动态注册机制）
funasr_hiddenimports = collect_submodules('funasr')

a = Analysis(
    [r'{PROJECT_DIR / "app.py"}'],
    pathex=[r'{PROJECT_DIR}'],
    binaries=[],
    datas=[
{datas_str}
    ],
    hiddenimports=[
        {hidden_imports_str}
    ] + funasr_hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'IPython',
        'notebook',
        'jupyter',
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
    name='xiaozhi-server',
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
    name='xiaozhi-server',
)
'''
    
    with open(SPEC_FILE, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"✓ 已创建 spec 文件: {SPEC_FILE}")


def build_exe():
    """使用 PyInstaller 编译"""
    print("\n" + "="*60)
    print("开始 PyInstaller 编译...")
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


def copy_license():
    """复制许可证文件"""
    # 目录模式下，EXE 在子文件夹中
    exe_dir = OUTPUT_DIR / "xiaozhi-server"
    license_file = PROJECT_DIR / "license.lic"
    if license_file.exists() and exe_dir.exists():
        shutil.copy2(license_file, exe_dir / "license.lic")
        print("✓ 复制 license.lic")


def create_readme():
    """创建说明文件"""
    exe_dir = OUTPUT_DIR / "xiaozhi-server"
    readme_content = """# XiaoZhi Server (独立版)

## 运行方法

1. 确保 license.lic 文件在本目录下
2. 双击运行 xiaozhi-server.exe
3. 程序会自动打开测试页面

## 文件说明

- xiaozhi-server.exe  - 主程序
- license.lic         - 许可证文件 (必需)
- _internal/          - 运行时依赖文件夹 (请勿删除)

## 端口说明

- WebSocket: 8000
- HTTP API: 8003  
- 测试页面: 8006

## 分发说明

分发时请将整个 xiaozhi-server 文件夹一起打包分发。

## 故障排除

如果程序无法启动：
1. 检查 license.lic 是否存在且有效
2. 检查端口是否被占用
3. 以管理员身份运行

## 日志

运行日志会保存在程序目录下的 exp/log 文件夹中。
"""
    
    if exe_dir.exists():
        with open(exe_dir / "README.txt", "w", encoding="utf-8") as f:
            f.write(readme_content)
        print("✓ 创建 README.txt")


def main():
    print("="*60)
    print("XiaoZhi Server - PyInstaller 打包工具")
    print("="*60)
    print(f"项目目录: {PROJECT_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    print()
    
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
        copy_license()
        create_readme()
        print("\n" + "="*60)
        print(f"打包完成! EXE 位置: {OUTPUT_DIR / 'xiaozhi-server' / 'xiaozhi-server.exe'}")
        print("分发时请将整个 xiaozhi-server 文件夹打包")
        print("="*60)
    else:
        print("\n打包失败，请检查错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()
