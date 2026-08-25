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


def _mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
    headers: dict | None = None,
):
    """构造 mock httpx.Response。headers 必须是真 dict:MagicMock 的
    headers.get() 返回 truthy 的 MagicMock,会误触发版本提醒。"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = json.dumps(json_data or {})
    resp.headers = headers or {}
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

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    @pytest.mark.parametrize(
        "alive,fragment",
        [(True, "alive"), (False, "未在推进")],
    )
    def test_overview_shows_reconciler_liveness(
        self, mock_client_class, alive, fragment
    ):
        """overview 附带 /health 的 reconciler 存活行(陈旧=一切推进停止,须醒目)。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.side_effect = [
            _mock_response(
                200,
                {
                    "running": 1,
                    "succeeded": 5,
                    "failed": 0,
                    "cancelled": 0,
                    "total": 6,
                    "by_pipeline": [],
                    "queue_waiting": 0,
                },
            ),
            _mock_response(
                200,
                {
                    "status": "healthy" if alive else "degraded",
                    "database": {"connected": True},
                    "queue": {},
                    "reconciler": {
                        "alive": alive,
                        "last_tick_at": "2026-07-04T10:00:00+00:00",
                    },
                },
            ),
        ]
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["overview"])

        assert result.exit_code == 0
        assert "reconciler" in result.output
        assert fragment in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_overview_json_includes_reconciler(self, mock_client_class):
        """JSON 模式同样合并 reconciler 信号(Agent 是 -f json 的主要用户)。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.side_effect = [
            _mock_response(
                200,
                {
                    "running": 1,
                    "succeeded": 5,
                    "failed": 0,
                    "cancelled": 0,
                    "total": 6,
                    "by_pipeline": [],
                    "queue_waiting": 0,
                },
            ),
            _mock_response(
                200,
                {
                    "status": "degraded",
                    "database": {"connected": True},
                    "queue": {},
                    "reconciler": {
                        "alive": False,
                        "last_tick_at": "2026-07-04T10:00:00+00:00",
                    },
                },
            ),
        ]
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "overview"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["reconciler"]["alive"] is False


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
    def test_list_table_shows_analysis_only(self, mock_client_class):
        """Workflow 列表只展示分析轴，存储状态属于 launch_dir 资源。"""
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
                        "analysis_status": "succeeded",
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

        # 放宽终端宽度,避免 Rich 表格截断待断言的列值
        result = runner.invoke(app, ["list"], env={"COLUMNS": "200"})

        assert result.exit_code == 0
        assert "succeeded" in result.output
        assert "Archive" not in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_list_filter_sends_analysis_status(self, mock_client_class):
        """-s 只过滤 Workflow 分析状态。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200, {"total": 0, "page": 1, "page_size": 20, "items": []}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["list", "-s", "queued,running"])

        assert result.exit_code == 0
        sent_params = mock_client.request.call_args.kwargs["params"]
        assert sent_params["analysis_status"] == "queued,running"
        assert "pp_status" not in sent_params
        assert "status" not in sent_params
        assert "display_status" not in sent_params

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_list_exact_launch_dir_normalizes_path_and_fetches_complete_history(
        self, mock_client_class, tmp_path
    ):
        """-L 精确过滤并自动取全，输出当前目录占用者。"""
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
                        "workflow_id": "wf-running",
                        "analysis_status": "running",
                        "launch_dir_occupied": True,
                        "progress_percent": 1.0,
                        "pipeline_name": "rna-seq",
                        "env": "prod",
                        "project_sn": "BQ-TEST",
                        "updated_at": "2026-08-18T05:00:00+00:00",
                    }
                ],
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            ["list", "-L", str(tmp_path / "child" / "..")],
            env={"COLUMNS": "220"},
        )

        assert result.exit_code == 0
        params = mock_client.request.call_args.kwargs["params"]
        assert params["launch_dir"] == str(tmp_path.resolve())
        assert params["page"] == 1
        assert "wf-running" in result.output
        assert "当前占用" in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_list_grouped_by_launch_dir(self, mock_client_class):
        """目录分页、组内完整 workflow 历史由 launch-dirs 资源返回。"""
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
                        "launch_dir": "/work/prod/BQ-TEST/run1",
                        "workflow_count": 2,
                        "storage_state": "materialized",
                        "plan_workflow_id": "wf-old",
                        "archive_path": "/archive/run1",
                        "updated_at": "2026-08-18T05:00:00+00:00",
                        "occupied_workflow_id": "wf-running",
                        "workflows": [
                            {
                                "workflow_id": "wf-running",
                                "analysis_status": "running",
                                "progress_percent": 1.0,
                                "pipeline_name": "rna-seq",
                                "env": "prod",
                                "project_sn": "BQ-TEST",
                                "updated_at": "2026-08-18T05:00:00+00:00",
                            },
                            {
                                "workflow_id": "wf-old",
                                "analysis_status": "succeeded",
                                "progress_percent": 100.0,
                                "pipeline_name": "rna-seq",
                                "env": "prod",
                                "project_sn": "BQ-TEST",
                                "updated_at": "2026-08-07T12:00:00+00:00",
                            },
                        ],
                    }
                ],
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            ["list", "--group-by", "launch-dir"],
            env={"COLUMNS": "220"},
        )

        assert result.exit_code == 0
        assert "/work/prod/BQ-TEST/run1" in result.output
        assert "wf-running" in result.output
        assert "wf-old" in result.output
        assert "State materialized" in result.output
        assert "存储计划 wf-old" in result.output
        call_args = mock_client.request.call_args
        assert call_args.args == ("GET", "/launch-dirs")
        assert call_args.kwargs["params"]["sort_by"] == "updated_at"

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_list_all_launch_dirs_fetches_every_group_page(self, mock_client_class):
        """--all 的翻页单位是 launch_dir，JSON 合并后仍保留完整组。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.side_effect = [
            _mock_response(
                200,
                {
                    "total": 2,
                    "page": 1,
                    "page_size": 1,
                    "items": [{"launch_dir": "/work/run1", "workflows": []}],
                },
            ),
            _mock_response(
                200,
                {
                    "total": 2,
                    "page": 2,
                    "page_size": 1,
                    "items": [{"launch_dir": "/work/run2", "workflows": []}],
                },
            ),
        ]
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "list",
                "--group-by",
                "launch-dir",
                "--all",
                "-n",
                "1",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert [item["launch_dir"] for item in data["items"]] == [
            "/work/run1",
            "/work/run2",
        ]
        assert [
            call.kwargs["params"]["page"] for call in mock_client.request.call_args_list
        ] == [1, 2]

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_list_launch_dir_storage_filters(self, mock_client_class):
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
                "list",
                "--group-by",
                "launch-dir",
                "--state",
                "materialized",
                "--archive-due",
            ],
        )

        assert result.exit_code == 0
        params = mock_client.request.call_args.kwargs["params"]
        assert params["storage_state"] == "materialized"
        assert params["archive_due"] is True

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_list_rejects_unknown_group(self, mock_client_class):
        result = runner.invoke(app, ["list", "--group-by", "pipeline"])

        assert result.exit_code == 2
        assert "launch-dir" in result.output
        mock_client_class.assert_not_called()

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_list_pp_filter_is_removed(self, mock_client_class):
        result = runner.invoke(app, ["list", "--pp", "failed"])

        assert result.exit_code == 2
        assert "No such option" in result.output
        mock_client_class.assert_not_called()


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
                "analysis_status": "failed",
                "progress_percent": 80.0,
                "pipeline_name": "WGS",
                "env": "prod",
                "launch_dir": "/data/wf-001",
                "run_name": "run1",
                "job_id": "12345",
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
    def test_status_shows_analysis_derived_fields(self, mock_client_class):
        """Workflow 详情展示分析状态与摘要，不混入目录存储字段。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "workflow_id": "wf-001",
                "analysis_status": "succeeded",
                "status_summary": "分析完成，结果可用",
                "needs_action": False,
                "progress_percent": 100.0,
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["status", "wf-001"])

        assert result.exit_code == 0
        assert "succeeded" in result.output
        assert "summary" in result.output
        assert "分析完成" in result.output
        assert "archive_due_at" not in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_needs_action_no_separate_row(self, mock_client_class):
        """需介入不单列 needs_action，summary 承载分析动作提示。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "workflow_id": "wf-001",
                "analysis_status": "failed",
                "status_summary": "分析失败，需排查后 resume",
                "needs_action": True,
                "progress_percent": 100.0,
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["status", "wf-001"], env={"COLUMNS": "200"})

        assert result.exit_code == 0
        assert "needs_action" not in result.output
        assert "需介入" not in result.output
        assert "需排查后 resume" in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_cancelled_hides_error_row(self, mock_client_class):
        """cancelled 场景不单列 error 行:server 已把取消原因并入 summary
        (接管/用户取消不是错误,error 标签误导且与 summary 重复)。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "workflow_id": "wf-001",
                "analysis_status": "cancelled",
                "status_summary": "已取消（被新流程 abc123 接管）",
                "needs_action": False,
                "progress_percent": 100.0,
                "error_message": "被新流程 abc123 接管",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["status", "wf-001"], env={"COLUMNS": "200"})

        assert result.exit_code == 0
        # 原因经 summary 可见,error 行不再出现
        assert "被新流程 abc123 接管" in result.output
        assert "error" not in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_failed_keeps_error_row(self, mock_client_class):
        """failed 场景 error_message 是真实报错,保持单列展示。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "workflow_id": "wf-001",
                "analysis_status": "failed",
                "status_summary": "分析失败，需排查后 resume",
                "progress_percent": 80.0,
                "error_message": "Process FASTQC failed",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["status", "wf-001"], env={"COLUMNS": "200"})

        assert result.exit_code == 0
        assert "error" in result.output
        assert "Process FASTQC failed" in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_succeeded_hides_stale_error_row(self, mock_client_class):
        """succeeded 场景不露 error 行:干净成功应无错,残留 error_message
        (server 侧修复前的存量)由 needs_action=false 门控挡下,不自相矛盾。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "workflow_id": "wf-001",
                "analysis_status": "succeeded",
                "status_summary": "分析完成，结果可用",
                "progress_percent": 100.0,
                "error_message": "旧 attempt 的残留错误",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["status", "wf-001"], env={"COLUMNS": "200"})

        assert result.exit_code == 0
        assert "分析完成" in result.output
        assert "残留错误" not in result.output
        assert "error" not in result.output

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
                "analysis_status": "failed",
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
                "workflow_id": "wf-new",
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
                "workflow_id": "wf-new",
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
    def test_submit_normalizes_relative_launch_dir(
        self, mock_client_class, monkeypatch, tmp_path
    ):
        """相对路径必须按 nfctl 调用者 cwd 解析，不能留给远端 server 解析。"""
        monkeypatch.chdir(tmp_path)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.side_effect = [
            _mock_response(
                200,
                {
                    "can_submit": True,
                    "workflow_id": "wf-relative",
                    "checks": {
                        "workflow_id": {
                            "passed": True,
                            "detail": "TOWER_WORKFLOW_ID=wf-relative",
                        }
                    },
                },
            ),
            _mock_response(
                202,
                {"workflow_id": "wf-relative", "pipeline_name": "WGS"},
            ),
        ]
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "submit",
                ".",
                "-p",
                "WGS",
                "-S",
                "SN-2026-001",
            ],
        )

        assert result.exit_code == 0
        expected = str(tmp_path.resolve())
        validate_body = mock_client.request.call_args_list[0].kwargs["json"]
        submit_body = mock_client.request.call_args_list[1].kwargs["json"]
        assert validate_body["launch_dir"] == expected
        assert submit_body["launch_dir"] == expected

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
                "workflow_id": "wf-sn-1",
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
    def test_delete_succeeded_rejected_by_server(self, mock_client_class):
        """succeeded 不可删的合规守卫已下沉 server:CLI 直发 DELETE,透传 400。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            400,
            {
                "detail": "已成功完成的分析不可删除（成功结果视为合规资产）",
                "error_code": "VALIDATION_ERROR",
                "resource_id": "wf-ok",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "delete", "wf-ok"])

        assert result.exit_code == 2  # EXIT_VALIDATION
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"]["type"] == "VALIDATION_ERROR"
        assert "不可删除" in data["error"]["message"]
        # 不再有 CLI 预查 GET,唯一请求就是 DELETE
        assert mock_client.request.call_count == 1
        assert mock_client.request.call_args.args[0] == "DELETE"

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_delete_failed_proceeds(self, mock_client_class):
        """failed/cancelled 等其他终态可正常删除(单次 DELETE,无预查)。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200, {"workflow_id": "wf-bad", "deleted": True}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "delete", "wf-bad"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["deleted"] is True
        assert mock_client.request.call_count == 1
        assert mock_client.request.call_args.args == (
            "DELETE",
            "/workflow/wf-bad",
        )

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_delete_404_passes_through(self, mock_client_class):
        """不存在的分析:DELETE 404 直接透传为错误。"""
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
    """nf-server 错误格式:{detail, error_code, hint, resource_id, job_id}"""

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_error_code_takes_precedence_over_status_map(self, mock_client_class):
        """error_code 优先于 HTTP 状态码映射决定退出码,结构化字段完整透传。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            409,  # 状态码默认映射 EXIT_CONFLICT(5)
            {
                "detail": "取消目标状态已变化",
                "error_code": "VALIDATION_ERROR",  # code 映射 EXIT_VALIDATION(2),应胜出
                "resource_id": "wf-001",
                "hint": "先查 status 再重试",
                "job_id": "12345",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "cancel", "wf-001"])

        assert result.exit_code == 2
        data = json.loads(result.output)
        assert data["ok"] is False
        err = data["error"]
        assert err["type"] == "VALIDATION_ERROR"
        assert err["job_id"] == "12345"
        assert err["resource_id"] == "wf-001"
        assert "重试" in err["hint"]

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_error_context_is_preserved_for_agents(self, mock_client_class, tmp_path):
        """RESTORE_CONFLICT 等结构化上下文不能在 CLI 信封转换时丢失。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            409,
            {
                "detail": "launch_dir 已有非隐藏数据目录",
                "error_code": "RESTORE_CONFLICT",
                "resource_id": str(tmp_path),
                "conflicts": ["work", "Variation"],
                "operation_id": "op-restore",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            ["--format", "json", "archive", "restore", str(tmp_path)],
        )

        assert result.exit_code == 5
        error = json.loads(result.output)["error"]
        assert error["type"] == "RESTORE_CONFLICT"
        assert error["conflicts"] == ["work", "Variation"]
        assert error["operation_id"] == "op-restore"

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_structured_error_displays_in_human_mode(self, mock_client_class):
        """人类模式展示 error_code + job_id + hint"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            409,
            {
                "detail": "launch_dir 被活跃流程占用",
                "error_code": "LAUNCH_DIR_BUSY",
                "hint": "先取消占用流程",
                "job_id": "99999",
            },
        )
        mock_client_class.return_value = mock_client

        # cancel 在人类模式会要求确认,input="y" 绕过
        result = runner.invoke(app, ["cancel", "wf-001"], input="y\n")

        # 未在 code 映射表的 error_code 回退 HTTP 状态码映射(409→EXIT_CONFLICT)
        assert result.exit_code == 5
        combined = result.stdout + (result.stderr or "")
        assert "LAUNCH_DIR_BUSY" in combined
        assert "99999" in combined
        assert "先取消占用流程" in combined

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_missing_detail_falls_back_to_http_status(self, mock_client_class):
        """detail 缺失/非字符串时消息回退 'HTTP {status}',不崩溃。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(503, {"error_code": None})
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "cancel", "wf-001"])

        assert result.exit_code == 6  # EXIT_SERVER
        data = json.loads(result.output)
        assert data["error"]["message"] == "HTTP 503"

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_422_keeps_sanitized_validation_details(self, mock_client_class):
        """FastAPI 校验列表应可读、可解析，且不能回显可能敏感的 input。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            422,
            {
                "detail": [
                    {
                        "type": "string_too_long",
                        "loc": ["body", "project_sn"],
                        "msg": "String should have at most 200 characters",
                        "input": "sensitive-value",
                    }
                ],
                "error_code": "VALIDATION_ERROR",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "submit",
                "/work/run1",
                "-p",
                "WGS",
                "-S",
                "too-long",
            ],
        )

        assert result.exit_code == 2
        error = json.loads(result.output)["error"]
        assert "body.project_sn" in error["message"]
        assert error["validation_errors"] == [
            {
                "loc": ["body", "project_sn"],
                "msg": "String should have at most 200 characters",
                "type": "string_too_long",
            }
        ]
        assert "sensitive-value" not in result.output


class TestCancel:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_cancel_body_has_no_storage_scope(self, mock_client_class):
        """Workflow cancel 只表达分析取消，不再复用 scope 路由存储操作。"""
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
        assert "scope" not in body

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_cancel_scope_option_removed(self, mock_client_class):
        """--scope 已从 cancel 硬切掉(归档取消收拢进 nfctl archive cancel)。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app, ["--format", "json", "cancel", "wf-001", "--scope", "archive"]
        )

        assert result.exit_code == 2
        mock_client.request.assert_not_called()


