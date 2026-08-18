"""
HTTP 客户端

封装 httpx,统一错误处理,输出 JSON 信封格式(与 lims2 CLI 对齐)。

## 错误信封规范

nf-server 错误响应顶层扁平:
    {
        "detail": "人类可读消息",
        "error_code": "CONFLICT|NOT_FOUND|...",
        "hint": "修复建议(可选)",
        "resource_id": "workflow_id 等(可选)",
        "job_id": "调度器作业 ID(可选,cancel 失败时)"
    }

本客户端的错误信封:
    {"ok": False, "error": {"type": ..., "message": ..., "hint": ..., "job_id": ..., "resource_id": ..., ...}}
其中 type 优先用服务端 error_code,回退到 HTTP 状态码映射。
服务端结构化上下文（如 conflicts / operation_id）原名保留在 error 中，供 Agent 决策。
"""

import time
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Any

import httpx

from nfctl.config import ConfigError, get_url
from nfctl.output import debug, err_console

try:
    _VERSION = _pkg_version("nfctl")
except PackageNotFoundError:  # 源码直跑未安装：UA 不带版本段，server 端 fail open
    _VERSION = ""

# 版本握手：server 按此 UA 判定契约兼容性,过旧 426、偏旧回 X-Nfctl-Latest 提醒头
_USER_AGENT = f"nfctl/{_VERSION}" if _VERSION else "nfctl"

# 退出码(0-4 与 lims2 对齐)
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_VALIDATION = 2
EXIT_AUTH = 3  # 保留,当前无认证
EXIT_NETWORK = 4
EXIT_CONFLICT = 5
EXIT_SERVER = 6

# HTTP 状态码 → (退出码, 默认 error_type);error_code 缺失时回退到这里。
_STATUS_MAP: dict[int, tuple[int, str]] = {
    400: (EXIT_VALIDATION, "VALIDATION_ERROR"),
    404: (EXIT_VALIDATION, "NOT_FOUND"),
    409: (EXIT_CONFLICT, "CONFLICT"),
    422: (EXIT_VALIDATION, "VALIDATION_ERROR"),
    426: (EXIT_VALIDATION, "UPGRADE_REQUIRED"),  # server 版本握手:CLI 过旧须升级
}

# 服务端 error_code → 退出码;未列出的 error_code 按 HTTP 状态码映射。
# (Temporal 时代的 *_UNAVAILABLE 等网络类 code 已随 server 去引擎不再发射,条目删除)
_ERROR_CODE_EXIT: dict[str, int] = {
    "CONFLICT": EXIT_CONFLICT,
    "VALIDATION_ERROR": EXIT_VALIDATION,
    "BAD_REQUEST": EXIT_VALIDATION,
    "NOT_FOUND": EXIT_VALIDATION,
    "UPGRADE_REQUIRED": EXIT_VALIDATION,
}


