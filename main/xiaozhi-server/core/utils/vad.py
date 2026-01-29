import importlib
import os
import sys
from core.providers.vad.base import VADProviderBase
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


def get_base_path():
    """获取基础路径，支持打包环境"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_instance(class_name: str, *args, **kwargs) -> VADProviderBase:
    """工厂方法创建VAD实例"""
    base_path = get_base_path()
    provider_path = os.path.join(base_path, "core", "providers", "vad", f"{class_name}.py")
    dev_path = os.path.join("core", "providers", "vad", f"{class_name}.py")
    
    if os.path.exists(provider_path) or os.path.exists(dev_path):
        lib_name = f"core.providers.vad.{class_name}"
        if lib_name not in sys.modules:
            sys.modules[lib_name] = importlib.import_module(f"{lib_name}")
        return sys.modules[lib_name].VADProvider(*args, **kwargs)

    raise ValueError(f"不支持的VAD类型: {class_name}，请检查该配置的type是否设置正确")
