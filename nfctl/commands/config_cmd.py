"""
配置命令：config show / set / use / list / remove
"""

import os

import typer

from nfctl.config import (
    get_url,
    list_profiles,
    remove_profile,
    set_profile_url,
    use_profile,
)
from nfctl.output import console, is_json, print_data, print_kv, print_table

app = typer.Typer(no_args_is_help=True)


@app.command("show")
def show() -> None:
    """显示当前配置"""
    profiles, current = list_profiles()
    resolved = get_url()
    env_url = os.environ.get("NFCTL_URL")

    current_url = None
    if current and current in profiles:
        current_url = profiles[current].get("url")

    payload = {
        "current": current,
        "current_url": current_url,
        "resolved_url": resolved,
        "profiles": profiles,
        "env_override": bool(env_url),
    }

    if is_json():
        print_data(payload)
        return

    print_kv(
        "当前配置",
        [
            ("current", current or "(未设置)"),
            ("current_url", current_url or "(未设置)"),
            ("resolved_url", resolved),
        ],
    )
    console.print()
    if env_url:
        console.print(f"[yellow]NFCTL_URL 环境变量生效，已覆盖 profile：{env_url}[/yellow]")
        console.print()
    console.print("[dim]解析顺序: --profile > NFCTL_URL > 当前 profile > 默认值[/dim]")
    console.print("[dim]使用 nfctl config list 查看全部 profile[/dim]")


@app.command("set")
def set_value(
    key: str = typer.Argument(help="配置项名称（目前仅支持 url）"),
    value: str = typer.Argument(help="配置项值"),
    profile: str | None = typer.Option(
        None, "--profile", "-p", help="写入到指定 profile（默认写入当前 profile）"
    ),
) -> None:
    """设置配置项。--profile 未指定时写入当前 profile（配置为空则创建 default 并设为当前）。"""
    if key != "url":
        msg = f"未知配置项: {key}（目前仅支持 url）"
        if is_json():
            print_data({"error": msg})
        else:
            console.print(f"[red]{msg}[/red]")
        raise typer.Exit(2)

    _, current = list_profiles()
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
    except ValueError as e:
        if is_json():
            print_data({"error": str(e)})
        else:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e

    if is_json():
        print_data({"current": name})
        return
    console.print(f"[green]当前 profile:[/green] {name}")


@app.command("list")
def list_cmd() -> None:
    """列出全部 profile"""
    profiles, current = list_profiles()

    if is_json():
        print_data(
            {
                "current": current,
                "profiles": [
                    {"name": name, "url": prof.get("url"), "current": name == current}
                    for name, prof in profiles.items()
                ],
            }
        )
        return

    if not profiles:
        console.print("[dim]（未配置 profile）使用 nfctl config set url <地址> 创建[/dim]")
        return

    rows = [
        {
            "current": "*" if name == current else "",
            "name": name,
            "url": prof.get("url", ""),
        }
        for name, prof in profiles.items()
    ]
    print_table(
        title="Profiles",
        columns=[("current", ""), ("name", "NAME"), ("url", "URL")],
        rows=rows,
    )


@app.command("remove")
def remove(
    name: str = typer.Argument(help="profile 名称"),
) -> None:
    """删除 profile"""
    try:
        remove_profile(name)
    except ValueError as e:
        if is_json():
            print_data({"error": str(e)})
        else:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e

    if is_json():
        print_data({"removed": name})
        return
    console.print(f"[green]已删除 profile:[/green] {name}")
