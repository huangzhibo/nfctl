# nfctl

nf-server CLI — 面向生信工程师和 AI Agent 的命令行工具。

## 安装

```bash
pip install nfctl
```

## 配置

```bash
# 设置服务地址（默认 http://localhost:8000）
nfctl config set url http://nf-server:8000

# 或通过环境变量
export NFCTL_URL=http://nf-server:8000
```

## 命令

### 查询

```bash
nfctl overview                           # 系统概览
nfctl list [--status running] [-n 20]    # 工作流列表
nfctl list --all                         # 获取全部工作流（自动翻页）
nfctl list --sort created_at --sort-order asc  # 按创建时间升序
nfctl list --pipeline WGS --env prod     # 按 Pipeline / 环境过滤
nfctl list --project-sn P2026001         # 按 LIMS 项目编号过滤
nfctl list --query sample1               # 按 workflow_id / launch_dir 搜索
nfctl status <id>                        # 工作流详情
nfctl progress <id>                      # 进度（含 process 级别明细）
nfctl tasks <id> [--status failed]       # 子任务列表
nfctl tasks <id> --sort duration --sort-order desc  # 按耗时排序
nfctl task <id> <task_id>                # 子任务详情
nfctl log <id> [--grep ERROR]            # 日志查看
nfctl resources <id>                     # 资源统计
```

### 管理

```bash
nfctl submit <dir> -p <name> -S P2026001                 # 投递工作流（--project-sn 必填）
nfctl submit <dir> -p <name> -S P2026001 --env prod      # 指定环境（test/gray/prod）
nfctl submit <dir> -p <name> -S P2026001 --dry-run       # 仅验证，不实际投递
nfctl resume <id>                                        # 恢复失败/取消的工作流
nfctl cancel <id> [--reason "原因"]                      # 取消运行中的流程
nfctl delete <id>                                        # 删除工作流（succeeded 不可删）
```

### 其他

```bash
nfctl pipeline list                      # Pipeline 配置
nfctl config set/show                    # 配置管理
```

## 手动 submit 场景

LIMS 本身就是通过 `nfctl submit` 通道向 nf-server 投递 nextflow 任务的。日常分析任务由 LIMS 自动触发,无需手动操作。以下两种情况需要手动 submit:

1. **LIMS 未正常触发投递**:作为应急补投手段。
2. **本地独立流程**:不需要同步到 LIMS2 云平台的分析任务。

**只有走过 submit 通道的任务(LIMS 自动触发或手动补投均可),nf-server 才会记录这个任务,才能监控状态、查日志、续跑。**

### 用法

| 参数 | 说明 |
|------|------|
| `-p, --pipeline` | Pipeline 名称(必填) |
| `-S, --project-sn` | LIMS 项目编号(必填) |
| `-e, --env` | 环境,可选 `test` / `gray` / `prod`;**省略则不转发到 LIMS2 云平台**,按本地独立流程处理 |
| `--dry-run` | 仅校验参数,不实际投递 |

```bash
# 场景 1:LIMS 应急补投(同步到云平台)
nfctl submit /path/to/launch_dir -p WGS -S P2026001 -e prod

# 场景 2:本地独立流程(不同步云平台)
nfctl submit /path/to/launch_dir -p WGS -S P2026001
```

### resume 与 qsub 的衔接

- ✅ 走过 submit → 失败后可 `nfctl resume <workflow_id>` 续跑;手动 `qsub run.sh` 接管也能被识别为同一任务。
- ❌ 没走过 submit、直接 qsub → nf-server 无记录,无法 resume,也无法监控,且没有补救路径。

## AI Agent 使用

所有命令支持 `--format json`，输出标准信封格式：

```bash
nfctl -f json list
# {"ok": true, "data": {"total": 5, "items": [...]}}
```

使用 `--jq` 过滤 JSON 输出：

```bash
nfctl --jq '.data.items[].workflow_id' list
nfctl --jq '.data.items[] | select(.status=="failed")' list
```

安装 Agent Skills：

```bash
npx skills add huangzhibo/nfctl
```

## 开发

```bash
uv sync
uv run nfctl --help
uv run pytest
```

提交前自动跑 ruff（首次 clone 后执行一次）：

```bash
uv tool install pre-commit   # 或 brew install pre-commit / pipx install pre-commit
pre-commit install
```
