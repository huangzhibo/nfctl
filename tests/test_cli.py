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


def _mock_client(mock_client_class, *responses):
    """按调用顺序返回响应；只给一个时每次请求都返回它。"""
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    if len(responses) == 1:
        mock_client.request.return_value = responses[0]
    else:
        mock_client.request.side_effect = list(responses)
    mock_client_class.return_value = mock_client
    return mock_client


def _detail(attempt_no=1, workflow_id="wf-001", workflow=None, **run):
    """GET /workflow/{id}：运行信息嵌套在 current_attempt。"""
    return {
        "workflow_id": workflow_id,
        "project_sn": "SN",
        "created_at": "2026-04-13T10:00:00+00:00",
        "updated_at": "2026-04-13T10:00:00+00:00",
        **(workflow or {}),
        "current_attempt": {
            "attempt_no": attempt_no,
            "progress_percent": 0.0,
            **run,
        },
    }


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
                        "current_attempt": {
                            "attempt_no": 2,
                            "analysis_status": "succeeded",
                            "needs_action": False,
                            "progress_percent": 100.0,
                        },
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
        assert "100%" in result.output
        assert "Attempt" in result.output
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
                        "current_attempt": {
                            "attempt_no": 1,
                            "analysis_status": "running",
                            "launch_dir_occupied": True,
                            "progress_percent": 1.0,
                        },
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
                                "current_attempt": {
                                    "attempt_no": 1,
                                    "analysis_status": "running",
                                    "progress_percent": 1.0,
                                },
                                "pipeline_name": "rna-seq",
                                "env": "prod",
                                "project_sn": "BQ-TEST",
                                "updated_at": "2026-08-18T05:00:00+00:00",
                            },
                            {
                                "workflow_id": "wf-old",
                                "current_attempt": {
                                    "attempt_no": 1,
                                    "analysis_status": "succeeded",
                                    "progress_percent": 100.0,
                                },
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
        assert "succeeded" in result.output
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
        _mock_client(
            mock_client_class,
            _mock_response(
                200,
                _detail(
                    workflow={
                        "pipeline_name": "WGS",
                        "env": "prod",
                        "launch_dir": "/data/wf-001",
                    },
                    analysis_status="failed",
                    progress_percent=80.0,
                    run_name="run1",
                    job_id="12345",
                    error_message="Process failed",
                    error_report="FATAL: process FASTQC failed\nexit code 137",
                ),
            ),
        )

        result = runner.invoke(app, ["status", "wf-001"])

        assert result.exit_code == 0
        assert "Process failed" in result.output
        assert "12345" in result.output
        assert "error_report" not in result.output
        assert "exit code 137" not in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_json(self, mock_client_class):
        _mock_client(
            mock_client_class,
            _mock_response(200, _detail(analysis_status="running")),
        )

        result = runner.invoke(app, ["--format", "json", "status", "wf-001"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["current_attempt"]["attempt_no"] == 1

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_shows_current_attempt_and_storage(self, mock_client_class):
        """运行信息来自当前执行；目录状态解释排队原因（如等待恢复）。"""
        _mock_client(
            mock_client_class,
            _mock_response(
                200,
                _detail(
                    attempt_no=2,
                    workflow={
                        "launch_dir_state": {
                            "launch_dir": "/data/wf-001",
                            "storage_state": "archived",
                            "operation_kind": "restore",
                            "operation_status": "running",
                        }
                    },
                    analysis_status="queued",
                    status_summary="排队中，等待队列空出后自动启动",
                    needs_action=False,
                ),
            ),
        )

        result = runner.invoke(app, ["status", "wf-001"], env={"COLUMNS": "200"})

        assert result.exit_code == 0
        assert "Workflow wf-001#2" in result.output
        assert "attempt_no" in result.output
        assert "2（共 2 次）" in result.output
        assert "queued" in result.output
        assert "archived（restore:running）" in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_hides_ordinary_storage_state(self, mock_client_class):
        """4.x 迁来的目录都是 unknown，常态不占行，避免每条详情都多一行噪音。"""
        _mock_client(
            mock_client_class,
            _mock_response(
                200,
                _detail(
                    workflow={"launch_dir_state": {"storage_state": "unknown"}},
                    analysis_status="succeeded",
                ),
            ),
        )

        result = runner.invoke(app, ["status", "wf-001"], env={"COLUMNS": "200"})

        assert result.exit_code == 0
        assert "storage" not in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_needs_action_no_separate_row(self, mock_client_class):
        """需介入不单列 needs_action，summary 承载分析动作提示。"""
        _mock_client(
            mock_client_class,
            _mock_response(
                200,
                _detail(
                    analysis_status="failed",
                    status_summary="分析失败，需排查后 resume",
                    needs_action=True,
                ),
            ),
        )

        result = runner.invoke(app, ["status", "wf-001"], env={"COLUMNS": "200"})

        assert result.exit_code == 0
        assert "needs_action" not in result.output
        assert "需排查后 resume" in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_cancelled_hides_error_row(self, mock_client_class):
        """cancelled 不单列 error 行：取消原因已由 server 并入 summary。"""
        _mock_client(
            mock_client_class,
            _mock_response(
                200,
                _detail(
                    analysis_status="cancelled",
                    status_summary="已取消（5.0 升级）",
                    failure_code="USER_CANCELLED",
                    failure_message="5.0 升级",
                ),
            ),
        )

        result = runner.invoke(app, ["status", "wf-001"], env={"COLUMNS": "200"})

        assert result.exit_code == 0
        assert "5.0 升级" in result.output
        assert "error" not in result.output
        assert "USER_CANCELLED" not in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_failed_prefers_error_summary_and_shows_code(
        self, mock_client_class
    ):
        """failed 展示与 LIMS 推送同口径的错误，并给出失败原因码。"""
        _mock_client(
            mock_client_class,
            _mock_response(
                200,
                _detail(
                    analysis_status="failed",
                    error_summary="报错步骤：FASTQC",
                    error_message="Process FASTQC failed (raw)",
                    failure_code="TRACE_REPORTED_FAILURE",
                ),
            ),
        )

        result = runner.invoke(app, ["status", "wf-001"], env={"COLUMNS": "200"})

        assert result.exit_code == 0
        assert "报错步骤：FASTQC" in result.output
        assert "(raw)" not in result.output
        assert "TRACE_REPORTED_FAILURE" in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_failed_falls_back_to_failure_message(self, mock_client_class):
        """没有 trace 错误时（如恢复失败），展示服务端失败原因。"""
        _mock_client(
            mock_client_class,
            _mock_response(
                200,
                _detail(
                    analysis_status="failed",
                    failure_code="RESTORE_FAILED",
                    failure_message="恢复失败: exitcode=1",
                ),
            ),
        )

        result = runner.invoke(app, ["status", "wf-001"], env={"COLUMNS": "200"})

        assert result.exit_code == 0
        assert "恢复失败: exitcode=1" in result.output
        assert "RESTORE_FAILED" in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_succeeded_hides_stale_error_row(self, mock_client_class):
        """succeeded 不露 error 行，避免"成功 + 报错"自相矛盾。"""
        _mock_client(
            mock_client_class,
            _mock_response(
                200,
                _detail(
                    analysis_status="succeeded",
                    status_summary="分析完成，结果可用",
                    error_message="旧 attempt 的残留错误",
                ),
            ),
        )

        result = runner.invoke(app, ["status", "wf-001"], env={"COLUMNS": "200"})

        assert result.exit_code == 0
        assert "分析完成" in result.output
        assert "残留错误" not in result.output
        assert "error" not in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_multiline_error_is_aligned(self, mock_client_class):
        """多行 error 的续行对齐到 value 列,不顶格。"""
        _mock_client(
            mock_client_class,
            _mock_response(
                200,
                _detail(
                    analysis_status="failed",
                    error_summary="报错步骤：enrich (1)\n报错原因：'g1'",
                ),
            ),
        )

        result = runner.invoke(app, ["status", "wf-001"])

        assert result.exit_code == 0
        assert "报错步骤" in result.output
        assert "报错原因" in result.output
        assert "\n报错原因" not in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_previous_reads_history_attempt(self, mock_client_class):
        """--previous = 当前序号减 1，读 /attempts/{n}；历史执行不显示当下目录状态。"""
        detail = _detail(
            attempt_no=3,
            workflow={"launch_dir_state": {"storage_state": "materialized"}},
            analysis_status="running",
        )
        history = {
            "attempt_no": 2,
            "analysis_status": "failed",
            "progress_percent": 40.0,
            "failure_code": "PROGRESS_STALLED",
        }
        mock_client = _mock_client(
            mock_client_class,
            _mock_response(200, detail),
            _mock_response(200, history),
            _mock_response(200, detail),
        )

        result = runner.invoke(
            app, ["status", "wf-001", "--previous"], env={"COLUMNS": "200"}
        )

        assert result.exit_code == 0
        assert mock_client.request.call_args_list[1].args == (
            "GET",
            "/workflow/wf-001/attempts/2",
        )
        assert "2（共 3 次）" in result.output
        assert "PROGRESS_STALLED" in result.output
        assert "storage" not in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_status_attempt_json_returns_attempt_view(self, mock_client_class):
        mock_client = _mock_client(
            mock_client_class,
            _mock_response(200, {"attempt_no": 1, "analysis_status": "failed"}),
        )

        result = runner.invoke(app, ["-f", "json", "status", "wf-001", "-a", "1"])

        assert result.exit_code == 0
        assert json.loads(result.output)["data"]["attempt_no"] == 1
        assert mock_client.request.call_count == 1

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_previous_on_first_attempt_is_rejected(self, mock_client_class):
        mock_client = _mock_client(
            mock_client_class, _mock_response(200, _detail(attempt_no=1))
        )

        result = runner.invoke(app, ["-f", "json", "progress", "wf-001", "--previous"])

        assert result.exit_code == 2
        assert json.loads(result.output)["error"]["type"] == "ATTEMPT_NOT_FOUND"
        assert mock_client.request.call_count == 1

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_attempt_and_previous_are_exclusive(self, mock_client_class):
        result = runner.invoke(
            app, ["progress", "wf-001", "--attempt", "1", "--previous"]
        )

        assert result.exit_code == 2
        mock_client_class.assert_not_called()


class TestAttempts:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_attempts_table(self, mock_client_class):
        mock_client = _mock_client(
            mock_client_class,
            _mock_response(
                200,
                {
                    "workflow_id": "wf-001",
                    "total": 2,
                    "page": 1,
                    "page_size": 20,
                    "attempts": [
                        {
                            "attempt_no": 2,
                            "analysis_status": "running",
                            "progress_percent": 30.0,
                            "status_summary": "分析进行中（30%）",
                        },
                        {
                            "attempt_no": 1,
                            "analysis_status": "failed",
                            "progress_percent": 80.0,
                            "failure_code": "EXECUTION_TIMEOUT",
                            "status_summary": "分析失败，需排查后 resume",
                        },
                    ],
                },
            ),
        )

        result = runner.invoke(app, ["attempts", "wf-001"], env={"COLUMNS": "200"})

        assert result.exit_code == 0
        assert mock_client.request.call_args.args == (
            "GET",
            "/workflow/wf-001/attempts",
        )
        assert "EXECUTION_TIMEOUT" in result.output
        assert "分析进行中" in result.output
        assert "需排查后 resume" not in result.output


class TestAttemptQueries:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("argv", "path"),
        [
            (["progress", "wf-001"], "/workflow/wf-001/progress"),
            (["tasks", "wf-001"], "/workflow/wf-001/tasks"),
            (["task", "wf-001", "7"], "/workflow/wf-001/tasks/7"),
            (["resources", "wf-001"], "/workflow/wf-001/resource-stats"),
            (["log", "wf-001"], "/workflow/wf-001/log"),
        ],
    )
    @patch("nfctl.client.httpx.Client")
    def test_attempt_is_sent_as_query_param(self, mock_client_class, argv, path):
        mock_client = _mock_client(mock_client_class, _mock_response(200, {}))

        default = runner.invoke(app, ["-f", "json", *argv])
        pinned = runner.invoke(app, ["-f", "json", *argv, "--attempt", "1"])

        assert default.exit_code == 0 and pinned.exit_code == 0
        first, second = mock_client.request.call_args_list
        assert first.args == ("GET", path)
        assert "attempt_no" not in first.kwargs["params"]
        assert second.kwargs["params"]["attempt_no"] == 1

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_log_names_matched_file_on_stderr(self, mock_client_class):
        _mock_client(
            mock_client_class,
            _mock_response(
                200,
                {
                    "workflow_id": "wf-001",
                    "attempt_no": 1,
                    "log_file": "/data/wf-001/.nextflow.log.1",
                    "lines": ["line-a", "line-b"],
                },
            ),
        )

        result = runner.invoke(app, ["log", "wf-001", "-a", "1"])

        assert result.exit_code == 0
        assert result.stdout == "line-a\nline-b\n"
        assert ".nextflow.log.1" in result.stderr

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_log_not_found_shows_reason(self, mock_client_class):
        _mock_client(
            mock_client_class,
            _mock_response(
                404,
                {
                    "detail": "该次执行的日志已被轮转删除",
                    "error_code": "LOG_NOT_FOUND",
                    "reason": "not_retained",
                },
            ),
        )

        result = runner.invoke(app, ["log", "wf-001", "-a", "1"])

        assert result.exit_code == 2
        assert "LOG_NOT_FOUND" in result.stderr
        assert "not_retained" in result.stderr


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
    def test_delete_sends_single_request(self, mock_client_class):
        """控制命令只作用于当前执行，不先读序号；成功结果的守卫在 server。"""
        mock_client = _mock_client(
            mock_client_class,
            _mock_response(200, {"workflow_id": "wf-bad", "deleted": True}),
        )

        result = runner.invoke(app, ["--format", "json", "delete", "wf-bad"])

        assert result.exit_code == 0
        assert json.loads(result.output)["data"]["deleted"] is True
        assert mock_client.request.call_count == 1
        call = mock_client.request.call_args
        assert call.args == ("DELETE", "/workflow/wf-bad")
        assert call.kwargs["params"] == {}

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_delete_rejected_by_server_passes_through(self, mock_client_class):
        _mock_client(
            mock_client_class,
            _mock_response(
                409,
                {
                    "detail": "存在有效的成功结果，先 cancel 作废后才能删除",
                    "error_code": "DELETE_REJECTED",
                    "resource_id": "wf-ok",
                },
            ),
        )

        result = runner.invoke(app, ["--format", "json", "delete", "wf-ok"])

        assert result.exit_code == 5
        assert json.loads(result.output)["error"]["type"] == "DELETE_REJECTED"

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_delete_404_passes_through(self, mock_client_class):
        _mock_client(
            mock_client_class,
            _mock_response(
                404,
                {"detail": "Workflow not found", "error_code": "WORKFLOW_NOT_FOUND"},
            ),
        )

        result = runner.invoke(app, ["--format", "json", "delete", "wf-missing"])

        assert result.exit_code == 2
        assert json.loads(result.output)["error"]["type"] == "WORKFLOW_NOT_FOUND"


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
    @pytest.mark.parametrize(
        ("main_status", "shown"),
        [("stopping", "Stopping: wf-001#3"), ("cancelled", "Cancelled: wf-001#3")],
    )
    @patch("nfctl.client.httpx.Client")
    def test_cancel_sends_reason_only(self, mock_client_class, main_status, shown):
        """运行中则停止、已成功则作废，由 server 判断；CLI 只发一次请求。"""
        mock_client = _mock_client(
            mock_client_class,
            _mock_response(
                202,
                {"workflow_id": "wf-001", "attempt_no": 3, "main_status": main_status},
            ),
        )

        result = runner.invoke(
            app, ["-q", "cancel", "wf-001", "-r", "升级"], env={"COLUMNS": "200"}
        )

        assert result.exit_code == 0
        assert mock_client.request.call_count == 1
        call = mock_client.request.call_args
        assert call.args == ("POST", "/workflow/wf-001/cancel")
        assert call.kwargs["json"] == {"reason": "升级"}
        assert shown in result.output

    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_cancel_abort_sends_nothing(self, mock_client_class):
        result = runner.invoke(app, ["cancel", "wf-001"], input="n\n")

        assert result.exit_code == 1
        mock_client_class.assert_not_called()


class TestResume:
    @pytest.mark.unit
    @patch("nfctl.client.httpx.Client")
    def test_resume_sends_no_body(self, mock_client_class):
        mock_client = _mock_client(
            mock_client_class,
            _mock_response(
                202,
                {"workflow_id": "wf-001", "attempt_no": 2, "main_status": "running"},
            ),
        )

        result = runner.invoke(app, ["resume", "wf-001"])

        assert result.exit_code == 0
        assert mock_client.request.call_count == 1
        call = mock_client.request.call_args
        assert call.args == ("POST", "/workflow/wf-001/resume")
        assert call.kwargs["json"] is None
        assert "Resumed: wf-001#2" in result.output

    @pytest.mark.unit
    def test_withdraw_command_is_removed(self):
        result = runner.invoke(app, ["withdraw", "wf-001", "-r", "x"])

        assert result.exit_code == 2
        assert "No such command" in result.output


class TestCancelOptions:
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
