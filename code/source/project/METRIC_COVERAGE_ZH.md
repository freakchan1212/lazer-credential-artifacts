# 截图指标逐项覆盖与验收

冻结范围是官方匿名凭证示例，不是全套LaZer应用、全部论文实验或新增安全证明。

| 截图项目 | 实现与输出 | 验收依据 |
|---|---|---|
| P01 出示生成 | experiment_worker.py timed；performance_metrics.csv p2_prove_ms | 逐次样本独立复算均值/中位数/P95 |
| P02 出示验证 | p2_verify_ms | 同上；与生成分列 |
| P03 出示证明大小 | presentation_proof_bytes，min/max | 实际len(proof)；披露24B单列；API容器64B另列 |
| P04 签发时间/通信 | p1_prove_ms、p1_verify_and_issue_ms、request/blind bytes、issuance_payload_total_bytes | fresh逐次；steady setup一次；不拆改发行者原sign方法 |
| P05 初始化/预处理 | 模块导入含公共参数展开、keygen、user/issuer/verifier init | setup_metrics.csv；不混入出示延迟；不冒充OS冷缓存启动 |
| P06 峰值内存 | resource.ru_maxrss KiB | 各负载隔离进程生命周期峰值，含导入和setup；不解释为每阶段内存 |
| P07 内部重试/合法失败 | P1/issue/P2各8计数；合法失败、超预算、未完成、进程超时 | 计数恒等式；所有样本保留；分母明确；预算不终止原算法 |
| S01 经典攻击成本 | security/attack_costs.csv classical_log2_cost | 固定ADPS16 Core-SVP 0.292*beta，声明通用攻击覆盖 |
| S02 量子攻击成本 | quantum_log2_cost | 单独0.265*beta；不把经典位数减半 |
| S03 不可伪造性 | security_properties.csv S03 | 保留BLNS条件性分析；辅助提示假设/提取/归约不可被Falcon单项替代；无新数值全协议界 |
| S04 匿名/不可关联 | S04，原P2关系与新随机证明 | 披露/隐藏位置、对手与可识别公开信息限制明确；随机证明去重只是回归检查 |
| S05 知识可靠性 | knowledge_bounds.json与原参数头 | 原MSIS条件下2^-127，复算挑战空间及放大公式；不等同FS整体安全位数 |
| S06 零知识误差 | S06，原MLWE模拟声明、原sigma/M/拒绝机制元数据 | 计算零知识条件保持；未独立给出数值统计距离或总优势界；不伪称已算 |

均值/中位数/P95是默认；P99只在样本数>=100输出；均值区间仅是n>=30时的正态近似，长尾样本使用时需谨慎。零失败单侧95%上界采用1-0.05^(1/n)，前提是独立同分布Bernoulli，仅为可用性统计。

内部计数覆盖范围：range外层尝试、z3/z4拒绝，quadratic外层尝试、z1/z2/范数拒绝，Falcon原像采样外层尝试。不是每一个标量高斯底层采样步骤、密钥生成或消息r采样的全量计数。

没有缺项被悄悄删除。S03/S04/S06的条件性/非数值边界在冻结时即明确；若要求这些项目都有独立数值安全界，该理论目标尚未完成，本包不宣称完成。
