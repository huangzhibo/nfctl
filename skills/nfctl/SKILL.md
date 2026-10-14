---
name: nfctl
description: "用 nfctl 查询、投递和诊断 Nextflow 分析，并按 launch_dir 操作归档、迁移和 restore。"
---

# nfctl

## 执行契约

- Agent 调用必须使用 `-f json`；全局选项写在子命令前。
- 成功信封：`{"ok":true,"data":...}`。
- 失败信封：`{"ok":false,"error":{"type":"...","message":"...","hint":"..."}}`；服务端上下文会以 `current_attempt_no`、`operation_id` 等原字段名保留在 `error` 中，422 参数错误另有 `validation_errors`。
- `--jq` 隐含 JSON；JSON/quiet 模式跳过交互确认。

退出码：0 成功，1 一般错误，2 参数/验证错误，4 网络错误，5 冲突，6 服务端错误。

服务地址优先级：`--profile` / `NFCTL_PROFILE` > `NFCTL_URL` > 用户当前 profile > 系统当前 profile。系统默认来自 `/etc/nfctl/config.json`，用户同名 profile 优先。`CONFIG_ERROR` 按 hint 配置 URL；`UPGRADE_REQUIRED` 先升级 nfctl。

## 领域边界

- Workflow 由 `workflow_id` 标识，只描述一次分析。每次 submit/resume 是一次执行，用
  `attempt_no` 区分（从 1 连续递增，当前执行永远是最大号）。运行信息在 `current_attempt` 里。
- LaunchDir 由规范化绝对路径标识，是目录存储状态、归档计划和 operation 的唯一资源。
- 一个 LaunchDir 可以有多条 Workflow 历史。不要用“最新 Workflow 的归档字段”推断目录状态。

分析状态 `analysis_status`（当前执行的）：`queued | running | stopping | succeeded | failed | cancelled`。
`stopping` 表示已请求停止、调度任务还没确认退出，目录仍被占用。

目录 `storage_state`：`unknown | materialized | archived | empty | partial`。

存储 operation：kind=`migrate | archive | restore`，status=`pending | running | cancelling | succeeded | failed | cancelled`，每次 attempt 有独立 `operation_id`。

## 命令速查

```text
overview
list [-s ANALYSIS_STATUS] [-p PIPELINE] [--env ENV] [-S PROJECT_SN]
     [-D DATA_NUMBER] [-q QUERY] [-L LAUNCH_DIR] [--all]
list --group-by launch-dir [--state STORAGE_STATE] [--archive-due] [--all]
status    WORKFLOW_ID [-a N | --previous]
attempts  WORKFLOW_ID
progress  WORKFLOW_ID [-a N | --previous]
tasks     WORKFLOW_ID [-s STATUS] [--process PROCESS] [-a N | --previous]
task      WORKFLOW_ID TASK_ID [-a N | --previous]
log       WORKFLOW_ID [-g GREP] [-a N | --previous]
resources WORKFLOW_ID [--exclude-cached] [-a N | --previous]

submit   LAUNCH_DIR -p PIPELINE -S PROJECT_SN [-e ENV] [--dry-run]
resume   WORKFLOW_ID
cancel   WORKFLOW_ID [-r REASON]
delete   WORKFLOW_ID

archive status  LAUNCH_DIR
archive start   LAUNCH_DIR
archive restore LAUNCH_DIR [--wait]
archive resume  LAUNCH_DIR
archive cancel  LAUNCH_DIR [-r REASON]
```

## 标准工作流

### 投递和监控

```bash
nfctl -f json submit /data/project/run1 -p WGS -S P2026001 --dry-run
nfctl -f json submit /data/project/run1 -p WGS -S P2026001 -e prod
nfctl -f json status <workflow_id>
```

相对 LAUNCH_DIR 会按 nfctl 调用者的 cwd 转为绝对路径，因此可在启动目录内使用 `submit .`。submit 从 `run.sh` 提取 `TOWER_WORKFLOW_ID`。成功受理后 `analysis_status` 通常先为 `queued`，有容量后转 `running`；目录已归档时会先自动 restore，期间保持 `queued`，详情的 `launch_dir_state.operation_kind=restore`。分析结束只看 `analysis_status`，存储进度另查 LaunchDir。

