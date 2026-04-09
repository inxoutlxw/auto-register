"""Qwen OAuth 2.0 设备码流程，获取 portal API token。

所有 OAuth 参数均从 SiteConfig.oauth 配置段读取，无硬编码。
"""

import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Callable, Optional

from utils.logger import get_logger

logger = get_logger("sites.qwen.oauth")


def _pkce() -> tuple[str, str]:
    """生成 PKCE verifier 与 challenge (base64url)。"""
    verifier = secrets.token_urlsafe(32)
    challenge = hashlib.sha256(verifier.encode()).digest()
    challenge_b64 = base64.urlsafe_b64encode(challenge).decode().rstrip("=")
    return verifier, challenge_b64


def request_device_code(
    oauth_config: dict[str, Any],
    page: Optional[Any] = None,
) -> dict[str, Any]:
    """请求设备码。

    Args:
        oauth_config: 来自 SiteConfig.oauth 的配置。
        page: 可选 Playwright Page，在浏览器上下文中请求以通过 WAF。

    Returns:
        包含 device_code, user_code, verification_uri 等字段的字典（附加 _verifier）。
    """
    base_url = oauth_config["base_url"]
    device_code_path = oauth_config.get("device_code_path", "/api/v1/oauth2/device/code")
    client_id = oauth_config["client_id"]
    scope = oauth_config.get("scope", "openid profile email")
    url = f"{base_url}{device_code_path}"

    verifier, challenge = _pkce()
    body = {
        "client_id": client_id,
        "scope": scope,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    body_str = urllib.parse.urlencode(body)

    if page is not None:
        raw = _fetch_via_page(page, url, body_str)
    else:
        raw = _fetch_via_urllib(url, body_str)

    if not raw.strip():
        raise ValueError("设备码接口返回空响应")

    out = json.loads(raw)
    out["_verifier"] = verifier
    return out


def poll_token(
    device_code: str,
    code_verifier: str,
    oauth_config: dict[str, Any],
    page: Optional[Any] = None,
) -> tuple[str, Optional[dict[str, Any]]]:
    """轮询 token 端点。

    返回 (status, result)：
      ("pending", None) - 等待授权
      ("pending", {"slow_down": True}) - 需降低轮询频率
      ("success", dict) - 成功，包含 access, refresh, expires
      ("error", {"message": ...}) - 失败
    """
    base_url = oauth_config["base_url"]
    token_path = oauth_config.get("token_path", "/api/v1/oauth2/token")
    client_id = oauth_config["client_id"]
    grant_type = "urn:ietf:params:oauth:grant-type:device_code"
    url = f"{base_url}{token_path}"

    body = {
        "grant_type": grant_type,
        "client_id": client_id,
        "device_code": device_code,
        "code_verifier": code_verifier,
    }
    body_str = urllib.parse.urlencode(body)

    if page is not None:
        return _poll_via_page(page, url, body_str)
    else:
        return _poll_via_urllib(url, body_str)


def run_device_code_flow(
    oauth_config: dict[str, Any],
    open_verification_url: Callable[[str, str], None],
    on_wait: Optional[Callable[[], None]] = None,
    poll_interval: float = 2.0,
    timeout_seconds: float = 300.0,
    page_for_requests: Optional[Any] = None,
) -> Optional[dict[str, Any]]:
    """执行设备码 OAuth 流程，获取 API token。

    Args:
        oauth_config: 来自 SiteConfig.oauth 的配置。
        open_verification_url: 回调 (url, user_code)，打开授权页。
        on_wait: 可选，轮询时回调。
        poll_interval: 轮询间隔（秒）。
        timeout_seconds: 超时（秒）。
        page_for_requests: 可选 Playwright Page，在浏览器上下文中请求。

    Returns:
        {access, refresh, expires} 或 None。
    """
    dev = request_device_code(oauth_config, page=page_for_requests)
    dc = dev.get("device_code")
    uc = dev.get("user_code")
    uri = dev.get("verification_uri_complete") or dev.get("verification_uri")
    verifier = dev.get("_verifier", "")
    exp_in = int(dev.get("expires_in", 900))
    interval = max(float(dev.get("interval", 2)), poll_interval)

    if not dc or not uc or not uri or not verifier:
        logger.error("设备码响应缺少必要字段")
        return None

    # logger.info(f"设备码: {uc}，授权页: {uri}")
    open_verification_url(uri, uc)

    deadline = time.time() + min(timeout_seconds, exp_in)
    while time.time() < deadline:
        status, result = poll_token(dc, verifier, oauth_config, page=page_for_requests)

        if status == "success" and result:
            logger.info("OAuth token 获取成功")
            return result

        if status == "error":
            msg = result.get("message", "未知错误") if result else "未知错误"
            logger.error(f"OAuth token 获取失败: {msg}")
            return None

        if status == "pending" and result and result.get("slow_down"):
            interval = min(interval * 1.5, 10.0)

        if on_wait:
            on_wait()
        time.sleep(interval)

    logger.error(f"OAuth 授权超时（{timeout_seconds}s）")
    return None


# ============================================================
# 内部辅助函数
# ============================================================


def _fetch_via_page(page: Any, url: str, body_str: str) -> str:
    """通过 Playwright Page 的 fetch 发送请求（通过 WAF）。"""
    script = """
    async ([url, body, requestId]) => {
        const r = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "x-request-id": requestId
            },
            body: body
        });
        return { status: r.status, text: await r.text() };
    }
    """
    result = page.evaluate(script, [url, body_str, str(uuid.uuid4())])
    if result["status"] != 200:
        raise ValueError(f"设备码请求失败: HTTP {result['status']}")
    return result["text"]


def _fetch_via_urllib(url: str, body_str: str) -> str:
    """通过 urllib 发送 HTTP 请求。"""
    req = urllib.request.Request(
        url,
        data=body_str.encode(),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "x-request-id": str(uuid.uuid4()),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode()


def _poll_via_page(
    page: Any, url: str, body_str: str
) -> tuple[str, Optional[dict[str, Any]]]:
    """通过 Playwright Page 轮询 token。"""
    script = """
    async ([url, body]) => {
        const r = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            },
            body: body
        });
        return { status: r.status, text: await r.text() };
    }
    """
    result = page.evaluate(script, [url, body_str])
    raw = result["text"]

    try:
        payload = json.loads(raw)
    except Exception:
        if result["status"] != 200:
            return "error", {"message": f"HTTP {result['status']}: {raw[:200]}"}
        raise

    if result["status"] != 200:
        return _parse_error_response(payload)

    return _parse_success_response(payload)


def _poll_via_urllib(
    url: str, body_str: str
) -> tuple[str, Optional[dict[str, Any]]]:
    """通过 urllib 轮询 token。"""
    req = urllib.request.Request(
        url,
        data=body_str.encode(),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode())
        except Exception:
            return "error", {"message": str(e)}
        return _parse_error_response(payload)

    return _parse_success_response(payload)


def _parse_error_response(
    payload: dict[str, Any],
) -> tuple[str, Optional[dict[str, Any]]]:
    """解析错误响应。"""
    err = payload.get("error", "")
    if err == "authorization_pending":
        return "pending", None
    if err == "slow_down":
        return "pending", {"slow_down": True}
    return "error", {
        "message": payload.get("error_description")
        or payload.get("error")
        or "未知错误"
    }


def _parse_success_response(
    payload: dict[str, Any],
) -> tuple[str, Optional[dict[str, Any]]]:
    """解析成功响应，提取 token。"""
    err = payload.get("error", "")
    if err == "authorization_pending":
        return "pending", None
    if err == "slow_down":
        return "pending", {"slow_down": True}
    if err:
        return "error", {
            "message": payload.get("error_description") or payload.get("error") or err
        }

    acc = payload.get("access_token") or payload.get("access")
    ref = payload.get("refresh_token") or payload.get("refresh")
    exp = payload.get("expires_in")

    if not acc or not ref:
        return "error", {"message": "OAuth 返回的 token 不完整"}

    # 计算过期时间（毫秒时间戳）
    expires = (
        int(time.time() * 1000) + (int(exp) * 1000)
        if exp
        else int(time.time() * 1000) + 30 * 24 * 60 * 60 * 1000
    )

    result: dict[str, Any] = {"access": acc, "refresh": ref, "expires": expires}
    if payload.get("resource_url"):
        result["resource_url"] = payload["resource_url"]

    return "success", result
