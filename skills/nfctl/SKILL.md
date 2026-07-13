---
name: nfctl
description: "用 nfctl CLI 投递、查询、诊断 Nextflow 分析，并操作归档/解压（nf-server 后端）。涵盖 JSON 输出契约、退出码、submit / status / progress / tasks / log / resources / archive 等命令的正确用法，以及失败诊断与资源效率判读。当用户需要操作 Nextflow 分析或排查 nfctl 报错时触发。"
---

# nfctl

本技能教 AI Agent 正确使用 nfctl 管理 Nextflow 分析。参数细节用 `nfctl <cmd> --help` 按需查询，本文件聚焦**契约、判断、工作流**。

## 契约（Agent 执行前必读）

### 输出信封

所有 `--format json` 输出遵循统一结构：

```json
// 成功
{"ok": true, "data": {...}}

// 错误
{"ok": false, "error": {"type": "LAUNCH_DIR_BUSY", "message": "launch_dir 上 workflow wf-xxx 分析进行中,不可提交新分析", "hint": "如需重跑，请先 cancel 该流程再 resume。", "resource_id": "..."}}
```

`error.type` 优先取服务端 `error_code`（如 `LAUNCH_DIR_BUSY` / `WORKFLOW_ID_EXISTS` / `RESUME_REJECTED`），无法读出时按 HTTP 状态归类为通用类型。`error.resource_id` 等字段按场景出现。`hint` 是服务端给的自愈建议，**优先照 hint 执行**。

### Agent 规则

- 所有命令 **必须加 `--format json`**（简写 `-f json`）
- `--format json` 自动隐含 `--quiet`，无交互确认
- `--jq <expr>` 隐含 `--format json`，直接过滤字段：`nfctl --jq '.data.items[].workflow_id' list`
- 全局选项必须写在**子命令之前**：`nfctl -f json list`，不是 `nfctl list -f json`

### 退出码

| 码 | 含义 | 处理 |
|----|------|------|
| 0 | 成功 | — |
| 1 | 一般错误 | 读 `error.message` |
| 2 | 参数/验证错误 | 检查输入 |
| 4 | 网络不可达/超时（本地到 server） | 可自动重试 |
| 5 | 冲突（409：launch_dir 占用、重复提交、状态不允许等） | 按 `hint` 处理 |
| 6 | 服务端错误 | 查服务日志 |

### 错误类型速查

| type | 归类 | 典型处理 |
|------|------|----------|
| `NETWORK_ERROR` / `TIMEOUT` | 本地连接问题 | 检查 `NFCTL_URL`、服务是否运行 |
| `NOT_FOUND` | workflow 不存在 | `nfctl list` 确认 |
| `LAUNCH_DIR_BUSY` / `WORKFLOW_ID_EXISTS` / `CONFLICT` | 409 冲突（分析进行中、重复提交） | 按 `hint`；确需重跑先 `cancel` 再 `resume` |
| `RESUME_REJECTED` | 当前状态不支持该 resume | 按 `hint` 换端点（`resume` vs `archive resume`） |
| `VALIDATION_ERROR` / `BAD_REQUEST` | 参数/状态校验错误（含 `delete` 拒删 succeeded 分析的情况） | 检查参数；清理已成功的分析走后端运维通道 |
| `UPGRADE_REQUIRED` | 426：nfctl 版本低于 server 门槛 | `pip install -U nfctl` |
| `SERVER_ERROR` | 服务端内部错误 | 查服务日志 |

### 配置

服务地址通过 `NFCTL_URL` 环境变量或 `nfctl config set url <URL>` 设置，默认 `http://localhost:8000`。连接失败会返回 `NETWORK_ERROR` 和 `NFCTL_URL` 提示。

## Core Concepts