class TestLaunchDirArchive:
    @pytest.mark.unit
    def test_archive_now_command_is_removed(self):
        result = runner.invoke(app, ["archive", "now", "/work/run1"])

        assert result.exit_code == 2
        assert "No such command" in result.output

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("command", "endpoint"),
        [
            ("start", "/launch-dirs/archive"),
            ("resume", "/launch-dirs/resume"),
            ("restore", "/launch-dirs/restore"),
        ],
    )
    @patch("nfctl.client.httpx.Client")
    def test_command_targets_launch_dir_resource(
        self, mock_client_class, command, endpoint, tmp_path
    ):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "launch_dir": str(tmp_path),
                "operation_id": "op-1",
                "operation_kind": "archive" if command == "start" else command,
                "operation_status": "pending",
                "job_id": None,
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            ["--format", "json", "archive", command, str(tmp_path)],
        )

        assert result.exit_code == 0
        assert mock_client.request.call_args.args[1] == endpoint
        assert mock_client.request.call_args.kwargs["json"] == {
            "launch_dir": str(tmp_path.resolve())
        }

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_cancel_targets_launch_dir_operation(self, mock_client_class, tmp_path):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200,
            {
                "launch_dir": str(tmp_path),
                "operation_id": "op-1",
                "operation_kind": "archive",
                "operation_status": "cancelled",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "archive",
                "cancel",
                str(tmp_path),
                "--reason",
                "maintenance",
            ],
        )

        assert result.exit_code == 0
        assert mock_client.request.call_args.args[1] == "/launch-dirs/cancel"
        assert mock_client.request.call_args.kwargs["json"] == {
            "launch_dir": str(tmp_path.resolve()),
            "reason": "maintenance",
        }

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_returns_launch_dir_state_json(self, mock_client_class, tmp_path):
        state = {
            "launch_dir": str(tmp_path),
            "storage_state": "archived",
            "archive_path": "/archive/run-1",
            "auto_archive_enabled": True,
            "operation": {
                "operation_id": "op-1",
                "kind": "archive",
                "status": "succeeded",
                "job_id": "7001",
            },
        }
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200, {"total": 1, "page": 1, "page_size": 1, "items": [state]}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            ["--format", "json", "archive", "status", str(tmp_path)],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["data"] == state
        assert mock_client.request.call_args.args[1] == "/launch-dirs"
        assert mock_client.request.call_args.kwargs["params"]["launch_dir"] == str(
            tmp_path.resolve()
        )

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_unregistered_launch_dir_is_validation_error(
        self, mock_client_class, tmp_path
    ):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200, {"total": 0, "page": 1, "page_size": 1, "items": []}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            ["--format", "json", "archive", "status", str(tmp_path)],
        )

        assert result.exit_code == 2
        assert json.loads(result.output)["error"]["type"] == "LAUNCH_DIR_NOT_FOUND"

    @pytest.mark.unit
    @patch("nfctl.commands.archive.time.sleep")
    @patch("nfctl.client.httpx.Client")
    def test_restore_waits_on_operation_id(
        self, mock_client_class, _mock_sleep, tmp_path
    ):
        def group(status):
            return {
                "total": 1,
                "page": 1,
                "page_size": 1,
                "items": [
                    {
                        "launch_dir": str(tmp_path),
                        "storage_state": "materialized",
                        "operation": {
                            "operation_id": "op-restore",
                            "kind": "restore",
                            "status": status,
                            "job_id": "7001",
                        },
                    }
                ],
            }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.side_effect = [
            _mock_response(
                200,
                {
                    "launch_dir": str(tmp_path),
                    "operation_id": "op-restore",
                    "operation_kind": "restore",
                    "operation_status": "pending",
                },
            ),
            _mock_response(200, group("running")),
            _mock_response(200, group("succeeded")),
        ]
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "archive",
                "restore",
                str(tmp_path),
                "--wait",
            ],
        )

        assert result.exit_code == 0
        assert json.loads(result.output)["data"]["operation"]["status"] == "succeeded"

    @pytest.mark.unit
    @patch("nfctl.commands.archive.time.sleep")
    @patch("nfctl.client.httpx.Client")
    def test_restore_wait_failure_returns_error_envelope(
        self, mock_client_class, _mock_sleep, tmp_path
    ):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.side_effect = [
            _mock_response(
                200,
                {
                    "launch_dir": str(tmp_path),
                    "operation_id": "op-restore",
                    "operation_kind": "restore",
                    "operation_status": "pending",
                },
            ),
            _mock_response(
                200,
                {
                    "total": 1,
                    "page": 1,
                    "page_size": 1,
                    "items": [
                        {
                            "launch_dir": str(tmp_path),
                            "storage_state": "partial",
                            "last_error": "restore exit code 2",
                            "operation": {
                                "operation_id": "op-restore",
                                "kind": "restore",
                                "status": "failed",
                            },
                            "workflows": [],
                        }
                    ],
                },
            ),
        ]
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "archive",
                "restore",
                str(tmp_path),
                "--wait",
            ],
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["ok"] is False
        assert payload["error"]["type"] == "STORAGE_OPERATION_FAILED"
        assert payload["error"]["operation_id"] == "op-restore"
        assert payload["error"]["storage_state"] == "partial"

    @pytest.mark.unit
    @patch("nfctl.commands.archive.time.sleep")
    @patch("nfctl.client.httpx.Client")
    def test_restore_wait_detects_replaced_operation(
        self, mock_client_class, _mock_sleep, tmp_path
    ):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.side_effect = [
            _mock_response(
                200,
                {
                    "launch_dir": str(tmp_path),
                    "operation_id": "op-restore",
                    "operation_kind": "restore",
                    "operation_status": "pending",
                },
            ),
            _mock_response(
                200,
                {
                    "total": 1,
                    "page": 1,
                    "page_size": 1,
                    "items": [
                        {
                            "launch_dir": str(tmp_path),
                            "storage_state": "materialized",
                            "operation": {
                                "operation_id": "op-archive",
                                "kind": "archive",
                                "status": "pending",
                            },
                            "workflows": [],
                        }
                    ],
                },
            ),
        ]
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "archive",
                "restore",
                str(tmp_path),
                "--wait",
            ],
        )

        assert result.exit_code == 1
        error = json.loads(result.output)["error"]
        assert error["type"] == "STORAGE_OPERATION_REPLACED"
        assert error["expected_operation_id"] == "op-restore"
        assert error["current_operation_id"] == "op-archive"


