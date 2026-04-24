"""
查询命令：overview / list / status / tasks / log / resources
"""

import typer

from nfctl.client import AgentClient
from nfctl.output import (
    err_console,
    format_local_time,
    is_json,
    print_kv,
    print_result,
    print_table,
)


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
    project_sn: str | None = typer.Option(
        None, "--project-sn", "-S", help="按项目编号 (LIMS project_sn) 过滤"
    ),
    q: str | None = typer.Option(
        None, "--query", "-q", help="搜索 workflow_id/launch_dir"
    ),
    n: int = typer.Option(20, "-n", help="每页条数"),
    page: int = typer.Option(1, "--page", help="页码"),
    all_pages: bool = typer.Option(
        False, "--all", help="自动遍历分页（最多 50 页，超出静默截断）"
    ),
    sort_by: str = typer.Option("created_at", "--sort", help="排序字段"),
    sort_order: str = typer.Option("desc", "--sort-order", help="排序方向 (asc/desc)"),
) -> None:
    """工作流列表"""
    client = AgentClient()
    params = {
        "status": status,
        "pipeline_name": pipeline_name,
        "env": env,
        "project_sn": project_sn,
        "q": q,
        "page_size": n,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }

    if all_pages:
        all_items: list[dict] = []
        current_page = 1
        total = None
        while current_page <= 50:
            envelope, code = client.get("/workflow/list", page=current_page, **params)
            if not envelope["ok"]:
                print_result(envelope, code)
            data = envelope["data"]
            page_items = data.get("items", [])
            if not page_items:
                break
            all_items.extend(page_items)
            total = data.get("total", 0)
            if not is_json():
                err_console.print(
                    f"[dim][pagination] 第 {current_page} 页，已获取 {len(all_items)} / {total} 条[/dim]"
                )
            if len(all_items) >= total:
                break
            current_page += 1
        envelope = {
            "ok": True,
            "data": {"items": all_items, "total": total, "page": 1, "page_size": total},
        }
        code = 0
    else:
        envelope, code = client.get("/workflow/list", page=page, **params)

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    data = envelope["data"]
    items = data.get("items", [])
    for item in items:
        item["progress_percent"] = f"{item.get('progress_percent', 0):.0f}%"
        if item.get("updated_at"):
            item["updated_at"] = format_local_time(item["updated_at"])
        # env 为空表示内部流程,不向 LIMS 推送进度
        if not item.get("env"):
            item["env"] = "internal"

    print_table(
        "Workflow 列表",
        [
            ("workflow_id", "ID"),
            ("status", "Status"),
            ("progress_percent", "Progress"),
            ("pipeline_name", "Pipeline"),
            ("env", "Env"),
            ("project_sn", "ProjectSN"),
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
        # env 为空表示内部流程,不向 LIMS 推送进度
        ("env", d.get("env") or "internal"),
        ("launch_dir", d.get("launch_dir")),
        ("run_name", d.get("run_name")),
        ("sge_job_id", d.get("sge_job_id")),
    ]
    if d.get("project_sn"):
        items.append(("project_sn", d["project_sn"]))
    if d.get("pp_phase"):
        items.append(("post_process", d["pp_phase"]))
    if d.get("error_message"):
        items.append(("error", d["error_message"]))
    if d.get("duration"):
        items.append(("duration", f"{d['duration'] / 1000:.0f}s"))
    if d.get("start_time"):
        items.append(("start_time", format_local_time(d["start_time"])))
    if d.get("complete_time"):
        items.append(("complete_time", format_local_time(d["complete_time"])))
    if d.get("created_at"):
        items.append(("created_at", format_local_time(d["created_at"])))
    if d.get("updated_at"):
        items.append(("updated_at", format_local_time(d["updated_at"])))

    print_kv(f"Workflow {workflow_id}", items)


def tasks(
    workflow_id: str = typer.Argument(help="Workflow ID"),
    status_filter: str | None = typer.Option(None, "--status", "-s", help="状态过滤"),
    process: str | None = typer.Option(None, "--process", help="Process 过滤"),
    n: int = typer.Option(50, "-n", help="每页条数"),
    page: int = typer.Option(1, "--page", help="页码"),
    sort_by: str = typer.Option("task_id", "--sort", help="排序字段"),
    sort_order: str = typer.Option("asc", "--sort-order", help="排序方向 (asc/desc)"),
) -> None:
    """子任务列表"""
    client = AgentClient()
    envelope, code = client.get(
        f"/workflow/{workflow_id}/tasks",
        status=status_filter,
        process=process,
        page_size=n,
        page=page,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    data = envelope["data"]
    for t in data.get("tasks", []):
        h = t.get("hash")
        if isinstance(h, str):
            hex_only = h.replace("/", "")
            if len(hex_only) >= 8:
                t["hash"] = f"{hex_only[:2]}/{hex_only[2:8]}"

    print_table(
        f"Tasks ({workflow_id})",
        [
            ("task_id", "ID"),
            ("hash", "Hash"),
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
        False,
        "--exclude-cached",
        help="排除 Nextflow 缓存复用的 task（默认聚合含其历史指标）",
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


def task_detail(
    workflow_id: str = typer.Argument(help="Workflow ID"),
    task_id: int = typer.Argument(help="Task ID"),
) -> None:
    """子任务详情"""
    client = AgentClient()
    envelope, code = client.get(f"/workflow/{workflow_id}/tasks/{task_id}")

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    items = [
        ("task_id", d.get("task_id")),
        ("workflow_id", d.get("workflow_id")),
        ("process", d.get("process")),
        ("name", d.get("name")),
        ("status", d.get("status")),
        ("exit_status", d.get("exit_status")),
        ("hash", d.get("hash")),
        ("workdir", d.get("workdir")),
        ("container", d.get("container")),
        ("cpus", d.get("cpus")),
        ("memory", _fmt_bytes(d["memory"]) if d.get("memory") else None),
        ("duration", f"{d['duration'] / 1000:.1f}s" if d.get("duration") else None),
        ("realtime", f"{d['realtime'] / 1000:.1f}s" if d.get("realtime") else None),
        ("peak_rss", _fmt_bytes(d["peak_rss"]) if d.get("peak_rss") else None),
        ("peak_vmem", _fmt_bytes(d["peak_vmem"]) if d.get("peak_vmem") else None),
        ("pcpu", f"{d['pcpu']:.1f}%" if d.get("pcpu") is not None else None),
        ("queue", d.get("queue")),
    ]
    if d.get("script"):
        items.append(("script", d["script"].strip()))
    if d.get("error_action"):
        items.append(("error_action", d["error_action"]))

    print_kv(f"Task {task_id} ({workflow_id})", items)


def _fmt_bytes(n: int) -> str:
    """格式化字节数"""
    if n == 0:
        return "0"
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"
