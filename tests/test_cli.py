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

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_list_table_shows_display_status(self, mock_client_class):
        """Status 列展示 server 派生的 display_status,而非原始 main_status。"""
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
                        "status": "succeeded",
                        "display_status": "archive_pending",
                        "needs_action": False,
                        "progress_percent": 100.0,
                        "pipeline_name": "WGS",
                        "env": "prod",
                        "updated_at": "2026-04-13T10:00:00",
                    }
                ],
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        # Status 列改用 display_status(表格列宽可能截断长值,故断言前缀);
        # 同时确认不再展示原始 main_status。
        assert "archive" in result.output
        assert "succeeded" not in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_list_falls_back_to_main_status_for_old_server(self, mock_client_class):
        """旧 server 无 display_status 时回退到 main_status,不留空。"""
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

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "running" in result.output


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

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_shows_derived_fields(self, mock_client_class):
        """详情展示 display_status + summary + archive_eta（等待归档场景）。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "workflow_id": "wf-001",
                "status": "succeeded",
                "display_status": "archive_pending",
                "status_summary": "等待归档（约 9h 后自动开始）",
                "needs_action": False,
                "archive_eta": "2026-06-18T04:43:16+00:00",
                "pp_phase": "archive_wait",
                "pp_status": "running",
                "progress_percent": 100.0,
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["status", "wf-001"])

        assert result.exit_code == 0
        assert "archive_pending" in result.output
        assert "summary" in result.output
        assert "等待归档" in result.output
        assert "archive_eta" in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_marks_needs_action(self, mock_client_class):
        """归档失败需介入时,详情有醒目的 needs_action 标记。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "workflow_id": "wf-001",
                "status": "succeeded",
                "display_status": "archive_failed",
                "status_summary": "分析成功、结果可用；归档失败，可 resume 重试",
                "needs_action": True,
                "pp_phase": "archive",
                "pp_status": "failed",
                "progress_percent": 100.0,
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["status", "wf-001"])

        assert result.exit_code == 0
        assert "archive_failed" in result.output
        assert "needs_action" in result.output
        assert "需介入" in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_multiline_error_is_aligned(self, mock_client_class):
        """多行 error 的续行对齐到 value 列,不顶格。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "workflow_id": "wf-001",
                "status": "failed",
                "progress_percent": 38.0,
                "error_message": "报错步骤：enrich (1)\n报错原因：'g1'",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["status", "wf-001"])

        assert result.exit_code == 0
        assert "报错步骤" in result.output
        assert "报错原因" in result.output
        # 续行已缩进对齐:不存在顶格(紧跟换行)的续行
        assert "\n报错原因" not in result.output


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

        # Typer 缺参退出 2；输出含 "project" 即可（Rich 可能在中间插 ANSI 码）
        assert result.exit_code == 2
        assert "project" in result.output.lower()


class TestDelete:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_delete_succeeded_is_blocked(self, mock_client_class):
        """succeeded 工作流不可删除（CLI 层硬阻止），不应触发 DELETE。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        # 仅返回一次：GET /workflow/{id}
        mock_client.request.return_value = _mock_response(
            200,
            {"workflow_id": "wf-ok", "status": "succeeded"},
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "delete", "wf-ok"])

        assert result.exit_code == 2  # EXIT_VALIDATION
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"]["type"] == "VALIDATION_ERROR"
        assert "成功" in data["error"]["message"]
        assert data["error"]["resource_id"] == "wf-ok"
        # 只调用了 GET，没有 DELETE
        assert mock_client.request.call_count == 1
        assert mock_client.request.call_args.args[0] == "GET"

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_delete_failed_proceeds(self, mock_client_class):
        """failed/cancelled 等其他终态可正常删除。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        get_resp = _mock_response(200, {"workflow_id": "wf-bad", "status": "failed"})
        del_resp = _mock_response(200, {"workflow_id": "wf-bad", "deleted": True})
        mock_client.request.side_effect = [get_resp, del_resp]
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "delete", "wf-bad"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["deleted"] is True
        # 第二次调用是 DELETE
        assert mock_client.request.call_count == 2
        assert mock_client.request.call_args_list[1].args == (
            "DELETE",
            "/workflow/wf-bad",
        )

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_delete_get_404_passes_through(self, mock_client_class):
        """GET 拿不到的工作流（404）应直接返回错误，不进行 DELETE。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            404, {"detail": "workflow not found", "error_code": "NOT_FOUND"}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "delete", "wf-missing"])

        assert result.exit_code == 2
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"]["type"] == "NOT_FOUND"
        assert mock_client.request.call_count == 1


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
    """nf-server 新格式:{detail, error_code, hint, resource_id, job_id}"""

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
                "job_id": "12345",
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
        assert err["job_id"] == "12345"
        assert err["resource_id"] == "wf-001"
        assert "qdel 12345" in err["hint"]

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_new_format_displays_in_human_mode(self, mock_client_class):
        """人类模式展示 error_code + job_id + hint"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            503,
            {
                "detail": "Temporal 不可达",
                "error_code": "TEMPORAL_UNAVAILABLE",
                "hint": "稍后重试",
                "job_id": "99999",
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
        """旧格式 detail=dict + 旧字段 sge_job_id 仍能解析并归一化为 job_id(历史响应兼容)"""
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
        assert err["job_id"] == "77777"
        assert "qdel 77777" in err["hint"]


class TestCancel:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_cancel_default_scope_workflow(self, mock_client_class):
        """默认 scope=workflow,整体撤销(可作用于已成功的流程)。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200, {"workflow_id": "wf-001"}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "cancel", "wf-001"])

        assert result.exit_code == 0
        body = mock_client.request.call_args.kwargs["json"]
        assert body["scope"] == "workflow"

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_cancel_archive_scope(self, mock_client_class):
        """--scope archive 只取消归档,保留分析结果。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200, {"workflow_id": "wf-001"}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app, ["--format", "json", "cancel", "wf-001", "--scope", "archive"]
        )

        assert result.exit_code == 0
        body = mock_client.request.call_args.kwargs["json"]
        assert body["scope"] == "archive"

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_cancel_invalid_scope_rejected(self, mock_client_class):
        """非法 scope 在 CLI 层拦截,不发请求。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app, ["--format", "json", "cancel", "wf-001", "--scope", "bogus"]
        )

        assert result.exit_code == 2
        mock_client.request.assert_not_called()


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
    def test_pipeline_get_table(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            [
                {
                    "pipeline_name": "ngm",
                    "max_concurrent": 20,
                    "enabled": True,
                    "feishu_webhook": None,
                    "archive_enabled": True,
                    "large_file_threshold": None,
                    "archive_dirs": "work",
                    "archive_delay_hours": 72,
                    "created_at": "2026-06-24T02:09:39",
                    "updated_at": "2026-06-24T03:00:00",
                },
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

        result = runner.invoke(app, ["pipeline", "get", "ngm"])

        assert result.exit_code == 0
        # 从 list 筛出 ngm,详情含归档目录与 updated_at;不渲染其它 pipeline
        assert "ngm" in result.output
        assert "work" in result.output
        assert "archive_dirs" in result.output
        assert "updated_at" in result.output
        assert "WGS" not in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_get_json_single(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            [
                {
                    "pipeline_name": "ngm",
                    "enabled": True,
                    "created_at": "2026-06-24T02:09:39",
                    "updated_at": "2026-06-24T03:00:00",
                },
                {
                    "pipeline_name": "WGS",
                    "enabled": True,
                    "created_at": "2026-04-10T08:00:00",
                    "updated_at": "2026-04-10T08:00:00",
                },
            ],
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "pipeline", "get", "ngm"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        # 输出的是筛出的单个对象,不是整个 list
        assert isinstance(data["data"], dict)
        assert data["data"]["pipeline_name"] == "ngm"

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_get_not_found(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            [
                {
                    "pipeline_name": "WGS",
                    "enabled": True,
                    "created_at": "2026-04-10T08:00:00",
                    "updated_at": "2026-04-10T08:00:00",
                },
            ],
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "pipeline", "get", "NOPE"])

        assert result.exit_code != 0
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"]["type"] == "NOT_FOUND"

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
    def test_pipeline_create_with_archive_policy(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            201,
            {
                "pipeline_name": "WES",
                "max_concurrent": None,
                "enabled": True,
                "archive_enabled": True,
                "large_file_threshold": "500M",
                "archive_dirs": "work,results",
                "archive_delay_hours": 48,
                "created_at": "2026-04-16T10:00:00",
                "updated_at": "2026-04-16T10:00:00",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "pipeline",
                "create",
                "WES",
                "--archive",
                "--large-file-threshold",
                "500M",
                "--archive-dirs",
                "work,results",
                "--archive-delay-hours",
                "48",
            ],
        )

        assert result.exit_code == 0
        body = mock_client.request.call_args.kwargs["json"]
        assert body["archive_enabled"] is True
        assert body["large_file_threshold"] == "500M"
        assert body["archive_dirs"] == "work,results"
        assert body["archive_delay_hours"] == 48

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_create_defaults_archive_off(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            201,
            {
                "pipeline_name": "WES",
                "enabled": True,
                "archive_enabled": False,
                "created_at": "2026-04-16T10:00:00",
                "updated_at": "2026-04-16T10:00:00",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "pipeline", "create", "WES"])

        assert result.exit_code == 0
        body = mock_client.request.call_args.kwargs["json"]
        # 未指定时默认不归档、不迁移
        assert body["archive_enabled"] is False
        assert "large_file_threshold" not in body

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_pipeline_update_disable_migrate(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "pipeline_name": "WGS",
                "enabled": True,
                "archive_enabled": True,
                "large_file_threshold": "",
                "created_at": "2026-04-10T08:00:00",
                "updated_at": "2026-04-16T12:00:00",
            },
        )
        mock_client_class.return_value = mock_client

        # 传空串 = 关闭迁移（服务端 bool("") → migrate off）
        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "pipeline",
                "update",
                "WGS",
                "--large-file-threshold",
                "",
            ],
        )

        assert result.exit_code == 0
        body = mock_client.request.call_args.kwargs["json"]
        assert body["large_file_threshold"] == ""

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
