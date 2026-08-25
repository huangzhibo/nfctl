"""
测试默认环境：给 AgentClient 一个可解析的 URL，并清理 profile override 跨测试状态。
需要断言未配置行为的测试请在用例内 monkeypatch.delenv("NFCTL_URL")。
"""

import pytest


@pytest.fixture(autouse=True)
def _isolate_nfctl(monkeypatch, tmp_path):
    monkeypatch.setenv("NFCTL_URL", "http://test")
    monkeypatch.setattr("nfctl.config._profile_override", None)
    # 测试不得受开发机 /etc/nfctl/config.json 影响。需要系统配置的
    # 用例在各自 tmp_path 下写入这个文件。
    monkeypatch.setattr(
        "nfctl.config.SYSTEM_CONFIG_FILE", tmp_path / "system-config.json"
    )
