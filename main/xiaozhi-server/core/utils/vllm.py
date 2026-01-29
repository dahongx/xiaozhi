import os
import sys

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
sys.path.insert(0, project_root)

from config.logger import setup_logging
import importlib

logger = setup_logging()


def get_base_path():
    """获取基础路径，支持打包环境"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后
        return sys._MEIPASS
    else:
        # 开发环境
        return project_root


def create_instance(class_name, *args, **kwargs):
    # 创建VLLM实例
    base_path = get_base_path()
    provider_path = os.path.join(base_path, "core", "providers", "vllm", f"{class_name}.py")
    
    # 也检查开发环境路径
    dev_path = os.path.join("core", "providers", "vllm", f"{class_name}.py")
    
    if os.path.exists(provider_path) or os.path.exists(dev_path):
        lib_name = f"core.providers.vllm.{class_name}"
        if lib_name not in sys.modules:
            sys.modules[lib_name] = importlib.import_module(f"{lib_name}")
        return sys.modules[lib_name].VLLMProvider(*args, **kwargs)

    raise ValueError(f"不支持的VLLM类型: {class_name}，请检查该配置的type是否设置正确")
