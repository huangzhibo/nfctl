# submit 的隐式流程与参数语义

`nfctl submit` 背后不是单次 HTTP 调用，而是一套链路。理解这套链路能让你在 dry-run 失败时准确定位问题。

## 隐式流程

```
submit <launch_dir> -p <pipeline>
  │
  ├─► POST /workflow/validate
  │     输入: pipeline_name, launch_dir
  │     校验: capacity（并发未超限）、run_sh（存在且合法）、workflow_id（可从 run.sh 提取）
  │     输出: can_submit + checks.{capacity, workflow_id, run_sh}.{passed, detail}
  │
  ├─► 从 checks.workflow_id.detail 解析 "TOWER_WORKFLOW_ID=xxx"
  │
  └─► POST /workflow/submit（仅当 --dry-run 未设置）
        输入: workflow_id, launch_dir, pipeline_name, project_sn（必填），可选 env
        输出: data.workflow_id, data.pipeline_name
```

**--dry-run** 只跑到 validate 为止，不实际启动；可反复执行，不会改变服务端状态。

## workflow_id 从哪里来

不是服务端生成，不是用户传入，而是从 `<launch_dir>/run.sh` 中匹配 `TOWER_WORKFLOW_ID=xxx`。如果 run.sh 缺少这一行，validate 会在 `workflow_id` 这一项失败。

提示：同一 workflow_id 重复投递会返回 `CONFLICT`（退出码 5），先 `cancel` 或等到终态 `delete`。

## 参数语义

| 参数 | 语义 | 关键点 |
|------|------|--------|
| `launch_dir`（位置参数） | 分析工作目录，必须含可执行的 `run.sh` | 路径是服务端可见的绝对路径 |
| `-p / --pipeline` | Pipeline 名称，决定并发配额和后处理策略 | 必须是 `pipeline list` 里已注册的名字 |
| `-e / --env` | 运行环境：`test` / `gray` / `prod` | 决定下游系统（LIMS/存储/归档）走哪一套；**不影响 run.sh 执行**；可省略 |
| `-S / --project-sn` | LIMS 项目编号（**必填**） | 业务归档与 launch_dir 所有权校验；与 `--env` 正交 |
| `--dry-run` | 只 validate 不 submit | 服务端幂等，可重复调用；**仍需提供 `-S`**（CLI 层校验） |

## dry-run 响应字段

```json
{
  "ok": true,
  "data": {
    "can_submit": true,
    "checks": {
      "capacity":    {"passed": true,  "detail": "running=2, limit=5"},
      "run_sh":      {"passed": true,  "detail": "OK"},
      "workflow_id": {"passed": true,  "detail": "TOWER_WORKFLOW_ID=wf-xxx"}
    }
  }
}
```

任何一项 `passed=false` → `can_submit=false`，服务端返回 `VALIDATION_ERROR`（退出码 2），`error.message` 取未通过项的 `detail`。

## 常见失败

| 症状 | 根因 | 处置 |
|------|------|------|
| `capacity` 未通过 | 该 pipeline 并发已满 | 等一轮、或 `pipeline update -m` 调大 `max_concurrent` |
| `workflow_id` 未通过，detail "无法提取" | run.sh 没写 `TOWER_WORKFLOW_ID=` | 补上这一行 |
| `run_sh` 未通过 | 路径不存在或不可读 | 检查 `launch_dir` 在服务端视角下是否有效 |
| 投递成功后立即 `CONFLICT` | 同 workflow_id 已有在跑任务 | `list` 查重，先 cancel 或 delete |

## 投递后

响应含 `data.workflow_id` 与 `data.pipeline_name`。**Agent 必须保存 `workflow_id` 才能后续 status/tasks/log/cancel**。
若 Agent 会话中失联 workflow_id，用 `list -q <launch_dir 关键词>` 反查。
