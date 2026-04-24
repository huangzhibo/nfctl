"""
nfctl CLI 测试

mock httpx 响应，测试 JSON 信封格式、退出码、人类输出。
"""

import json
from importlib.metadata import version as pkg_version
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from nfctl.main import app

runner = CliRunner()


def _mock_response(status_code: int = 200, json_data: dict | None = None):
    """构造 mock httpx.Response"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = json.dumps(json_data or {})
    return resp


class TestGlobalOptions:
    @pytest.mark.unit
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "nfctl" in result.output.lower() or "Nextflow" in result.output

    @pytest.mark.unit
    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert pkg_version("nfctl") in result.output


class TestOverview:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_overview_json(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "running": 3,
                "pending": 1,
                "succeeded": 10,
                "failed": 2,
                "cancelled": 0,
                "total": 16,
                "by_pipeline": [],
                "queue_waiting": 5,
                "queue_waiting_limit": 50,
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "overview"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["running"] == 3

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_overview_table(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "running": 1,
                "pending": 0,
                "succeeded": 5,
                "failed": 0,
                "cancelled": 0,
                "total": 6,
                "by_pipeline": [],
                "queue_waiting": 0,
                "queue_waiting_limit": 50,
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["overview"])

        assert result.exit_code == 0
        assert "running" in result.output.lower()


class TestList:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_list_json(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "total": 1,
                "page": 1,
                "page_size": 20,
                "items": [
                    {
                        "workflow_id": "wf-001",
                        "status": "running",
                        "progress_percent": 45.0,
                        "pipeline_name": "WGS",
                        "env": "prod",
                        "updated_at": "2026-04-13T10:00:00",
                    }
                ],
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "list"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["total"] == 1


class TestStatus:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_hides_error_report_in_human_output(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "workflow_id": "wf-001",
                "status": "failed",
                "progress_percent": 80.0,
                "pipeline_name": "WGS",
                "env": "prod",
                "launch_dir": "/data/wf-001",
                "run_name": "run1",
                "sge_job_id": "12345",
                "error_message": "Process failed",
                "error_report": "FATAL: process FASTQC failed\nexit code 137",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["status", "wf-001"])

        assert result.exit_code == 0
        assert "Process failed" in result.output
        assert "error_report" not in result.output
        assert "exit code 137" not in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_json(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "workflow_id": "wf-001",
                "status": "running",
                "progress_percent": 50.0,
                "error_report": None,
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "status", "wf-001"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["workflow_id"] == "wf-001"


class TestProgress:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_progress_json(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "workflow_id": "wf-001",
                "progress_percent": 42.5,
                "processes": [
                    {
                        "name": "FASTQC",
                        "pending": 0,
                        "submitted": 0,
                        "running": 1,
                        "succeeded": 3,
                        "cached": 0,
                        "failed": 0,
                        "aborted": 0,
                    },
                ],
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "progress", "wf-001"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["progress_percent"] == 42.5
        assert data["data"]["processes"][0]["name"] == "FASTQC"
        assert mock_client.request.call_args.args == (
            "GET",
            "/workflow/wf-001/progress",
        )

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_progress_table(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "workflow_id": "wf-001",
                "progress_percent": 10.0,
                "processes": [
                    {"name": "FASTQC", "running": 2, "succeeded": 1},
                ],
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["progress", "wf-001"])

        assert result.exit_code == 0
        assert "FASTQC" in result.output
        assert "10.0%" in result.output


class TestTaskDetail:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_task_detail_json(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "task_id": 1,
                "workflow_id": "wf-001",
                "process": "FASTQC",
                "name": "FASTQC (sample1)",
                "status": "COMPLETED",
                "hash": "ab/cd1234",
                "workdir": "/work/ab/cd1234",
                "script": "fastqc input.fq",
                "exit_status": 0,
                "duration": 30000,
                "realtime": 28000,
                "peak_rss": 1073741824,
                "cpus": 4,
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "task", "wf-001", "1"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["task_id"] == 1

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_task_detail_table(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "task_id": 1,
                "workflow_id": "wf-001",
                "process": "FASTQC",
                "name": "FASTQC (sample1)",
                "status": "COMPLETED",
                "hash": "ab/cd1234",
                "workdir": "/work/ab/cd1234",
                "script": "fastqc input.fq",
                "exit_status": 0,
                "duration": 30000,
                "realtime": 28000,
                "peak_rss": 1073741824,
                "cpus": 4,
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["task", "wf-001", "1"])

        assert result.exit_code == 0
        assert "FASTQC" in result.output
        assert "ab/cd1234" in result.output
        assert "/work/ab/cd1234" in result.output


class TestTasksSort:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_tasks_with_sort(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "workflow_id": "wf-001",
                "total": 1,
                "page": 1,
                "page_size": 50,
                "tasks": [
                    {
                        "task_id": 1,
                        "process": "FASTQC",
                        "name": "FASTQC (s1)",
                        "status": "COMPLETED",
                        "duration": 5000,
                        "peak_rss": 100000,
                        "exit_status": 0,
                    }
                ],
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "tasks",
                "wf-001",
                "--sort",
                "duration",
                "--sort-order",
                "desc",
            ],
        )

        assert result.exit_code == 0
        # 验证 sort 参数传递到了请求中
        call_args = mock_client.request.call_args
        params = call_args.kwargs.get("params", {})
        assert params["sort_by"] == "duration"
        assert params["sort_order"] == "desc"


class TestListAll:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_list_all_pages(self, mock_client_class):
        """--all 自动遍历多页"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        page1 = _mock_response(
            200,
            {
                "total": 3,
                "page": 1,
                "page_size": 2,
                "items": [
                    {
                        "workflow_id": "wf-001",
                        "status": "running",
                        "progress_percent": 50.0,
                        "pipeline_name": "WGS",
                        "env": "prod",
                        "updated_at": "2026-04-13T10:00:00",
                    },
                    {
                        "workflow_id": "wf-002",
                        "status": "succeeded",
                        "progress_percent": 100.0,
                        "pipeline_name": "WGS",
                        "env": "prod",
                        "updated_at": "2026-04-13T09:00:00",
                    },
                ],
            },
        )
        page2 = _mock_response(
            200,
            {
                "total": 3,
                "page": 2,
                "page_size": 2,
                "items": [
                    {
                        "workflow_id": "wf-003",
                        "status": "failed",
                        "progress_percent": 80.0,
                        "pipeline_name": "WES",
                        "env": "test",
                        "updated_at": "2026-04-13T08:00:00",
                    },
                ],
            },
        )
        mock_client.request.side_effect = [page1, page2]
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "list", "--all", "-n", "2"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert len(data["data"]["items"]) == 3
        assert mock_client.request.call_count == 2


