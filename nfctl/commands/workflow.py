"""
管理命令：submit / resume / cancel / delete

控制动作只作用于当前执行，不带执行序号。
"""

import sys

import typer

from nfctl.attempts import label
from nfctl.client import EXIT_VALIDATION, AgentClient, _error
from nfctl.output import confirm, console, is_json, print_kv, print_result
from nfctl.paths import normalize_launch_dir


def _do_validate(
    client: AgentClient, pipeline: str, launch_dir: str
) -> tuple[dict, str]:
    """执行 validate 并返回 (val_data, workflow_id)，失败时直接退出"""
    val_envelope, val_code = client.post(
        "/workflow/validate", json={"pipeline_name": pipeline, "launch_dir": launch_dir}
    )
    if not val_envelope["ok"]:
        print_result(val_envelope, val_code)

    val_data = val_envelope["data"]
    if not val_data.get("can_submit"):
        checks = val_data.get("checks", {})
        failed = next(
            (
                v.get("detail", "验证失败")
                for v in checks.values()
                if not v.get("passed")
            ),
            "验证失败",
        )
        print_result(
            _error("VALIDATION_ERROR", failed),
            EXIT_VALIDATION,
        )

    # workflow_id 是 validate 响应的一等字段(3.0 起;曾要解析 check detail 字符串)
    workflow_id = val_data.get("workflow_id") or ""

    if not workflow_id:
        print_result(
            _error(
                "VALIDATION_ERROR",
                "无法从 run.sh 中提取 TOWER_WORKFLOW_ID",
                hint="检查 launch_dir 下的 run.sh 是否包含 TOWER_WORKFLOW_ID",
            ),
            EXIT_VALIDATION,
        )

    return val_data, workflow_id


def submit(
    launch_dir: str = typer.Argument(
        help="Launch directory（相对路径按本机当前目录转为绝对路径）"
    ),
    pipeline: str = typer.Option(..., "--pipeline", "-p", help="Pipeline 名称"),
    project_sn: str = typer.Option(
        ..., "--project-sn", "-S", help="项目编号 (LIMS project_sn)"
    ),
    env: str | None = typer.Option(None, "--env", "-e", help="环境 (test/gray/prod)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="仅验证，不实际投递"),
) -> None:
    """提交分析"""
    launch_dir = normalize_launch_dir(launch_dir)
    client = AgentClient()
    val_data, workflow_id = _do_validate(client, pipeline, launch_dir)

    if dry_run:
        if is_json():
            print_result({"ok": True, "data": val_data}, 0)
        checks = val_data.get("checks", {})
        items = [
            ("can_submit", val_data.get("can_submit")),
            ("workflow_id", workflow_id),
            ("project_sn", project_sn),
        ]
        for name, check in checks.items():
            passed = check.get("passed", False)
            detail = check.get("detail", "")
            symbol = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
            items.append((name, f"{symbol}  {detail}" if detail else symbol))
        print_kv("验证结果 (dry-run)", items)
        sys.exit(0)

    body: dict = {
        "workflow_id": workflow_id,
        "launch_dir": launch_dir,
        "pipeline_name": pipeline,
        "project_sn": project_sn,
    }
    if env:
        body["env"] = env

    envelope, code = client.post("/workflow/submit", json=body)

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    console.print(
        f"[green]Submitted:[/green] {label(d.get('workflow_id'), d.get('attempt_no'))} "
        f"(pipeline: {d.get('pipeline_name')})"
    )
    sys.exit(code)


def resume(
    workflow_id: str = typer.Argument(help="Workflow ID"),
) -> None:
    """重跑分析，新建一次执行。

    支持 failed/cancelled（含已作废的成功结果）；已归档目录会先自动恢复再投递。
    """
    envelope, code = AgentClient().post(f"/workflow/{workflow_id}/resume")

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    console.print(
        f"[green]Resumed:[/green] {label(d.get('workflow_id'), d.get('attempt_no'))}"
    )
    sys.exit(code)


def cancel(
    workflow_id: str = typer.Argument(help="Workflow ID"),
    reason: str | None = typer.Option(None, "--reason", "-r", help="取消原因"),
) -> None:
    """取消当前执行：运行中则停止，已成功则作废结果。

    LIMS 都会收到 error，之后可以 resume；目录存储操作用 archive cancel。
    """
    confirm(
        f"确认取消 {workflow_id} 的当前执行? 运行中会停止，已成功会作废结果并通知 LIMS。"
    )

    body: dict = {}
    if reason:
        body["reason"] = reason
    envelope, code = AgentClient().post(f"/workflow/{workflow_id}/cancel", json=body)

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    run = label(d.get("workflow_id"), d.get("attempt_no"))
    if d.get("main_status") == "stopping":
        console.print(
            f"[yellow]Stopping:[/yellow] {run} "
            f"(确认调度任务退出后变为 cancelled,可用 nfctl status 查看)"
        )
    else:
        console.print(f"[yellow]Cancelled:[/yellow] {run} (结果已作废,可 resume 重跑)")
    sys.exit(code)


def delete(
    workflow_id: str = typer.Argument(help="Workflow ID"),
) -> None:
    """删除分析及全部执行历史。

    不动目录文件；有效的成功结果需先 cancel 作废，server 才允许删除。
    """
    confirm(f"确认删除 {workflow_id} 及其全部执行历史? 此操作不可恢复。")

    envelope, code = AgentClient().delete(f"/workflow/{workflow_id}")

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    console.print(f"[red]Deleted:[/red] {d.get('workflow_id')}")
    sys.exit(code)
