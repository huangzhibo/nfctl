---
name: nfctl-workflow
version: 1.0.0
description: "Nextflow 工作流管理：投递、监控、取消、诊断、资源分析。当用户需要运行分析流程、查看状态、排查失败原因、分析资源使用时触发。"
metadata:
  requires:
    bins: ["nfctl"]
  cliHelp: "nfctl --help"
---

# workflow (v1)

**CRITICAL — 开始前 MUST 先用 Read 工具读取 [`../nfctl-shared/SKILL.md`](../nfctl-shared/SKILL.md)，其中包含配置、输出格式、错误处理**

## Core Concepts

- **Workflow**: 一个 Nextflow 分析流程实例，由 `workflow_id` 标识（从 run.sh 中的 TOWER_WORKFLOW_ID 获取）
- **Pipeline**: 流程类型（如 WGS、RNA-seq），有并发控制配置
- **Task**: Nextflow 子任务（process 的一次执行），由 `task_id` 标识
- **Status**: pending → running → succeeded/failed/cancelled

## Resource Relationships

```
Pipeline (并发控制)
└── Workflow (workflow_id)
    ├── Task (task_id) × N
    ├── Progress (process 级别进度)
    └── Log (Nextflow .nextflow.log)
```

## 命令总览

| 命令 | 说明 | 参考 |
|------|------|------|
| `overview` | 系统概览 | [`references/nfctl-overview.md`](references/nfctl-overview.md) |
| `list` | 工作流列表 | [`references/nfctl-list.md`](references/nfctl-list.md) |
| `status` | 工作流详情 | [`references/nfctl-status.md`](references/nfctl-status.md) |
| `tasks` | 子任务列表 | [`references/nfctl-tasks.md`](references/nfctl-tasks.md) |
| `task` | 子任务详情 | [`references/nfctl-task.md`](references/nfctl-task.md) |
| `log` | 日志查看 | [`references/nfctl-log.md`](references/nfctl-log.md) |
| `resources` | 资源统计 | [`references/nfctl-resources.md`](references/nfctl-resources.md) |
| `submit` | 投递工作流 | [`references/nfctl-submit.md`](references/nfctl-submit.md) |
| `cancel` | 取消工作流 | [`references/nfctl-cancel.md`](references/nfctl-cancel.md) |
| `delete` | 删除工作流 | [`references/nfctl-delete.md`](references/nfctl-delete.md) |
| `pipeline list` | Pipeline 配置 | [`references/nfctl-pipeline-list.md`](references/nfctl-pipeline-list.md) |

## 常用工作流

### 投递并监控

```bash
# 1. 验证（dry-run）
nfctl -f json submit /data/project/sample1 --pipeline WGS --dry-run

# 2. 投递
nfctl -f json -q submit /data/project/sample1 --pipeline WGS --env prod

# 3. 获取 workflow_id（从 submit 响应 data.workflow_id 提取）

# 4. 轮询状态
nfctl -f json status <workflow_id>
# data.status: running → 继续等待, succeeded → 完成, failed → 诊断
```

### 失败诊断

```bash
# 1. 查看状态和错误信息
nfctl -f json status <workflow_id>
# 关注: data.status, data.error_message, data.error_report

# 2. 找到失败的 task
nfctl -f json tasks <workflow_id> --status failed
# 关注: exit_status, peak_rss, duration

# 2.5 查看单个 task 详情（script, workdir, 完整资源占用）
nfctl -f json task <workflow_id> <task_id>

# 3. 查看错误日志
nfctl -f json log <workflow_id> --grep "ERROR"

# 4. 资源分析（判断 OOM）
nfctl -f json resources <workflow_id> --exclude-cached
# 关注: cpu_efficiency, memory_efficiency
```

### 常见失败模式

| 信号 | 诊断 | 建议 |
|------|------|------|
| exit_status=137, peak_rss 接近 memory | OOM Kill | 增加 memory 配置 |
| exit_status=143 | SIGTERM（超时或被取消） | 检查超时设置 |
| 日志含 "No space left" | 磁盘满 | 清理 work 目录或扩容 |
| 日志含 "command not found" | 环境缺失 | 检查 container/module |
| 日志含 "Permission denied" | 权限问题 | 检查目录权限 |
| cpu_efficiency < 20% | CPU 分配过多 | 降低 cpus 参数 |
