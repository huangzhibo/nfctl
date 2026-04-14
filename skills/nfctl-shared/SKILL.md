---
name: nfctl-shared
version: 1.0.0
description: "nfctl CLI 共享基础：配置连接、全局选项、输出格式、退出码约定。首次使用 nfctl 或遇到连接错误时触发。"
metadata:
  requires:
    bins: ["nfctl"]
  cliHelp: "nfctl --help"
---

# nfctl 共享规则

本技能指导你如何通过 nfctl 操作 Nextflow Monitor Agent。

## 配置

nfctl 连接本地 HPC 上的 Agent 服务，无需认证。

```bash
# 查看当前配置
nfctl config show

# 设置 Agent URL（默认 http://localhost:8000）
nfctl config set url http://10.0.1.100:8000

# 也可通过环境变量（优先级高于配置文件）
export NFCTL_URL=http://10.0.1.100:8000
```

## 全局选项

| 选项 | 说明 |
|------|------|
| `--format json` | JSON 信封输出（AI Agent 必须使用） |
| `--format table` | 人类可读表格（默认） |
| `--quiet` / `-q` | 跳过确认提示（`--format json` 自动隐含） |
| `--verbose` / `-v` | 调试日志 |
| `--no-color` | 禁用颜色 |

**AI Agent 规则**：所有命令必须加 `--format json`，输出为标准信封格式。

## 输出信封格式

所有 `--format json` 输出遵循统一结构：

```json
// 成功
{"ok": true, "data": {...}}

// 错误
{"ok": false, "error": {"type": "CONFLICT", "message": "流程正在运行中", "hint": "使用 nfctl cancel 先取消"}}
```

## 退出码

| 退出码 | 含义 | 处理建议 |
|--------|------|----------|
| 0 | 成功 | - |
| 1 | 一般错误 | 读取 error.message |
| 2 | 参数/验证错误 | 检查命令参数 |
| 3 | 认证失败（保留） | - |
| 4 | 网络/连接错误 | 检查 Agent 是否运行，确认 NFCTL_URL |
| 5 | 冲突（流程正在运行） | 先取消再重试 |
| 6 | 服务端错误 | 检查 Agent 日志 |

## 错误处理

遇到错误时，读取 JSON 输出的 `error` 字段：

- `error.type`：错误分类，用于决策下一步动作
- `error.message`：错误描述
- `error.hint`：建议的修复命令（如果有）

**优先按 hint 执行修复**。如果没有 hint，按 type 判断：

| type | 处理 |
|------|------|
| `NETWORK_ERROR` | 检查 Agent 连接 |
| `NOT_FOUND` | workflow 不存在，用 `nfctl list` 确认 |
| `CONFLICT` | 流程已在运行，需先 cancel |
| `VALIDATION_ERROR` | 参数错误，检查输入 |
| `SERVER_ERROR` | Agent 内部错误，查看 Agent 日志 |
