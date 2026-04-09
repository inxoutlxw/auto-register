"""站点策略注册表。新增站点只需在此文件注册即可。"""

from core.interfaces import SiteStrategy
from sites.qwen.qwen_site import QwenSiteStrategy

# 站点策略注册表：key 对应配置文件中的 name 字段
SITE_STRATEGY_REGISTRY: dict[str, type[SiteStrategy]] = {
    "qwen": QwenSiteStrategy,
}


def get_site_strategy(site_name: str) -> SiteStrategy:
    """根据站点名称从注册表获取策略实例。

    Args:
        site_name: 站点名称（注册表的 key）。

    Returns:
        SiteStrategy 实例。

    Raises:
        ValueError: 未找到对应的策略。
    """
    name = site_name.lower().strip()
    cls = SITE_STRATEGY_REGISTRY.get(name)
    if cls is None:
        available = ", ".join(SITE_STRATEGY_REGISTRY.keys())
        raise ValueError(f"未知的站点: '{name}'。可用: {available}")
    return cls()
