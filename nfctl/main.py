"""
nfctl -- Nextflow Monitor Agent CLI

面向生信工程师和 AI Agent 的命令行工具。
输出契约（JSON 信封、退出码）与 lims2 CLI 对齐。
"""

import typer

from nfctl.output import OutputFormat, set_format

app = typer.Typer(
    name="nfctl",
    help="Nextflow Monitor Agent CLI",
    no_args_is_help=True,
    add_completion=False,
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
    quiet: bool = typer.Option(False, "--quiet", "-q", help="静默模式"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="调试日志"),
    no_color: bool = typer.Option(False, "--no-color", help="禁用颜色"),
    _version: bool | None = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True
    ),
) -> None:
    """Nextflow Monitor Agent CLI"""
    # --format json 隐含 --quiet
    if format == OutputFormat.JSON:
        quiet = True

    set_format(format)

    # 存储全局状态供命令使用
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

# 管理命令（扁平注册）
app.command("submit")(workflow.submit)
app.command("validate")(workflow.validate)
app.command("resume")(workflow.resume)
app.command("cancel")(workflow.cancel)
app.command("delete")(workflow.delete)
