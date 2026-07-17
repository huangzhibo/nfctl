"""
管理命令：submit / cancel / delete / resume
"""

import sys

import typer

from nfctl.client import EXIT_VALIDATION, AgentClient, _error
from nfctl.output import confirm, console, is_json, print_kv, print_result


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
    launch_dir: str = typer.Argument(help="分析目录路径"),
    pipeline: str = typer.Option(..., "--pipeline", "-p", help="Pipeline 名称"),
    project_sn: str = typer.Option(
        ..., "--project-sn", "-S", help="项目编号 (LIMS project_sn)"
    ),
    env: str | None = typer.Option(None, "--env", "-e", help="环境 (test/gray/prod)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="仅验证，不实际投递"),
) -> None:
    """提交分析"""
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
        f"[green]Submitted:[/green] {d.get('workflow_id')} (pipeline: {d.get('pipeline_name')})"
    )
    sys.exit(code)


def resume(
    workflow_id: str = typer.Argument(help="Workflow ID"),
) -> None:
    """重跑失败/取消的分析（恢复归档用 nfctl archive resume）"""
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
    """取消整个分析（仅取消归档、保留分析结果用 nfctl archive cancel）"""
    confirm(f"确认取消 {workflow_id}? 已成功的分析将被整体撤销并通知 LIMS 作废。")

    client = AgentClient()
    # 归档取消已收拢进 archive 命令组(nfctl archive cancel),本命令固定整体撤销;
    # server API 的 scope 参数保持不变,只是 CLI 不再暴露
    body: dict = {"scope": "workflow"}
    if reason:
        body["reason"] = reason

    envelope, code = client.post(f"/workflow/{workflow_id}/cancel", json=body)

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    console.print(
        f"[yellow]Cancel signal sent:[/yellow] {d.get('workflow_id')} "
        f"(状态更新需数秒,可用 nfctl status 确认)"
    )
    sys.exit(code)


def delete(
    workflow_id: str = typer.Argument(help="Workflow ID"),
) -> None:
    """删除分析（仅终态；succeeded 视为合规资产，server 拒删）"""
    # succeeded 不可删的合规守卫已下沉 server(直调 API 也拦得住),CLI 不再预查
    confirm(f"确认删除 {workflow_id}? 此操作不可恢复。")

    client = AgentClient()
    envelope, code = client.delete(f"/workflow/{workflow_id}")

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    console.print(f"[red]Deleted:[/red] {d.get('workflow_id')}")
    sys.exit(code)
