# nfctl

Nextflow Monitor Agent CLI — 面向生信工程师和 AI Agent 的命令行工具。

## 安装

```bash
pip install nfctl
```

## 配置

```bash
# 设置 Agent URL（默认 http://localhost:8000）
nfctl config set url http://agent-host:8000

# 或通过环境变量
export NFCTL_URL=http://agent-host:8000
```

## 命令

```bash
nfctl overview                           # 系统概览
nfctl list [--status running] [-n 20]    # 工作流列表
nfctl status <id>                        # 工作流详情
nfctl tasks <id> [--status failed]       # 子任务列表
nfctl log <id> [--grep ERROR]            # 日志查看
nfctl resources <id>                     # 资源统计

nfctl submit <dir> --pipeline <name>     # 投递工作流
nfctl validate --pipeline <name>         # 投递前验证
nfctl resume <id>                        # 恢复失败/取消的工作流
nfctl cancel <id>                        # 取消运行中的流程
nfctl delete <id>                        # 删除工作流

nfctl pipeline list                      # Pipeline 配置
nfctl config set/show                    # 配置管理
```

## AI Agent 使用

所有命令支持 `--format json`，输出标准信封格式：

```bash
nfctl --format json list
# {"ok": true, "data": {"total": 5, "items": [...]}}
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
