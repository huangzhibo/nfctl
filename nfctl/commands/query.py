"""
查询命令：overview / list / status / tasks / log / resources
"""

from pathlib import Path

import typer
from rich.markup import escape

from nfctl.client import AgentClient
from nfctl.output import (
    console,
    err_console,
    format_local_time,
    is_json,
    print_kv,
    print_result,
    print_table,
)

_WORKFLOW_COLUMNS = [
    ("workflow_id", "ID"),
    ("analysis_status", "Status"),
    ("progress_percent", "Progress"),
    ("archive", "Archive"),
    ("pipeline_name", "Pipeline"),
    ("env", "Env"),
    ("project_sn", "ProjectSN"),
    ("updated_at", "Updated"),
]


def _prepare_workflow_items(items: list[dict]) -> None:
    """把 workflow API 字段转换成人类表格字段。"""
    for item in items:
        item["progress_percent"] = f"{item.get('progress_percent', 0):.0f}%"
        if item.get("updated_at"):
            item["updated_at"] = format_local_time(item["updated_at"])
        # env 为空表示内部流程,不向 LIMS 推送进度
        if not item.get("env"):
            item["env"] = "internal"
        # 归档轴列:推进中显示阶段(migrate/archive_wait/archive),终态显示
        # pp_status(succeeded/failed/cancelled/skipped),未开始显示 -
        pp_status_value = item.get("pp_status")
        if pp_status_value in ("not_started", "running"):
            item["archive"] = item.get("pp_phase") or "-"
        else:
            item["archive"] = pp_status_value or "-"


def _fetch_all_pages(
    client: AgentClient,
    path: str,
    params: dict,
    *,
    unit: str,
) -> tuple[dict, int]:
    """遍历到 API total，不用固定页数上限截断显式的 --all 请求。"""
    all_items: list[dict] = []
    current_page = 1
    total = 0
    while True:
        envelope, code = client.get(path, page=current_page, **params)
        if not envelope["ok"]:
            print_result(envelope, code)
        data = envelope["data"]
        total = data.get("total", 0)
        page_items = data.get("items", [])
        if not page_items:
            break
        all_items.extend(page_items)
        if not is_json():
            err_console.print(
                f"[dim][pagination] 第 {current_page} 页，"
                f"已获取 {len(all_items)} / {total} {unit}[/dim]"
            )
        if len(all_items) >= total:
            break
        current_page += 1
    return (
        {
            "ok": True,
            "data": {
                "items": all_items,
                "total": total,
                "page": 1,
                "page_size": len(all_items),
            },
        },
        0,
    )


