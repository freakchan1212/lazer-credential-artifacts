# 原装配置基线实验报告

机器：AMD EPYC 9V74 80-Core Processor；状态：EXPERIMENT_CHECKS_PASSED

本报告使用官方原始协议、参数和验证API；只有计时、RSS和重试计数。没有会话扩展、额外验证条件或安全降参。

| 负载 | 接受/计划 | 生成均值 ms | 验证均值 ms | P95总时间 ms | 证明 B | 进程峰值RSS MiB |
|---|---:|---:|---:|---:|---:|---:|
| raw_steady | 30/30 | 126.43 | 49.76 | 356.44 | 29113.37 | 63.64 |
| raw_fresh | 30/30 | 129.29 | 49.56 | 381.11 | 29118.17 | 79.55 |

时间不含网络；签发、初始化、CPU time、重试次数详见CSV/JSON。fresh每次重新签发，steady一次签发多次出示；两者协议和参数相同。RSS是子进程生命周期峰值。

## 上游原始安全配置

上游生成器目标：128位。按原参数原样记录；这里没有重新给协议定级。条件性安全声明仍依赖原方案假设和分析。

| 项目 | P1 | P2 |
|---|---|---|
| 证明环次数 | 64 | 64 |
| 证明内部模数 | 2199023255717 | 1125899906843221 |
| 原知识错误上界log2 | -127.0 | -127.0 |
| 原MSIS根Hermite因子 | 1.0043951 | 1.0043793 |
| 原MLWE根Hermite因子 | 1.0043734 | 1.0043146 |
| 原理论重复率 | 6.8220576 | 6.6355669 |

原关系环次数64、模数12289，P1矩阵8×24，P2矩阵8×48；披露下标[0,4,5]。参数头、矩阵、范数、采样分布和Fiat–Shamir不改。

## 原API预期行为检查

| 用例 | 预期 | 实际 | 符合预期 |
|---|---|---|---|
| raw_honest | ACCEPT | ACCEPT | True |
| raw_repeat_same_proof | ACCEPT_ORIGINAL_BEHAVIOR | ACCEPT | True |
| raw_changed_public_attribute | REJECT | REJECT | True |
| raw_wrong_issuer | REJECT | REJECT | True |
| raw_bitflip | REJECT | REJECT | True |
| raw_wrong_disclosure | REJECT | REJECT | True |
| raw_trailing | ACCEPT_ORIGINAL_BEHAVIOR | ACCEPT | True |
| raw_hidden_slot_injection | ACCEPT_ORIGINAL_BEHAVIOR | ACCEPT | True |
| p1_bitflip | REJECT | REJECT | True |

重复提交、证明后追加字节、未披露槽位内容被忽略，按原API行为记录，不偷偷增加拒绝检查。它们不应被本实验包装成已实现的会话防重放或严格传输解析。

没有把新的模型估计强加到原始参数上。08_security_sage.sh仅为单独研究估计器入口，不会更改协议或参数；默认未运行。

本次小样本测试是实现证据，不会产生新的密码学证明。