class TestPipeline:
    @pytest.mark.unit
    def test_archive_dirs_option_removed(self):
        result = runner.invoke(
            app, ["pipeline", "create", "WES", "--archive-dirs", "work"]
        )

        assert result.exit_code == 2
        assert "No such option" in result.output

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
        # 从 list 筛出 ngm,详情含归档策略与 updated_at;不渲染其它 pipeline
        assert "ngm" in result.output
        assert "archive_enabled" in result.output
        assert "archive_dirs" not in result.output
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

        # 与 client 层 404/NOT_FOUND 同退出码(EXIT_VALIDATION)
        assert result.exit_code == 2
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
                "--archive-delay-hours",
                "48",
            ],
        )

        assert result.exit_code == 0
        body = mock_client.request.call_args.kwargs["json"]
        assert body["archive_enabled"] is True
        assert body["large_file_threshold"] == "500M"
        assert "archive_dirs" not in body
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
    def test_system_config_is_zero_config_fallback(self, tmp_path, monkeypatch):
        system_file = tmp_path / "system-config.json"
        user_file = tmp_path / "user" / "config.json"
        system_file.write_text(
            json.dumps(
                {
                    "current": "prod",
                    "profiles": {
                        "prod": {"url": "https://nf-server.internal"},
                        "test": {"url": "https://nf-server-test.internal"},
                    },
                }
            )
        )
        monkeypatch.setattr("nfctl.config.SYSTEM_CONFIG_FILE", system_file)
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", user_file)
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", user_file.parent)
        monkeypatch.delenv("NFCTL_URL", raising=False)

        from nfctl.config import get_url

        assert get_url() == "https://nf-server.internal"
        assert get_url("test") == "https://nf-server-test.internal"

        result = runner.invoke(app, ["--format", "json", "config", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert data["current"] == "prod"
        assert {item["source"] for item in data["profiles"]} == {"system"}

    @pytest.mark.unit
    def test_user_profile_overrides_system_without_copying_it(
        self, tmp_path, monkeypatch
    ):
        system_file = tmp_path / "system-config.json"
        user_file = tmp_path / "user" / "config.json"
        system_file.write_text(
            json.dumps(
                {
                    "current": "prod",
                    "profiles": {
                        "prod": {"url": "https://system-prod"},
                        "test": {"url": "https://system-test"},
                    },
                }
            )
        )
        monkeypatch.setattr("nfctl.config.SYSTEM_CONFIG_FILE", system_file)
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", user_file)
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", user_file.parent)

        result = runner.invoke(app, ["config", "set", "url", "https://user-prod"])
        assert result.exit_code == 0

        written = json.loads(user_file.read_text())
        assert written == {
            "current": "prod",
            "profiles": {"prod": {"url": "https://user-prod"}},
        }

        from nfctl.config import get_config_sources, list_profiles

        profiles, current = list_profiles()
        sources, current_source = get_config_sources()
        assert current == "prod"
        assert profiles["prod"]["url"] == "https://user-prod"
        assert profiles["test"]["url"] == "https://system-test"
        assert sources == {"prod": "user", "test": "system"}
        assert current_source == "user"

    @pytest.mark.unit
    def test_config_use_can_select_system_profile(self, tmp_path, monkeypatch):
        system_file = tmp_path / "system-config.json"
        user_file = tmp_path / "user" / "config.json"
        system_file.write_text(
            json.dumps(
                {
                    "current": "prod",
                    "profiles": {
                        "prod": {"url": "https://system-prod"},
                        "test": {"url": "https://system-test"},
                    },
                }
            )
        )
        monkeypatch.setattr("nfctl.config.SYSTEM_CONFIG_FILE", system_file)
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", user_file)
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", user_file.parent)
        monkeypatch.delenv("NFCTL_URL", raising=False)

        result = runner.invoke(app, ["--format", "json", "config", "use", "test"])
        assert result.exit_code == 0
        assert json.loads(user_file.read_text()) == {
            "current": "test",
            "profiles": {},
        }

        from nfctl.config import get_url

        assert get_url() == "https://system-test"

    @pytest.mark.unit
    def test_config_remove_rejects_system_profile(self, tmp_path, monkeypatch):
        system_file = tmp_path / "system-config.json"
        user_file = tmp_path / "user" / "config.json"
        system_file.write_text(
            '{"current":"prod","profiles":{"prod":{"url":"https://system"}}}'
        )
        monkeypatch.setattr("nfctl.config.SYSTEM_CONFIG_FILE", system_file)
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", user_file)
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", user_file.parent)

        result = runner.invoke(app, ["--format", "json", "config", "remove", "prod"])
        assert result.exit_code == 2
        error = json.loads(result.output)["error"]
        assert error["type"] == "CONFIG_ERROR"
        assert "系统配置" in error["message"]
        assert not user_file.exists()

    @pytest.mark.unit
    def test_config_remove_user_override_reveals_system_profile(
        self, tmp_path, monkeypatch
    ):
        system_file = tmp_path / "system-config.json"
        user_file = tmp_path / "user" / "config.json"
        system_file.write_text(
            '{"current":"prod","profiles":{"prod":{"url":"https://system"}}}'
        )
        user_file.parent.mkdir()
        user_file.write_text(
            '{"current":"prod","profiles":{"prod":{"url":"https://user"}}}'
        )
        monkeypatch.setattr("nfctl.config.SYSTEM_CONFIG_FILE", system_file)
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", user_file)
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", user_file.parent)
        monkeypatch.delenv("NFCTL_URL", raising=False)

        result = runner.invoke(app, ["--format", "json", "config", "remove", "prod"])
        assert result.exit_code == 0
        assert json.loads(user_file.read_text()) == {
            "current": "prod",
            "profiles": {},
        }

        from nfctl.config import get_url

        assert get_url() == "https://system"

    @pytest.mark.unit
    def test_invalid_system_config_reports_its_path(self, tmp_path, monkeypatch):
        system_file = tmp_path / "system-config.json"
        user_file = tmp_path / "user" / "config.json"
        system_file.write_text("not-json")
        monkeypatch.setattr("nfctl.config.SYSTEM_CONFIG_FILE", system_file)
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", user_file)
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", user_file.parent)

        result = runner.invoke(app, ["--format", "json", "config", "list"])
        assert result.exit_code == 2
        error = json.loads(result.output)["error"]
        assert error["type"] == "CONFIG_ERROR"
        assert str(system_file) in error["message"]

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
    def test_config_use_missing_profile_json(self, tmp_path, monkeypatch):
        """JSON 模式下错误必须走 ok:false 信封 + 退出码 2,不能包成 ok:true"""
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", tmp_path / "config.json")
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)

        result = runner.invoke(app, ["--format", "json", "config", "use", "nope"])
        assert result.exit_code == 2
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"]["type"] == "CONFIG_ERROR"
        assert "config list" in data["error"]["hint"]

    @pytest.mark.unit
    def test_config_remove_missing_profile_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", tmp_path / "config.json")
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)

        result = runner.invoke(app, ["--format", "json", "config", "remove", "nope"])
        assert result.exit_code == 2
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"]["type"] == "CONFIG_ERROR"

    @pytest.mark.unit
    def test_config_set_unknown_key_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", tmp_path / "config.json")
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)

        result = runner.invoke(app, ["--format", "json", "config", "set", "foo", "bar"])
        assert result.exit_code == 2
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"]["type"] == "VALIDATION_ERROR"

    @pytest.mark.unit
    def test_config_set_url_requires_scheme(self, tmp_path, monkeypatch):
        """无 scheme 的 URL 在 set 时即拦下,不等首次请求才报难懂的 httpx 错误"""
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)

        result = runner.invoke(
            app, ["--format", "json", "config", "set", "url", "nf-server:8000"]
        )
        assert result.exit_code == 2
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"]["type"] == "VALIDATION_ERROR"
        assert not config_file.exists()

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
    def test_global_profile_option_unknown_json(self, tmp_path, monkeypatch):
        """JSON 模式下未知 --profile 也要输出 CONFIG_ERROR 信封,不能只留 stderr 文本"""
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", tmp_path / "config.json")
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)

        result = runner.invoke(app, ["--format", "json", "--profile", "nope", "list"])
        assert result.exit_code == 2
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"]["type"] == "CONFIG_ERROR"
        assert "config list" in data["error"]["hint"]

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


