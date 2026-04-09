"""ENV 格式输出写入器。将 token 数据写入 .env 风格的文件。"""

import os
import time
from pathlib import Path
from typing import Any

from core.interfaces import Credentials, OutputWriter, SiteConfig
from utils.logger import get_logger

logger = get_logger("writers.env")


class EnvWriter(OutputWriter):
    """将 token 数据写入 .env 格式文件（KEY=VALUE 每行一个）。"""

    def write(
        self,
        token_data: dict[str, Any],
        creds: Credentials,
        config: SiteConfig,
    ) -> Path:
        """将 token 数据写入 .env 文件。"""
        output_cfg = config.output

        # 确定输出目录
        if save_dir := os.environ.get("SAVE_DIR"):
            out_dir = Path(save_dir)
        else:
            directory = output_cfg.get("directory", "./token")
            out_dir = Path(directory)
            if not out_dir.is_absolute():
                project_root = Path(__file__).resolve().parents[2]
                out_dir = project_root / out_dir

        # 生成文件名
        template = output_cfg.get(
            "filename_template", "{site_name}-{timestamp}.env"
        )
        timestamp = str(int(time.time() * 1000))
        filename = template.format(site_name=config.name, timestamp=timestamp)

        # 如果模板产出 .json 后缀则替换为 .env
        if filename.endswith(".json"):
            filename = filename[:-5] + ".env"

        # 构建内容
        lines = [
            f"# Auto Register Token - {config.name}",
            f"# Generated at {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"ACCESS_TOKEN={token_data.get('access', '')}",
            f"REFRESH_TOKEN={token_data.get('refresh', '')}",
            f"EMAIL={creds.email}",
            f"RESOURCE_URL={token_data.get('resource_url', '')}",
            f"TYPE={config.name}",
            "",
        ]

        file_path = out_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Token 已写入（ENV 格式）: {file_path}")
        return file_path