class TestSubmitDryRun:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_submit_dry_run_json(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "can_submit": True,
                "checks": {
                    "capacity": {"passed": True, "detail": "1/10"},
                    "workflow_id": {
                        "passed": True,
                        "detail": "TOWER_WORKFLOW_ID=wf-new",
                    },
                    "run_sh": {"passed": True, "detail": "OK"},
                },
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "submit",
                "--dry-run",
                "-p",
                "WGS",
                "-S",
                "SN-2026-001",
                "/data/sample1",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["can_submit"] is True
        # 只调用了 validate，没有调用 submit
        assert mock_client.request.call_count == 1

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_submit_dry_run_table(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "can_submit": True,
                "checks": {
                    "capacity": {"passed": True, "detail": "1/10"},
                    "workflow_id": {
                        "passed": True,
                        "detail": "TOWER_WORKFLOW_ID=wf-new",
                    },
                    "run_sh": {"passed": True, "detail": "OK"},
                },
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "submit",
                "--dry-run",
                "-p",
                "WGS",
                "-S",
                "SN-2026-001",
                "/data/sample1",
            ],
        )

        assert result.exit_code == 0
        assert "dry-run" in result.output
        assert "PASS" in result.output


class TestSubmitProjectSn:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_submit_sends_project_sn_in_body(self, mock_client_class):
        """--project-sn 要带到 POST /workflow/submit body 里。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        validate_resp = _mock_response(
            200,
            {
                "can_submit": True,
                "checks": {
                    "workflow_id": {
                        "passed": True,
                        "detail": "TOWER_WORKFLOW_ID=wf-sn-1",
                    },
                },
            },
        )
        submit_resp = _mock_response(
            202, {"workflow_id": "wf-sn-1", "pipeline_name": "WGS"}
        )
        mock_client.request.side_effect = [validate_resp, submit_resp]
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "submit",
                "-p",
                "WGS",
                "--project-sn",
                "SN-2026-001",
                "/data/sample1",
            ],
        )

        assert result.exit_code == 0
        # 第二次调用是 /workflow/submit
        submit_call = mock_client.request.call_args_list[1]
        body = submit_call.kwargs.get("json")
        assert body["project_sn"] == "SN-2026-001"
        assert body["workflow_id"] == "wf-sn-1"

    @pytest.mark.unit
    def test_submit_without_project_sn_errors(self):
        """未传 --project-sn 时 CLI 应直接拒绝（后端已要求必填）。"""
        result = runner.invoke(
            app,
            ["submit", "-p", "WGS", "/data/sample1"],
        )

        assert result.exit_code != 0
        assert (
            "project-sn" in result.output.lower()
            or "project_sn" in result.output.lower()
        )


class TestListProjectSn:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_list_sends_project_sn_filter_param(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200, {"total": 0, "page": 1, "page_size": 20, "items": []}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "list",
                "--project-sn",
                "SN-2026-001",
            ],
        )

        assert result.exit_code == 0
        params = mock_client.request.call_args.kwargs.get("params", {})
        assert params["project_sn"] == "SN-2026-001"


class TestStatusProjectSn:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_displays_project_sn(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "workflow_id": "wf-001",
                "status": "running",
                "progress_percent": 50.0,
                "pipeline_name": "WGS",
                "project_sn": "SN-2026-001",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["status", "wf-001"])

        assert result.exit_code == 0
        assert "project_sn" in result.output
        assert "SN-2026-001" in result.output


class TestNetworkError:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_connection_error_json(self, mock_client_class):
        import httpx

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.side_effect = httpx.ConnectError("refused")
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "overview"])

        assert result.exit_code == 4  # EXIT_NETWORK
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"]["type"] == "NETWORK_ERROR"

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_connection_error_table(self, mock_client_class):
        import httpx

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.side_effect = httpx.ConnectError("refused")
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["overview"])

        assert result.exit_code == 4
        assert "Error" in result.output or "无法连接" in result.output


class TestHttpError:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_404_json(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            404, {"detail": "Workflow not found"}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "status", "wf-xxx"])

        assert result.exit_code == 2  # EXIT_VALIDATION (404 maps to this)
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"]["type"] == "NOT_FOUND"

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_409_json(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            409, {"detail": "流程正在运行中"}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "cancel", "wf-001"])

        assert result.exit_code == 5  # EXIT_CONFLICT
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"]["type"] == "CONFLICT"
        # 服务端未给 hint 时,envelope 不携带本地兜底(避免 cancel/resume 等场景出现误导性建议)
        assert "hint" not in data["error"]


class TestStructuredError:
    """nf-server 新格式:{detail, error_code, hint, resource_id, sge_job_id}"""

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_error_code_drives_exit_code(self, mock_client_class):
        """TEMPORAL_UNAVAILABLE 走 EXIT_NETWORK(4),便于脚本重试"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            503,
            {
                "detail": "Temporal 不可达,无法取消 Main: ...",
                "error_code": "TEMPORAL_UNAVAILABLE",
                "resource_id": "wf-001",
                "hint": "恢复 Temporal 后重试;如需立即释放资源: qdel 12345",
                "sge_job_id": "12345",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "cancel", "wf-001"])

        # error_code 映射到 EXIT_NETWORK(4),而非 503 默认的 EXIT_SERVER(6)
        assert result.exit_code == 4
        data = json.loads(result.output)
        assert data["ok"] is False
        err = data["error"]
        assert err["type"] == "TEMPORAL_UNAVAILABLE"
        assert err["sge_job_id"] == "12345"
        assert err["resource_id"] == "wf-001"
        assert "qdel 12345" in err["hint"]

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_new_format_displays_in_human_mode(self, mock_client_class):
        """人类模式展示 error_code + sge_job_id + hint"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            503,
            {
                "detail": "Temporal 不可达",
                "error_code": "TEMPORAL_UNAVAILABLE",
                "hint": "稍后重试",
                "sge_job_id": "99999",
            },
        )
        mock_client_class.return_value = mock_client

        # cancel 在人类模式会要求确认,input="y" 绕过
        result = runner.invoke(app, ["cancel", "wf-001"], input="y\n")

        assert result.exit_code == 4
        combined = result.stdout + (result.stderr or "")
        assert "TEMPORAL_UNAVAILABLE" in combined
        assert "99999" in combined
        assert "稍后重试" in combined

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_legacy_dict_detail_still_works(self, mock_client_class):
        """旧格式 detail=dict 仍然能解析(历史响应兼容)"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            503,
            {
                "detail": {
                    "message": "Temporal 不可达",
                    "sge_job_id": "77777",
                    "hint": "qdel 77777",
                }
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "cancel", "wf-001"])

        # 旧格式无 error_code,回退到 HTTP 状态码映射 → EXIT_SERVER
        assert result.exit_code == 6
        data = json.loads(result.output)
        err = data["error"]
        assert err["sge_job_id"] == "77777"
        assert "qdel 77777" in err["hint"]


