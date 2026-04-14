"""
HTTP 客户端

封装 httpx，统一错误处理，输出 JSON 信封格式（与 lims2 CLI 对齐）。
"""

from typing import Any

import httpx

from nfctl.config import get_url

# 退出码（0-4 与 lims2 对齐）
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_VALIDATION = 2
EXIT_AUTH = 3  # 保留，当前无认证
EXIT_NETWORK = 4
EXIT_CONFLICT = 5
EXIT_SERVER = 6

# HTTP 状态码 → (退出码, 错误类型)
_STATUS_MAP: dict[int, tuple[int, str]] = {
    400: (EXIT_VALIDATION, "VALIDATION_ERROR"),
    404: (EXIT_VALIDATION, "NOT_FOUND"),
    409: (EXIT_CONFLICT, "CONFLICT"),
    422: (EXIT_VALIDATION, "VALIDATION_ERROR"),
}

# 错误类型 → 用户提示
_HINTS: dict[str, str] = {
    "CONFLICT": "使用 nfctl cancel 先取消当前流程",
    "NOT_FOUND": "使用 nfctl list 查看可用的 workflow",
}


class AgentClient:
    """Agent HTTP 客户端"""

    def __init__(self, base_url: str | None = None, timeout: float = 30):
        self._base_url = base_url or get_url()
        self._timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> tuple[dict, int]:
        """发送请求，返回 (响应体, 退出码)"""
        try:
            with httpx.Client(base_url=self._base_url, timeout=self._timeout) as client:
                resp = client.request(method, path, **kwargs)
        except httpx.ConnectError:
            return _error(
                EXIT_NETWORK,
                "NETWORK_ERROR",
                f"无法连接 Agent: {self._base_url}",
                hint="检查 Agent 是否运行，或设置 NFCTL_URL 环境变量",
            ), EXIT_NETWORK
        except httpx.TimeoutException:
            return _error(
                EXIT_NETWORK, "TIMEOUT", f"请求超时: {self._base_url}{path}"
            ), EXIT_NETWORK

        if resp.status_code >= 400:
            return _handle_http_error(resp), _STATUS_MAP.get(
                resp.status_code, (EXIT_SERVER, "SERVER_ERROR")
            )[0]

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
    _exit_code: int, error_type: str, message: str, hint: str | None = None
) -> dict:
    """构造错误信封"""
    err: dict[str, Any] = {"type": error_type, "message": message}
    if hint:
        err["hint"] = hint
    elif error_type in _HINTS:
        err["hint"] = _HINTS[error_type]
    return {"ok": False, "error": err}


def _handle_http_error(resp: httpx.Response) -> dict:
    """将 HTTP 错误响应转为信封"""
    exit_code, error_type = _STATUS_MAP.get(
        resp.status_code, (EXIT_SERVER, "SERVER_ERROR")
    )

    try:
        body = resp.json()
        message = body.get("detail", str(body))
    except Exception:
        message = resp.text or f"HTTP {resp.status_code}"

    return _error(exit_code, error_type, message)