def overview() -> None:
    """系统概览：运行/待机/成功/失败统计 + reconciler 存活"""
    client = AgentClient()
    envelope, code = client.get("/stats/overview")

    if not envelope["ok"]:
        print_result(envelope, code)

    data = envelope["data"]

    # reconciler 存活(server /health 心跳判定):陈旧 = 一切推进停止,
    # 两种模式都要暴露(Agent 走 JSON,同样依赖这个信号);/health 不可达时静默省略
    reconciler = None
    health_env, _ = client.get("/health")
    if health_env.get("ok"):
        rec = health_env["data"].get("reconciler") or {}
        if rec.get("alive") is not None:
            reconciler = rec

    if is_json():
        if reconciler is not None:
            data["reconciler"] = reconciler
        print_result(envelope, code)

    items: list[tuple[str, object]] = [
        ("running", data.get("running", 0)),
        ("succeeded", data.get("succeeded", 0)),
        ("failed", data.get("failed", 0)),
        ("cancelled", data.get("cancelled", 0)),
        ("total", data.get("total", 0)),
        # SGE 当前等待数(纯监控);全局阈值已退役,并发控制下沉到 per-pipeline max_concurrent
        ("queue_waiting", data.get("queue_waiting", 0)),
    ]
    if reconciler is not None:
        items.append(
            (
                "reconciler",
                "[green]alive[/green]"
                if reconciler["alive"]
                else "[red]未在推进(daemon 死/卡死/DB 不可写,查 daemon 日志)[/red]",
            )
        )

    print_kv("Workflow 概览", items)

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
        None,
        "--status",
        "-s",
        help=(
            "分析状态过滤（逗号分隔:queued|running|succeeded|failed|cancelled）,"
            "与 Status 列同口径"
        ),
    ),
    pp: str | None = typer.Option(
        None,
        "--pp",
        help="归档/后处理状态过滤（逗号分隔:not_started|running|succeeded|failed|cancelled|skipped）",
    ),
    pipeline_name: str | None = typer.Option(
        None, "--pipeline", "-p", help="Pipeline 过滤"
    ),
    env: str | None = typer.Option(None, "--env", help="环境过滤"),
    project_sn: str | None = typer.Option(
        None, "--project-sn", "-S", help="按项目编号 (LIMS project_sn) 过滤"
    ),
    data_number: str | None = typer.Option(
        None, "--data-number", "-D", help="按数据编号 (data_number) 过滤"
    ),
    q: str | None = typer.Option(
        None, "--query", "-q", help="搜索 workflow_id/launch_dir/data_number"
    ),
    launch_dir: str | None = typer.Option(
        None,
        "--launch-dir",
        "-L",
        help="按规范化启动目录精确过滤；相对路径（如 .）会转成绝对路径",
    ),
    group_by: str | None = typer.Option(
        None,
        "--group-by",
        help="分组展示（当前仅支持 launch-dir）",
    ),
    storage_state: str | None = typer.Option(
        None,
        "--state",
        help="目录存储状态（unknown/materialized/archived/partial）",
    ),
    rearchive_due: bool = typer.Option(
        False,
        "--rearchive-due",
        help="仅显示 restore 后已到重新归档时间的目录",
    ),
    n: int = typer.Option(20, "-n", help="每页条数"),
    page: int = typer.Option(1, "--page", help="页码"),
    all_pages: bool = typer.Option(False, "--all", help="自动遍历全部分页"),
    sort_by: str | None = typer.Option(
        None,
        "--sort",
        help="排序字段（普通列表默认 created_at，目录分组默认 updated_at）",
    ),
    sort_order: str = typer.Option("desc", "--sort-order", help="排序方向 (asc/desc)"),
) -> None:
    """分析列表"""
    if group_by not in (None, "launch-dir"):
        raise typer.BadParameter(
            "当前仅支持 launch-dir",
            param_hint="--group-by",
        )

    normalized_launch_dir = None
    if launch_dir is not None:
        normalized_launch_dir = str(Path(launch_dir).expanduser().resolve(strict=False))

    grouped = group_by == "launch-dir"
    if not grouped and (storage_state is not None or rearchive_due):
        raise typer.BadParameter(
            "--state/--rearchive-due 仅适用于 --group-by launch-dir",
            param_hint="--group-by",
        )
    path = "/launch-dirs" if grouped else "/workflow/list"
    client = AgentClient()
    params = {
        # 两轴过滤,与表格 Status/Archive 列同口径(server 端 SQL 谓词,
        # 见 nf-server ADR-0006):显示与过滤必须同字段。
        "analysis_status": status,
        "pp_status": pp,
        "pipeline_name": pipeline_name,
        "env": env,
        "project_sn": project_sn,
        "data_number": data_number,
        "launch_dir": normalized_launch_dir,
        "q": q,
        "page_size": n,
        "sort_by": sort_by or ("updated_at" if grouped else "created_at"),
        "sort_order": sort_order,
    }
    if grouped:
        params["storage_state"] = storage_state
        params["rearchive_due"] = True if rearchive_due else None

    # 精确目录查询的语义就是完整历史，自动翻页避免较老的占用/归档记录被截掉。
    fetch_all = all_pages or (normalized_launch_dir is not None and not grouped)
    if fetch_all:
        envelope, code = _fetch_all_pages(
            client,
            path,
            params,
            unit="个目录" if grouped else "条",
        )
    else:
        envelope, code = client.get(path, page=page, **params)

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    data = envelope["data"]
    if grouped:
        _print_launch_dir_groups(data)
        return

    items = data.get("items", [])
    _prepare_workflow_items(items)
    columns = list(_WORKFLOW_COLUMNS)
    if normalized_launch_dir is not None:
        columns.insert(4, ("launch_dir_occupied", "Occupied"))
    print_table("Workflow 列表", columns, items, total=data.get("total"))

    if normalized_launch_dir is not None:
        occupied = next(
            (item for item in items if item.get("launch_dir_occupied")), None
        )
        if occupied:
            stage = (
                "analysis"
                if occupied.get("analysis_status") in ("queued", "running")
                else occupied.get("archive", "post_process")
            )
            console.print(
                f"[yellow]当前占用:[/yellow] "
                f"{escape(str(occupied.get('workflow_id')))} ({escape(str(stage))})"
            )
        else:
            console.print("[green]当前无活跃 workflow 占用[/green]")


