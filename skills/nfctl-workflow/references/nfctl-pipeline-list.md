# nfctl pipeline list

列出所有 Pipeline 配置（名称、并发限制、启用状态）。

```bash
nfctl pipeline list --format json
```

## 响应

```json
{
  "ok": true,
  "data": [
    {"pipeline_name": "WGS", "max_concurrent": 5, "enabled": true},
    {"pipeline_name": "RNA-seq", "max_concurrent": 3, "enabled": true},
    {"pipeline_name": "Exome", "max_concurrent": 2, "enabled": false}
  ]
}
```

## 用途

- 投递前确认 Pipeline 存在且已启用
- 查看并发限制以规划批量投递
