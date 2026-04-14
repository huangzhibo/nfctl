"""
配置管理

解析优先级：NFCTL_URL 环境变量 > ~/.nfctl/config.json > 默认 http://localhost:8000
"""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".nfctl"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_URL = "http://localhost:8000"


def get_url() -> str:
    """获取 Agent URL"""
    env_url = os.environ.get("NFCTL_URL")
    if env_url:
        return env_url.rstrip("/")

    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            if url := data.get("url"):
                return str(url).rstrip("/")
        except (json.JSONDecodeError, OSError):
            pass

    return DEFAULT_URL


def get_config() -> dict:
    """读取完整配置"""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def set_config(key: str, value: str) -> None:
    """设置配置项"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = get_config()
    data[key] = value
    CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
