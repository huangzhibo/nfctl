"""
输出层

人类模式（rich table）和 JSON 模式（信封格式）的统一输出。
JSON 信封格式与 lims2 CLI 完全对齐。
"""

import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


class OutputFormat(StrEnum):
    """输出格式"""

    TABLE = "table"
    JSON = "json"


# 全局状态（由 main.py callback 设置）
_format: OutputFormat = OutputFormat.TABLE
_jq_expr: str | None = None


def set_format(fmt: OutputFormat) -> None:
    global _format
    _format = fmt


def set_jq(expr: str | None) -> None:
    global _jq_expr
    _jq_expr = expr


def apply_options(
    fmt: OutputFormat = OutputFormat.TABLE, jq: str | None = None
) -> None:
    """全局 --format/--jq 处理"""
    set_jq(None)
    if jq:
        if shutil.which("jq") is None:
            err_console.print("[red]Error:[/red] jq 未安装，请先安装 jq")
            sys.exit(1)
        set_format(OutputFormat.JSON)
        set_jq(jq)
    else:
        set_format(fmt)


def get_format() -> OutputFormat:
    return _format


def is_json() -> bool:
    return _format == OutputFormat.JSON


def _output_json(obj: dict) -> None:
    """输出 JSON，如果设置了 --jq 则过滤"""
    raw = json.dumps(obj, ensure_ascii=False, default=str)
    if _jq_expr:
        try:
            proc = subprocess.run(
                ["jq", _jq_expr],
                input=raw,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            err_console.print("[red]Error:[/red] jq 未安装，请先安装 jq")
            sys.exit(1)
        if proc.returncode != 0:
            err_console.print(f"[red]jq error:[/red] {proc.stderr.strip()}")
            sys.exit(1)
        print(proc.stdout, end="")
    else:
        print(raw)


def print_result(envelope: dict, exit_code: int) -> None:
    """统一输出：JSON 模式直接打印信封，人类模式由调用方渲染"""
    if is_json():
        _output_json(envelope)
    elif not envelope.get("ok"):
        err = envelope.get("error", {})
        err_console.print(f"[red]Error:[/red] {err.get('message', '未知错误')}")
        if hint := err.get("hint"):
            err_console.print(f"[dim]Hint: {hint}[/dim]")
    sys.exit(exit_code)


def print_data(data: Any, exit_code: int = 0) -> None:
    """输出成功数据（JSON 模式包装信封，人类模式由调用方已渲染）"""
    if is_json():
        _output_json({"ok": True, "data": data})
        sys.exit(exit_code)


def format_local_time(value: Any) -> Any:
    """将后端返回的 ISO 8601 时间字符串转为本地时区的 'YYYY-MM-DD HH:MM:SS'。

    服务端约定返回 UTC 时间；若字符串不带时区则按 UTC 解释。
    解析失败或非字符串原样返回。仅供人类展示使用，JSON 输出应保留原始值。
    """
    if not isinstance(value, str) or not value:
        return value
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def print_table(
    title: str,
    columns: list[tuple[str, str]],
    rows: list[dict],
    total: int | None = None,
) -> None:
    """渲染 rich 表格（仅人类模式）"""
    table = Table(title=title, show_lines=False)
    for _col_key, col_label in columns:
        table.add_column(col_label)

    for row in rows:
        table.add_row(*[_format_cell(row.get(col_key)) for col_key, _ in columns])

    console.print(table)
    if total is not None and total > len(rows):
        console.print(f"[dim]共 {total} 条，当前显示 {len(rows)} 条[/dim]")


def print_kv(title: str, items: list[tuple[str, Any]]) -> None:
    """渲染 key-value 详情（仅人类模式）"""
    console.print(f"[bold]{title}[/bold]")
    max_key = max(len(k) for k, _ in items) if items else 0
    for key, value in items:
        console.print(f"  {key:<{max_key}}  {_format_cell(value)}")


# 状态颜色映射
_STATUS_COLORS: dict[str, str] = {
    "running": "blue",
    "pending": "yellow",
    "succeeded": "green",
    "failed": "red",
    "cancelled": "dim",
}


def _format_cell(value: Any) -> str:
    """格式化单元格值"""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "[green]Yes[/green]" if value else "[red]No[/red]"
    s = str(value)
    if s in _STATUS_COLORS:
        return f"[{_STATUS_COLORS[s]}]{s}[/{_STATUS_COLORS[s]}]"
    return s
