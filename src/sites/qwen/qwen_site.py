"""Qwen 站点注册策略。实现 SiteStrategy 接口，所有选择器、URL 和超时均从 SiteConfig 读取。"""

import json
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

from core.interfaces import Credentials, SiteConfig, SiteStrategy
from sites.qwen.qwen_oauth import run_device_code_flow
from utils.logger import get_logger
from utils.token_utils import is_valid_jwt, validate_tokens

logger = get_logger("sites.qwen")


class QwenSiteStrategy(SiteStrategy):
    """Qwen 站点的注册/激活/登录/Token 提取策略。

    所有超时值通过 config.get_timeout() 从 YAML 配置读取：
    - navigation_ms: 页面导航超时
    - element_visible_ms: 等待元素可见
    - element_short_ms: 短等待
    - page_load_ms: 页面加载后等待
    - post_activation_ms: 激活后等待
    - post_login_ms: 登录后等待
    - pre_token_ms: 提取 token 前等待
    - networkidle_ms: 等待网络空闲
    - submit_ready_ms: 等待提交按钮就绪
    - oauth_code_input_ms: 设备码输入框等待
    - oauth_approve_btn_ms: 同意按钮等待
    - post_approve_ms: 点击同意后等待
    """

    def register(self, page: Any, creds: Credentials, config: SiteConfig) -> None:
        """在 Qwen 注册页填写表单并提交。"""
        register_url = config.urls.get("register", "")
        nav_timeout = config.get_timeout("navigation_ms", 30000)
        page_load_wait = config.get_timeout("page_load_ms", 2000)
        el_visible = config.get_timeout("element_visible_ms", 10000)
        el_short = config.get_timeout("element_short_ms", 5000)
        submit_ready = config.get_timeout("submit_ready_ms", 10000)
        selectors = config.selectors
        reg_config = config.registration
        
        page.goto(register_url, wait_until="domcontentloaded", timeout=nav_timeout)
        page.wait_for_timeout(page_load_wait)

        # 填写用户名（可选）
        if reg_config.get("has_username", False):
            self._try_fill(page, selectors.get("username", ""), creds.username, "用户名", el_short)

        # 填写邮箱（必选）
        email_sel = selectors.get("email", 'input[type="email"]')
        email_input = page.locator(email_sel).first
        email_input.wait_for(state="visible", timeout=el_visible)
        email_input.fill(creds.email)
        logger.info("已填写邮箱")

        # 填写密码
        pw_sel = selectors.get("password", 'input[type="password"]')
        pw_inputs = page.locator(pw_sel)
        count = pw_inputs.count()
        if count >= 1:
            pw_inputs.nth(0).fill(creds.password)
        if count >= 2 and reg_config.get("has_confirm_password", False):
            pw_inputs.nth(1).fill(creds.password)
        logger.info("已填写密码")

        # 勾选同意协议（可选）
        if reg_config.get("has_agree_checkbox", False):
            self._try_click_agree(page, selectors.get("agree", ""))

        page.wait_for_timeout(800)

        # 提交表单
        submit_sel = selectors.get("submit_register", 'button[type="submit"]')
        submit = page.locator(submit_sel).first
        submit.wait_for(state="visible", timeout=el_short)

        # 等待按钮可点击（选择器从配置读取）
        submit_js_sel = selectors.get("submit_button_js", "button[type=submit]")
        page.wait_for_function(
            f"""() => {{
                const btn = document.querySelector('{submit_js_sel}');
                if (!btn) return false;
                if (btn.disabled) return false;
                if (btn.classList.contains('disabled')) return false;
                return true;
            }}""",
            timeout=submit_ready,
        )
        submit.click()

        post_wait = reg_config.get("post_submit_wait_ms", 3000)
        page.wait_for_timeout(post_wait)
        logger.info("注册表单已提交")

    def activate(self, page: Any, activation_url: str, config: SiteConfig) -> None:
        """打开激活链接。"""
        nav_timeout = config.get_timeout("navigation_ms", 30000)
        post_activation = config.get_timeout("post_activation_ms", 3000)

        logger.info("打开激活链接...")
        page.goto(activation_url, wait_until="domcontentloaded", timeout=nav_timeout)
        page.wait_for_timeout(post_activation)
        logger.info("激活链接已打开")

    def needs_login(self, page: Any, config: SiteConfig) -> bool:
        """判断激活后是否需要手动登录。"""
        if config.registration.get("post_activation_skip_login", False):
            return False

        url = page.url or ""
        home_url = config.urls.get("home", "")

        # 如果已在主站（非 auth 页），则不需要登录
        if home_url and home_url in url and "/auth" not in url:
            return False

        # 检查是否存在登录表单
        try:
            email_sel = config.selectors.get("email", 'input[type="email"]')
            email_input = page.locator(email_sel).first
            return email_input.is_visible()
        except Exception:
            return False

    def login(self, page: Any, creds: Credentials, config: SiteConfig) -> None:
        """在 Qwen 登录页填写邮箱密码并提交。"""
        login_url = config.urls.get("login", "")
        nav_timeout = config.get_timeout("navigation_ms", 30000)
        page_load_wait = config.get_timeout("page_load_ms", 2000)
        el_visible = config.get_timeout("element_visible_ms", 10000)
        post_login = config.get_timeout("post_login_ms", 5000)
        selectors = config.selectors

        # 如果当前不在登录页，先导航
        if "auth" not in page.url.lower() or "register" in page.url:
            logger.info(f"导航到登录页: {login_url}")
            page.goto(login_url, wait_until="domcontentloaded", timeout=nav_timeout)
            page.wait_for_timeout(page_load_wait)

        # 填写邮箱
        email_sel = selectors.get("email", 'input[type="email"]')
        email_input = page.locator(email_sel).first
        email_input.wait_for(state="visible", timeout=el_visible)
        email_input.fill(creds.email)

        # 填写密码
        pw_sel = selectors.get("password", 'input[type="password"]')
        pw_input = page.locator(pw_sel).first
        pw_input.fill(creds.password)

        # 提交
        submit_sel = selectors.get("submit_login", 'button[type="submit"]')
        submit = page.locator(submit_sel).first
        submit.click()

        page.wait_for_timeout(post_login)
        logger.info("登录已提交")

    def extract_token(
        self,
        page: Any,
        config: SiteConfig,
        headless: bool = False,
        on_step: Optional[Callable[[str], None]] = None,
    ) -> Optional[dict[str, Any]]:
        """通过 OAuth 设备码流程获取 API token。"""
        nav_timeout = config.get_timeout("navigation_ms", 30000)
        pre_token = config.get_timeout("pre_token_ms", 3000)
        oauth_config = config.oauth
        log = on_step or (lambda msg: logger.info(msg))

        if not oauth_config.get("enabled", False):
            logger.warning("OAuth 未启用，跳过 token 提取")
            return None

        # 确保在主站页面（通过 WAF）
        home_url = config.urls.get("home", "")
        try:
            if home_url and home_url not in (page.url or ""):
                page.goto(home_url, wait_until="domcontentloaded", timeout=nav_timeout)
            page.wait_for_load_state("networkidle", timeout=nav_timeout)
        except Exception as e:
            logger.warning(f"导航到主站失败（继续尝试）: {e}")
        page.wait_for_timeout(pre_token)

        # 从配置读取 OAuth 轮询参数
        poll_interval = float(oauth_config.get("poll_interval", 2.0))
        timeout_seconds = float(oauth_config.get("timeout_seconds", 300.0))

        # 定义 OAuth 回调
        def open_url(url: str, user_code: str) -> None:
            page.goto(url, wait_until="domcontentloaded", timeout=nav_timeout)
            if headless:
                log("[OAuth] 无头模式：自动填写设备码并点击「同意」...")
                self._auto_approve_oauth(page, user_code, oauth_config, config)
            else:
                log(f"请在打开的页面输入码 {user_code} 并点击「同意」")

        def on_wait() -> None:
            log("[OAuth] 等待用户授权...")

        log("启动 OAuth 设备码流程，获取 API token...")
        tokens = run_device_code_flow(
            oauth_config=oauth_config,
            open_verification_url=open_url,
            on_wait=on_wait,
            poll_interval=poll_interval,
            timeout_seconds=timeout_seconds,
            page_for_requests=page,
        )

        if not tokens:
            log("OAuth 获取失败")
            return None

        # 验证 token
        access = tokens["access"]
        refresh = tokens["refresh"]
        jwt_flag = "JWT" if is_valid_jwt(access) else "非 JWT"
        log(f"[调试] Token 格式: {jwt_flag}, access(len={len(access)}) refresh(len={len(refresh)})")

        try:
            validate_tokens(
                access, refresh,
                allow_same=(access == refresh),
                allow_api_token=True,
            )
        except ValueError as e:
            log(f"Token 验证失败: {e}")
            return None

        return tokens

    # ============================================================
    # 内部辅助方法
    # ============================================================

    @staticmethod
    def _try_fill(
        page: Any, selector: str, value: str, field_name: str, timeout: int = 5000
    ) -> None:
        """尝试填写表单字段，失败时记录日志但不中断流程。"""
        if not selector:
            return
        try:
            input_el = page.locator(selector).first
            input_el.wait_for(state="visible", timeout=timeout)
            input_el.fill(value)
            logger.info(f"已填写 {field_name}")
        except Exception as e:
            logger.warning(f"填写 {field_name} 失败（非致命）: {e}")

    @staticmethod
    def _try_click_agree(page: Any, selector: str) -> None:
        """尝试勾选同意框。"""
        if not selector:
            return
        try:
            parts = [s.strip() for s in selector.split(",")]
            for part in parts:
                try:
                    el = page.locator(part).first
                    if el.count() > 0:
                        el.click()
                        logger.info("已勾选同意协议")
                        return
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"勾选同意框失败（非致命）: {e}")

    def _auto_approve_oauth(
        self, page: Any, user_code: str,
        oauth_config: dict[str, Any], config: SiteConfig,
    ) -> None:
        """无头模式下自动填写设备码并点击 OAuth 授权同意按钮。"""
        networkidle_timeout = config.get_timeout("networkidle_ms", 15000)
        page_load_wait = config.get_timeout("page_load_ms", 2000)

        try:
            page.wait_for_load_state("networkidle", timeout=networkidle_timeout)
        except Exception:
            pass
        # 等待页面加载完成，使用 page_load_ms 的两倍作为额外安全等待
        page.wait_for_timeout(page_load_wait * 2)

        # 填写设备码
        if user_code:
            self._fill_device_code(page, user_code, oauth_config, config)

        # 点击同意按钮
        self._click_approve_button(page, oauth_config, config)

    def _fill_device_code(
        self, page: Any, user_code: str,
        oauth_config: dict[str, Any], config: SiteConfig,
    ) -> None:
        """填写设备码输入框。选择器列表从 oauth_config 读取。"""
        code_selectors = oauth_config.get("code_input_selectors", [])
        code_input_timeout = config.get_timeout("oauth_code_input_ms", 2000)

        for sel in code_selectors:
            try:
                inp = page.locator(sel).first
                if inp.count() > 0:
                    inp.wait_for(state="visible", timeout=code_input_timeout)
                    inp.fill(user_code)
                    page.wait_for_timeout(1500)
                    logger.info("已自动填写设备码")
                    return
            except Exception:
                continue
        logger.warning("未找到设备码输入框")

    def _click_approve_button(
        self, page: Any, oauth_config: dict[str, Any], config: SiteConfig,
    ) -> None:
        """遍历选择器列表点击同意按钮，失败则用 JS 回退。"""
        approve_selectors = oauth_config.get("approve_selectors", [])
        approve_btn_timeout = config.get_timeout("oauth_approve_btn_ms", 3000)
        post_approve = config.get_timeout("post_approve_ms", 2000)

        # 方式一：Playwright 选择器
        for sel in approve_selectors:
            try:
                btn = page.locator(sel).first
                btn.wait_for(state="visible", timeout=approve_btn_timeout)
                btn.click()
                logger.info("已自动点击同意按钮")
                page.wait_for_timeout(post_approve)
                return
            except Exception:
                continue

        # 方式二：JS 回退查找（文本列表从配置读取）
        js_texts = oauth_config.get("js_approve_texts", [
            "同意", "授权", "允许", "Approve", "Authorize", "Allow", "确认"
        ])
        js_texts_json = json.dumps(js_texts, ensure_ascii=False)
        clicked = page.evaluate(f"""() => {{
            const texts = {js_texts_json};
            const nodes = document.querySelectorAll('button, a, [role="button"], input[type="submit"]');
            for (const el of nodes) {{
                const t = (el.textContent || '').trim();
                if (texts.some(x => t.includes(x))) {{
                    el.click();
                    return true;
                }}
            }}
            return false;
        }}""")
        if clicked:
            logger.info("已自动点击同意按钮（JS 回退）")
            page.wait_for_timeout(post_approve)
            return

        # 失败截图
        try:
            path = Path(tempfile.gettempdir()) / "oauth_approve_fail.png"
            page.screenshot(path=path)
            logger.error(f"未找到同意按钮，截图已保存: {path}")
        except Exception:
            logger.error("未找到同意按钮，请检查授权页结构")
