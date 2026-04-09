"""核心接口定义。所有可插拔组件必须实现对应的 ABC 接口。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


# ============================================================
# 数据结构
# ============================================================


@dataclass
class SiteConfig:
    """站点配置数据结构（从 YAML 加载）。"""

    name: str

    # URL 配置
    urls: dict[str, str] = field(default_factory=dict)

    # 超时配置
    timeouts: dict[str, int] = field(default_factory=dict)

    # 表单选择器
    selectors: dict[str, str] = field(default_factory=dict)

    # 注册流程配置
    registration: dict[str, Any] = field(default_factory=dict)

    # 激活邮件配置
    activation: dict[str, Any] = field(default_factory=dict)

    # OAuth 配置（可选，部分站点不需要）
    oauth: dict[str, Any] = field(default_factory=dict)

    # 输出配置
    output: dict[str, Any] = field(default_factory=dict)

    # 密码策略配置
    password: dict[str, Any] = field(default_factory=dict)

    def get_timeout(self, key: str, default: int = 30000) -> int:
        """获取超时配置值（毫秒）。"""
        return int(self.timeouts.get(key, default))


@dataclass
class Credentials:
    """注册凭证。"""

    username: str
    email: str
    password: str


# ============================================================
# 可插拔组件接口
# ============================================================


class EmailProvider(ABC):
    """临时邮箱提供者接口。"""

    @abstractmethod
    def generate_email(self) -> str:
        """生成临时邮箱地址。"""
        ...

    @abstractmethod
    def wait_for_activation_link(
        self,
        email: str,
        subject_contains: str | None = None,
        from_contains: str | None = None,
    ) -> str:
        """轮询激活邮件并返回激活链接。

        Args:
            email: 要监听的邮箱地址。
            subject_contains: 可选，邮件主题包含的关键词。
            from_contains: 可选，发件人包含的关键词。

        Returns:
            激活链接 URL。

        Raises:
            TimeoutError: 超时未收到邮件。
        """
        ...


class SiteStrategy(ABC):
    """站点注册策略接口。每个目标站点实现此接口。"""

    @abstractmethod
    def register(self, page: Any, creds: Credentials, config: SiteConfig) -> None:
        """在页面上执行注册流程（填写表单并提交）。"""
        ...

    @abstractmethod
    def activate(self, page: Any, activation_url: str, config: SiteConfig) -> None:
        """打开激活链接并处理激活后的页面跳转。"""
        ...

    @abstractmethod
    def needs_login(self, page: Any, config: SiteConfig) -> bool:
        """判断激活后是否需要手动登录。"""
        ...

    @abstractmethod
    def login(self, page: Any, creds: Credentials, config: SiteConfig) -> None:
        """在页面上执行登录流程。"""
        ...

    @abstractmethod
    def extract_token(
        self,
        page: Any,
        config: SiteConfig,
        headless: bool = False,
        on_step: Optional[Callable[[str], None]] = None,
    ) -> Optional[dict[str, Any]]:
        """从页面中提取 token（如 OAuth 设备码流程）。

        Returns:
            包含 token 信息的字典，失败返回 None。
            至少应包含 access_token 和 refresh_token。
        """
        ...


class OutputWriter(ABC):
    """输出写入器接口。将 token 数据按指定格式写入文件。"""

    @abstractmethod
    def write(
        self,
        token_data: dict[str, Any],
        creds: Credentials,
        config: SiteConfig,
    ) -> Path:
        """将 token 数据写入文件。

        Args:
            token_data: 从站点策略提取的 token 信息。
            creds: 注册使用的凭证信息。
            config: 站点配置。

        Returns:
            写入的文件路径。
        """
        ...