- **Workflow**：一次 Nextflow 分析流程实例，由 `workflow_id` 标识。`workflow_id` 从 `launch_dir/run.sh` 中的 `TOWER_WORKFLOW_ID=xxx` 读取。
- **Pipeline**：流程类型（如 `WGS`、`16s`、`ampliseq`），按流程配置并发（`max_concurrent`）、飞书通知（`feishu_webhook`）、后处理归档/迁移策略（`archive_enabled` / `large_file_threshold` / `archive_dirs` / `archive_delay_hours`）、超时覆盖（`stall_timeout_hours` / `execution_timeout_hours`）。未建配置行的流程：归档与迁移均关，后处理 `skipped`。
- **Task**：Nextflow 子任务（process 的一次执行），由 `task_id` 标识；运行态见 `status` 字段（CACHED / COMPLETED / FAILED 等）。
- **Cached task**：Nextflow `-resume` 命中缓存、本次未真正执行、直接复用历史 workdir 的 task。聚合指标里会**保留其首次运行时的 used/requested**（不是 0）。调优本次资源分配请用 `resources --exclude-cached`。
- **两轴生命周期**（对外契约，server 派生）：
  - **分析轴**：字段 `analysis_status`，取值 `queued`（已受理未启动，含并发满挂起）/ `running` / `succeeded` / `failed`（需 resume 重跑）/ `cancelled`。内部的 `main_status` 不对外暴露，**展示与过滤都用 `analysis_status`**。
  - **归档轴**：分析成功后的后处理，字段 `pp_status`（取值 `not_started / running / succeeded / failed / cancelled / skipped`）+ `pp_phase`（取值 `migrate / archive_wait / archive`），等待归档时 `archive_eligible_after` 给到期时间，归档产物路径在 `archive_path`。
  - `analysis_status=succeeded` 时归档轴可能仍在推进；判断"全部完结"须同时看 `pp_status`（`succeeded / skipped` 才算收尾完成）。
  - 跨轴派生字段：`needs_action`（是否需人介入：分析失败或归档失败）、`status_summary`（一句话处境，含归档倒计时/失败指引）。
- **Project SN / Data Number**：`project_sn` 是 LIMS 项目编号，`data_number` 是项目下的数据编号（更细一层）；两者均可用于 `list` 过滤（`-S` / `-D`），`-q` 搜索范围也覆盖 `data_number`。

### 资源关系

```
Pipeline (可选并发控制)
└── Workflow (workflow_id)
    ├── Task (task_id) × N
    ├── Phase: main → post_process (archive ...)
    └── Log (.nextflow.log)
```

## 命令签名速查

参数细节请 `nfctl <cmd> --help`；字段语义可先跑一次 `-f json` 看响应。

```
# 查询
overview
list      [-s ANALYSIS_STATUS][--pp PP_STATUS][-p PIPELINE][--env E][-S PROJECT_SN][-D DATA_NUMBER][-q QUERY][-n N][--page P][--all][--sort F][--sort-order asc|desc]
status    WORKFLOW_ID
progress  WORKFLOW_ID                    # 整体进度 + process 级 pending/running/succeeded/cached/failed/...
tasks     WORKFLOW_ID [-s STATUS][--process P][-n N][--page P][--sort F][--sort-order asc|desc]
task      WORKFLOW_ID TASK_ID
log       WORKFLOW_ID [-n TAIL][-g GREP]
resources WORKFLOW_ID [--exclude-cached]

# 管理
submit    LAUNCH_DIR -p PIPELINE -S PROJECT_SN [-e ENV][--dry-run]   # -S 必填
resume    WORKFLOW_ID                    # 重跑失败/取消的分析（恢复归档用 archive resume）
cancel    WORKFLOW_ID [-r REASON]       # 取消整个分析：running/succeeded 均可，终态置 cancelled 并把作废重推 LIMS
delete    WORKFLOW_ID                    # 仅 failed/cancelled 可删；succeeded 视为合规资产，硬阻止

# 归档/后处理
archive status  WORKFLOW_ID              # 归档轴状态（产物位置/倒计时）+ 最近一次解压任务
archive now     WORKFLOW_ID              # 跳过归档等待期，立即开始归档（仅 archive_wait 阶段可用）
archive resume  WORKFLOW_ID              # 恢复失败/取消的归档或后处理（分析须已成功）
archive restore WORKFLOW_ID [--wait]     # 解压归档产物回 launch_dir 原位（进度用 archive status 查）
archive cancel  WORKFLOW_ID [-r REASON]  # 仅取消归档，保留分析结果（LIMS 仍 100%）

# 配置
config    set KEY VALUE | show | use NAME | list | remove NAME   # 多 profile 管理与切换
pipeline  list | get NAME | create NAME [选项] | update NAME [选项] | delete NAME
          选项: -m N | --enabled/--disabled | --feishu-webhook URL
                --archive/--no-archive | --large-file-threshold T(如 500M;update 传 '' 关迁移)
                --archive-dirs D(逗号分隔,相对 launch_dir) | --archive-delay-hours H
                --stall-timeout-hours H | --execution-timeout-hours H
```

状态值（`analysis_status`）：`queued / running / succeeded / failed / cancelled`。归档轴 `pp_status` 见 Core Concepts。  
排序字段常用：`created_at / updated_at`（list），`task_id / duration`（tasks）。

## 工作流

### 投递并监控