class TestPipeline:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_list_json(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            [
                {
                    "pipeline_name": "WGS",
                    "max_concurrent": 5,
                    "enabled": True,
                    "created_at": "2026-04-10T08:00:00",
                    "updated_at": "2026-04-10T08:00:00",
                },
            ],
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "pipeline", "list"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert len(data["data"]) == 1
        assert data["data"][0]["pipeline_name"] == "WGS"

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_list_table(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            [
                {
                    "pipeline_name": "WGS",
                    "max_concurrent": 5,
                    "enabled": True,
                    "created_at": "2026-04-10T08:00:00",
                    "updated_at": "2026-04-10T08:00:00",
                },
            ],
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["pipeline", "list"])

        assert result.exit_code == 0
        assert "WGS" in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_create_json(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            201,
            {
                "pipeline_name": "WES",
                "max_concurrent": 3,
                "enabled": True,
                "created_at": "2026-04-16T10:00:00",
                "updated_at": "2026-04-16T10:00:00",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            ["--format", "json", "pipeline", "create", "WES", "-m", "3"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["pipeline_name"] == "WES"
        assert data["data"]["max_concurrent"] == 3

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_create_table(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            201,
            {
                "pipeline_name": "WES",
                "max_concurrent": None,
                "enabled": True,
                "created_at": "2026-04-16T10:00:00",
                "updated_at": "2026-04-16T10:00:00",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["pipeline", "create", "WES"])

        assert result.exit_code == 0
        assert "WES" in result.output
        assert "已创建" in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_create_disabled(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            201,
            {
                "pipeline_name": "WES",
                "max_concurrent": None,
                "enabled": False,
                "created_at": "2026-04-16T10:00:00",
                "updated_at": "2026-04-16T10:00:00",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            ["--format", "json", "pipeline", "create", "WES", "--disabled"],
        )

        assert result.exit_code == 0
        # 验证请求体中 enabled=False
        call_args = mock_client.request.call_args
        assert call_args.kwargs["json"]["enabled"] is False

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_update_json(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "pipeline_name": "WGS",
                "max_concurrent": 10,
                "enabled": True,
                "created_at": "2026-04-10T08:00:00",
                "updated_at": "2026-04-16T12:00:00",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            ["--format", "json", "pipeline", "update", "WGS", "-m", "10"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["max_concurrent"] == 10

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_update_disable(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "pipeline_name": "WGS",
                "max_concurrent": 5,
                "enabled": False,
                "created_at": "2026-04-10T08:00:00",
                "updated_at": "2026-04-16T12:00:00",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            ["--format", "json", "pipeline", "update", "WGS", "--disabled"],
        )

        assert result.exit_code == 0
        call_args = mock_client.request.call_args
        assert call_args.kwargs["json"]["enabled"] is False

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_update_table(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "pipeline_name": "WGS",
                "max_concurrent": 10,
                "enabled": True,
                "created_at": "2026-04-10T08:00:00",
                "updated_at": "2026-04-16T12:00:00",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["pipeline", "update", "WGS", "-m", "10"])

        assert result.exit_code == 0
        assert "WGS" in result.output
        assert "已更新" in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_delete_json(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {"pipeline_name": "WGS", "deleted": True},
        )
        mock_client_class.return_value = mock_client

        # --format json 跳过确认
        result = runner.invoke(app, ["--format", "json", "pipeline", "delete", "WGS"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["deleted"] is True

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_delete_table(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {"pipeline_name": "WGS", "deleted": True},
        )
        mock_client_class.return_value = mock_client

        # input "y" 确认删除
        result = runner.invoke(app, ["pipeline", "delete", "WGS"], input="y\n")

        assert result.exit_code == 0
        assert "Deleted" in result.output

    @pytest.mark.unit
    def test_pipeline_delete_abort(self):
        # input "n" 拒绝删除
        result = runner.invoke(app, ["pipeline", "delete", "WGS"], input="n\n")

        assert result.exit_code != 0  # Abort

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_create_conflict(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            409, {"detail": "Pipeline 'WGS' already exists"}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            ["--format", "json", "pipeline", "create", "WGS"],
        )

        assert result.exit_code == 5  # EXIT_CONFLICT
        data = json.loads(result.output)
        assert data["ok"] is False

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_delete_not_found(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            404, {"detail": "Pipeline not found"}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app, ["--format", "json", "pipeline", "delete", "NONEXIST"]
        )

        assert result.exit_code == 2  # EXIT_VALIDATION (NOT_FOUND)
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"]["type"] == "NOT_FOUND"


class TestConfig:
    @pytest.mark.unit
    def test_config_show_json(self):
        result = runner.invoke(app, ["--format", "json", "config", "show"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert "resolved_url" in data["data"]
        assert "profiles" in data["data"]

    @pytest.mark.unit
    def test_config_set_creates_default_profile(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)

        result = runner.invoke(
            app, ["--format", "json", "config", "set", "url", "http://test:9000"]
        )
        assert result.exit_code == 0

        data = json.loads(config_file.read_text())
        assert data["current"] == "default"
        assert data["profiles"]["default"]["url"] == "http://test:9000"

    @pytest.mark.unit
    def test_config_set_named_profile(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)

        result = runner.invoke(
            app,
            ["config", "set", "url", "http://dev:8000", "--profile", "dev"],
        )
        assert result.exit_code == 0
        result = runner.invoke(
            app,
            ["config", "set", "url", "http://prod:8000", "--profile", "prod"],
        )
        assert result.exit_code == 0

        data = json.loads(config_file.read_text())
        assert set(data["profiles"].keys()) == {"dev", "prod"}
        assert data["current"] == "dev"

    @pytest.mark.unit
    def test_config_use_switches_current(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)
        monkeypatch.setattr("nfctl.config._profile_override", None)

        runner.invoke(app, ["config", "set", "url", "http://a", "--profile", "a"])
        runner.invoke(app, ["config", "set", "url", "http://b", "--profile", "b"])

        result = runner.invoke(app, ["--format", "json", "config", "use", "b"])
        assert result.exit_code == 0

        data = json.loads(config_file.read_text())
        assert data["current"] == "b"

    @pytest.mark.unit
    def test_config_use_missing_profile(self, tmp_path, monkeypatch):
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", tmp_path / "config.json")
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)

        result = runner.invoke(app, ["config", "use", "nope"])
        assert result.exit_code == 2

    @pytest.mark.unit
    def test_config_list(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)

        runner.invoke(app, ["config", "set", "url", "http://a", "--profile", "a"])
        runner.invoke(app, ["config", "set", "url", "http://b", "--profile", "b"])

        result = runner.invoke(app, ["--format", "json", "config", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert data["current"] == "a"
        names = {p["name"] for p in data["profiles"]}
        assert names == {"a", "b"}

    @pytest.mark.unit
    def test_config_remove(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)

        runner.invoke(app, ["config", "set", "url", "http://a", "--profile", "a"])
        runner.invoke(app, ["config", "set", "url", "http://b", "--profile", "b"])

        result = runner.invoke(app, ["config", "remove", "a"])
        assert result.exit_code == 0
        data = json.loads(config_file.read_text())
        assert "a" not in data["profiles"]
        assert data["current"] == "b"

    @pytest.mark.unit
    def test_legacy_config_migrated_on_read(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text('{"url": "http://legacy:8000"}')
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)
        monkeypatch.delenv("NFCTL_URL", raising=False)
        monkeypatch.setattr("nfctl.config._profile_override", None)

        from nfctl.config import get_url, list_profiles

        profiles, current = list_profiles()
        assert current == "default"
        assert profiles["default"]["url"] == "http://legacy:8000"
        assert get_url() == "http://legacy:8000"

    @pytest.mark.unit
    def test_global_profile_option_unknown(self, tmp_path, monkeypatch):
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", tmp_path / "config.json")
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)

        result = runner.invoke(app, ["--profile", "nope", "config", "show"])
        assert result.exit_code == 2

    @pytest.mark.unit
    def test_request_without_config(self, tmp_path, monkeypatch):
        """未配置 URL 且无 NFCTL_URL 时，命令应返回 CONFIG_ERROR 信封"""
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", tmp_path / "config.json")
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)
        monkeypatch.delenv("NFCTL_URL", raising=False)

        result = runner.invoke(app, ["--format", "json", "list"])
        assert result.exit_code == 2
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"]["type"] == "CONFIG_ERROR"
        assert "nfctl config set url" in data["error"]["hint"]

    @pytest.mark.unit
    def test_show_without_config(self, tmp_path, monkeypatch):
        """未配置时 config show 不应崩溃"""
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", tmp_path / "config.json")
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)
        monkeypatch.delenv("NFCTL_URL", raising=False)

        result = runner.invoke(app, ["--format", "json", "config", "show"])
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert data["resolved_url"] is None
        assert "resolve_error" in data
