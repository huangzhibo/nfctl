# nfctl task

子任务详情，查看单个 task 的完整信息（script、workdir、资源占用等）。

```bash
nfctl -f json task <workflow_id> <task_id>
```

## 参数

| 参数 | 说明 |
|------|------|
| `workflow_id` | Workflow ID |
| `task_id` | Task ID |

## 响应

```json
{
  "ok": true,
  "data": {
    "task_id": 1,
    "workflow_id": "wf-001",
    "process": "BWA_MEM",
    "name": "BWA_MEM (sample1)",
    "status": "FAILED",
    "hash": "ab/cd1234",
    "workdir": "/work/ab/cd1234",
    "script": "bwa mem -t 4 ref.fa input.fq",
    "container": "biocontainers/bwa:0.7.17",
    "cpus": 4,
    "memory": 8589934592,
    "exit_status": 137,
    "duration": 600000,
    "realtime": 580000,
    "peak_rss": 8500000000,
    "peak_vmem": 12000000000,
    "pcpu": 350.0,
    "queue": "all.q",
    "error_action": "FINISH"
  }
}
```

## 诊断要点

- `workdir` 可直接查看 task 的 `.command.sh`、`.command.log`、`.exitcode` 等文件
- `script` 显示实际执行的命令，用于排查参数错误
- `peak_rss` 接近 `memory` + `exit_status=137` → OOM Kill
- `error_action` 为 RETRY 时表示 Nextflow 已自动重试
