# resources 的效率判读

`nfctl resources <workflow_id>` 返回工作流聚合的 CPU / 内存 / IO / 时长指标。关键是**读懂数字**而不是罗列数字。

## Nextflow 基础：cached task 是什么

`-resume` 执行时，Nextflow 对每个 task 计算输入哈希；哈希命中上次成功的结果就跳过执行，标记为 `CACHED`，直接复用历史 workdir 的输出。**cached task 本次没有真正消耗资源**，但聚合里会**保留它第一次真正成功时的 used / requested 指标**（不是 0，也不是本次的值）。

`--exclude-cached` 的字面含义：从聚合里剔除 `status=CACHED` 的 task。

## 默认 vs `--exclude-cached` 的视角差异

| 视角 | 用途 |
|------|------|
| 默认（含 cached） | 看整条 pipeline 的**历史聚合画像** |
| `--exclude-cached` | 看**本次 resume 真正新跑的 task**，用于判断当下分配是否合理 |

**调优资源分配时必须加 `--exclude-cached`**——否则读到的是历史均值，未必反映当下。

## 实测对比（真实数据）

同一 workflow，160 个 task 中 159 个 CACHED、仅 1 个本次真跑：

```
                         默认          --exclude-cached
task_count               160           1
cpu_time_used            5.3 h         1.2 min
cpu_time_requested       18.4 h        1.2 min
cpu_efficiency           28.84%        98.3%
memory_peak_rss          22.3 GB       414 MB
memory_requested         672 GB        2 GB
memory_efficiency        17.53%        20.24%
```

数据校验（自我保护习惯）：
- 默认 used − exclude-cached used = 159 个 cached 历史贡献的 used
  = 19053 − 71 = **18982 秒**（不为 0，证明 cached 对 used 也有贡献）
- 如果谁告诉你"cached 只进 requested 不进 used"，用这条算式直接证伪

## cpu_efficiency 判读（加 `--exclude-cached` 后）

`cpu_efficiency = cpu_time_used / cpu_time_requested × 100%`

- **> 80%**：资源分配合理
- **50–80%**：略有浪费，可微调
- **20–50%**：CPU 明显过量，建议降 `cpus`
- **< 20%**：严重过量；或工作负载是 IO-bound，加 CPU 也无用

单个 task 的 `pcpu` 可以 >> 100%（多线程，如 `1983.7%` ≈ 20 核满载），属正常；但聚合的 `cpu_efficiency` 不会 > 100%。

## memory_efficiency 判读（加 `--exclude-cached` 后）

`memory_efficiency = peak_rss / memory_requested × 100%`

- **50–80%**：合理，留有余量抗尖峰
- **20–50%**：请求偏高，可以降
- **< 20%**：严重过量
- **> 80%**：**危险**，余量不足，尖峰可能触发 OOM

诊断 OOM：看单个 failed task 的 `peak_rss` 是否接近 `memory`。  
`peak_vmem >> peak_rss` 是正常的（含未 commit 的 mmap），**不是** OOM 信号。

## IO 与时长

- `io_read_bytes` / `io_write_bytes`：聚合 IO 量
- `time_duration_seconds`：wall-clock（流程实际从开始到结束）
- `task_time_used_seconds`：所有 task 运行时间之和（含并行叠加）
- `task_time_used / time_duration` 可粗估并行度

## 常见误判（含我自己犯过的）

- **"cached 只进 requested 不进 used" → 错**。两边都进，进的是历史值。用默认 − exclude 差额（如 19053 − 71 = 18982 秒）可立即证伪。
- 只看默认模式的 `cpu_efficiency` 低就喊浪费 → 忘了这是历史均值，调优要看 `--exclude-cached`。
- `peak_vmem >> memory_requested` 就判 OOM → 错，要看 `peak_rss`。
- `memory_efficiency = 100%` 以为最优 → 没留余量，随时 OOM；目标是 50–80%。