### 执行历史

查询命令默认当前执行，响应都回显 `attempt_no`；翻页或连续查询时用 `-a <回显的 attempt_no>` 钉住同一次执行。`--previous` 是当前序号减 1，第 1 次执行没有上一次（`ATTEMPT_NOT_FOUND`）。`status -a N` 的 JSON 是该次执行本身（不含 Workflow 级字段）。

### 分析失败诊断

```bash
nfctl -f json status <workflow_id>
nfctl -f json attempts <workflow_id>
nfctl -f json tasks <workflow_id> -s failed
nfctl -f json task <workflow_id> <task_id>
nfctl -f json log <workflow_id> -g ERROR
nfctl -f json resources <workflow_id> --exclude-cached
```

失败原因看 `current_attempt.error_summary`（trace 错误摘要）和 `failure_code`：`TRACE_REPORTED_FAILURE` 为流程报错，`EXECUTION_TIMEOUT` / `PROGRESS_STALLED` 为超时/停滞，`RESTORE_FAILED` 为分析前的自动恢复失败（查 `archive status`）。`status`（含 `-a N`）的 JSON 带 `error_message` / `error_report` 原文；`list` / `attempts` 不含这些大字段。

常见信号：137 通常为 OOM；143 为 SIGTERM/超时；`No space left` 为磁盘；`Permission denied` 为权限。

`log` 返回 `LOG_NOT_FOUND` 时看 `error.reason`：`not_started` 为还没开始运行，`not_retained` 为日志已被 Nextflow 轮转删除（只保留最近 10 次调用），`launch_dir_missing` 为目录不存在。

### 取消与重跑

控制命令只作用于当前执行。

- `cancel`：运行中则停止（先 `stopping`），已成功则作废结果；LIMS 都会收到 error。操作前先 `status` 确认当前执行就是你要处理的那次。
- `resume`：失败或取消（含作废的成功结果）后重跑，新建一次执行。有效的成功结果要先 cancel 作废。
- 换了 workflow_id 的重分析是新分析，走 `submit`。

### 目录存储盘点

```bash
nfctl -f json list --group-by launch-dir --state unknown,materialized,partial --all
nfctl -f json list --group-by launch-dir --archive-due --all
nfctl -f json archive status /data/project/run1
```

关注 `storage_state`、`archive_due_at`、`archive_path`、`operation`、`last_error`。`partial` 需要先确认物理目录和日志，再决定 resume/restore/人工处理。

### Restore

```bash
nfctl -f json archive restore /data/project/run1 --wait
```

restore 不覆盖已有数据：归档里的目录都已在原位时直接成功；只有一部分在时 operation 失败（见 `last_error`），目录通常变为 `partial`。不要自动删除或覆盖；先让用户/运维确认现场。分析的 submit/resume 会自动 restore，不需要先手动执行。

## 冲突处理

- `LAUNCH_DIR_BUSY`：有分析占用目录，具体 Workflow 见 `error.occupied_workflow_id`。不要隐式 cancel；按用户意图明确处理。
- `STORAGE_OPERATION_ACTIVE`：等待当前 operation，或明确 `archive cancel` 后重试。
- `STORAGE_RESUME_REJECTED`：只有最近 operation 为 failed/cancelled 才能 resume。
- `LAUNCH_DIR_STORAGE_UNCERTAIN`：目录为 `partial`；只能 resume 最近操作或先人工核对现场。
- `ARCHIVE_NOT_FOUND`：确认 archive_path 和 `archive.tar.zst`，不要伪造成功。
- `WORKFLOW_ID_EXISTS`：查现有 Workflow；不要直接生成另一个 ID 绕过业务意图。
- `RESUME_REJECTED`：执行仍在运行/停止中，或成功结果尚未 cancel 作废。
- `CANCEL_REJECTED`：执行已失败或已取消，没有可取消的。
- `DELETE_REJECTED`：执行未结束，或这个分析有过成功执行（成功历史不可删）。

## 批量投递

Pipeline `max_concurrent` 满时 submit 仍可受理并显示 queued。逐条提交即可，不需要 Agent 自己实现并发队列；用 `list -s queued` 观察等待项。
