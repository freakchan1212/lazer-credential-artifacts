# BLNS23 / LaZer 审计修复与 `B0`/`B1`/`V0`~`V5` 源码变更说明 (`E2`)

## 1. 版本阶梯定义（`switch_variant.py`）

| 版本 | 代码标识 | 包含的源码改动 | Fixed-Coin 证明与 `B1`/`V0` 逐字节恒等 |
| :--- | :--- | :--- | :---: |
| **`B0`** | `B0_pristine_hooked` | 上游 `10eafeca` + `baseline_hooks.h` 计数探针（0 修复，0 优化） | 否（未修复 `stdev2sqr`） |
| **`B1`** | `B1_bugfix_only` | `B0` + 4 项安全/正确性修复（`stdev2sqr` + `blindsig.c` `r2` 范数 + $\mathcal{H}_2$ 持有者验签 + `strict=True` 边界校验） | **基准（100% 恒等）** |
| **`V0`** | `V0_google_base` | `B1` + 方向 1（`R2*s` 外提）+ 方向 2（无分支 `int64_t svR` AVX2）+ 方向 4a（Python 层 `A_P1`/`A_P2` 缓存） | **是（100% 恒等）** |
| **`V1`** | `V1_opt5_c_statement_cache` | `V0` + 方向 5（C 层 `Ds` SHAKE128 无尾填充前缀缓存 + `oDs` CRT 域常驻，线程局部动态扩容） | **是（100% 恒等）** |
| **`V2`** | `V2_opt6_arp_z34_avx2` | `V1` + 方向 6（Prover 端 `__lnp_tbox_compute_z34` 紧凑 `int64_t` 数组无分支 AVX2 点积） | **是（100% 恒等）** |
| **`V3A`** | `V3a_opt7a_lazy_cs2_only` | `V2` + 方向 7a（`lnp-quad.c` 仅在 `z1` 通过 `rej1` 后惰性计算 `cs2 = c*s2`） | **是（100% 恒等）** |
| **`V3`** | `V3_opt7_lazy_cs2_and_crt_scale` | `V3A` + 方向 7b（`poly.c` 无符号 `uint64_t` 预约减的单 limb `__int128` 标量模乘快速路径，全 64-bit 精确） | **是（100% 恒等）** |
| **`V4`** | `V4_opt8_double_fastpath_rejection` | `V3` + 方向 8（`rejection.c` `_int_to_double_hi53` 双精度 $10^{-11}$ 保护带过滤 + 命中/回退计数） | **是（100% 恒等）** |
| **`V5`** | `V5_opt9_dynamic_dim_pruning` | `V4` + 方向 9（`anon_cred_params.h` 导出 $k=1\dots 8$ 全套紧致参数集 `p2_compact{k}_param`，动态裁剪已披露零列） | 否（证明按 $k$ 线性缩减） |

## 2. 自动化验证与补丁导出

- 运行 `python3 switch_variant.py --export-all-patches` 可在 `variants_patches/` 下导出全部 9 个版本的累积补丁与相邻版本的增量补丁；
- 运行 `python3 verify_e2_all.py` 可自动完成跨版本固定随机币证明 SHA-256 对照、`poly_scale` $\pm 2^{63}$ 极值检验、40 并发实例缓存压力测试与 $k=0\dots 8$ 子空间投影矩阵验证。