class AgentClient:
    """Agent HTTP 客户端"""

    def __init__(self, base_url: str | None = None, timeout: float = 30):
        self._explicit_base_url = base_url
        self._timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> tuple[dict, int]:
        """发送请求,返回 (响应体, 退出码)"""
        try:
            base_url = self._explicit_base_url or get_url()
        except ConfigError as e:
            return _error("CONFIG_ERROR", str(e), hint=e.hint), EXIT_VALIDATION

        # 耗时自测(不用 resp.elapsed:含连接建立更真实,且对 mock 响应友好)
        debug(f"→ {method} {base_url}{path}")
        t0 = time.monotonic()
        try:
            with httpx.Client(
                base_url=base_url,
                timeout=self._timeout,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                resp = client.request(method, path, **kwargs)
        except httpx.ConnectError:
            return _error(
                "NETWORK_ERROR",
                f"无法连接 Agent: {base_url}",
                hint="检查 Agent 是否运行，或使用 nfctl config set url 更新地址",
            ), EXIT_NETWORK
        except httpx.TimeoutException:
            return _error("TIMEOUT", f"请求超时: {base_url}{path}"), EXIT_NETWORK

        debug(f"← {resp.status_code} ({time.monotonic() - t0:.2f}s)")
        _maybe_warn_new_version(resp)

        if resp.status_code >= 400:
            envelope, exit_code = _handle_http_error(resp)
            return envelope, exit_code

        try:
            data = resp.json()
        except Exception:
            data = resp.text

        return {"ok": True, "data": data}, EXIT_SUCCESS

    def get(self, path: str, **params: Any) -> tuple[dict, int]:
        clean = {k: v for k, v in params.items() if v is not None}
        return self._request("GET", path, params=clean)

    def post(self, path: str, json: dict | None = None) -> tuple[dict, int]:
        return self._request("POST", path, json=json)

    def put(self, path: str, json: dict | None = None) -> tuple[dict, int]:
        return self._request("PUT", path, json=json)

    def delete(self, path: str) -> tuple[dict, int]:
        return self._request("DELETE", path)


_new_version_warned = False


def _maybe_warn_new_version(resp: httpx.Response) -> None:
    """server 回 X-Nfctl-Latest 提醒头（兼容但偏旧）时往 stderr 提示一次。

    stderr 不污染 stdout 的 JSON 输出;进程内只提示一次(restore --wait
    等轮询场景不刷屏)。
    """
    global _new_version_warned
    if _new_version_warned:
        return
    latest = resp.headers.get("x-nfctl-latest")
    if latest:
        _new_version_warned = True
        err_console.print(
            f"[dim]提示: nfctl 有新版本 {latest}（当前 {_VERSION or '未知'}），"
            f"可执行 pip install -U nfctl 更新[/dim]"
        )


def _error(
    error_type: str,
    message: str,
    *,
    hint: str | None = None,
    resource_id: str | None = None,
    job_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict:
    """构造错误信封"""
    err: dict[str, Any] = {"type": error_type, "message": message}
    if hint:
        err["hint"] = hint
    if resource_id:
        err["resource_id"] = resource_id
    if job_id:
        err["job_id"] = job_id
    for key, value in (context or {}).items():
        err.setdefault(key, value)
    return {"ok": False, "error": err}


def _handle_http_error(resp: httpx.Response) -> tuple[dict, int]:
    """把 HTTP 错误响应转为 (信封, 退出码)。

    优先读服务端 error_code 决定 error_type 和退出码。
    """
    default_exit, default_type = _STATUS_MAP.get(
        resp.status_code, (EXIT_SERVER, "SERVER_ERROR")
    )

    body: Any
    try:
        body = resp.json()
    except Exception:
        body = None

    if not isinstance(body, dict):
        message = resp.text or f"HTTP {resp.status_code}"
        return _error(default_type, message), default_exit

    error_code = body.get("error_code")
    error_type = error_code or default_type
    exit_code = (
        _ERROR_CODE_EXIT[error_code] if error_code in _ERROR_CODE_EXIT else default_exit
    )

    detail = body.get("detail")
    validation_errors = _validation_errors(detail)
    if isinstance(detail, str) and detail:
        message = detail
    elif validation_errors:
        summary = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in validation_errors
        )
        message = f"请求参数校验失败: {summary}"
    else:
        message = f"HTTP {resp.status_code}"
    hint = body.get("hint")
    resource_id = body.get("resource_id")
    job_id = body.get("job_id")
    reserved = {"detail", "error_code", "hint", "resource_id", "job_id"}
    context = {key: value for key, value in body.items() if key not in reserved}
    if validation_errors:
        context["validation_errors"] = validation_errors

    return _error(
        error_type,
        message,
        hint=hint,
        resource_id=resource_id,
        job_id=job_id,
        context=context,
    ), exit_code


def _validation_errors(detail: Any) -> list[dict[str, Any]]:
    """Sanitize FastAPI/Pydantic 422 details for the public error envelope."""
    if not isinstance(detail, list):
        return []
    errors: list[dict[str, Any]] = []
    for item in detail:
        if not isinstance(item, dict):
            continue
        loc = item.get("loc")
        msg = item.get("msg")
        if not isinstance(loc, (list, tuple)) or not isinstance(msg, str):
            continue
        error: dict[str, Any] = {"loc": list(loc), "msg": msg}
        if isinstance(item.get("type"), str):
            error["type"] = item["type"]
        errors.append(error)
    return errors
