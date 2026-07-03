"""
归档/后处理操作命令组：archive resume / restore / status / cancel

归档专属操作的统一归宿,与主流程操作(resume/cancel)分开,
避免"resume 会不会重跑主流程"的歧义。
"""

import sys
import time

import typer

from nfctl.client import AgentClient
from nfctl.output import console, format_local_time, is_json, print_kv, print_result

app = typer.Typer(no_args_is_help=True)

# restore --wait 的轮询间隔与 gone 容忍次数(server NFS 宽限 120s,略放宽)
_WAIT_POLL_SECONDS = 10
_WAIT_GONE_LIMIT = 15


@app.command("resume")
def resume(
    workflow_id: str = typer.Argument(help="Workflow ID"),
) -> None:
    """恢复失败/取消的归档或后处理（主流程须已成功；重跑主流程用 nfctl resume）"""
    client = AgentClient()
    envelope, code = client.post(f"/workflow/{workflow_id}/archive/resume")

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    console.print(f"[green]Archive resumed:[/green] {d.get('workflow_id')}")
    sys.exit(code)


@app.command("restore")
def restore(
    workflow_id: str = typer.Argument(help="Workflow ID"),
    wait: bool = typer.Option(
        False, "--wait", help="轮询等待解压完成(大归档可达小时级,也可稍后查询)"
    ),
) -> None:
    """解压归档数据回 launch_dir 原位（进度用 nfctl archive status 查询）"""
    client = AgentClient()
    envelope, code = client.post(f"/workflow/{workflow_id}/archive/restore")

    if not envelope["ok"]:
        print_result(envelope, code)

    job_id = envelope["data"].get("job_id")
    if not wait:
        if is_json():
            print_result(envelope, code)
        console.print(f"[green]Restore submitted:[/green] job {job_id}")
        console.print(f"进度查询: nfctl archive status {workflow_id}")
        sys.exit(code)

    if not is_json():
        console.print(f"Restore submitted (job {job_id}), waiting...")
    gone_count = 0
    while True:
        time.sleep(_WAIT_POLL_SECONDS)
        status_env, status_code = client.get(f"/workflow/{workflow_id}/archive/restore")
        if not status_env["ok"]:
            print_result(status_env, status_code)
        data = status_env["data"]
        status = data.get("status")
        if status == "done":
            if is_json():
                print_result(status_env, 0)
            console.print(f"[green]Restore completed:[/green] {workflow_id}")
            sys.exit(0)
        if status == "failed":
            if is_json():
                print_result(status_env, 1)
            console.print(f"[red]Restore failed:[/red] {data.get('detail')}")
            sys.exit(1)
        if status == "gone":
            # job 已不在且无退出码:NFS 延迟内继续等,持续 gone 视为异常退出
            gone_count += 1
            if gone_count >= _WAIT_GONE_LIMIT:
                if is_json():
                    print_result(status_env, 1)
                console.print(
                    "[red]Restore job 已消失且无退出码[/red]"
                    "(可能被外部清理),请重新执行 restore"
                )
                sys.exit(1)
        else:
            gone_count = 0


@app.command("status")
def status(
    workflow_id: str = typer.Argument(help="Workflow ID"),
) -> None:
    """查看归档信息（产物位置/归档倒计时）与最近一次解压任务状态"""
    client = AgentClient()
    detail_env, detail_code = client.get(f"/workflow/{workflow_id}")
    if not detail_env["ok"]:
        print_result(detail_env, detail_code)
    restore_env, restore_code = client.get(f"/workflow/{workflow_id}/archive/restore")
    if not restore_env["ok"]:
        print_result(restore_env, restore_code)

    d = detail_env["data"]
    r = restore_env["data"]
    if is_json():
        print_result(
            {
                "ok": True,
                "data": {
                    "workflow_id": workflow_id,
                    "display_status": d.get("display_status"),
                    "status_summary": d.get("status_summary"),
                    "pp_phase": d.get("pp_phase"),
                    "pp_status": d.get("pp_status"),
                    "archive_eta": d.get("archive_eta"),
                    "archive_path": d.get("archive_path"),
                    "restore": r,
                },
            },
            0,
        )

    items: list[tuple[str, object]] = [
        ("workflow_id", workflow_id),
        ("display_status", d.get("display_status")),
        ("summary", d.get("status_summary")),
    ]
    if d.get("pp_phase"):
        items.append(("pp", f"{d['pp_phase']} ({d.get('pp_status')})"))
    if d.get("archive_eta"):
        items.append(("archive_eta", format_local_time(d["archive_eta"])))
    items.append(("archive_path", d.get("archive_path") or "-"))
    items.append(("restore_job", r.get("job_id") or "-"))
    items.append(("restore_status", r.get("status")))
    if r.get("detail"):
        items.append(("restore_detail", r["detail"]))
    print_kv("归档状态", items)
    sys.exit(0)


@app.command("cancel")
def cancel(
    workflow_id: str = typer.Argument(help="Workflow ID"),
    reason: str | None = typer.Option(None, "--reason", "-r", help="取消原因"),
) -> None:
    """取消后处理/归档，保留成功的分析结果（整体撤销流程用 nfctl cancel）"""
    from nfctl.commands.workflow import _confirm

    _confirm(f"确认仅取消 {workflow_id} 的归档(保留分析结果)?")

    client = AgentClient()
    body: dict = {"scope": "archive"}
    if reason:
        body["reason"] = reason

    envelope, code = client.post(f"/workflow/{workflow_id}/cancel", json=body)

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    d = envelope["data"]
    console.print(
        f"[yellow]归档已取消:[/yellow] {d.get('workflow_id')} "
        f"(状态更新需数秒,可用 nfctl status 确认)"
    )
    sys.exit(code)
