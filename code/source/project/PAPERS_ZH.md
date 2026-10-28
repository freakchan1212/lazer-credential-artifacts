# 论文与实现对应关系

## 直接对应本实现的论文

Vadim Lyubashevsky, Gregor Seiler, Patrick Steuer. **The LaZer Library: Lattice-Based Zero Knowledge and Succinct Proofs for Quantum-Safe Privacy**. ACM CCS 2024, pp.3125–3137. DOI: 10.1145/3658644.3690330.

- 论文页：https://eprint.iacr.org/2024/1846
- 官方PDF：https://eprint.iacr.org/2024/1846.pdf
- DOI：https://doi.org/10.1145/3658644.3690330
- 官方代码：https://github.com/lazer-crypto/lazer
- 官方README将python/anon_cred/anon_cred.py明确对应论文第6.2节，并指定本包提交10eafeca4cd53ff4fc54193dce904dbd0026fefd为复现版本。
- 原README保存在lazer/README；匿名凭证构造说明保存在lazer/docs/source/anoncred.rst。

这是论文中匿名凭证示例的原装配置复现，不是整篇论文所有应用与表格实验的复现。AVX2兼容编译及计数器需在论文实验环境中说明。

## 匿名凭证构造来源（同时提供作者公开PDF）

Jonathan Bootle, Vadim Lyubashevsky, Ngoc Khanh Nguyen, Alessandro Sorniotti. **A Framework for Practical Anonymous Credentials from Lattices**. CRYPTO 2023, LNCS14082, pp.384–417. DOI:10.1007/978-3-031-38545-2_13.

- ePrint：https://eprint.iacr.org/2023/560
- 官方PDF：https://eprint.iacr.org/2023/560.pdf
- 作者公开PDF：https://ale.sopit.net/pdf/2023-560.pdf
- LaZer官方anoncred.rst明确引用BLNS23，并解释环映射、P1签发和P2选择性披露。

两篇不能混成“全部实验已复现”。LaZer是实现论文与本包直接性能出处，BLNS是其匿名凭证构造依据。BLNS ePrint页面标注其为CRYPTO2023版本的major revision；附带作者公开PDF的具体哈希另见论文来源记录。

## 本次全文获取状态

BLNS作者站公开PDF可下载并原样附带。LaZer官方ePrint/ACM PDF在本环境返回403，已核实官方论文页、作者信息、DOI、代码对应关系；未将网页/摘要伪装成PDF。以上官方PDF直链供本地打开，若无法访问可通过DOI或作者页获取。

## 安全指标依据

- 原头文件anon_cred_params.h：P1/P2条件性知识错误、MLWE模拟声明、范数、挑战、sigma与拒绝因子。
- lnp-tbox-codegen.sage：KAPPA=128、Csize=2^129、eknow表达式。
- 本包固定Lattice Estimator源码estimator/reduction.py的ADPS16：经典0.292、量子0.265的Core-SVP系数。
- 截图中的不可伪造性、匿名/不可关联、零知识条目以原假设与模型为依据，不以30次实验代替证明。数值全协议归约与ZK统计距离推导不在本包完成范围。
