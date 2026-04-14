# nfctl tasks

子任务列表，支持状态过滤和 process 过滤。

```bash
nfctl tasks <workflow_id> --format json
nfctl tasks <workflow_id> --status failed --format json
nfctl tasks <workflow_id> --process BWA_MEM --format json
```

## 参数

| 参数 | 说明 |
|------|------|
| `--status` / `-s` | 状态过滤（RUNNING/COMPLETED/FAILED/CACHED） |
| `--process` | Process 名称过滤 |
| `-n` | 每页条数（默认 50） |
| `--page` | 页码 |

## 响应

```json
{
  "ok": true,
  "data": {
    "workflow_id": "wf-001",
    "total": 2,
    "tasks": [
      {
        "task_id": 1,
        "process": "BWA_MEM",
        "name": "BWA_MEM (sample1)",
        "status": "FAILED",
        "exit_status": 137,
        "duration": 600000,
        "peak_rss": 8589934592,
        "cpus": 4,
        "memory": 8589934592
      }
    ]
  }
}
```

## 诊断要点

- `exit_status=137` + `peak_rss` 接近 `memory` → OOM Kill
- `status=CACHED` 的 task 是缓存复用，不消耗资源
