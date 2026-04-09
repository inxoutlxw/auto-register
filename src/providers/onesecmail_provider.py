"""1secMail 临时邮箱提供者。作为 Mail.tm 的备选方案（部分地区可能 403）。"""

import os
import random
import re
import string
import tempfile
import time
import uuid
from typing import Any, Optional

import httpx

from core.interfaces import EmailProvider
from utils.logger import get_logger

logger = get_logger("providers.onesecmail")

_1SEC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.1secmail.com/",
}
_1SEC_BASE = "https://www.1secmail.com/api/v1/"


def _extract_activation_url_from_text(text: str) -> Optional[str]:
    """从文本中提取激活链接 URL。"""
    url_pattern = r"https://[^\s<>\"']+"
    urls = re.findall(url_pattern, text)
    for url in urls:
        lower = url.lower()
        if any(
            kw in lower for kw in ("verify", "activate", "confirm", "token", "auth")
        ):
            return url
    return urls[0] if urls else None


class OneSecMailProvider(EmailProvider):
    """通过 1secMail API 提供临时邮箱。"""

    def __init__(self, poll_interval: float = 5.0, timeout: float = 120.0):
        self._poll_interval = poll_interval
        self._timeout = timeout
        self._domains: list[str] = []
        self._generated_in_session: set[str] = set()
        self._cache_path = os.environ.get(
            "AUTO_REGISTER_EMAIL_CACHE_PATH",
            os.path.join(tempfile.gettempdir(), "auto_register_used_emails.txt"),
        )

    def _load_used_cache(self) -> set[str]:
        """从文件缓存加载已使用的邮箱地址。"""
        try:
            if not os.path.exists(self._cache_path):
                return set()
            with open(self._cache_path, encoding="utf-8") as f:
                return {line.strip().lower() for line in f if line.strip()}
        except Exception as e:
            logger.warning(f"读取邮箱缓存失败: {e}")
            return set()

    def _append_used_cache(self, email: str) -> None:
        """将已使用的邮箱追加到文件缓存。"""
        try:
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            with open(self._cache_path, "a", encoding="utf-8") as f:
                f.write(email.lower().strip() + "\n")
        except Exception as e:
            logger.warning(f"写入邮箱缓存失败: {e}")

    def _request(self, action: str, params: Optional[dict[str, Any]] = None) -> Any:
        """向 1secMail API 发送请求。"""
        q: dict[str, Any] = {"action": action}
        if params:
            q.update(params)
        with httpx.Client(headers=_1SEC_HEADERS, timeout=30) as client:
            r = client.get(_1SEC_BASE, params=q)
            r.raise_for_status()
            return r.json()

    def _get_domains(self) -> list[str]:
        """获取可用域名列表（带缓存）。"""
        if not self._domains:
            self._domains = self._request("getDomainList")
        return self._domains

    def generate_email(self) -> str:
        """生成唯一的 1secMail 临时邮箱。"""
        domains = self._get_domains()
        used = self._load_used_cache()

        for _ in range(30):
            login = (
                uuid.uuid4().hex[:16] + "".join(random.choices(string.digits, k=4))
            ).lower()
            domain = random.choice(domains)
            email = f"{login}@{domain}".lower()

            # 防重：检查 session 缓存和文件缓存
            if email in self._generated_in_session or email in used:
                continue

            # 检查邮箱不存在未读邮件
            try:
                inbox = self._request(
                    "getMessages", params={"login": login, "domain": domain}
                )
                if inbox:
                    continue
            except Exception:
                pass

            self._generated_in_session.add(email)
            self._append_used_cache(email)
            logger.info(f"已生成 1secMail 邮箱: {email}")
            return email

        raise RuntimeError("1secMail: 生成唯一邮箱失败（已尝试 30 次）")

    def wait_for_activation_link(
        self,
        email: str,
        subject_contains: Optional[str] = None,
        from_contains: Optional[str] = None,
    ) -> str:
        """轮询 1secMail 收件箱，提取激活链接。"""
        login, domain = email.split("@")
        start = time.time()
        seen_ids: set[int] = set()

        while (time.time() - start) < self._timeout:
            inbox = self._request(
                "getMessages",
                params={"login": login, "domain": domain},
            )
            for msg in inbox or []:
                msg_id = msg.get("id")
                if msg_id in seen_ids:
                    continue

                # 按主题和发件人过滤
                subj = (msg.get("subject") or "").lower()
                from_addr = (msg.get("from", "") or "").lower()
                if subject_contains and subject_contains.lower() not in subj:
                    continue
                if from_contains and from_contains.lower() not in from_addr:
                    continue

                seen_ids.add(msg_id)

                # 获取完整邮件
                full = self._request(
                    "readMessage",
                    params={"login": login, "domain": domain, "id": msg_id},
                )
                text = full.get("htmlBody") or full.get("textBody") or full.get("body") or ""
                url = _extract_activation_url_from_text(text)
                if url:
                    return url

            time.sleep(self._poll_interval)

        raise TimeoutError(f"等待激活邮件超时（{self._timeout}s）: {email}")
