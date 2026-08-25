"""
配置管理（多 profile）

解析优先级：
  显式 profile 参数/--profile CLI/NFCTL_PROFILE
  > NFCTL_URL（直连 URL，绕过 profile）
  > 用户配置的当前 profile
  > 系统配置的当前 profile
  > 未配置则抛 ConfigError（不再静默回落到 localhost）

配置文件：
  - /etc/nfctl/config.json：系统级只读默认，由集群管理员维护
  - ~/.nfctl/config.json：用户级配置，同名 profile 覆盖系统配置

格式：
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
SYSTEM_CONFIG_FILE = Path("/etc/nfctl/config.json")
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


def _load_raw(path: Path) -> dict:
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return {}
    except OSError as e:
        raise ConfigError(
            f"无法读取配置文件: {path}",
            hint="检查文件权限后重试",
        ) from e

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(
            f"配置文件不是有效 JSON: {path}",
            hint="修复配置文件后重试",
        ) from e
    if not isinstance(data, dict):
        raise ConfigError(
            f"配置文件顶层必须是 JSON object: {path}",
            hint="修复配置文件后重试",
        )
    return data


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


def _load_user_config() -> dict:
    return _normalize(_load_raw(CONFIG_FILE))


def _load_system_config() -> dict:
    return _normalize(_load_raw(SYSTEM_CONFIG_FILE))


def _save_user_config(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def load_config() -> dict:
    """读取系统+用户分层后的有效配置。"""
    system = _load_system_config()
    user = _load_user_config()
    return {
        "current": user["current"] or system["current"],
        "profiles": {**system["profiles"], **user["profiles"]},
    }


def get_config_sources() -> tuple[dict[str, str], str | None]:
    """返回 (profile 来源, current 来源)，供 config 命令解释解析结果。"""
    system = _load_system_config()
    user = _load_user_config()
    profile_sources = dict.fromkeys(system["profiles"], "system")
    profile_sources.update(dict.fromkeys(user["profiles"], "user"))
    current_source = "user" if user["current"] else None
    if current_source is None and system["current"]:
        current_source = "system"
    return profile_sources, current_source


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
    """写入用户 profile；若用户未选择 profile 则同时选中它。"""
    cfg = _load_user_config()
    profiles = cfg["profiles"]
    profiles.setdefault(name, {})["url"] = url.rstrip("/")
    if cfg["current"] is None:
        cfg["current"] = name
    _save_user_config(cfg)


def use_profile(name: str) -> None:
    effective = load_config()
    if name not in effective["profiles"]:
        raise ConfigError(
            f"profile '{name}' 不存在",
            hint="使用 nfctl config list 查看可用 profile",
        )
    cfg = _load_user_config()
    cfg["current"] = name
    _save_user_config(cfg)


def remove_profile(name: str) -> None:
    cfg = _load_user_config()
    profiles = cfg["profiles"]
    if name not in profiles:
        system = _load_system_config()
        if name in system["profiles"]:
            raise ConfigError(
                f"profile '{name}' 由系统配置提供，用户不能删除",
                hint=f"由管理员修改 {SYSTEM_CONFIG_FILE}，或使用同名用户 profile 覆盖",
            )
        raise ConfigError(
            f"profile '{name}' 不存在",
            hint="使用 nfctl config list 查看可用 profile",
        )
    del profiles[name]
    if cfg["current"] == name:
        system = _load_system_config()
        # 删除同名覆盖时保留当前选择，自然回落到系统 profile。
        if name not in system["profiles"]:
            cfg["current"] = next(iter(profiles), None)
    _save_user_config(cfg)


def resolve_profile_name(profile: str | None = None) -> str | None:
    """返回最终生效的 profile 名（考虑 override / current）。NFCTL_URL 直连时返回 None。"""
    effective = profile or _profile_override
    if effective:
        return effective
    if os.environ.get("NFCTL_URL"):
        return None
    _, current = list_profiles()
    return current
