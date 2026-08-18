# nfctl

nf-server CLI，面向生信工程师和 AI Agent。

nfctl 3.x 对应 nf-server 5.x。3.0 起存储生命周期改为 LaunchDir 资源，
不兼容旧的 workflow 级 archive API。

## 安装与配置

```bash
pip install nfctl

nfctl config set url http://nf-server:8000

# 多环境 profile
nfctl config set url http://test-server:8000 --profile test
nfctl config use test
nfctl --profile prod list

# 环境变量可直连
export NFCTL_URL=http://nf-server:8000
```

解析优先级：`--profile` / `NFCTL_PROFILE` > `NFCTL_URL` > 当前 profile。

## 两类资源

- Workflow：一次 Nextflow 分析，由 `workflow_id` 标识。
- LaunchDir：物理启动目录及其存储生命周期，由规范化绝对路径标识。

分析状态只出现在 Workflow；归档、迁移和 restore 状态只出现在 LaunchDir。不要用某个 Workflow ID 代表目录存储状态。

## 查询

```bash
nfctl overview
nfctl list --status running
nfctl list --pipeline WGS --env prod
nfctl list --project-sn P2026001
nfctl list --launch-dir .              # 该目录的 Workflow 历史
nfctl status <workflow_id>
nfctl progress <workflow_id>
nfctl tasks <workflow_id> --status failed
nfctl task <workflow_id> <task_id>
nfctl log <workflow_id> --grep ERROR
nfctl resources <workflow_id> --exclude-cached
```

按目录盘点：

```bash
nfctl list --group-by launch-dir
nfctl list --group-by launch-dir --all
nfctl list --group-by launch-dir --state unknown,materialized,partial --all
nfctl list --group-by launch-dir --state archived,empty --all
nfctl list --group-by launch-dir --archive-due --all
```

`--group-by launch-dir` 的分页单位是目录，组内返回完整 Workflow 历史。
`unknown,materialized,partial` 适合盘点仍有工作盘数据或物理状态不确定的目录；
`archived,empty` 表示目录已经归档，或确认没有需要归档的数据。

## 分析控制

```bash
nfctl submit <launch_dir> -p <pipeline> -S <project_sn> [--env prod]
nfctl submit . -p <pipeline> -S <project_sn> [--env prod]
nfctl submit <launch_dir> -p <pipeline> -S <project_sn> --dry-run
nfctl resume <workflow_id>
nfctl cancel <workflow_id> [--reason 原因]
nfctl delete <workflow_id>
```

相对 launch_dir 会先按 nfctl 调用者的当前目录转换为绝对路径，因此可以在启动目录内直接使用 `submit .`。submit 会从 `run.sh` 读取 `TOWER_WORKFLOW_ID` 并校验请求一致。受理成功后服务端立即记录 `progress=1`，由 reconciler 异步启动。手动 qsub 只有在 Workflow 已通过 submit 登记时才能被 trace 接管。

`cancel` 只取消分析，不取消目录存储操作。

## 存储控制

所有参数都是 launch_dir，可直接在目录内传 `.`：

```bash
nfctl archive status .
nfctl archive start .
nfctl archive restore . --wait
nfctl archive resume .
nfctl archive cancel . --reason maintenance
```

- `start`：立即发起 archive，不以 workflow_id 定位。
- `restore`：已有一级非隐藏目录时拒绝覆盖；`--wait` 按 operation_id 等待终态。
- `resume`：重试最近一次 failed/cancelled migrate/archive/restore。
- `cancel`：关闭自动归档并请求取消活跃 job；operation 在 scheduler 确认退出前保持 `cancelling`。

`storage_state` 为 `unknown | materialized | archived | empty | partial`；operation 状态为 `pending | running | cancelling | succeeded | failed | cancelled`。

## Pipeline

```bash
nfctl pipeline list
nfctl pipeline create WGS --archive --archive-delay-hours 72
nfctl pipeline update WGS --large-file-threshold 500M
```

归档范围固定为 launch_dir 下所有一级非隐藏真实目录。Pipeline 只配置开关、迁移阈值、延迟、并发、通知和分析超时。

## JSON / Agent

```bash
nfctl -f json list
nfctl -f json archive status .
nfctl --jq '.data.items[].workflow_id' list
```

JSON 使用统一信封：

```json
{"ok": true, "data": {}}
{"ok": false, "error": {"type": "LAUNCH_DIR_BUSY", "message": "...", "hint": "..."}}
```

服务端的结构化错误上下文会保留在 `error` 中。例如 restore 冲突会返回
`error.conflicts`，存储任务冲突会返回 `error.operation_id` / `error.job_id`。

全局选项写在子命令前。`--format json` 自动跳过交互确认。

## 开发

```bash
uv sync
uv run ruff check nfctl tests
uv run pytest
```
