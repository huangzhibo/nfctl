"""
Pipeline 命令：pipeline list / create / update / delete
"""

import sys

import typer

from nfctl.client import AgentClient
from nfctl.output import console, is_json, print_kv, print_result, print_table

app = typer.Typer(no_args_is_help=True)


def _is_quiet() -> bool:
    from nfctl.main import app as main_app

    return getattr(main_app, "_quiet", False)


def _confirm(message: str) -> None:
    """交互确认（--quiet 或 --format json 时跳过）"""
    if _is_quiet() or is_json():
        return
    if not typer.confirm(message, default=False):
        raise typer.Abort()


@app.command("list")
def list_pipelines() -> None:
    """列出 Pipeline 配置"""
    client = AgentClient()
    envelope, code = client.get("/pipeline/")

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    data = envelope["data"]
    if not isinstance(data, list):
        data = []

    print_table(
        "Pipeline 配置",
        [
            ("pipeline_name", "Name"),
            ("max_concurrent", "Max Concurrent"),
            ("enabled", "Enabled"),
        ],
        data,
    )


@app.command("create")
def create_pipeline(
    pipeline_name: str = typer.Argument(help="Pipeline 名称"),
    max_concurrent: int | None = typer.Option(
        None, "--max-concurrent", "-m", help="最大并发数"
    ),
    enabled: bool = typer.Option(True, "--enabled/--disabled", help="是否启用"),
) -> None:
    """创建 Pipeline 配置"""
    body: dict = {"pipeline_name": pipeline_name, "enabled": enabled}
    if max_concurrent is not None:
        body["max_concurrent"] = max_concurrent

    client = AgentClient()
    envelope, code = client.post("/pipeline/", json=body)

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    print_kv(
        "Pipeline 已创建",
        [
            ("pipeline_name", d.get("pipeline_name")),
            ("max_concurrent", d.get("max_concurrent")),
            ("enabled", d.get("enabled")),
            ("created_at", d.get("created_at")),
        ],
    )
    sys.exit(code)


@app.command("update")
def update_pipeline(
    pipeline_name: str = typer.Argument(help="Pipeline 名称"),
    max_concurrent: int | None = typer.Option(
        None, "--max-concurrent", "-m", help="最大并发数"
    ),
    enabled: bool | None = typer.Option(None, "--enabled/--disabled", help="是否启用"),
) -> None:
    """更新 Pipeline 配置"""
    body: dict = {}
    if max_concurrent is not None:
        body["max_concurrent"] = max_concurrent
    if enabled is not None:
        body["enabled"] = enabled

    client = AgentClient()
    envelope, code = client.put(f"/pipeline/{pipeline_name}", json=body)

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    print_kv(
        "Pipeline 已更新",
        [
            ("pipeline_name", d.get("pipeline_name")),
            ("max_concurrent", d.get("max_concurrent")),
            ("enabled", d.get("enabled")),
            ("updated_at", d.get("updated_at")),
        ],
    )
    sys.exit(code)


@app.command("delete")
def delete_pipeline(
    pipeline_name: str = typer.Argument(help="Pipeline 名称"),
) -> None:
    """删除 Pipeline 配置"""
    _confirm(f"确认删除 Pipeline '{pipeline_name}'? 此操作不可恢复。")

    client = AgentClient()
    envelope, code = client.delete(f"/pipeline/{pipeline_name}")

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    console.print(f"[red]Deleted:[/red] Pipeline '{pipeline_name}'")
    sys.exit(code)
