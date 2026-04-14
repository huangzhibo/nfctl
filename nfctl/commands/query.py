"""
查询命令：overview / list / status / tasks / log / resources
"""

import typer

from nfctl.client import AgentClient
from nfctl.output import is_json, print_kv, print_result, print_table


def overview() -> None:
    """系统概览：运行/待机/成功/失败统计"""
    client = AgentClient()
    envelope, code = client.get("/stats/overview")

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    data = envelope["data"]
    print_kv(
        "Workflow 概览",
        [
            ("running", data.get("running", 0)),
            ("pending", data.get("pending", 0)),
            ("succeeded", data.get("succeeded", 0)),
            ("failed", data.get("failed", 0)),
            ("cancelled", data.get("cancelled", 0)),
            ("total", data.get("total", 0)),
            (
                "queue_waiting",
                f"{data.get('queue_waiting', 0)} / {data.get('queue_waiting_limit', 0)}",
            ),
        ],
    )

    pipelines = data.get("by_pipeline", [])
    if pipelines:
        print_table(
            "Pipeline 统计",
            [
                ("pipeline_name", "Pipeline"),
                ("running", "Running"),
                ("pending", "Pending"),
                ("succeeded", "OK"),
                ("failed", "Failed"),
            ],
            pipelines,
        )


def list_workflows(
    status: str | None = typer.Option(
        None, "--status", "-s", help="状态过滤（逗号分隔）"
    ),
    pipeline_name: str | None = typer.Option(
        None, "--pipeline", "-p", help="Pipeline 过滤"
    ),
    env: str | None = typer.Option(None, "--env", help="环境过滤"),
    q: str | None = typer.Option(
        None, "--query", "-q", help="搜索 workflow_id/launch_dir"
    ),
    n: int = typer.Option(20, "-n", help="每页条数"),
    page: int = typer.Option(1, "--page", help="页码"),
    sort_by: str = typer.Option("created_at", "--sort", help="排序字段"),
) -> None:
    """工作流列表"""
    client = AgentClient()
    envelope, code = client.get(
        "/workflow/list",
        status=status,
        pipeline_name=pipeline_name,
        env=env,
        q=q,
        page_size=n,
        page=page,
        sort_by=sort_by,
        sort_order="desc",
    )

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    data = envelope["data"]
    items = data.get("items", [])
    for item in items:
        item["progress_percent"] = f"{item.get('progress_percent', 0):.0f}%"
        if ts := item.get("updated_at"):
            item["updated_at"] = str(ts)[:19].replace("T", " ")

    print_table(
        "Workflow 列表",
        [
            ("workflow_id", "ID"),
            ("status", "Status"),
            ("progress_percent", "Progress"),
            ("pipeline_name", "Pipeline"),
            ("env", "Env"),
            ("updated_at", "Updated"),
        ],
        items,
        total=data.get("total"),
    )


def status(
    workflow_id: str = typer.Argument(help="Workflow ID"),
) -> None:
    """工作流详情"""
    client = AgentClient()
    envelope, code = client.get(f"/workflow/{workflow_id}")

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    items = [
        ("workflow_id", d.get("workflow_id")),
        ("status", d.get("status")),
        ("progress", f"{d.get('progress_percent', 0):.1f}%"),
        ("pipeline", d.get("pipeline_name")),
        ("env", d.get("env")),
        ("launch_dir", d.get("launch_dir")),
        ("run_name", d.get("run_name")),
        ("sge_job_id", d.get("sge_job_id")),
    ]
    if d.get("error_message"):
        items.append(("error", d["error_message"]))
    if d.get("duration"):
        items.append(("duration", f"{d['duration'] / 1000:.0f}s"))
    if d.get("start_time"):
        items.append(("start_time", d["start_time"]))
    if d.get("complete_time"):
        items.append(("complete_time", d["complete_time"]))

    print_kv(f"Workflow {workflow_id}", items)


def tasks(
    workflow_id: str = typer.Argument(help="Workflow ID"),
    status_filter: str | None = typer.Option(None, "--status", "-s", help="状态过滤"),
    process: str | None = typer.Option(None, "--process", help="Process 过滤"),
    n: int = typer.Option(50, "-n", help="每页条数"),
    page: int = typer.Option(1, "--page", help="页码"),
) -> None:
    """子任务列表"""
    client = AgentClient()
    envelope, code = client.get(
        f"/workflow/{workflow_id}/tasks",
        status=status_filter,
        process=process,
        page_size=n,
        page=page,
    )

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    data = envelope["data"]
    print_table(
        f"Tasks ({workflow_id})",
        [
            ("task_id", "ID"),
            ("process", "Process"),
            ("name", "Name"),
            ("status", "Status"),
            ("duration", "Duration(ms)"),
            ("peak_rss", "Peak RSS"),
            ("exit_status", "Exit"),
        ],
        data.get("tasks", []),
        total=data.get("total"),
    )


def log(
    workflow_id: str = typer.Argument(help="Workflow ID"),
    tail: int = typer.Option(100, "--tail", "-n", help="显示最后 N 行"),
    grep: str | None = typer.Option(None, "--grep", "-g", help="过滤关键词"),
) -> None:
    """查看 Nextflow 日志"""
    client = AgentClient()
    envelope, code = client.get(
        f"/workflow/{workflow_id}/log",
        tail=tail,
        grep=grep,
    )

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    data = envelope["data"]
    for line in data.get("lines", []):
        typer.echo(line)


def resources(
    workflow_id: str = typer.Argument(help="Workflow ID"),
    exclude_cached: bool = typer.Option(
        False, "--exclude-cached", help="排除 cached task"
    ),
) -> None:
    """资源使用统计"""
    client = AgentClient()
    envelope, code = client.get(
        f"/workflow/{workflow_id}/resource-stats",
        exclude_cached=exclude_cached,
    )

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    print_kv(
        f"资源统计 ({workflow_id})",
        [
            ("task_count", d.get("task_count", 0)),
            ("cpu_efficiency", f"{d.get('cpu_efficiency', 0):.1f}%"),
            ("cpu_time_used", d.get("cpu_time_used_human", "-")),
            ("cpu_time_requested", d.get("cpu_time_requested_human", "-")),
            ("memory_peak_rss", _fmt_bytes(d.get("memory_peak_rss", 0))),
            ("memory_requested", _fmt_bytes(d.get("memory_requested", 0))),
            ("memory_efficiency", f"{d.get('memory_efficiency', 0):.1f}%"),
            ("io_read", _fmt_bytes(d.get("io_read_bytes", 0))),
            ("io_write", _fmt_bytes(d.get("io_write_bytes", 0))),
            ("duration", d.get("time_duration_human", "-")),
        ],
    )


def _fmt_bytes(n: int) -> str:
    """格式化字节数"""
    if n == 0:
        return "0"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} PB"
