"""
管理命令：submit / cancel / delete / resume
"""

import sys

import typer

from nfctl.client import EXIT_VALIDATION, AgentClient, _error
from nfctl.output import console, is_json, print_kv, print_result


def _is_quiet() -> bool:
    from nfctl.main import app

    return getattr(app, "_quiet", False)


def _confirm(message: str) -> None:
    """交互确认（--quiet 或 --format json 时跳过）"""
    if _is_quiet() or is_json():
        return
    if not typer.confirm(message, default=False):
        raise typer.Abort()


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
            _error(EXIT_VALIDATION, "VALIDATION_ERROR", failed),
            EXIT_VALIDATION,
        )

    # 从 validate 响应提取 workflow_id（detail 格式："TOWER_WORKFLOW_ID=xxx"）
    wf_id_detail = val_data.get("checks", {}).get("workflow_id", {}).get("detail", "")
    workflow_id = wf_id_detail.split("=", 1)[1] if "=" in wf_id_detail else ""

    if not workflow_id:
        print_result(
            _error(
                EXIT_VALIDATION,
                "VALIDATION_ERROR",
                "无法从 run.sh 中提取 TOWER_WORKFLOW_ID",
                hint="检查 launch_dir 下的 run.sh 是否包含 TOWER_WORKFLOW_ID",
            ),
            EXIT_VALIDATION,
        )

    return val_data, workflow_id


def submit(
    launch_dir: str = typer.Argument(help="分析目录路径"),
    pipeline: str = typer.Option(..., "--pipeline", "-p", help="Pipeline 名称"),
    env: str | None = typer.Option(None, "--env", "-e", help="环境 (test/gray/prod)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="仅验证，不实际投递"),
) -> None:
    """投递工作流"""
    client = AgentClient()
    val_data, workflow_id = _do_validate(client, pipeline, launch_dir)

    if dry_run:
        if is_json():
            print_result({"ok": True, "data": val_data}, 0)
        checks = val_data.get("checks", {})
        items = [
            ("can_submit", val_data.get("can_submit")),
            ("workflow_id", workflow_id),
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
    }
    if env:
        body["env"] = env

    envelope, code = client.post("/workflow/submit", json=body)

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    console.print(
        f"[green]Submitted:[/green] {d.get('workflow_id')} (pipeline: {d.get('pipeline_name')})"
    )
    sys.exit(code)


def resume(
    workflow_id: str = typer.Argument(help="Workflow ID"),
) -> None:
    """恢复失败/取消的工作流"""
    client = AgentClient()
    envelope, code = client.post(f"/workflow/{workflow_id}/resume")

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    console.print(f"[green]Resumed:[/green] {d.get('workflow_id')}")
    sys.exit(code)


def cancel(
    workflow_id: str = typer.Argument(help="Workflow ID"),
    reason: str | None = typer.Option(None, "--reason", "-r", help="取消原因"),
) -> None:
    """取消运行中的流程"""
    _confirm(f"确认取消 {workflow_id}?")

    client = AgentClient()
    body: dict = {}
    if reason:
        body["reason"] = reason

    envelope, code = client.post(f"/workflow/{workflow_id}/cancel", json=body)

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    console.print(f"[yellow]Cancelled:[/yellow] {d.get('workflow_id')}")
    sys.exit(code)


def delete(
    workflow_id: str = typer.Argument(help="Workflow ID"),
) -> None:
    """删除工作流（仅终态）"""
    _confirm(f"确认删除 {workflow_id}? 此操作不可恢复。")

    client = AgentClient()
    envelope, code = client.delete(f"/workflow/{workflow_id}")

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    console.print(
        f"[red]Deleted:[/red] {d.get('workflow_id')} ({d.get('deleted_tasks', 0)} tasks)"
    )
    sys.exit(code)
