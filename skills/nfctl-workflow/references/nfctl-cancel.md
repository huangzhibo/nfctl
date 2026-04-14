# nfctl cancel

取消运行中的工作流。发送 cancel signal 给 Temporal workflow。

```bash
nfctl cancel <workflow_id> --format json --quiet
nfctl cancel <workflow_id> --reason "内存不足需调整参数" --format json --quiet
```

## 参数

| 参数 | 说明 |
|------|------|
| `workflow_id` | Workflow ID（必填） |
| `--reason` / `-r` | 取消原因（可选） |

## 响应

```json
{
  "ok": true,
  "data": {
    "workflow_id": "wf-001",
    "main_job_killed": true,
    "sub_jobs_killed": 0
  }
}
```

## 注意

- `--quiet` 跳过确认（AI Agent 必须加此选项）
- 只能取消 running/pending 状态的流程
- 已结束的流程返回错误
