"""
配置管理（多 profile）

解析优先级：
  显式 profile 参数/--profile CLI/NFCTL_PROFILE
  > NFCTL_URL（直连 URL，绕过 profile）
  > 当前 profile 的 url
  > 未配置则抛 ConfigError（不再静默回落到 localhost）

配置文件 ~/.nfctl/config.json：
  {
    "current": "dev",
    "profiles": {
      "dev":  {"url": "http://..."},
      ...
    }
  }

旧格式 {"url": "..."} 读取时自动归一化为 default profile；写盘时才持久化迁移。
"""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".nfctl"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_PROFILE = "default"

_profile_override: str | None = None


class ConfigError(Exception):
    """配置缺失或无效。附带可选 hint 让上层复用到错误信封。"""

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.hint = hint


def apply_profile_option(name: str | None) -> None:
    """由 main 回调注入全局 --profile 选项"""
    global _profile_override
    _profile_override = name or None


def _load_raw() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _normalize(data: dict) -> dict:
    if "profiles" in data:
        return {
            "current": data.get("current"),
            "profiles": dict(data.get("profiles") or {}),
        }
    profiles: dict[str, dict] = {}
    if url := data.get("url"):
        profiles[DEFAULT_PROFILE] = {"url": str(url).rstrip("/")}
    return {
        "current": DEFAULT_PROFILE if profiles else None,
        "profiles": profiles,
    }


def _save(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def load_config() -> dict:
    """读取归一化后的完整配置"""
    return _normalize(_load_raw())


def list_profiles() -> tuple[dict[str, dict], str | None]:
    cfg = load_config()
    return cfg["profiles"], cfg["current"]


def get_profile_url(name: str) -> str | None:
    profiles, _ = list_profiles()
    prof = profiles.get(name)
    if prof and (url := prof.get("url")):
        return str(url).rstrip("/")
    return None


def get_url(profile: str | None = None) -> str:
    """按解析链得到 URL。无任何配置时抛 ConfigError。"""
    effective = profile or _profile_override
    if effective:
        url = get_profile_url(effective)
        if url is None:
            raise ConfigError(
                f"profile '{effective}' 不存在",
                hint="使用 nfctl config list 查看可用 profile",
            )
        return url

    if env_url := os.environ.get("NFCTL_URL"):
        return env_url.rstrip("/")

    profiles, current = list_profiles()
    if current and (prof := profiles.get(current)) and (url := prof.get("url")):
        return str(url).rstrip("/")

    raise ConfigError(
        "未配置 nf-server 地址",
        hint="运行 nfctl config set url <地址>，或设置 NFCTL_URL 环境变量",
    )


def set_profile_url(name: str, url: str) -> None:
    """写入指定 profile 的 URL；若配置为空则把它设为当前 profile。"""
    cfg = load_config()
    profiles = cfg["profiles"]
    profiles.setdefault(name, {})["url"] = url.rstrip("/")
    if cfg["current"] is None:
        cfg["current"] = name
    _save(cfg)


def use_profile(name: str) -> None:
    cfg = load_config()
    if name not in cfg["profiles"]:
        raise ConfigError(
            f"profile '{name}' 不存在",
            hint="使用 nfctl config list 查看可用 profile",
        )
    cfg["current"] = name
    _save(cfg)


def remove_profile(name: str) -> None:
    cfg = load_config()
    profiles = cfg["profiles"]
    if name not in profiles:
        raise ConfigError(
            f"profile '{name}' 不存在",
            hint="使用 nfctl config list 查看可用 profile",
        )
    del profiles[name]
    if cfg["current"] == name:
        cfg["current"] = next(iter(profiles), None)
    _save(cfg)


def resolve_profile_name(profile: str | None = None) -> str | None:
    """返回最终生效的 profile 名（考虑 override / current）。NFCTL_URL 直连时返回 None。"""
    effective = profile or _profile_override
    if effective:
        return effective
    if os.environ.get("NFCTL_URL"):
        return None
    _, current = list_profiles()
    return current
