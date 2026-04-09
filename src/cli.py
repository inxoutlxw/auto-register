"""命令行入口，配置驱动的自动注册流程。"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 确保加载项目根目录的 .env
_project_root = Path(__file__).resolve().parents[1]
_env_path = _project_root / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)

# 将 src/ 加入模块搜索路径
_src_dir = Path(__file__).resolve().parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from core.config_loader import load_site_config
from core.engine import RegistrationEngine
from providers import get_email_provider
from sites import get_site_strategy
from writers import get_output_writer
from utils.logger import get_logger

logger = get_logger("cli")


def main() -> int:
    """CLI 入口函数。"""
    parser = argparse.ArgumentParser(
        description="可配置的自动注册工具。通过 YAML 配置驱动注册流程。"
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="使用无头浏览器运行",
    )
    parser.add_argument(
        "--site", type=str,
        help="目标站点名称（对应 config/ 下的 yaml 文件名，覆盖 TARGET_SITE 环境变量）",
    )
    parser.add_argument(
        "--email-provider", type=str,
        help="邮箱提供者（覆盖 AUTO_REGISTER_EMAIL_PROVIDER 环境变量）",
    )
    args = parser.parse_args()

    # 环境变量覆盖
    if args.site:
        os.environ["TARGET_SITE"] = args.site
    if args.email_provider:
        os.environ["AUTO_REGISTER_EMAIL_PROVIDER"] = args.email_provider

    try:
        # 加载站点配置
        config = load_site_config()
        logger.info(f"目标站点: {config.name}")

        # 从注册表获取组件
        email_provider_name = os.environ.get("AUTO_REGISTER_EMAIL_PROVIDER", "mailtm")
        poll_interval = float(os.environ.get("AUTO_REGISTER_POLL_INTERVAL", "5"))
        email_timeout = float(os.environ.get("AUTO_REGISTER_EMAIL_TIMEOUT", "120"))

        email_provider = get_email_provider(
            provider_name=email_provider_name,
            poll_interval=poll_interval,
            timeout=email_timeout,
        )
        site_strategy = get_site_strategy(config.name)
        output_format = config.output.get("format", "json")
        output_writer = get_output_writer(output_format)

        logger.info(f"邮箱提供者: {email_provider_name}")

        # 创建引擎并执行
        engine = RegistrationEngine(
            config=config,
            email_provider=email_provider,
            site_strategy=site_strategy,
            output_writer=output_writer,
            headless=args.headless,
        )
        success = engine.run()
        return 0 if success else 1

    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
