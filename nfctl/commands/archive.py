"""launch_dir 级存储生命周期命令。"""

import sys
import time

import typer

from nfctl.client import (
    EXIT_ERROR,
    EXIT_SUCCESS,
    EXIT_VALIDATION,
    AgentClient,
    _error,
)
from nfctl.output import (
    confirm,
    console,
    format_local_time,
    is_json,
    print_kv,
    print_result,
)
from nfctl.paths import normalize_launch_dir

app = typer.Typer(no_args_is_help=True)

_WAIT_POLL_SECONDS = 10


def _post_command(
    path: str, launch_dir: str, *, reason: str | None = None
) -> tuple[dict, int]:
    body = {"launch_dir": normalize_launch_dir(launch_dir)}
    if reason:
        body["reason"] = reason
    return AgentClient().post(path, json=body)


def _get_state(client: AgentClient, launch_dir: str) -> tuple[dict, int]:
    normalized = normalize_launch_dir(launch_dir)
    envelope, code = client.get(
        "/launch-dirs",
        launch_dir=normalized,
        page=1,
        page_size=1,
    )
    if not envelope["ok"]:
        return envelope, code
    items = envelope["data"].get("items", [])
    if not items:
        return (
            _error(
                "LAUNCH_DIR_NOT_FOUND",
                "launch_dir 尚未登记",
                resource_id=normalized,
            ),
            EXIT_VALIDATION,
        )
    return {"ok": True, "data": items[0]}, EXIT_SUCCESS


def _print_accepted(action: str, envelope: dict, code: int) -> None:
    if not envelope["ok"] or is_json():
        print_result(envelope, code)
    data = envelope["data"]
    console.print(
        f"[green]{action} 已受理:[/green] {data.get('launch_dir')} "
        f"(operation {data.get('operation_id')}, 下个对账周期提交)"
    )
    sys.exit(code)


@app.command("start")
def start(
    launch_dir: str = typer.Argument(help="Launch directory（可传 .）"),
) -> None:
    """立即对 launch_dir 发起归档。"""
    envelope, code = _post_command("/launch-dirs/archive", launch_dir)
    _print_accepted("Archive", envelope, code)


@app.command("resume")
def resume(
    launch_dir: str = typer.Argument(help="Launch directory（可传 .）"),
) -> None:
    """恢复该目录最近一次 failed/cancelled 存储操作。"""
    envelope, code = _post_command("/launch-dirs/resume", launch_dir)
    _print_accepted("Storage resume", envelope, code)


@app.command("restore")
def restore(
    launch_dir: str = typer.Argument(help="Launch directory（可传 .）"),
    wait: bool = typer.Option(False, "--wait", help="轮询目录状态，等待 restore 完成"),
) -> None:
    """把该 launch_dir 的归档数据解压回原位。"""
    envelope, code = _post_command("/launch-dirs/restore", launch_dir)
    if not envelope["ok"]:
        print_result(envelope, code)
    if not wait:
        _print_accepted("Restore", envelope, code)

    operation_id = envelope["data"].get("operation_id")
    normalized = normalize_launch_dir(launch_dir)
    if not is_json():
        console.print(f"Restore {operation_id} 已受理，等待完成...")
    client = AgentClient()
    while True:
        time.sleep(_WAIT_POLL_SECONDS)
        state_env, state_code = _get_state(client, normalized)
        if not state_env["ok"]:
            print_result(state_env, state_code)
        state = state_env["data"]
        operation = state.get("operation") or {}
        if operation.get("operation_id") != operation_id:
            print_result(
                _error(
                    "STORAGE_OPERATION_REPLACED",
                    "等待中的 restore 已被另一存储操作替代",
                    resource_id=normalized,
                    context={
                        "expected_operation_id": operation_id,
                        "current_operation_id": operation.get("operation_id"),
                    },
                ),
                EXIT_ERROR,
            )
        operation_status = operation.get("status")
        if operation_status == "succeeded":
            if is_json():
                print_result(state_env, 0)
            console.print(f"[green]Restore completed:[/green] {normalized}")
            sys.exit(0)
        if operation_status in ("failed", "cancelled"):
            print_result(
                _error(
                    f"STORAGE_OPERATION_{operation_status.upper()}",
                    state.get("last_error") or f"Restore operation {operation_status}",
                    resource_id=normalized,
                    context={
                        "operation_id": operation_id,
                        "operation_status": operation_status,
                        "storage_state": state.get("storage_state"),
                    },
                ),
                EXIT_ERROR,
            )


@app.command("status")
def status(
    launch_dir: str = typer.Argument(help="Launch directory（可传 .）"),
) -> None:
    """查看目录存储状态、归档计划及最近一次操作。"""
    envelope, code = _get_state(AgentClient(), launch_dir)
    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    data = envelope["data"]
    operation = data.get("operation") or {}
    items: list[tuple[str, object]] = [
        ("launch_dir", data.get("launch_dir")),
        ("storage_state", data.get("storage_state")),
        ("auto_archive", data.get("auto_archive_enabled")),
        ("plan_workflow_id", data.get("plan_workflow_id")),
        ("archive_path", data.get("archive_path")),
    ]
    if data.get("archive_due_at"):
        items.append(("archive_due_at", format_local_time(data["archive_due_at"])))
    if data.get("archived_at"):
        items.append(("archived_at", format_local_time(data["archived_at"])))
    if data.get("restored_at"):
        items.append(("restored_at", format_local_time(data["restored_at"])))
    if operation:
        items.extend(
            [
                ("operation_id", operation.get("operation_id")),
                ("operation_kind", operation.get("kind")),
                ("operation_status", operation.get("status")),
                ("operation_job_id", operation.get("job_id")),
            ]
        )
        if operation.get("gone_since"):
            items.append(
                ("operation_gone_since", format_local_time(operation["gone_since"]))
            )
    if data.get("last_error"):
        items.append(("error", data["last_error"]))
    print_kv("LaunchDir 存储状态", items)
    sys.exit(0)


@app.command("cancel")
def cancel(
    launch_dir: str = typer.Argument(help="Launch directory（可传 .）"),
    reason: str | None = typer.Option(None, "--reason", "-r", help="取消原因"),
) -> None:
    """取消当前存储操作，并关闭该目录的自动归档计划。"""
    normalized = normalize_launch_dir(launch_dir)
    confirm(f"确认取消 {normalized} 的存储操作并关闭自动归档?")
    envelope, code = _post_command(
        "/launch-dirs/cancel",
        normalized,
        reason=reason,
    )
    if not envelope["ok"] or is_json():
        print_result(envelope, code)
    console.print(
        f"[yellow]自动归档已关闭；活跃任务（如有）已提交取消请求:[/yellow] {normalized}"
    )
    sys.exit(code)
