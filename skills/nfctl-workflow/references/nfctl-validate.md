# nfctl validate

投递前验证：检查 Pipeline 容量、队列、run.sh 脚本、workflow_id。

```bash
nfctl validate --pipeline WGS --format json
nfctl validate --pipeline WGS --launch-dir /data/project/sample1 --format json
```

## 参数

| 参数 | 说明 |
|------|------|
| `--pipeline` / `-p` | Pipeline 名称（必填） |
| `--launch-dir` / `-d` | 分析目录（可选，传入后做完整验证） |

## 响应

```json
{
  "ok": true,
  "data": {
    "can_submit": true,
    "checks": {
      "capacity": {"passed": true, "detail": "running=2, limit=5"},
      "queue": {"passed": true, "detail": "waiting=3, limit=50"},
      "script": {"passed": true, "detail": "run.sh found"},
      "workflow_id": {"passed": true, "detail": "TOWER_WORKFLOW_ID=wf-001"}
    }
  }
}
```

## 判断

- `can_submit=false` 时读取 `checks` 中 `passed=false` 的项
- 只传 `--pipeline` 时仅检查容量和队列
- 传 `--launch-dir` 时额外检查 run.sh 和 workflow_id
