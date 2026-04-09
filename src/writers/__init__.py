"""输出写入器注册表。新增输出格式只需在此文件注册即可。"""

from core.interfaces import OutputWriter
from writers.json_writer import JsonWriter
from writers.env_writer import EnvWriter

# 输出写入器注册表：key 对应配置文件中 output.format 的值
OUTPUT_WRITER_REGISTRY: dict[str, type[OutputWriter]] = {
    "json": JsonWriter,
    "env": EnvWriter,
}


def get_output_writer(format_name: str = "json") -> OutputWriter:
    """根据格式名称从注册表获取输出写入器实例。

    Args:
        format_name: 输出格式名称（注册表的 key）。

    Returns:
        OutputWriter 实例。

    Raises:
        ValueError: 未找到对应的写入器。
    """
    name = format_name.lower().strip()
    cls = OUTPUT_WRITER_REGISTRY.get(name)
    if cls is None:
        available = ", ".join(OUTPUT_WRITER_REGISTRY.keys())
        raise ValueError(f"未知的输出格式: '{name}'。可用: {available}")
    return cls()
