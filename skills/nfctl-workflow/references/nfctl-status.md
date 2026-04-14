# nfctl status

工作流详情：状态、进度、元数据、错误信息。

```bash
nfctl -f json status <workflow_id>
```

## 响应

```json
{
  "ok": true,
  "data": {
    "workflow_id": "wf-001",
    "status": "failed",
    "progress_percent": 75.0,
    "pipeline_name": "WGS",
    "env": "prod",
    "launch_dir": "/data/project/sample1",
    "run_name": "happy_eagle",
    "sge_job_id": "12345",
    "error_message": "Process exceeded memory limit",
    "error_report": "task BWA_MEM (1) failed",
    "start_time": "2026-04-13T10:00:00",
    "complete_time": "2026-04-13T12:30:00",
    "duration": 9000000,
    "exit_status": 1,
    "success": false
  }
}
```

## 关键字段

- `status`: pending / running / succeeded / failed / cancelled
- `error_message`: Nextflow 报告的错误信息
- `error_report`: 详细错误报告（含失败 task 信息）
- `duration`: 毫秒
