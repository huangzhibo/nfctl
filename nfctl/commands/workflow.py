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
            _error("VALIDATION_ERROR", failed),
            EXIT_VALIDATION,
        )

    # 从 validate 响应提取 workflow_id（detail 格式："TOWER_WORKFLOW_ID=xxx"）
    wf_id_detail = val_data.get("checks", {}).get("workflow_id", {}).get("detail", "")
    workflow_id = wf_id_detail.split("=", 1)[1] if "=" in wf_id_detail else ""

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
    scope: str = typer.Option(
        "workflow",
        "--scope",
        help=(
            "取消范围。workflow(默认)=整体撤销:可取消运行中或已成功的流程,"
            "终态置 cancelled 并把作废状态重推 LIMS;archive=仅取消后处理/归档,"
            "保留成功的分析结果(LIMS 仍 100%)"
        ),
    ),
) -> None:
    """取消流程(整体撤销)或仅取消归档"""
    if scope not in ("workflow", "archive"):
        print_result(
            _error(
                "VALIDATION_ERROR",
                f"无效的 --scope: {scope}",
                hint="可选值: workflow(整体撤销,默认) / archive(仅取消归档)",
            ),
            EXIT_VALIDATION,
        )

    prompt = (
        f"确认仅取消 {workflow_id} 的归档(保留分析结果)?"
        if scope == "archive"
        else f"确认取消 {workflow_id}? 已成功的流程将被整体撤销并通知 LIMS 作废。"
    )
    _confirm(prompt)

    client = AgentClient()
    body: dict = {"scope": scope}
    if reason:
        body["reason"] = reason

    envelope, code = client.post(f"/workflow/{workflow_id}/cancel", json=body)

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    label = "归档已取消" if scope == "archive" else "Cancel signal sent"
    console.print(
        f"[yellow]{label}:[/yellow] {d.get('workflow_id')} "
        f"(状态更新需数秒,可用 nfctl status 确认)"
    )
    sys.exit(code)


def delete(
    workflow_id: str = typer.Argument(help="Workflow ID"),
) -> None:
    """删除工作流（仅终态；succeeded 视为合规资产，禁止删除）"""
    client = AgentClient()

    # 成功结果视为合规资产 — CLI 层硬阻止；如需强删走后端 API。
    detail_envelope, detail_code = client.get(f"/workflow/{workflow_id}")
    if not detail_envelope["ok"]:
        print_result(detail_envelope, detail_code)

    if detail_envelope["data"].get("status") == "succeeded":
        print_result(
            _error(
                "VALIDATION_ERROR",
                "已成功完成的工作流不可删除（成功结果视为合规资产）",
                hint="如确需清理，请联系管理员通过后端 API 强制处理",
                resource_id=workflow_id,
            ),
            EXIT_VALIDATION,
        )

    _confirm(f"确认删除 {workflow_id}? 此操作不可恢复。")

    envelope, code = client.delete(f"/workflow/{workflow_id}")

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    console.print(f"[red]Deleted:[/red] {d.get('workflow_id')}")
    sys.exit(code)
