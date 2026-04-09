"""JSON 格式输出写入器。按配置中的 output.fields 模板生成 JSON 文件。"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.interfaces import Credentials, OutputWriter, SiteConfig
from utils.logger import get_logger

logger = get_logger("writers.json")


class JsonWriter(OutputWriter):
    """将 token 数据按 YAML 配置中定义的字段映射写入 JSON 文件。"""

    def write(
        self,
        token_data: dict[str, Any],
        creds: Credentials,
        config: SiteConfig,
    ) -> Path:
        """将 token 数据写入 JSON 文件。

        配置段 output 中的关键字段：
        - directory: 输出目录（默认 ./token）
        - filename_template: 文件名模板（支持 {site_name}、{timestamp}）
        - fields: 字段映射模板

        Args:
            token_data: 从站点策略提取的原始 token 信息。
            creds: 注册凭证。
            config: 站点配置。

        Returns:
            写入的文件路径。
        """
        output_cfg = config.output

        # 确定输出目录
        out_dir = self._resolve_output_dir(output_cfg)

        # 生成文件名
        filename = self._resolve_filename(output_cfg, config.name)

        # 构建输出数据
        data = self._build_output(output_cfg, token_data, creds, config)

        # 写入文件
        file_path = out_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Token 已写入: {file_path}")
        return file_path

    def _resolve_output_dir(self, output_cfg: dict[str, Any]) -> Path:
        """解析输出目录。优先环境变量 SAVE_DIR，否则使用配置中的 directory。"""
        if save_dir := os.environ.get("SAVE_DIR"):
            return Path(save_dir)

        directory = output_cfg.get("directory", "./token")
        path = Path(directory)

        # 如果是相对路径，则相对于项目根目录
        if not path.is_absolute():
            project_root = Path(__file__).resolve().parents[2]
            path = project_root / path

        return path

    def _resolve_filename(self, output_cfg: dict[str, Any], site_name: str) -> str:
        """根据模板生成文件名。"""
        template = output_cfg.get(
            "filename_template", "{site_name}-{timestamp}.json"
        )
        timestamp = str(int(time.time() * 1000))
        return template.format(site_name=site_name, timestamp=timestamp)

    def _build_output(
        self,
        output_cfg: dict[str, Any],
        token_data: dict[str, Any],
        creds: Credentials,
        config: SiteConfig,
    ) -> dict[str, Any]:
        """根据配置中的 fields 模板构建输出数据。

        支持的变量：
        - {access_token}: access token
        - {refresh_token}: refresh token
        - {email}: 注册邮箱
        - {resource_url}: 资源 URL（从 token_data 中获取）
        - {expired_iso}: 过期时间 ISO 格式
        - {last_refresh_iso}: 最后刷新时间 ISO 格式
        - {site_name}: 站点名称
        """
        fields_template = output_cfg.get("fields")

        if not fields_template:
            # 无模板配置，直接返回 token_data 的原始数据
            return token_data

        # 构建变量上下文
        now = datetime.now(timezone.utc)
        expires_ms = token_data.get("expires", 0)
        expires_dt = datetime.fromtimestamp(expires_ms / 1000, tz=timezone.utc) if expires_ms else now

        context = {
            "access_token": token_data.get("access", ""),
            "refresh_token": token_data.get("refresh", ""),
            "email": creds.email,
            "resource_url": token_data.get("resource_url", ""),
            "expired_iso": expires_dt.isoformat(),
            "last_refresh_iso": now.isoformat(),
            "site_name": config.name,
        }

        # 渲染模板
        result: dict[str, Any] = {}
        for key, value in fields_template.items():
            if isinstance(value, str) and "{" in value:
                try:
                    result[key] = value.format(**context)
                except KeyError:
                    result[key] = value
            else:
                # 非模板值（如 disabled: false），直接保留
                result[key] = value

        return result