```bash
# 1. dry-run 验证（不实际投递；--project-sn 也是必填）
nfctl -f json submit /data/project/sample1 -p WGS -S P2026001 --dry-run
# 关注 data.can_submit；失败时 data.checks.* 指出哪一项未过

# 2. 投递
nfctl -f json submit /data/project/sample1 -p WGS -S P2026001 -e prod
# 成功返回 data.workflow_id

# 3. 轮询（注意两轴：分析 + 归档都收尾才算全部完成）
nfctl -f json status <workflow_id>
# 分析终态：data.analysis_status ∈ {succeeded, failed, cancelled}
# 进行中：analysis_status ∈ {queued, running}，或 succeeded 且 pp_status ∈ {not_started, running}（归档轴仍在推进）

# 想看每个 process 各自跑到哪：
nfctl -f json progress <workflow_id>
# data.processes[*]: {name, pending, submitted, running, succeeded, cached, failed, aborted}
```

**submit 的隐式流程**：`POST /workflow/validate` → 从 `launch_dir/run.sh` 提取 `TOWER_WORKFLOW_ID` → `POST /workflow/submit`。详见 [`references/submit.md`](references/submit.md)。

### 失败诊断

```bash
# 1. 看状态与错误
nfctl -f json status <workflow_id>
# 关注: analysis_status, status_summary, needs_action, pp_status, pp_phase, error_message

# 2. 定位失败 task
nfctl -f json tasks <workflow_id> -s failed
# 关注: task_id, exit_status, peak_rss, memory, duration

# 3. 任务详情（含 script、workdir）
nfctl -f json task <workflow_id> <task_id>

# 4. 日志关键字过滤
nfctl -f json log <workflow_id> -g "ERROR"

# 5. 资源判读（务必加 --exclude-cached，否则 cached task 拉低效率）
nfctl -f json resources <workflow_id> --exclude-cached
```

资源效率判读见 [`references/resources.md`](references/resources.md)。

### 失败模式速判

| 信号 | 根因 | 处置 |
|------|------|------|
| `exit_status=137`，`peak_rss` 接近 `memory` | OOM Kill | 调大 memory |
| `exit_status=143` | SIGTERM（超时/被杀） | 检查超时设置或并发挤占 |
| 日志含 `No space left` | 磁盘满 | 清理 work 目录或扩容 |
| 日志含 `command not found` | 环境缺失 | 检查 container/module |
| 日志含 `Permission denied` | 权限问题 | 检查目录权限 |
| `cpu_efficiency < 20%`（`--exclude-cached`） | CPU 分配过多 | 降 `cpus` |
| `memory_efficiency < 20%`（`--exclude-cached`） | 内存分配过多 | 降 `memory` |
| `analysis_status=succeeded` 但 `pp_status=failed` | 后处理失败（迁移/归档） | `archive status` 看失败原因与日志指引，修复后 `archive resume` |

### 归档与解压

```bash
# 归档轴一站式状态：产物位置 / 归档倒计时 / 最近一次解压任务进度
nfctl -f json archive status <workflow_id>

# 已归档数据需要回看/续跑时：解压回 launch_dir 原位（大归档可达小时级，--wait 阻塞轮询到完成）
nfctl -f json archive restore <workflow_id> --wait

# 不想等归档延迟到期：立即开始归档（仅 pp_phase=archive_wait 时可用）
nfctl -f json archive now <workflow_id>
```

### 批量投递（并发边界）

- 并发控制下沉到 per-pipeline `max_concurrent`（见 `pipeline list`）；**全局队列阈值已退役**，`overview` 的 `queue_waiting` 仅作 SGE 等待数监控，无上限字段
- **submit 不再因并发满拒绝**：达到该 pipeline 的 `max_concurrent` 时，新投递照常受理（202），但挂起等待空位，`analysis_status=queued`，有空位后由服务端自动启动 → 无需 Agent 自己限流；放心逐个投
- 想看哪些在排队：`list -s queued`（已受理未启动）vs `list -s running`（已启动在跑）
- 批量投递 = 逐个 `submit`（无 `submit-batch` 命令）
- 部分失败时，成功的 workflow_id 已落库，可用 `list --status failed` 收集、`resume` 或 `delete` 后重投

## 何时读 references/

- **排查资源效率问题**、判读 `cpu_efficiency` / `memory_efficiency` 数值 → [`references/resources.md`](references/resources.md)
- **首次投递**、需要理解 `--dry-run` 到底校验了什么、`env` 与 `project_sn` 的业务语义 → [`references/submit.md`](references/submit.md)

其他命令的参数和响应字段直接 `nfctl <cmd> --help` + 跑一次 `-f json` 看即可，不需要额外文档。
