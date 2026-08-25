"""
配置命令：config show / set / use / list / remove
"""

import os

import typer

from nfctl.client import EXIT_VALIDATION, _error
from nfctl.config import (
    CONFIG_FILE,
    SYSTEM_CONFIG_FILE,
    ConfigError,
    get_config_sources,
    get_url,
    list_profiles,
    remove_profile,
    set_profile_url,
    use_profile,
)
from nfctl.output import (
    console,
    is_json,
    print_data,
    print_kv,
    print_result,
    print_table,
)

app = typer.Typer(no_args_is_help=True)


@app.command("show")
def show() -> None:
    """显示当前配置"""
    env_url = os.environ.get("NFCTL_URL")

    try:
        profiles, current = list_profiles()
        profile_sources, current_source = get_config_sources()
    except ConfigError as e:
        profiles = {}
        current = None
        profile_sources = {}
        current_source = None
        resolved = None
        resolve_error = str(e)
    else:
        try:
            resolved = get_url()
            resolve_error = None
        except ConfigError as e:
            resolved = None
            resolve_error = str(e)

    current_url = None
    if current and current in profiles:
        current_url = profiles[current].get("url")

    payload = {
        "current": current,
        "current_url": current_url,
        "resolved_url": resolved,
        "profiles": profiles,
        "profile_sources": profile_sources,
        "current_source": current_source,
        "env_override": bool(env_url),
        "user_config_file": str(CONFIG_FILE),
        "system_config_file": str(SYSTEM_CONFIG_FILE),
    }
    if resolve_error:
        payload["resolve_error"] = resolve_error

    if is_json():
        print_data(payload)
        return

    print_kv(
        "当前配置",
        [
            ("current", current or "(未设置)"),
            ("current_source", current_source or "(未设置)"),
            ("current_url", current_url or "(未设置)"),
            ("resolved_url", resolved or "(未配置)"),
            ("user_config", str(CONFIG_FILE)),
            ("system_config", str(SYSTEM_CONFIG_FILE)),
        ],
    )
    console.print()
    if env_url:
        console.print(
            f"[yellow]NFCTL_URL 环境变量生效，已覆盖 profile：{env_url}[/yellow]"
        )
        console.print()
    elif resolve_error:
        console.print(
            f"[yellow]{resolve_error}。运行 nfctl config set url <地址> 配置，或设置 NFCTL_URL。[/yellow]"
        )
        console.print()
    console.print(
        "[dim]解析顺序: --profile > NFCTL_URL > 用户 profile > 系统 profile[/dim]"
    )
    console.print("[dim]使用 nfctl config list 查看全部 profile[/dim]")


@app.command("set")
def set_value(
    key: str = typer.Argument(help="配置项名称（目前仅支持 url）"),
    value: str = typer.Argument(help="配置项值"),
    profile: str | None = typer.Option(
        None,
        "--profile",
        "-p",
        help="写入到指定用户 profile（默认覆盖当前生效 profile）",
    ),
) -> None:
    """设置用户配置；默认覆盖当前生效 profile，无配置时创建 default。"""
    if key != "url":
        print_result(
            _error("VALIDATION_ERROR", f"未知配置项: {key}（目前仅支持 url）"),
            EXIT_VALIDATION,
        )

    # 在写入时拦截缺少 scheme 的 URL，避免首次请求才报难懂的 httpx 错误。
    if not value.startswith(("http://", "https://")):
        print_result(
            _error(
                "VALIDATION_ERROR",
                f"url 需以 http:// 或 https:// 开头: {value}",
            ),
            EXIT_VALIDATION,
        )

    try:
        _, current = list_profiles()
    except ConfigError as e:
        print_result(_error("CONFIG_ERROR", str(e), hint=e.hint), EXIT_VALIDATION)
    target = profile or current or "default"
    set_profile_url(target, value)

    if is_json():
        print_data({"profile": target, "url": value.rstrip("/")})
        return

    console.print(f"[green]Set:[/green] profile [cyan]{target}[/cyan] url = {value}")


@app.command("use")
def use(
    name: str = typer.Argument(help="profile 名称"),
) -> None:
    """切换当前 profile"""
    try:
        use_profile(name)
    except ConfigError as e:
        print_result(_error("CONFIG_ERROR", str(e), hint=e.hint), EXIT_VALIDATION)

    if is_json():
        print_data({"current": name})
        return
    console.print(f"[green]当前 profile:[/green] {name}")


@app.command("list")
def list_cmd() -> None:
    """列出全部 profile"""
    try:
        profiles, current = list_profiles()
        profile_sources, _ = get_config_sources()
    except ConfigError as e:
        print_result(_error("CONFIG_ERROR", str(e), hint=e.hint), EXIT_VALIDATION)

    if is_json():
        print_data(
            {
                "current": current,
                "profiles": [
                    {
                        "name": name,
                        "url": prof.get("url"),
                        "current": name == current,
                        "source": profile_sources.get(name),
                    }
                    for name, prof in profiles.items()
                ],
            }
        )
        return

    if not profiles:
        console.print(
            "[dim]（未配置 profile）使用 nfctl config set url <地址> 创建[/dim]"
        )
        return

    rows = [
        {
            "current": "*" if name == current else "",
            "name": name,
            "url": prof.get("url", ""),
            "source": profile_sources.get(name, ""),
        }
        for name, prof in profiles.items()
    ]
    print_table(
        title="Profiles",
        columns=[
            ("current", ""),
            ("name", "NAME"),
            ("url", "URL"),
            ("source", "SOURCE"),
        ],
        rows=rows,
    )


@app.command("remove")
def remove(
    name: str = typer.Argument(help="profile 名称"),
) -> None:
    """删除 profile"""
    try:
        remove_profile(name)
    except ConfigError as e:
        print_result(_error("CONFIG_ERROR", str(e), hint=e.hint), EXIT_VALIDATION)

    if is_json():
        print_data({"removed": name})
        return
    console.print(f"[green]已删除 profile:[/green] {name}")
