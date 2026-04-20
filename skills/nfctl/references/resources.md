# resources 的效率判读

`nfctl resources <workflow_id>` 返回工作流聚合的 CPU / 内存 / IO / 时长指标。关键是**读懂数字**而不是罗列数字。

## 必须用 `--exclude-cached`

Nextflow 的 `-resume` 会复用上次成功的 task（状态 `CACHED`），这些 task 在 resources 聚合里会计入「请求」（requested）但不会计入「实际使用」（used），导致效率指标被严重拉低。

**实测对比**（同一 workflow，160 个 task 中 159 个 cached，仅 1 个真跑）：

```bash
# 默认（含 cached）：看起来 CPU 严重浪费
resources <id>
# cpu_efficiency = 28.84%
# cpu_time_used = 5.3 CPU-hours / requested = 18.4 CPU-hours
# memory_efficiency = 17.53%
# task_count = 160

# --exclude-cached：反映本次真实运行
resources <id> --exclude-cached
# cpu_efficiency = 98.3%        ← 真实表现
# cpu_time_used = 1.2 CPU-minutes / requested = 1.2 CPU-minutes
# memory_efficiency = 20.24%
# task_count = 1
```

规则：**任何以"调优 resources 分配"为目的的效率判读，一律加 `--exclude-cached`**。
若想评估「整条流程对机器的占用」（而非单次运行的效率），再去掉该标志。

## cpu_efficiency 判读

`cpu_efficiency = cpu_time_used / cpu_time_requested × 100%`。

- **> 80%**：资源分配合理
- **50–80%**：略有浪费，可考虑微调
- **20–50%**：CPU 明显过量，建议降 `cpus`
- **< 20%**：严重过量；或者工作负载是 IO-bound，加 CPU 也无用
- **> 100%**：出现在 `pcpu` 单 task 级别很正常（多线程），但聚合 efficiency 不会 > 100%

注意：单个 task 的 `pcpu` 可以 >> 100%（如 `1983.7%` 代表约 20 核满载），不是异常。

## memory_efficiency 判读

`memory_efficiency = peak_rss / memory_requested × 100%`。

- **50–80%**：合理留余量（避免偶发尖峰触发 OOM Kill）
- **20–50%**：内存请求偏高，可以降
- **< 20%**：严重过量，降 `memory`
- **> 80%**：**危险**，留余量不足，任何尖峰都可能 OOM（exit_status=137）

诊断 OOM 时对照单个 failed task：`peak_rss` 接近或超过 `memory` → OOM。`peak_vmem` 远高于 `peak_rss` 是正常的（虚拟内存含未 commit 的 mmap），不是 OOM 信号。

## IO 与时长

- `io_read_bytes` / `io_write_bytes`：聚合值，用于判断 IO 负载量级
- `time_duration_seconds`：wall-clock（墙上时间，实际从开始到结束）
- `task_time_used_seconds`：所有 task 实际运行时间之和（含并行叠加）
- `task_time_used / time_duration` 可粗略看并行度

## 常见误判

- 只看总 `cpu_efficiency` 低就喊浪费 → 忘了排除 cached；真正指标要看 `--exclude-cached`
- `peak_vmem >> memory_requested` 就判 OOM → 错，要看 `peak_rss`
- `memory_efficiency = 100%` 以为最优 → 没留余量，随时 OOM，目标应是 50–80%
