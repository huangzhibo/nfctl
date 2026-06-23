"""
Pipeline 命令：pipeline list / create / update / delete
"""

import sys
from typing import Any

import typer

from nfctl.client import EXIT_ERROR, AgentClient
from nfctl.output import (
    console,
    format_local_time,
    is_json,
    print_kv,
    print_result,
    print_table,
)

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


def _detail_items(d: dict, time_key: str) -> list[tuple[str, Any]]:
    """create/update 结果详情展示字段（含 per-pipeline 归档/迁移策略）。"""
    return [
        ("pipeline_name", d.get("pipeline_name")),
        ("max_concurrent", d.get("max_concurrent")),
        ("enabled", d.get("enabled")),
        ("feishu_webhook", d.get("feishu_webhook")),
        ("archive_enabled", d.get("archive_enabled")),
        ("large_file_threshold", d.get("large_file_threshold")),
        ("archive_dirs", d.get("archive_dirs")),
        ("archive_delay_hours", d.get("archive_delay_hours")),
        (time_key, format_local_time(d.get(time_key))),
    ]


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
            ("archive_enabled", "Archive"),
            ("archive_dirs", "Archive Dirs"),
            ("archive_delay_hours", "Delay(h)"),
            ("large_file_threshold", "Migrate(threshold)"),
        ],
        data,
    )


@app.command("get")
def get_pipeline(
    pipeline_name: str = typer.Argument(help="Pipeline 名称"),
) -> None:
    """查看单个 Pipeline 的完整配置（含 feishu_webhook 与时间戳等全字段）"""
    client = AgentClient()
    envelope, code = client.get("/pipeline/")

    if not envelope["ok"]:
        print_result(envelope, code)

    data = envelope["data"]
    if not isinstance(data, list):
        data = []
    match = next((p for p in data if p.get("pipeline_name") == pipeline_name), None)

    if match is None:
        print_result(
            {
                "ok": False,
                "error": {
                    "type": "NOT_FOUND",
                    "message": f"Pipeline '{pipeline_name}' 不存在",
                },
            },
            EXIT_ERROR,
        )
        return  # print_result 已退出,此处仅供类型收窄

    if is_json():
        print_result({"ok": True, "data": match}, code)

    items = _detail_items(match, "created_at")
    items.append(("updated_at", format_local_time(match.get("updated_at"))))
    print_kv(f"Pipeline {pipeline_name}", items)
    sys.exit(code)


@app.command("create")
def create_pipeline(
    pipeline_name: str = typer.Argument(help="Pipeline 名称"),
    max_concurrent: int | None = typer.Option(
        None, "--max-concurrent", "-m", help="最大并发数"
    ),
    enabled: bool = typer.Option(True, "--enabled/--disabled", help="是否启用"),
    feishu_webhook: str | None = typer.Option(
        None, "--feishu-webhook", help="飞书机器人 webhook URL；不设则不推送通知"
    ),
    archive: bool = typer.Option(
        False,
        "--archive/--no-archive",
        help="是否启用归档（打包后删除原目录，延迟执行）",
    ),
    large_file_threshold: str | None = typer.Option(
        None,
        "--large-file-threshold",
        help="大文件迁移阈值兼 migrate 开关（find -size 格式，如 500M；不设=不迁移）",
    ),
    archive_dirs: str | None = typer.Option(
        None, "--archive-dirs", help="待迁移/归档目录，逗号分隔，相对 launch_dir"
    ),
    archive_delay_hours: int | None = typer.Option(
        None, "--archive-delay-hours", help="归档延迟小时数（不设=服务端默认 72）"
    ),
) -> None:
    """创建 Pipeline 配置"""
    body: dict = {
        "pipeline_name": pipeline_name,
        "enabled": enabled,
        "archive_enabled": archive,
    }
    if max_concurrent is not None:
        body["max_concurrent"] = max_concurrent
    if feishu_webhook is not None:
        body["feishu_webhook"] = feishu_webhook
    if large_file_threshold is not None:
        body["large_file_threshold"] = large_file_threshold
    if archive_dirs is not None:
        body["archive_dirs"] = archive_dirs
    if archive_delay_hours is not None:
        body["archive_delay_hours"] = archive_delay_hours

    client = AgentClient()
    envelope, code = client.post("/pipeline/", json=body)

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    print_kv("Pipeline 已创建", _detail_items(d, "created_at"))
    sys.exit(code)


@app.command("update")
def update_pipeline(
    pipeline_name: str = typer.Argument(help="Pipeline 名称"),
    max_concurrent: int | None = typer.Option(
        None, "--max-concurrent", "-m", help="最大并发数"
    ),
    enabled: bool | None = typer.Option(None, "--enabled/--disabled", help="是否启用"),
    feishu_webhook: str | None = typer.Option(
        None, "--feishu-webhook", help="飞书机器人 webhook URL"
    ),
    archive: bool | None = typer.Option(
        None, "--archive/--no-archive", help="是否启用归档"
    ),
    large_file_threshold: str | None = typer.Option(
        None,
        "--large-file-threshold",
        help="大文件迁移阈值兼 migrate 开关（如 500M；传空串 '' = 关闭迁移）",
    ),
    archive_dirs: str | None = typer.Option(
        None, "--archive-dirs", help="待迁移/归档目录，逗号分隔，相对 launch_dir"
    ),
    archive_delay_hours: int | None = typer.Option(
        None, "--archive-delay-hours", help="归档延迟小时数"
    ),
) -> None:
    """更新 Pipeline 配置（仅传入的字段会被更新）"""
    body: dict = {}
    if max_concurrent is not None:
        body["max_concurrent"] = max_concurrent
    if enabled is not None:
        body["enabled"] = enabled
    if feishu_webhook is not None:
        body["feishu_webhook"] = feishu_webhook
    if archive is not None:
        body["archive_enabled"] = archive
    if large_file_threshold is not None:
        body["large_file_threshold"] = large_file_threshold
    if archive_dirs is not None:
        body["archive_dirs"] = archive_dirs
    if archive_delay_hours is not None:
        body["archive_delay_hours"] = archive_delay_hours

    client = AgentClient()
    envelope, code = client.put(f"/pipeline/{pipeline_name}", json=body)

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    print_kv("Pipeline 已更新", _detail_items(d, "updated_at"))
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
