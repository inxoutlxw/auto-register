"""邮箱提供者注册表。新增提供者只需在此文件注册即可。"""

from core.interfaces import EmailProvider
from providers.mailtm_provider import MailTmProvider
from providers.onesecmail_provider import OneSecMailProvider

# 邮箱提供者注册表：key 对应环境变量 AUTO_REGISTER_EMAIL_PROVIDER 的值
EMAIL_PROVIDER_REGISTRY: dict[str, type[EmailProvider]] = {
    "mailtm": MailTmProvider,
    "1secmail": OneSecMailProvider,
}


def get_email_provider(
    provider_name: str = "mailtm",
    poll_interval: float = 5.0,
    timeout: float = 120.0,
) -> EmailProvider:
    """根据名称从注册表获取邮箱提供者实例。

    Args:
        provider_name: 提供者名称（注册表的 key）。
        poll_interval: 轮询间隔（秒）。
        timeout: 等待超时（秒）。

    Returns:
        EmailProvider 实例。

    Raises:
        ValueError: 未找到对应的提供者。
    """
    name = provider_name.lower().strip()
    cls = EMAIL_PROVIDER_REGISTRY.get(name)
    if cls is None:
        available = ", ".join(EMAIL_PROVIDER_REGISTRY.keys())
        raise ValueError(f"未知的邮箱提供者: '{name}'。可用: {available}")
    return cls(poll_interval=poll_interval, timeout=timeout)
