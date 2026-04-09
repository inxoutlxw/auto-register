"""Mail.tm 临时邮箱提供者。免 API Key，无 403 问题。"""

import random
import re
import string
import time
from typing import Optional

import httpx

from core.interfaces import EmailProvider
from utils.logger import get_logger

logger = get_logger("providers.mailtm")

_MAILTM_BASE = "https://api.mail.tm"


def _extract_activation_url_from_text(text: str) -> Optional[str]:
    """从文本中提取激活链接 URL。

    优先返回 URL 中包含 verify/activate/confirm/token/auth 关键词的链接，
    若无匹配则返回第一个 URL，完全无 URL 返回 None。
    """
    url_pattern = r"https://[^\s<>\"']+"
    urls = re.findall(url_pattern, text)
    for url in urls:
        lower = url.lower()
        if any(
            kw in lower for kw in ("verify", "activate", "confirm", "token", "auth")
        ):
            return url
    return urls[0] if urls else None


class MailTmProvider(EmailProvider):
    """通过 Mail.tm API 提供临时邮箱。"""

    def __init__(self, poll_interval: float = 5.0, timeout: float = 120.0):
        self._poll_interval = poll_interval
        self._timeout = timeout
        self._email: Optional[str] = None
        self._password: Optional[str] = None

    def generate_email(self) -> str:
        """创建 Mail.tm 账户并返回邮箱地址。"""
        with httpx.Client(timeout=30) as client:
            # 获取可用域名
            r = client.get(f"{_MAILTM_BASE}/domains")
            r.raise_for_status()
            data = r.json()
            domains = [
                d["domain"] for d in data.get("hydra:member", []) if d.get("domain")
            ]
            if not domains:
                raise RuntimeError("Mail.tm: 无可用域名")

            domain = random.choice(domains)
            login = "".join(
                random.choices(string.ascii_lowercase + string.digits, k=12)
            )
            self._password = "".join(
                random.choices(string.ascii_letters + string.digits, k=16)
            )
            address = f"{login}@{domain}"

            # 创建账户
            r2 = client.post(
                f"{_MAILTM_BASE}/accounts",
                json={"address": address, "password": self._password},
                headers={"Content-Type": "application/json"},
            )
            r2.raise_for_status()
            self._email = address
            return address

    def wait_for_activation_link(
        self,
        email: str,
        subject_contains: Optional[str] = None,
        from_contains: Optional[str] = None,
    ) -> str:
        """轮询 Mail.tm 收件箱，提取激活链接。"""
        pw = self._password if email == self._email else None
        if not pw:
            raise ValueError(
                "MailTmProvider: 必须先调用 generate_email() 生成该邮箱地址"
            )

        # 获取 Bearer token
        with httpx.Client(timeout=30) as client:
            r = client.post(
                f"{_MAILTM_BASE}/token",
                json={"address": email, "password": pw},
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            token = r.json()["token"]

        start = time.time()
        seen_ids: set[str] = set()
        headers = {"Authorization": f"Bearer {token}"}

        logger.info(f"开始轮询 Mail.tm 收件箱（超时 {self._timeout}s）...")
        while (time.time() - start) < self._timeout:
            with httpx.Client(timeout=30) as c:
                r = c.get(f"{_MAILTM_BASE}/messages", headers=headers)
                r.raise_for_status()
                items = r.json().get("hydra:member", [])

            for msg in items:
                mid = msg.get("id")
                if mid in seen_ids:
                    continue

                # 按主题和发件人过滤
                subj = (msg.get("subject") or "").lower()
                from_addr = (msg.get("from", {}).get("address", "") or "").lower()
                if subject_contains and subject_contains.lower() not in subj:
                    continue
                if from_contains and from_contains.lower() not in from_addr:
                    continue

                seen_ids.add(mid)

                # 获取完整邮件内容
                with httpx.Client(timeout=30) as c:
                    r2 = c.get(f"{_MAILTM_BASE}/messages/{mid}", headers=headers)
                    r2.raise_for_status()
                    full = r2.json()

                # 解析邮件内容（优先级：html > text）
                text = self._extract_body(full)
                url = _extract_activation_url_from_text(text)
                if url:
                    logger.info("已找到激活链接")
                    return url

            time.sleep(self._poll_interval)

        raise TimeoutError(f"等待激活邮件超时（{self._timeout}s）: {email}")

    @staticmethod
    def _extract_body(full: dict) -> str:
        """从邮件完整数据中提取正文。优先级：html > text > str(full)。"""
        html = full.get("html")
        txt = full.get("text")

        if isinstance(html, list) and html:
            return html[0] or ""
        if isinstance(html, str):
            return html
        if isinstance(txt, list) and txt:
            return txt[0] or ""
        if isinstance(txt, str):
            return txt
        return str(full)
