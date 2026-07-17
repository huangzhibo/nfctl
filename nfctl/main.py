"""
nfctl -- nf-server CLI

面向生信工程师和 AI Agent 的命令行工具。
输出契约（JSON 信封、退出码）与 lims2 CLI 对齐。
"""

from importlib.metadata import version as _pkg_version

import typer

from nfctl.client import EXIT_VALIDATION, _error
from nfctl.config import ConfigError, apply_profile_option, get_url
from nfctl.output import OutputFormat, apply_options, print_result

app = typer.Typer(
    name="nfctl",
    help="nf-server CLI",
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"nfctl {_pkg_version('nfctl')}")
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
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="跳过交互式确认提示（--format json 自动隐含）"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="调试日志"),
    no_color: bool = typer.Option(False, "--no-color", help="禁用颜色"),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="使用指定 profile 覆盖当前 profile（不影响 NFCTL_URL 直连）",
        envvar="NFCTL_PROFILE",
    ),
    _version: bool | None = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True
    ),
) -> None:
    """nf-server CLI"""
    apply_options(fmt=format, jq=jq)
    if profile:
        # 未知 profile 快速失败;错误文案复用 get_url 的 ConfigError,
        # 信封与退出码同 client 层的 CONFIG_ERROR 口径
        try:
            get_url(profile)
        except ConfigError as e:
            print_result(_error("CONFIG_ERROR", str(e), hint=e.hint), EXIT_VALIDATION)
    apply_profile_option(profile)

    app._quiet = quiet  # type: ignore[attr-defined]
    app._verbose = verbose  # type: ignore[attr-defined]

    if no_color:
        from nfctl.output import console, err_console

        console.__init__(no_color=True)  # type: ignore[misc]
        err_console.__init__(stderr=True, no_color=True)  # type: ignore[misc]


# 注册命令
from nfctl.commands import archive, config_cmd, pipeline, query, workflow  # noqa: E402

app.add_typer(config_cmd.app, name="config", help="配置管理")
app.add_typer(pipeline.app, name="pipeline", help="Pipeline 管理")
app.add_typer(archive.app, name="archive", help="归档/后处理操作")

# 查询命令（扁平注册）
app.command("overview")(query.overview)
app.command("list")(query.list_workflows)
app.command("status")(query.status)
app.command("progress")(query.progress)
app.command("tasks")(query.tasks)
app.command("log")(query.log)
app.command("resources")(query.resources)
app.command("task")(query.task_detail)

# 管理命令（扁平注册）
app.command("submit")(workflow.submit)
app.command("resume")(workflow.resume)
app.command("cancel")(workflow.cancel)
app.command("delete")(workflow.delete)
