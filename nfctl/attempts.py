"""执行（attempt）寻址：对外只用 workflow_id + attempt_no。

attempt_no 从 1 连续递增，当前执行永远是最大号；"上一次"由客户端用当前序号减 1
算出，服务端只接受绝对编号。
"""

from typing import Any

import typer

from nfctl.client import EXIT_VALIDATION, AgentClient, _error
from nfctl.output import print_result


def attempt_option(help: str = "第几次执行（默认当前执行）") -> Any:
    return typer.Option(None, "--attempt", "-a", min=1, help=help)


def previous_option() -> Any:
    return typer.Option(False, "--previous", help="上一次执行（当前序号减 1）")


def label(workflow_id: str, attempt_no: object) -> str:
    """与服务端日志同口径的执行标识。"""
    return f"{workflow_id}#{attempt_no}"


def fetch_workflow(client: AgentClient, workflow_id: str) -> dict:
    envelope, code = client.get(f"/workflow/{workflow_id}")
    if not envelope["ok"]:
        print_result(envelope, code)
    return envelope["data"]


def current_attempt_no(client: AgentClient, workflow_id: str) -> int:
    return fetch_workflow(client, workflow_id)["current_attempt"]["attempt_no"]


def resolve_attempt_no(
    client: AgentClient, workflow_id: str, attempt: int | None, previous: bool
) -> int | None:
    """返回要查看的序号；None 交给服务端取当前执行。"""
    if not previous:
        return attempt
    if attempt is not None:
        raise typer.BadParameter(
            "--attempt 与 --previous 只能二选一", param_hint="--previous"
        )
    current = current_attempt_no(client, workflow_id)
    if current <= 1:
        print_result(
            _error(
                "ATTEMPT_NOT_FOUND",
                f"{workflow_id} 只执行过 1 次，没有上一次执行",
                resource_id=workflow_id,
            ),
            EXIT_VALIDATION,
        )
    return current - 1
