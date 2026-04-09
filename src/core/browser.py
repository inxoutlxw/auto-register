"""Playwright 浏览器管理器。封装浏览器启动、Stealth 注入和代理配置。"""

import os
from typing import Any

from utils.logger import get_logger

logger = get_logger("core.browser")


def create_browser_context(
    sync_playwright: Any,
    headless: bool = False,
) -> tuple[Any, Any]:
    """创建 Playwright 浏览器和上下文。

    根据环境变量自动配置：
    - USE_PLAYWRIGHT_STEALTH=true → 注入 playwright-stealth 插件防机器人检测
    - HTTP_PROXY_URL → 设置浏览器底层 HTTP/SOCKS 代理

    Args:
        sync_playwright: Playwright sync_playwright 实例。
        headless: 是否使用无头模式。

    Returns:
        (browser, context) 元组。
    """
    enable_stealth = os.environ.get("USE_PLAYWRIGHT_STEALTH", "false").lower() == "true"
    proxy_url = os.environ.get("HTTP_PROXY_URL")

    # 构建启动参数
    launch_kwargs: dict[str, Any] = {"headless": headless}
    if proxy_url:
        launch_kwargs["proxy"] = {"server": proxy_url}
        logger.info(f"已配置代理服务器: {proxy_url}")

    browser = sync_playwright.chromium.launch(**launch_kwargs)
    context = browser.new_context()

    # 可选：注入 Stealth 插件
    if enable_stealth:
        try:
            from playwright_stealth import Stealth  # type: ignore
            stealth = Stealth()
            stealth.apply_stealth_sync(context)
        except ImportError:
            logger.warning("playwright-stealth 未安装，跳过 Stealth 注入。请执行: pip install playwright-stealth")
        except Exception as e:
            logger.warning(f"Stealth 启用失败，回退到普通浏览器: {e}")

    return browser, context
