"""
nfctl CLI 测试

mock httpx 响应，测试 JSON 信封格式、退出码、人类输出。
"""

import json
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
        assert "0.3.0" in result.output


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
        assert "hint" in data["error"]


class TestConfig:
    @pytest.mark.unit
    def test_config_show_json(self):
        result = runner.invoke(app, ["--format", "json", "config", "show"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert "_resolved_url" in data["data"]

    @pytest.mark.unit
    def test_config_set_and_show(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("nfctl.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("nfctl.config.CONFIG_DIR", tmp_path)

        result = runner.invoke(
            app, ["--format", "json", "config", "set", "url", "http://test:9000"]
        )
        assert result.exit_code == 0

        data = json.loads(config_file.read_text())
        assert data["url"] == "http://test:9000"
