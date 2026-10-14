"""
管理命令：submit / resume / cancel / withdraw / delete

控制动作都针对某次执行：带 expected_attempt_no，执行已不是当前那次时服务端返回
409 ATTEMPT_CHANGED。默认取当前执行；--attempt N 让调用方钉住自己看到的那次。
"""

import sys

import typer

from nfctl.attempts import attempt_option, current_attempt_no, label
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


_EXPECTED_ATTEMPT_HELP = "只在第 N 次仍是当前执行时操作（默认当前执行）"


def _target(client: AgentClient, workflow_id: str, attempt: int | None) -> int:
    return attempt if attempt is not None else current_attempt_no(client, workflow_id)


def resume(
    workflow_id: str = typer.Argument(help="Workflow ID"),
    attempt: int | None = attempt_option(_EXPECTED_ATTEMPT_HELP),
) -> None:
    """重跑分析，新建一次执行。

    支持 failed/cancelled 和已撤销的成功；已归档目录会先自动恢复再投递。
    """
    client = AgentClient()
    expected = _target(client, workflow_id, attempt)
    envelope, code = client.post(
        f"/workflow/{workflow_id}/resume", json={"expected_attempt_no": expected}
    )

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
    attempt: int | None = attempt_option(_EXPECTED_ATTEMPT_HELP),
) -> None:
    """取消运行中的分析。

    成功结果用 withdraw 撤销；目录存储操作用 archive cancel。
    """
    client = AgentClient()
    expected = _target(client, workflow_id, attempt)
    confirm(f"确认取消 {label(workflow_id, expected)}?")

    body: dict = {"expected_attempt_no": expected}
    if reason:
        body["reason"] = reason

    envelope, code = client.post(f"/workflow/{workflow_id}/cancel", json=body)

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    console.print(
        f"[yellow]Stopping:[/yellow] {label(d.get('workflow_id'), d.get('attempt_no'))} "
        f"(确认调度任务退出后变为 cancelled,可用 nfctl status 查看)"
    )
    sys.exit(code)


def withdraw(
    workflow_id: str = typer.Argument(help="Workflow ID"),
    reason: str = typer.Option(..., "--reason", "-r", help="撤销原因（必填）"),
    attempt: int | None = attempt_option("撤销第几次执行的成功结果（默认当前执行）"),
) -> None:
    """撤销成功结果：LIMS 收到 error，之后可 resume 重跑。"""
    client = AgentClient()
    target = _target(client, workflow_id, attempt)
    confirm(f"确认撤销 {label(workflow_id, target)} 的成功结果? LIMS 将收到 error。")

    envelope, code = client.post(
        f"/workflow/{workflow_id}/attempts/{target}/withdraw", json={"reason": reason}
    )

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    console.print(
        f"[yellow]Withdrawn:[/yellow] {label(d.get('workflow_id'), d.get('attempt_no'))} "
        f"(如需重跑: nfctl resume {d.get('workflow_id')})"
    )
    sys.exit(code)


def delete(
    workflow_id: str = typer.Argument(help="Workflow ID"),
    attempt: int | None = attempt_option(_EXPECTED_ATTEMPT_HELP),
) -> None:
    """删除分析及全部执行历史。

    不动目录文件；有过成功执行的分析 server 拒删。
    """
    # succeeded 不可删的合规守卫已下沉 server(直调 API 也拦得住),CLI 不再预查
    client = AgentClient()
    expected = _target(client, workflow_id, attempt)
    confirm(f"确认删除 {workflow_id} 及其 {expected} 次执行历史? 此操作不可恢复。")

    envelope, code = client.delete(
        f"/workflow/{workflow_id}", expected_attempt_no=expected
    )

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    console.print(f"[red]Deleted:[/red] {d.get('workflow_id')}")
    sys.exit(code)
