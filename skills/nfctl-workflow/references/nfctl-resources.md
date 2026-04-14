# nfctl resources

资源使用统计：CPU/内存效率、IO、时间。

```bash
nfctl -f json resources <workflow_id>
nfctl -f json resources <workflow_id> --exclude-cached
```

## 参数

| 参数 | 说明 |
|------|------|
| `--exclude-cached` | 排除 CACHED task（更准确反映实际资源消耗） |

## 响应

```json
{
  "ok": true,
  "data": {
    "workflow_id": "wf-001",
    "task_count": 15,
    "cpu_efficiency": 67.5,
    "cpu_time_used_human": "2h 30m",
    "cpu_time_requested_human": "3h 42m",
    "memory_peak_rss": 17179869184,
    "memory_requested": 34359738368,
    "memory_efficiency": 50.0,
    "io_read_bytes": 107374182400,
    "io_write_bytes": 53687091200,
    "time_duration_human": "1h 15m"
  }
}
```

## 判断标准

- `cpu_efficiency < 30%` → CPU 过度分配，建议降低 cpus
- `memory_efficiency > 90%` → 内存接近上限，有 OOM 风险
- `memory_peak_rss` 接近 `memory_requested` → 需要增加内存
