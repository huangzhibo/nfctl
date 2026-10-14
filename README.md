# nfctl

nf-server CLI，面向生信工程师和 AI Agent。

nfctl 3.x 对应 nf-server 5.x。3.0 起存储生命周期改为 LaunchDir 资源，
不兼容旧的 workflow 级 archive API。

## 安装与配置

```bash
pip install nfctl

# 没有系统默认时，用户可配置自己的 profile
nfctl config set url http://nf-server:8000

# 多环境 profile
nfctl config set url http://test-server:8000 --profile test
nfctl config use test
nfctl --profile prod list

# 环境变量可直连
export NFCTL_URL=http://nf-server:8000
```

集群管理员可提供 `/etc/nfctl/config.json`，让新用户无需初始化即可使用：

```json
{
  "current": "prod",
  "profiles": {
    "prod": {"url": "https://nf-server.internal"},
    "test": {"url": "https://nf-server-test.internal"}
  }
}
```

系统配置只读，用户命令只修改 `~/.nfctl/config.json`。用户的同名
profile 覆盖系统 profile；`nfctl config list/show` 会显示来源和两个
配置文件路径。

解析优先级：`--profile` / `NFCTL_PROFILE` > `NFCTL_URL` > 用户当前
profile > 系统当前 profile。显式指定 profile 时仍是用户同名配置优先。

## 两类资源

- Workflow：一次分析，由 `workflow_id` 标识。每次 submit/resume 是它的一次执行，
  用 `attempt_no`（1、2、3…）区分；列表和详情默认展示当前执行，即最大的那个序号。
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
nfctl attempts <workflow_id>           # 执行历史，新的在前
nfctl progress <workflow_id>
nfctl tasks <workflow_id> --status failed
nfctl task <workflow_id> <task_id>
nfctl log <workflow_id> --grep ERROR
nfctl resources <workflow_id> --exclude-cached
```

`status`、`progress`、`tasks`、`task`、`log`、`resources` 默认看当前执行；
`--attempt N` 看第 N 次，`--previous` 看上一次。标题里的 `wf-001#2` 表示第 2 次执行。
`log` 按该次执行的 runName 找到对应的 `.nextflow.log*`，文件名打印在 stderr；
日志被 Nextflow 轮转删除后返回 `LOG_NOT_FOUND`。

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
nfctl withdraw <workflow_id> --reason 原因
nfctl delete <workflow_id>
```

相对 launch_dir 会先按 nfctl 调用者的当前目录转换为绝对路径，因此可以在启动目录内直接使用 `submit .`。submit 会从 `run.sh` 读取 `TOWER_WORKFLOW_ID` 并校验请求一致。受理成功后服务端立即记录 `progress=1`，由 reconciler 异步启动。手动 qsub 只有在 Workflow 已通过 submit 登记时才能被 trace 接管。

- `resume`：新建一次执行，支持 failed/cancelled 和已撤销的成功；已归档目录会先自动恢复再投递。
- `cancel`：只取消运行中的分析，先进入 `stopping`，调度任务确认退出后变为 `cancelled`；不取消目录存储操作。
- `withdraw`：撤销成功结果，LIMS 会收到 error；之后才能 resume 重跑。
- `delete`：删除分析及全部执行历史，不动目录文件；有过成功执行的分析不能删除。

控制命令针对当前执行，并把它的序号作为 `expected_attempt_no` 发给服务端；
期间若有人 resume 出了新的执行，服务端返回 `ATTEMPT_CHANGED` 和 `current_attempt_no`，
刷新状态后再决定。`--attempt N` 可以钉住自己看到的那次执行。

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
- `restore`：不覆盖已有数据。归档里的目录都已在原位时直接视为已恢复；只有一部分在时失败，
  需人工核对。`--wait` 按 operation_id 等待终态。
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

服务端的结构化错误上下文会保留在 `error` 中。例如执行已变化会返回
`error.current_attempt_no`，存储任务冲突会返回 `error.operation_id` / `error.job_id`。

全局选项写在子命令前。`--format json` 自动跳过交互确认。

## 开发

```bash
uv sync
uv run ruff check nfctl tests
uv run pytest
```
