# nfctl overview

系统概览：运行/待机/成功/失败统计 + Pipeline 分布 + 队列状态。

```bash
nfctl -f json overview
```

## 响应

```json
{
  "ok": true,
  "data": {
    "running": 3,
    "pending": 1,
    "succeeded": 10,
    "failed": 2,
    "cancelled": 0,
    "total": 16,
    "by_pipeline": [
      {"pipeline_name": "WGS", "running": 2, "pending": 0, "succeeded": 5, "failed": 1}
    ],
    "queue_waiting": 5,
    "queue_waiting_limit": 50
  }
}
```
