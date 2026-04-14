"""
Pipeline 命令：pipeline list
"""

import typer

from nfctl.client import AgentClient
from nfctl.output import is_json, print_result, print_table

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_pipelines() -> None:
    """列出 Pipeline 配置"""
    client = AgentClient()
    envelope, code = client.get("/pipeline/")

    if not envelope["ok"] or is_json():
        print_result(envelope, code)

    data = envelope["data"]
    if not isinstance(data, list):
        data = []

    print_table(
        "Pipeline 配置",
        [
            ("pipeline_name", "Name"),
            ("max_concurrent", "Max Concurrent"),
            ("enabled", "Enabled"),
        ],
        data,
    )
