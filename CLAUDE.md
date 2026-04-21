# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

nfctl 是 nf-server 的 CLI 客户端，面向生信工程师和 AI Agent。输出契约（JSON 信封格式、退出码体系）与 lims2 CLI 对齐。

后端服务 nf-server 的 API 规范文档：`/Users/huangzhibo/workitems/01.github/nf-server/openapi/nf-server.json`

## 常用命令

```bash
uv sync                      # 安装依赖
uv run nfctl --help          # 运行 CLI
uv run pytest                # 运行全部测试
uv run pytest tests/test_cli.py::TestOverview::test_overview_json  # 运行单个测试
uv run ruff check nfctl      # lint 检查
uv run ruff format nfctl     # 格式化
```

## 架构

### 核心数据流

命令函数 → `AgentClient`（httpx 封装） → HTTP 请求 → 返回 `(envelope_dict, exit_code)` → `output.print_result()` / `print_data()` 输出

### 输出契约

所有 `--format json` 输出遵循统一信封格式：
- 成功: `{"ok": true, "data": ...}`
- 失败: `{"ok": false, "error": {"type": "ERROR_TYPE", "message": "...", "hint": "..."}}`

`--format json` 隐含 `--quiet`，确保 stdout 只有合法 JSON。`--jq` 隐含 `--format json`，通过 jq 子进程过滤输出。`--format` 和 `--jq` 均为全局选项，写在子命令之前：`nfctl -f json list`。

### 退出码体系（与 lims2 对齐）

0=SUCCESS, 1=ERROR, 2=VALIDATION_ERROR, 4=NETWORK_ERROR, 5=CONFLICT, 6=SERVER_ERROR

### 命令注册方式

- 查询和管理命令在 `main.py` 中扁平注册（`app.command()`）
- `config` 和 `pipeline` 作为子命令组通过 `app.add_typer()` 注册

### 模块职责

| 模块 | 职责 |
|------|------|
| `main.py` | Typer app 定义、全局选项、命令注册 |
| `client.py` | httpx 封装、HTTP 状态码映射、错误信封构造 |
| `config.py` | 配置管理（`~/.nfctl/config.json`，`NFCTL_URL` 环境变量） |
| `output.py` | 双模式输出（Rich table / JSON 信封）、全局格式状态 |
| `commands/query.py` | 查询命令：overview, list, status, tasks, task, log, resources |
| `commands/workflow.py` | 管理命令：submit（含 --dry-run）, cancel, delete, resume |
| `commands/config_cmd.py` | 配置命令：set, show |
| `commands/pipeline.py` | Pipeline 命令：list |

### 测试模式

测试通过 mock `nfctl.client.httpx.Client` 来模拟 HTTP 响应，使用 `typer.testing.CliRunner` 驱动 CLI 调用。添加新命令测试时遵循此模式。

## 开发约定

- 版本号单一真源为 `pyproject.toml`；`main.py --version` 与测试都通过 `importlib.metadata.version("nfctl")` 读取
- Ruff 配置忽略 E501（行长）和 B008（参数默认值中的函数调用，Typer 需要）
- `skills/` 目录存放 AI Agent 的 Skill 文档，不是运行时代码
