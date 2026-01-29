import os
import sys
import importlib
from config.logger import setup_logging

logger = setup_logging()


def get_base_path():
    """获取基础路径，支持打包环境"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后
        return sys._MEIPASS
    else:
        # 开发环境
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_instance(class_name, *args, **kwargs):
    # 创建Memory实例
    base_path = get_base_path()
    provider_path = os.path.join(base_path, 'core', 'providers', 'memory', class_name, f'{class_name}.py')
    
    # 也检查开发环境路径
    dev_path = os.path.join('core', 'providers', 'memory', class_name, f'{class_name}.py')
    
    if os.path.exists(provider_path) or os.path.exists(dev_path):
        lib_name = f'core.providers.memory.{class_name}.{class_name}'
        if lib_name not in sys.modules:
            sys.modules[lib_name] = importlib.import_module(f'{lib_name}')
        return sys.modules[lib_name].MemoryProvider(*args, **kwargs)

    raise ValueError(f"不支持的记忆服务类型: {class_name}")
