"""站点 YAML 配置文件加载器。"""

import os
from pathlib import Path
from typing import Optional

import yaml

from utils.logger import get_logger
from core.interfaces import SiteConfig

logger = get_logger("core.config_loader")


def _get_config_dir() -> Path:
    """获取配置文件目录。优先使用环境变量 CONFIG_DIR，否则使用项目根下的 config/。"""
    if config_dir := os.environ.get("CONFIG_DIR"):
        return Path(config_dir)
    # src/ 的父目录即项目根
    return Path(__file__).resolve().parents[2] / "config"


def load_site_config(site_name: Optional[str] = None) -> SiteConfig:
    """加载站点配置。

    Args:
        site_name: 站点名称，对应 config/ 下的 yaml 文件名（不含 .yaml）。
                   为 None 时从环境变量 TARGET_SITE 读取，默认 "qwen"。

    Returns:
        SiteConfig 实例。

    Raises:
        FileNotFoundError: 找不到对应的配置文件。
        yaml.YAMLError: YAML 解析失败。
    """
    target = (site_name or os.environ.get("TARGET_SITE", "qwen")).strip().lower()
    config_path = _get_config_dir() / f"{target}.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"找不到站点配置文件: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"配置文件格式错误（顶层必须是字典）: {config_path}")

    # 提取全局超时配置（从环境变量）
    timeouts = {
        "navigation_ms": int(os.environ.get("TIMEOUT_NAVIGATION_MS", "30000")),
        "element_visible_ms": int(os.environ.get("TIMEOUT_ELEMENT_VISIBLE_MS", "10000")),
        "element_short_ms": int(os.environ.get("TIMEOUT_ELEMENT_SHORT_MS", "5000")),
        "page_load_ms": int(os.environ.get("TIMEOUT_PAGE_LOAD_MS", "2000")),
        "post_activation_ms": int(os.environ.get("TIMEOUT_POST_ACTIVATION_MS", "3000")),
        "post_login_ms": int(os.environ.get("TIMEOUT_POST_LOGIN_MS", "5000")),
        "pre_token_ms": int(os.environ.get("TIMEOUT_PRE_TOKEN_MS", "3000")),
        "networkidle_ms": int(os.environ.get("TIMEOUT_NETWORKIDLE_MS", "15000")),
        "submit_ready_ms": int(os.environ.get("TIMEOUT_SUBMIT_READY_MS", "10000")),
        "oauth_code_input_ms": int(os.environ.get("TIMEOUT_OAUTH_CODE_INPUT_MS", "2000")),
        "oauth_approve_btn_ms": int(os.environ.get("TIMEOUT_OAUTH_APPROVE_BTN_MS", "3000")),
        "post_approve_ms": int(os.environ.get("TIMEOUT_POST_APPROVE_MS", "2000")),
    }

    # 提取密码配置（从环境变量）
    def _is_true(val: str) -> bool:
        return val.lower() in ("true", "1", "yes", "y")

    password = {
        "length": int(os.environ.get("PASSWORD_LENGTH", "14")),
        "require_uppercase": _is_true(os.environ.get("PASSWORD_REQUIRE_UPPER", "true")),
        "require_lowercase": _is_true(os.environ.get("PASSWORD_REQUIRE_LOWER", "true")),
        "require_digits": _is_true(os.environ.get("PASSWORD_REQUIRE_DIGITS", "true")),
    }

    return SiteConfig(
        name=data.get("name", target),
        urls=data.get("urls", {}),
        timeouts=timeouts,
        selectors=data.get("selectors", {}),
        registration=data.get("registration", {}),
        activation=data.get("activation", {}),
        oauth=data.get("oauth", {}),
        output=data.get("output", {}),
        password=password,
    )
