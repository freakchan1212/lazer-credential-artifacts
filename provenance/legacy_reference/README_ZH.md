# LaZer正常路径优化：论文、补充材料与最终复现代码

发布版本：`LaZer-normal-path-final-20261019`。研究对象为固定BLNS/LaZer匿名凭证路径的状态复用、见证与约束紧致化和受范围检查约束的算术简化。主性能对照保留MPFR判定。本包基于FIX123代码、完整主实验数据和本轮最终正文整理；密码学C实现、凭证实现、参数数组、原始记录和归档原生库保持原字节。

## 直接查看

- `publication/LaZer_正常路径优化_最终版_20261019.docx`：双栏正文，图1—7、表1—7、公式（1）—（7）。
- `publication/LaZer_正常路径优化_补充材料_20261019.docx`：原附录A—D转为S1—S4、表S1—S13。
- `publication/最终核对与使用说明_20261019.md`：19项文献核对、编号变化与本轮验证边界。
- `paper_ready/`：已生成的中英文图、原始数据重算结果、按最终稿编号的CSV与安全条件核查结果。

## 一条入口重建当前图表

在本目录执行：

```bash
python3 verify_package.py
python3 -m venv .venv_figures
.venv_figures/bin/python -m pip install -r requirements-plots.txt
.venv_figures/bin/python reproduce_final.py
```

成功标志：`FINAL_PAPER_REPRODUCTION_COMPLETE`。输出为新的`final_reproduced_日期时间/`，不覆盖原批次。

这个入口**不会重跑full性能实验**，不执行原生证明，也不执行完整Sage安全估计；不用绑CPU，不要求AVX-512。它验证原始归档和回执、重算统计、复核参数并重绘图1—7。完整当前输出：

- `figures/{zh,en}/{png,pdf,svg}/`：中英文各7图、三种格式，共42文件。PNG为300dpi，PDF/SVG为矢量；图例、坐标使用可读名称。
- `tables/table_1...table_7`及`table_S1...table_S13`：最终稿转录；有原始数据依据者另附`_recomputed.csv`；来源状态见`TABLE_PROVENANCE.csv`。
- `FINAL_REPRODUCTION.json`：与最终稿直接对应的256个数值单元格核对。
- `security/`：七变体审计、C3/DC3紧致条件核查证书。证书不是完整协议安全认证。
- `legacy_fix123_tables/`：旧版编号的327个数字/标签单元格核对，仅作追溯；不要引用为最终论文表号。

图1/2是方法示意，图3—7读取实际主实验数据。图4保留负收益块，图5保留完整尾部。图6/7误差范围为样本最小—最大值，不能称置信区间。本地生成与验证之和不是网络端到端时延。

**历史E3原始full不在本包。** 表S1—S7是历史转录与摘要；表1外部数字来自已注明的文献。不能把它们声称为由E4原始记录重新产生。主实验原始full、406任务记录、归档源码/库及有限回归回执位于`results/e4_full_20261018_121816_c2df8c/`。

## 单独审计（仅Python标准库）

```bash
python3 verify_fix123.py --output CHECK_AUDIT.json
python3 project/check_compact_params.py \
  --header results/e4_full_20261018_121816_c2df8c/artifacts/C3/lazer/python/anon_cred/anon_cred_params.h \
  --output compact_checked
python3 project/security_audit.py \
  --header results/e4_full_20261018_121816_c2df8c/artifacts/C3/lazer/python/anon_cred/anon_cred_params.h \
  --variant C3 --disclosed-k 3 --output security_checked
```

审计归档头文件必须显式指定变体；披露索引不能与填充配置索引混淆。全k的单项MSIS模型与参数条件扫描不是全攻击族或ROM/QROM整协议估计。11项审计回归含故意改错方差、模数、索引及记录标签的负例。

## 若将来重新跑密码学性能实验

本轮不需要重跑full。需要新实验时先阅读`original_audit_scripts/README_ZH.md`及`project/README_ZH.md`，按实际环境构建，并从`python3 run_e4.py --help`查看参数。不要对旧full使用`--resume`；新脚本指纹已经不同。新数据请另建批次，图表入口为：

```bash
.venv_figures/bin/python reproduce_final.py \
  --batch results/你的新full批次 --output paper_new_full --allow-new-data
```

新测值可与旧稿不同，`--allow-new-data`将差异保留为报告，不把新结果伪装成原文数值。smoke/pilot不能替代论文full。

## 文件角色与完整性

当前论文以`publication/PUBLICATION_TARGET.json`为准；`paper_reference/`、原`PAPER_REVISION_CHANGES.json`、`FIX123_*`记录及`original_audit_scripts/`属于旧版追溯资料。`reproduce_paper.py`是最终入口内部使用的旧核对引擎；用户应使用`reproduce_final.py`以获得正确表号。

`PACKAGE_SHA256.json`覆盖交付文件；`verify_package.py`允许用户新建输出目录，检查原交付文件是否损坏。发布核对说明见`publication/`。字体文件经过FreeType面验证和中文字符覆盖检查；无效字体不会被当作可用字体静默继续。
