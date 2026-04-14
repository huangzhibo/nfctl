# nfctl log

查看 Nextflow 日志，支持 tail 和 grep。

```bash
nfctl -f json log <workflow_id>
nfctl -f json log <workflow_id> --grep ERROR
nfctl -f json log <workflow_id> --tail 50 --grep "OOM\|memory"
```

## 参数

| 参数 | 说明 |
|------|------|
| `--tail` / `-n` | 显示最后 N 行（默认 100） |
| `--grep` / `-g` | 过滤关键词 |

## 响应

```json
{
  "ok": true,
  "data": {
    "workflow_id": "wf-001",
    "log_file": "/data/project/sample1/.nextflow.log",
    "total_lines": 1500,
    "lines": [
      "ERROR: Process `BWA_MEM (sample1)` terminated with an error exit status (137)"
    ]
  }
}
```
