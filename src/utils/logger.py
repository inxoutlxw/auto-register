"""统一日志模块。所有模块应通过 get_logger() 获取 logger 实例，禁止使用裸 print。"""

import logging
import sys

# 项目根 logger 名称
_ROOT_LOGGER_NAME = "auto_register"

# 默认日志格式
_LOG_FORMAT = "[%(asctime)s] %(levelname)-5s %(name)s - %(message)s"
_DATE_FORMAT = "%H:%M:%S"

# 确保根 logger 只初始化一次
_initialized = False


def _init_root_logger() -> None:
    """初始化项目根 logger（仅首次调用生效）。"""
    global _initialized
    if _initialized:
        return

    root = logging.getLogger(_ROOT_LOGGER_NAME)
    root.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(handler)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """获取指定模块的 logger 实例。

    Args:
        name: 模块名，如 "core.engine"、"providers.mailtm"。
              最终 logger 名为 "auto_register.{name}"。

    Returns:
        配置好的 Logger 实例。
    """
    _init_root_logger()
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")