class TestVersionHandshake:
    """版本握手:UA 上报、426 升级指引、新版软提醒(响应头)。"""

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_user_agent_sent(self, mock_client_class):
        """每次请求的 httpx.Client 都带 nfctl UA(server 据此判定契约兼容性)。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200, {"items": [], "total": 0}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "list"])

        assert result.exit_code == 0
        ua = mock_client_class.call_args.kwargs["headers"]["User-Agent"]
        assert ua.startswith("nfctl")

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_426_upgrade_required(self, mock_client_class):
        """server 版本握手拒绝(426) → UPGRADE_REQUIRED 信封,detail/hint 直出。"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            426,
            {
                "detail": "nfctl 版本过旧，与当前 server 契约不兼容（最低要求 1.0.0）",
                "error_code": "UPGRADE_REQUIRED",
                "hint": "执行 pip install -U nfctl 升级后重试",
            },
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "list"])

        assert result.exit_code == 2
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error"]["type"] == "UPGRADE_REQUIRED"
        assert "版本过旧" in data["error"]["message"]
        assert "pip install -U nfctl" in data["error"]["hint"]

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_new_version_hint_once(self, mock_client_class, monkeypatch):
        """X-Nfctl-Latest 提醒头 → stderr 提示;多次请求只提示一次。"""
        monkeypatch.setattr("nfctl.client._new_version_warned", False)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        # overview 发两个请求(/stats/overview + /health),都带提醒头
        mock_client.request.side_effect = [
            _mock_response(
                200,
                {
                    "running": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "cancelled": 0,
                    "total": 0,
                    "by_pipeline": [],
                    "queue_waiting": 0,
                },
                headers={"x-nfctl-latest": "9.9.9"},
            ),
            _mock_response(
                200,
                {
                    "status": "healthy",
                    "reconciler": {"alive": True, "last_tick_at": None},
                },
                headers={"x-nfctl-latest": "9.9.9"},
            ),
        ]
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["overview"])

        assert result.exit_code == 0
        assert result.output.count("有新版本 9.9.9") == 1

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_no_hint_without_header(self, mock_client_class, monkeypatch):
        """无提醒头(版本已最新)不输出任何提示。"""
        monkeypatch.setattr("nfctl.client._new_version_warned", False)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200, {"items": [], "total": 0}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "有新版本" not in result.output


class TestVerbose:
    """--verbose/-v:HTTP 调试行走 stderr,stdout 的 JSON 契约不受污染。"""

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_verbose_debug_lines_on_stderr(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200, {"items": [], "total": 0}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "-v", "list"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert "→ GET http://test/workflow/list" in result.stderr
        assert "← 200" in result.stderr

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_no_debug_lines_without_verbose(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = _mock_response(
            200, {"items": [], "total": 0}
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["--format", "json", "list"])

        assert result.exit_code == 0
        assert "← 200" not in (result.stderr or "")
