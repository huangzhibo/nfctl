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
nfctl tasks <id> [--status failed]       # 子任务列表
nfctl tasks <id> --sort duration --sort-order desc  # 按耗时排序
nfctl task <id> <task_id>                # 子任务详情
nfctl log <id> [--grep ERROR]            # 日志查看
nfctl resources <id>                     # 资源统计
```

### 管理

```bash
nfctl submit <dir> --pipeline <name>                     # 投递工作流
nfctl submit <dir> --pipeline <name> --env prod          # 指定环境（test/gray/prod）
nfctl submit <dir> --pipeline <name> --project-sn P2026001  # 绑定 LIMS 项目编号
nfctl submit <dir> --pipeline <name> --dry-run           # 仅验证，不实际投递
nfctl resume <id>                                        # 恢复失败/取消的工作流
nfctl cancel <id> [--reason "原因"]                      # 取消运行中的流程
nfctl delete <id>                                        # 删除工作流
```

### 其他

```bash
nfctl pipeline list                      # Pipeline 配置
nfctl config set/show                    # 配置管理
```

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
