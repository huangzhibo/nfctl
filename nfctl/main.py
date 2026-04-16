"""
nfctl -- nf-server CLI

面向生信工程师和 AI Agent 的命令行工具。
输出契约（JSON 信封、退出码）与 lims2 CLI 对齐。
"""

import typer

from nfctl.output import OutputFormat, apply_options

app = typer.Typer(
    name="nfctl",
    help="nf-server CLI",
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo("nfctl 0.3.0")
        raise typer.Exit()


@app.callback()
def main(
    format: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--format",
        "-f",
        help="输出格式",
        envvar="NFCTL_FORMAT",
    ),
    jq: str | None = typer.Option(
        None, "--jq", help="jq 表达式过滤 JSON 输出（隐含 -f json）"
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="静默模式"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="调试日志"),
    no_color: bool = typer.Option(False, "--no-color", help="禁用颜色"),
    _version: bool | None = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True
    ),
) -> None:
    """nf-server CLI"""
    apply_options(fmt=format, jq=jq)

    app._quiet = quiet  # type: ignore[attr-defined]
    app._verbose = verbose  # type: ignore[attr-defined]

    if no_color:
        from nfctl.output import console, err_console

        console.__init__(no_color=True)  # type: ignore[misc]
        err_console.__init__(stderr=True, no_color=True)  # type: ignore[misc]


# 注册命令
from nfctl.commands import config_cmd, pipeline, query, workflow  # noqa: E402

app.add_typer(config_cmd.app, name="config", help="配置管理")
app.add_typer(pipeline.app, name="pipeline", help="Pipeline 管理")

# 查询命令（扁平注册）
app.command("overview")(query.overview)
app.command("list")(query.list_workflows)
app.command("status")(query.status)
app.command("tasks")(query.tasks)
app.command("log")(query.log)
app.command("resources")(query.resources)
app.command("task")(query.task_detail)

# 管理命令（扁平注册）
app.command("submit")(workflow.submit)
app.command("resume")(workflow.resume)
app.command("cancel")(workflow.cancel)
app.command("delete")(workflow.delete)
