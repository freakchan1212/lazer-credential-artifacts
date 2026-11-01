# LaZer匿名凭证实现优化

本仓库提供《面向重复出示与选择性披露的LaZer匿名凭证实现优化》的实现代码、补充材料、实验数据、中文图及验证证据。研究对象为LaZer匿名凭证的重复出示与选择性披露，优化包括跨调用状态复用、公开零坐标裁剪及带范围检查的定宽运算。三种主实现均保留原MPFR拒绝判定。

材料版本：**2026.11.01**。作者：陈帅，江苏科技大学计算机学院。

## 文稿与图

- [论文正文 PDF](paper/manuscript.pdf) · [Word](paper/manuscript.docx)
- [补充材料 PDF](supplement/supplement.pdf) · [Word](supplement/supplement.docx)
- [中文矢量图与兼容图](figures/)：正文图1—5、补充图S1—S3，每图提供SVG、PDF及PNG。
- [实验与比较范围](docs/COMPARISON_SCOPE_ZH.md)
- [数据来源和历史材料](provenance/README.md)

补充材料S1—S7给出主实验统计、参数模型、有限回归和复现定位；S8给出同机跨编译器及独立实现的适配配置实测。

## 目录

| 目录 | 内容 |
|---|---|
| `paper/` | 论文正文 |
| `supplement/` | 补充材料 |
| `code/` | 原主实验代码、参数与回归入口 |
| `data/` | 原主实验JSONL、回执、派生统计及独立核对结果 |
| `comparison/` | LaZer、Argo与PQZK-BLNS的对照驱动、适配代码及依赖源码 |
| `comparison_data/` | 当前补实验的原始记录、回执、环境、构建及统计 |
| `figures/` | 8幅中文图及图与数据对应关系 |
| `tools/` | 只读核验、统计复算及图的导出和重绘 |
| `evidence/` | 主实验、回归和补实验的完整原始归档 |
| `history/` | 独立历史批次和历史九级表，不与当前统计合并 |
| `provenance/` | 输入归档指纹、源码差异及历史来源说明 |

## 实验数据

主实验为3批随机交错实验，共7,200次正式会话；另有首次准备、策略变化、披露扫描和影子诊断。主实验及辅助任务合计12,480条正式计时，不把回归或影子记录计作新增主样本。

补实验包含26个条件，每条件300次，共7,800次正式会话及780次预热。LaZer分别采用GCC/G++11.4和Clang/Clang++14；Argo和PQZK-BLNS均使用GCC/G++11.4。独立流程检查包含52次正式样本及52次预热，不用于性能结论。此前4,200次补实验单独保留在`history/`。

统一适配输入为8个属性、每属性8 B和披露集{0,4,5}。Argo原生参照使用10×32 B且无披露。两外部适配的隐藏谓词、构造、模数嵌入与安全依据仍有差异，结果用于所列配置的工程比较；LaZer内部B1/G3/C3比较用于评估本文优化增量。详细条件见补充表S14和[比较范围说明](docs/COMPARISON_SCOPE_ZH.md)。

## 只读核验

解压或克隆仓库后，在根目录执行：

```bash
bash CHECK_SUBMISSION.sh
```

该入口仅使用Python标准库，核对冻结文件、原始回执、源码指纹、Word引用、图文件与表2，并重算7,800次补实验的26组汇总和18组分块效应。结果写入仓库外的独立目录，不覆盖原始记录。它不重新运行密码实验。

也可单独执行：

```bash
python3 tools/verify_submission.py
python3 tools/recompute_comparison.py --output ../recomputed_comparison
```

原主实验及历史统计的复算：

```bash
python3 -m pip install -r requirements-analysis.txt
python3 tools/recompute_statistics.py --output ../recomputed_main
python3 tools/analyze_retry_blocks.py --output ../recomputed_retry
python3 tools/recompute_revision.py --output ../recomputed_historical
```

`.gitattributes`关闭自动换行转换，避免Windows检出改变已归档CSV、JSONL和源码的指纹。原始记录及其回执不得手工修改。

## 重新运行实验

原主实验见[代码运行说明](code/README_代码复现.md)。重新运行补充对照：

```bash
cd comparison
bash RUN_UBUNTU.sh
```

入口依次完成依赖安装、源码核验、驱动测试、构建、流程检查和正式计时。实验条件为Ubuntu x86-64、AVX2/AES/FMA、禁用AVX-512及单线程绑核。系统与Python依赖首次安装需要网络。具体生命周期、编译器、计时范围和输出结构见[对照运行说明](comparison/README_ZH.md)。不同机器的重新测量不保证复制原绝对耗时。

## 图的精确导出与重绘

直接复制文稿所用图文件：

```bash
python3 tools/export_submission_figures.py --output ../figures_exact
```

从冻结数据重绘：

```bash
python3 -m pip install -r requirements-analysis.txt
python3 tools/plot_bw.py --output ../figures_redrawn
```

`figures/`是与文稿对应的精确版本。SVG中文字已转为路径，PDF保留矢量；PNG为兼容预览。重绘可能因绘图库和字体引擎版本产生字节差异，不能据此增加实验样本。字体及许可见`tools/fonts/`。

## 引用与固定归档

引用元数据见[CITATION.cff](CITATION.cff)。本材料的正式版本标识为2026.11.01，固定归档DOI应使用该版本的Zenodo发布记录。仓库地址为：

https://github.com/freakchan1212/lazer-credential-artifacts

旧归档`paper-artifacts-20261028`对应https://doi.org/10.5281/zenodo.23720366，仅标识此前材料；不代表已经包含本版本的双对照数据。固定版本的文件与指纹以相应发布记录为准。

## 权利与许可

第三方代码及字体保留各自许可和版权说明，见[LICENSES.md](LICENSES.md)。作者自有材料未另行附加统一开放许可证；仓库的可访问性不替代具体文件的授权条款。
