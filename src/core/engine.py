"""通用注册引擎。通过配置 + 策略编排完整的注册流程，不含任何站点特定逻辑。"""

from typing import Callable, Optional

from playwright.sync_api import sync_playwright

from core.browser import create_browser_context
from core.interfaces import Credentials, EmailProvider, OutputWriter, SiteConfig, SiteStrategy
from providers.username_provider import UsernameProvider
from utils.logger import get_logger
from utils.password import PasswordPolicy, generate_password

logger = get_logger("core.engine")


class RegistrationEngine:
    """通用注册引擎。

    通过注入的 EmailProvider / SiteStrategy / OutputWriter 执行流程，
    引擎本身不包含任何站点特定逻辑——遵循开闭原则。
    """

    def __init__(
        self,
        config: SiteConfig,
        email_provider: EmailProvider,
        site_strategy: SiteStrategy,
        output_writer: OutputWriter,
        headless: bool = False,
        on_step: Optional[Callable[[str], None]] = None,
    ):
        """初始化引擎。

        Args:
            config: 站点配置。
            email_provider: 邮箱提供者实例。
            site_strategy: 站点策略实例。
            output_writer: 输出写入器实例。
            headless: 是否使用无头浏览器。
            on_step: 可选进度回调。
        """
        self._config = config
        self._email_provider = email_provider
        self._site_strategy = site_strategy
        self._output_writer = output_writer
        self._headless = headless
        self._on_step = on_step or (lambda _: None)

    def _log(self, msg: str) -> None:
        """同时写入 logger 和进度回调。"""
        logger.info(msg)
        self._on_step(msg)

    def run(self) -> bool:
        """执行完整注册流程。

        流程：
        1. 生成凭证（邮箱、用户名、密码）
        2. 启动浏览器
        3. 填写注册表单
        4. 等待激活邮件
        5. 打开激活链接
        6. 判断是否需要登录 → 登录
        7. 提取 token
        8. 写入输出文件

        Returns:
            True 表示成功，False 表示失败。
        """
        # ① 生成凭证
        creds = self._generate_credentials()
        self._log(f"1. 临时邮箱: {creds.email}")
        self._log("2. 随机密码已生成")

        # ② 启动浏览器
        with sync_playwright() as p:
            browser, context = create_browser_context(p, headless=self._headless)
            page = context.new_page()

            try:
                return self._execute_flow(page, creds)
            except Exception as e:
                self._log(f"错误: {e}")
                raise
            finally:
                browser.close()

    def _generate_credentials(self) -> Credentials:
        """根据配置生成注册凭证。"""
        email = self._email_provider.generate_email()

        username = UsernameProvider().get()

        pwd_cfg = self._config.password
        policy = PasswordPolicy(
            length=pwd_cfg.get("length", 14),
            require_uppercase=pwd_cfg.get("require_uppercase", True),
            require_lowercase=pwd_cfg.get("require_lowercase", True),
            require_digits=pwd_cfg.get("require_digits", True),
        )
        password = generate_password(policy)

        return Credentials(username=username, email=email, password=password)

    def _execute_flow(self, page: object, creds: Credentials) -> bool:
        """在浏览器中执行完整流程。"""
        config = self._config

        # ③ 注册
        self._log("3. 打开注册页并填写表单")
        self._site_strategy.register(page, creds, config)
        self._log("4. 已提交注册，等待激活邮件...")

        # ④ 等待激活邮件
        activation_cfg = config.activation
        activation_url = self._email_provider.wait_for_activation_link(
            creds.email,
            subject_contains=activation_cfg.get("subject_contains"),
            from_contains=activation_cfg.get("from_contains"),
        )
        self._log("5. 收到激活邮件")

        # ⑤ 激活
        self._site_strategy.activate(page, activation_url, config)
        self._log("6. 已打开激活链接")

        # ⑥ 判断是否需要登录
        needs_login = self._site_strategy.needs_login(page, config)
        if needs_login:
            self._log("7. 填写登录表单")
            self._site_strategy.login(page, creds, config)
            self._log("8. 已提交登录")
        else:
            self._log("7. 激活后已自动登录，跳过登录步骤")

        post_login_wait = config.get_timeout("post_login_ms", 5000)
        page.wait_for_timeout(post_login_wait)

        # ⑦ 提取 token
        self._log("9. 提取 token...")
        tokens = self._site_strategy.extract_token(
            page, config,
            headless=self._headless,
            on_step=self._on_step,
        )
        if not tokens:
            self._log("9. Token 提取失败")
            return False

        # ⑧ 写入输出
        self._output_writer.write(tokens, creds, config)
        
        return True