def _print_launch_dir_groups(data: dict) -> None:
    groups = data.get("items", [])
    console.print("[bold]LaunchDir 列表[/bold]")
    for group in groups:
        workflows = group.get("workflows", [])
        _prepare_workflow_items(workflows)

        launch_dir = escape(str(group.get("launch_dir", "-")))
        console.print(f"\n[bold cyan]{launch_dir}[/bold cyan]")
        occupied_id = group.get("occupied_workflow_id")
        if occupied_id:
            occupied = (
                f"占用 {escape(str(occupied_id))} "
                f"({escape(str(group.get('occupied_stage') or 'unknown'))})"
            )
        else:
            occupied = "无活跃占用"

        storage_state = escape(str(group.get("storage_state") or "unknown"))
        archive_id = group.get("archive_workflow_id")
        if archive_id:
            archive = f"归档记录 {escape(str(archive_id))}"
        else:
            archive = "无归档记录"
        operation = group.get("operation") or {}
        operation_text = ""
        if operation.get("kind"):
            operation_text = (
                f" · 操作 {escape(str(operation['kind']))}:"
                f"{escape(str(operation.get('status') or 'unknown'))}"
            )
        updated = format_local_time(group.get("updated_at"))
        console.print(
            f"[dim]{group.get('workflow_count', len(workflows))} workflows · "
            f"State {storage_state} · {occupied} · {archive}"
            f"{operation_text} · Updated {escape(str(updated))}[/dim]"
        )
        print_table("", _WORKFLOW_COLUMNS, workflows)

    total = data.get("total", len(groups))
    if total > len(groups):
        console.print(f"[dim]共 {total} 个目录，当前显示 {len(groups)} 个[/dim]")


def status(
    workflow_id: str = typer.Argument(help="Workflow ID"),
) -> None:
    """分析详情"""
    client = AgentClient()
    envelope, code = client.get(f"/workflow/{workflow_id}")

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    # 需介入时(失败/归档失败)summary 标黄承载警示——needs_action 恒等价于
    # "summary 是带动作的那两句之一(需排查 resume / 可 archive resume 重试)",
    # 单列 needs_action 行只会重复 summary,故不显示,警示用颜色不用重复文字。
    # needs_action 布尔仍在 JSON 直出,供脚本 filter/告警。
    summary = d.get("status_summary")
    if summary and d.get("needs_action"):
        summary = f"[yellow]{summary}[/yellow]"
    items = [
        ("workflow_id", d.get("workflow_id")),
        # 分析轴状态(server 派生的 analysis_status,含 queued)
        ("status", d.get("analysis_status")),
        ("summary", summary),
        ("progress", f"{d.get('progress_percent', 0):.1f}%"),
        ("pipeline", d.get("pipeline_name")),
        # env 为空表示内部流程,不向 LIMS 推送进度
        ("env", d.get("env") or "internal"),
        ("launch_dir", d.get("launch_dir")),
        ("run_name", d.get("run_name")),
        ("job_id", d.get("job_id")),
    ]
    if d.get("project_sn"):
        items.append(("project_sn", d["project_sn"]))
    if d.get("data_number"):
        items.append(("data_number", d["data_number"]))
    if d.get("data_path"):
        items.append(("data_path", d["data_path"]))
    if d.get("pp_phase"):
        pp = d["pp_phase"]
        if d.get("pp_status"):
            pp = f"{pp} ({d['pp_status']})"
        items.append(("post_process", pp))
    # 等待归档时显示到期自动开始时间(原始字段直出)
    if d.get("archive_eligible_after"):
        items.append(
            ("archive_eligible_after", format_local_time(d["archive_eligible_after"]))
        )
    # error 行只在失败态显示(分析失败 / 归档失败):cancelled 的原因已在
    # summary、succeeded 应无错(残留 error_message 属 server bug),都不露
    # error 行,避免"succeeded + error"自相矛盾;也防御存量残留。
    is_failed = d.get("analysis_status") == "failed" or d.get("pp_status") == "failed"
    if d.get("error_message") and is_failed:
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


def progress(
    workflow_id: str = typer.Argument(help="Workflow ID"),
) -> None:
    """分析进度（含 process 级别明细）"""
    client = AgentClient()
    envelope, code = client.get(f"/workflow/{workflow_id}/progress")

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    print_kv(
        f"Progress ({workflow_id})",
        [("progress_percent", f"{d.get('progress_percent', 0):.1f}%")],
    )

    print_table(
        "Process 明细",
        [
            ("name", "Process"),
            ("pending", "Pending"),
            ("submitted", "Submitted"),
            ("running", "Running"),
            ("succeeded", "OK"),
            ("cached", "Cached"),
            ("failed", "Failed"),
            ("aborted", "Aborted"),
        ],
        d.get("processes", []),
    )


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
