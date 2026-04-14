# nfctl delete

删除工作流记录 + 分析目录。仅允许终态（succeeded/failed/cancelled）。

```bash
nfctl delete <workflow_id> --format json --quiet
```

## 参数

| 参数 | 说明 |
|------|------|
| `workflow_id` | Workflow ID（必填） |

## 响应

```json
{
  "ok": true,
  "data": {
    "workflow_id": "wf-001",
    "deleted_tasks": 15
  }
}
```

## 注意

- `--quiet` 跳过确认（AI Agent 必须加此选项）
- running/pending 状态拒绝删除，需先 cancel
- 会级联删除子任务、进度记录和分析目录
- 操作不可恢复
