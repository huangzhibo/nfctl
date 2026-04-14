# nfctl list

工作流列表，支持状态过滤、Pipeline 过滤、关键词搜索、分页排序。

```bash
nfctl -f json list
nfctl -f json list --status running,failed --pipeline WGS -n 10
nfctl -f json list --query sample123
nfctl -f json list --all                    # 自动遍历所有分页
```

## 参数

| 参数 | 说明 |
|------|------|
| `--status` / `-s` | 状态过滤（逗号分隔：running,failed,succeeded,cancelled,pending） |
| `--pipeline` / `-p` | Pipeline 名称过滤 |
| `--env` | 环境过滤（test/gray/prod） |
| `--query` / `-q` | 搜索 workflow_id 或 launch_dir |
| `-n` | 每页条数（默认 20） |
| `--page` | 页码（默认 1） |
| `--all` | 自动遍历所有分页 |
| `--sort` | 排序字段（默认 created_at） |
| `--sort-order` | 排序方向 asc/desc（默认 desc） |

## 响应

```json
{
  "ok": true,
  "data": {
    "total": 42,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "workflow_id": "wf-001",
        "status": "running",
        "progress_percent": 45.0,
        "pipeline_name": "WGS",
        "env": "prod",
        "updated_at": "2026-04-13T10:00:00"
      }
    ]
  }
}
```
