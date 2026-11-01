# lazer基线-指标版

冻结标识：LAZER-ORIGINAL-METRICS-1.0-20261014。

使用官方提交10eafeca4cd53ff4fc54193dce904dbd0026fefd的匿名凭证示例，原协议、参数、采样/范数、Fiat–Shamir与原验证API均保留。AVX2/AES/FMA兼容构建，无需AVX-512。原Python协议与参数文件哈希不变；三份上游C文件和Falcon依赖一份C文件只加入计数器，差异完整列于SOURCE_CHANGES.diff。

## 一键运行

解压后进入lazer_baseline_metrics目录，不要覆盖之前的旧目录：

```bash
cd ~/下载/lazer_baseline_metrics
bash 01_build.sh
bash 02_run_smoke.sh
# 仅在smoke通过后运行pilot：
bash 03_run_pilot.sh 30
bash 04_collect_results.sh
```

smoke和pilot都会自动验收；成功标记FROZEN_METRICS_ACCEPTANCE_PASSED。输出lazer_metrics_results_时间.zip供回传。当前不要求直接跑full。

依赖与之前基线一致：build-essential、cmake、unzip、patch、libgmp-dev、libmpfr-dev、python3.10-dev、python3.10-venv；Python环境安装cffi、setuptools、wheel需要网络。默认优先/usr/bin/python3.10；也可PYTHON_BIN=/path/python3 bash 01_build.sh。Sage不是默认构建或默认安全模型的依赖。

## 输出内容

- results/LATEST_METRICS.txt指向最新结果目录。
- CURRENT_BASELINE_ZH.md、report.html：本机报告。
- samples.csv、summary.json：逐次原始记录与统计。暖机不计入正式样本。
- performance_metrics.csv：时间、尺寸、RSS；均值、中位数、P95、最小/最大、标准差；至少100样本才给P99。
- setup_metrics.csv：模块导入/公共参数展开、密钥生成、初始化，以及steady一次签发成本。
- retry_metrics.csv：P1、发行者、P2分别统计8个内部计数。
- attacks.csv：9项原API行为核对，重复证明等按原版预期接受，不能都称为攻击拒绝。
- security/attack_costs.csv：固定通用GSA/Core-SVP模型的经典/量子攻击成本；security_properties.csv：六维安全证据与边界；knowledge_bounds.json：原知识错误公式复算。
- acceptance.json：逐项机器验收记录。

fresh每次新消息、新对象、新签发后出示；steady一次签发后同凭证使用新证明随机数重复出示。两种负载的安全配置相同，各用独立进程记录RSS。出示延迟不含初始化、签发或网络；steady签发成本在setup记录一次，不能当作每次出示成本。

默认出示预算250ms，事后按生成+验证时间判断，绝不修改原证明循环。可用bash 03_run_pilot.sh 30 --deadline-ms 100调整。可用--cpu N绑定本机可用核心（先确认可用CPU编号）。记录CPU affinity、governor、版本和AVX2构建配置。

## 完整性的固定口径

截图7类性能和6类安全项目逐项对应见METRIC_COVERAGE_ZH.md。理论性质按原论文和原参数条件记录，不能由本机计时变成新安全证明。经典/量子模型默认实际运行并输出，但只覆盖明确声明的通用攻击；不声称穷尽所有攻击或得出整个BLNS协议的新安全位数。零知识没有独立实例化的数值统计距离界，当前已明确记录这一边界；不能把128位目标填入该空缺。

KNOWN_SCOPE.json冻结功能范围：原匿名凭证的签发和选择性披露已实现；撤销、追责、持有者不可转让、会话防重放、网络部署不是原示例功能。不是LaZer整篇论文全部应用与实验的复现。后续优化与本版比较时，保持消息、披露、密钥复用、对象生命周期、CPU/编译口径相同。

bash 06_security.sh可单独重生成安全证据。08_security_sage.sh是另行使用Sage运行固定版本完整估计器的研究入口；未安装会明确退出2，不会用通用模型冒充Sage结果。

verification_release/是交付前开发机验收与逐字节等价记录，host_label明确标记开发机，不冒充你的电脑。reference_user/只保留你这次原版V1回传结果及来源，不能与新指标版fresh/steady直接混成一次测量。
