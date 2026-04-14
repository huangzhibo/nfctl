---
name: nfctl-batch
version: 1.0.0
description: "批量投递和监控多个 Nextflow 工作流。当用户需要批量运行多个样本、并行监控、汇总结果时触发。"
metadata:
  requires:
    bins: ["nfctl"]
  cliHelp: "nfctl --help"
---

# batch (v1)

**CRITICAL — 开始前 MUST 先用 Read 工具读取 [`../nfctl-shared/SKILL.md`](../nfctl-shared/SKILL.md) 和 [`../nfctl-workflow/SKILL.md`](../nfctl-workflow/SKILL.md)**

## 批量投递流程

```bash
# 1. 检查 pipeline 容量
nfctl -f json pipeline list
nfctl -f json overview

# 2. 逐个验证（dry-run）
nfctl -f json submit /data/project/sample1 --pipeline WGS --dry-run
nfctl -f json submit /data/project/sample2 --pipeline WGS --dry-run
# ... 全部通过后再投递

# 3. 逐个投递（注意并发限制）
nfctl -f json -q submit /data/project/sample1 --pipeline WGS --env prod
nfctl -f json -q submit /data/project/sample2 --pipeline WGS --env prod

# 4. 监控
nfctl -f json list --pipeline WGS --status running

# 5. 查看结果
nfctl -f json list --pipeline WGS --status failed
nfctl -f json list --pipeline WGS --status succeeded
```

## 注意事项

- 投递前检查 `pipeline list` 的 `max_concurrent`，避免超过并发限制
- `overview` 的 `queue_waiting` 接近 `queue_waiting_limit` 时暂停投递
- 全部投递后用 `list --status running` 轮询，直到全部完成
- 失败的 workflow 用 nfctl-workflow skill 的诊断流程逐个排查
