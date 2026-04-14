"""
配置命令：config set / config show
"""

import typer

from nfctl.config import get_config, get_url, set_config
from nfctl.output import console, is_json, print_data, print_kv

app = typer.Typer(no_args_is_help=True)


@app.command("show")
def show() -> None:
    """显示当前配置"""
    data = get_config()
    data["_resolved_url"] = get_url()

    if is_json():
        print_data(data)
        return

    print_kv(
        "当前配置",
        [
            ("url", data.get("url", "(未设置)")),
            ("resolved_url", data["_resolved_url"]),
        ],
    )


@app.command("set")
def set_value(
    key: str = typer.Argument(help="配置项名称 (url)"),
    value: str = typer.Argument(help="配置项值"),
) -> None:
    """设置配置项"""
    set_config(key, value)

    if is_json():
        print_data({"key": key, "value": value})
        return

    console.print(f"[green]Set:[/green] {key} = {value}")
