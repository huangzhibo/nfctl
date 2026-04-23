"""
HTTP 客户端

封装 httpx,统一错误处理,输出 JSON 信封格式(与 lims2 CLI 对齐)。

## 错误信封规范

nf-server 升级后错误响应顶层扁平:
    {
        "detail": "人类可读消息",
        "error_code": "CONFLICT|NOT_FOUND|TEMPORAL_UNAVAILABLE|...",
        "hint": "修复建议(可选)",
        "resource_id": "workflow_id 等(可选)",
        "sge_job_id": "SGE 作业 ID(可选,cancel 失败时)"
    }

本客户端的错误信封:
    {"ok": False, "error": {"type": ..., "message": ..., "hint": ..., "sge_job_id": ..., "resource_id": ...}}
其中 type 优先用服务端 error_code,回退到 HTTP 状态码映射。
"""

from typing import Any

import httpx

from nfctl.config import ConfigError, get_url

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
}

# 服务端 error_code → 退出码;未列出的 error_code 按 HTTP 状态码映射。
# 优先级高于 _STATUS_MAP,让运维/临时故障类错误走 EXIT_NETWORK 便于脚本自动重试。
_ERROR_CODE_EXIT: dict[str, int] = {
    "TEMPORAL_UNAVAILABLE": EXIT_NETWORK,
    "SERVICE_UNAVAILABLE": EXIT_NETWORK,
    "GATEWAY_TIMEOUT": EXIT_NETWORK,
    "UPSTREAM_ERROR": EXIT_NETWORK,
    "CONFLICT": EXIT_CONFLICT,
    "VALIDATION_ERROR": EXIT_VALIDATION,
    "BAD_REQUEST": EXIT_VALIDATION,
    "NOT_FOUND": EXIT_VALIDATION,
}

# 无 hint 时按 error_type 兜底的本地提示（只收录 CLI 语境下真正有帮助的）
_HINTS: dict[str, str] = {
    "CONFLICT": "使用 nfctl cancel 先取消当前流程",
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

        try:
            with httpx.Client(base_url=base_url, timeout=self._timeout) as client:
                resp = client.request(method, path, **kwargs)
        except httpx.ConnectError:
            return _error(
                "NETWORK_ERROR",
                f"无法连接 Agent: {base_url}",
                hint="检查 Agent 是否运行，或使用 nfctl config set url 更新地址",
            ), EXIT_NETWORK
        except httpx.TimeoutException:
            return _error("TIMEOUT", f"请求超时: {base_url}{path}"), EXIT_NETWORK

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


def _error(
    error_type: str,
    message: str,
    *,
    hint: str | None = None,
    resource_id: str | None = None,
    sge_job_id: str | None = None,
) -> dict:
    """构造错误信封"""
    err: dict[str, Any] = {"type": error_type, "message": message}
    if hint:
        err["hint"] = hint
    elif error_type in _HINTS:
        err["hint"] = _HINTS[error_type]
    if resource_id:
        err["resource_id"] = resource_id
    if sge_job_id:
        err["sge_job_id"] = sge_job_id
    return {"ok": False, "error": err}


def _handle_http_error(resp: httpx.Response) -> tuple[dict, int]:
    """把 HTTP 错误响应转为 (信封, 退出码)。

    优先读服务端 error_code 决定 error_type 和退出码,兼容历史纯字符串 detail。
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

    # 旧格式 `detail` 可能是 dict({message, hint, ...});新格式是纯字符串。
    detail = body.get("detail")
    if isinstance(detail, dict):
        message = str(detail.get("message") or detail)
        legacy_hint = detail.get("hint")
        legacy_sge = detail.get("sge_job_id")
    else:
        message = (
            detail if isinstance(detail, str) and detail else f"HTTP {resp.status_code}"
        )
        legacy_hint = None
        legacy_sge = None

    hint = body.get("hint") or legacy_hint
    resource_id = body.get("resource_id")
    sge_job_id = body.get("sge_job_id") or legacy_sge

    return _error(
        error_type,
        message,
        hint=hint,
        resource_id=resource_id,
        sge_job_id=sge_job_id,
    ), exit_code
