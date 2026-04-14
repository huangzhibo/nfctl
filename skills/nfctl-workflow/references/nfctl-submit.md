# nfctl submit

投递工作流。自动验证 → 创建 DB 记录 → 启动 Temporal workflow → qsub。

```bash
nfctl -f json -q submit <launch_dir> --pipeline <name>
nfctl -f json -q submit /data/project/sample1 --pipeline WGS --env prod
nfctl -f json submit /data/project/sample1 --pipeline WGS --dry-run
```

## 参数

| 参数 | 说明 |
|------|------|
| `launch_dir` | 分析目录路径（必须包含 run.sh） |
| `--pipeline` / `-p` | Pipeline 名称（必填） |
| `--env` / `-e` | 环境：test / gray / prod（可选，有 env 时校验 project_id） |
| `--dry-run` | 仅验证，不实际投递（检查容量、run.sh、workflow_id） |

## 响应

```json
{
  "ok": true,
  "data": {
    "workflow_id": "wf-001",
    "pipeline_name": "WGS"
  }
}
```

`--dry-run` 响应：

```json
{
  "ok": true,
  "data": {
    "can_submit": true,
    "checks": {
      "capacity": {"passed": true, "detail": "running=2, limit=5"},
      "workflow_id": {"passed": true, "detail": "TOWER_WORKFLOW_ID=wf-001"},
      "run_sh": {"passed": true, "detail": "OK"}
    }
  }
}
```

## 注意

- 投递前自动执行验证，不通过直接返回错误
- `--dry-run` 只跑验证步骤，不实际投递
- `--quiet` 跳过确认（AI Agent 必须加此选项）
- workflow_id 从 launch_dir/run.sh 中的 TOWER_WORKFLOW_ID 读取
- 同一 workflow_id 重复投递：running/pending 返回 409 CONFLICT
