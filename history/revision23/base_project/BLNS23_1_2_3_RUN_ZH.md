# `lazer-baseline-Google-E2` 全版本消融、差分验证与评测指南

本代码包是针对审稿与代码复核意见全面升级的 **`lazer-baseline-Google-E2`** 版本，支持一键完成**跨版本固定随机币逐字节等价性验证（Fixed-Coin Equivalence）**、**64-bit 边界测试**以及 **`B0` / `B1` / `V0` ~ `V5` 全序列消融对比实验**。

---

## 一、`E2` 版本核心修正与升级内容

1. **修复 `V1` (`lin-proofs.c`) Fiat–Shamir 编码尾填充偏移 + 线程局部动态扩容缓存**：
   - 移除了 `_lin_ds_cache_populate` 中提前调用的 `coder_enc_end(cstate)`（该调用会在 `Ds/Dm` 与 `u` 之间多插入 1 个 `0x01` 字节），利用 $d=64$ 下 `coder_enc_urandom4` 严格字节对齐（`bit_off == 0`）的性质，将唯一一次 `coder_enc_end(cstate)` 保留在 `__lnp_hash_statement_arp` 末尾；
   - 将 `_lin_ds_cache` 升级为线程局部（`__thread`）动态 `realloc` 扩容表，彻底消除 16 槽静态上限与并发存活实例驱逐隐患；
   - 实测固定随机币（Seed 1..3）下，**`B1`、`V0`、`V1`、`V2`、`V3A`、`V3`、`V4` 生成的 P1 请求与 P2 证明 SHA-256 100% 逐字节恒等**。
2. **修复 `V3` (`poly.c`) 单 limb `poly_scale` 全 64-bit 范围无符号预约减**：
   - 在施加符号位 `a->neg` 与 `belem->neg` 之前，先以无符号 `uint64_t` 对 `limbs[0] % uq` 进行预约减，消除 `limbs[0] >= 2^63` 时的有符号 `int64_t` 截断溢出（实测 $q=12289, b(X)=1, a=+2^{63} \to +2832, a=-2^{63} \to -2832$，39 组系数域/CRT 域/原地 `r==b` 边界测试 100% 通过）；
   - 新增独立变体 **`V3A` (`V3a_opt7a_lazy_cs2_only`)**，将 `lnp-quad.c` 惰性 `cs2` 计算与 `poly.c` 单 limb 标量模乘解耦评测。
3. **新增纯净基线 `B0` 与纯修复基线 `B1`（实现同频绑核下的严密消融）**：
   - **`B0` (`B0_pristine_hooked`)**：上游 `10eafeca` 原装代码 + 仅计数探针，不含任何漏洞修复或优化，用于在 `performance` 调频器与 `--cpu 2` 绑核下复测纯净原装基线；
   - **`B1` (`B1_bugfix_only`)**：仅启用 4 项安全与正确性审计修复，不含任何性能优化，严格分离“安全修复代价”与“算子优化收益”。
4. **完善 `V4` (`rejection.c`) 与 `V5` (`anon_cred_params.h`, `security_audit.py`)**：
   - `V4` 将双精度转换函数规范命名为 `_int_to_double_hi53`，给出显式 ULP 误差上界注释，并增加快速路径命中与 MPFR 回退运行期计数器；
   - `V5` 在 `anon_cred_params.h` 中导出 **$k = 1 \dots 8$ 全套紧致子空间投影参数集 `p2_compact1_param` ~ `p2_compact8_param`**，并在 `security_audit.py` / `security_metrics.py` / `acceptance.py` 中动态计算 `V5` 的真实矩阵维度 `[8, 45]`、MSIS 界（$\log_2 B = 40.133841, \delta_0 = 1.0043707$）与参数变更标志 `protocol_parameters_changed = True`。
5. **消除 `compare_all_variants.py` 硬编码与完善构建指纹（`build_fingerprint`）**：
   - 每轮实验在 `summary.json` 中记录 `liblazer.so`、CFFI 扩展与核心源文件的 SHA-256 指纹；
   - `compare_all_variants.py` 全部从 `security_metrics.json`、`acceptance.json` 与 `e2_verification_evidence.json` 动态读取数据，并输出带标准误（SE）与 $R^2$ 的 OLS 回归结果。

---

## 二、快速运行命令（推荐在 i5-13400F 上执行）

```bash
# 0. 切换 CPU 调频策略为 performance（消除省电降频抖动）
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# 1. 首次构建兼容环境与依赖库
bash 05_build_compatible.sh

# 2. 单独运行 E2 差分、64-bit 边界与 k=0..8 全基数验证套件
python3 verify_e2_all.py

# 3. 一键顺序运行全版本（B0, B1, V0, V1, V2, V3A, V3, V4, V5）消融基准并打包结果
bash 20_run_all_6_variants.sh 30 --cpu 2

# 4. （可选）运行多轮正反序交错（ABBA）消融实验以消除热漂移与随机重试方差
bash 22_run_interleaved_ablation.sh 3 30 --cpu 2
```
