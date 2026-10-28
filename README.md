# LaZer 匿名凭证实现优化：代码与补充材料

对应论文《面向重复出示与选择性披露的LaZer匿名凭证实现优化》。本仓库把补充材料、源码、数据、图和验证证据集中到同一个入口，供读者阅读与复核。正式发表后请在本页补充论文的正式书目信息和 DOI。

## 先阅读

- **[补充材料 PDF](supplement/supplement.pdf)**；[可编辑 Word](supplement/supplement.docx)。
- [对应正文 PDF](paper/manuscript.pdf)；[对应正文 Word](paper/manuscript.docx)。正文为 10 页，补充材料为 11 页；本次整理没有修改两份 Word。
- [中文 SVG](figures/SVG/) 与 [中文 PNG](figures/PNG/)：正文图1—5、补充图S1—S3共8图。正文图4为完整服务摊销曲线；图S3为同数据的大尺寸展示。
- [复现代码](code/source/)；[代码运行说明](code/README_代码复现.md)。
- [原始实验记录](data/raw/)、[绘图统计表](data/derived/)、[原有独立统计](data/independent_checks/)。
- [完整实验归档和专项验证](evidence/)；[整理核查报告](docs/整理核查报告.md)。

## 原附件如何对应本仓库

补充材料中仍使用原附件名称及内部相对路径，阅读时按下表定位。旧附件的源码、原始数据和证据内容保留；本仓库只增加统一导航和独立分析入口。

| 原文件中的说法 | 本仓库位置 |
| --- | --- |
| 附件1根目录及其 `source/`、`regression/` | `code/`、`code/source/`、`code/regression/` |
| 附件2的 `data/` | `data/` |
| 附件2的 `plot_sources/` | `analysis/original_attachment2/`（旧7图布局的来源程序） |
| 附件2中文图 | 当前图号统一见 `figures/`，不要按旧7图编号引用 |
| 附件3根目录及其 `results/`、`main_verification/` | `evidence/`、`evidence/results/`、`evidence/main_verification/` |
| 旧英文稿最终代码包 | 对比及来源见 `provenance/`，未覆盖本仓库当前代码 |

## 三种不同的复核

在仓库根目录执行。分析入口需要 Python 3.10 或兼容版本；统计和绘图依赖可用 `python3 -m pip install -r requirements-analysis.txt` 安装。完整性检查仅用标准库。

```bash
python3 tools/verify_artifacts.py
python3 tools/recompute_statistics.py --output ../statistics_recomputed
```

第一条检查交付文件哈希、406项原始任务回执、图与Word嵌图对应。第二条从原始记录独立重算主统计、配对块和分层Bootstrap；输出到仓库外，不改写冻结数据。

中文重绘需本机安装 Noto Serif CJK SC，或指定支持所需中文字符的字体。已交付 SVG 的字形转为路径，直接使用无需安装字体。

```bash
export LAZER_CJK_FONT=/path/to/Chinese-font.otf
python3 tools/redraw_figures.py --output ../figures_redrawn
```

该入口输出当前8图的 SVG 和 PNG；不同字体或软件版本可导致像素与文件哈希变化。图1/2/3/5的绘图数值来自当前稿件已报告值，图4及补充图使用随附统计表；独立统计程序用于核对原始记录。

重新运行密码实现属于另一种复现，需要 Ubuntu x86-64、GCC/G++、CMake、GMP/MPFR 开发包及原构建依赖。先阅读 `code/README_代码复现.md` 和 `code/source/project/00_check_env.sh`、`01_build.sh`。

```bash
python3 code/source/run_e4.py --help
python3 code/source/run_e4.py --mode smoke --cpu 0 --no-plots
```

将CPU编号改为本机可用编号；初次构建及依赖要求见原代码说明。完整 `full` 运行会产生新的计时批次；不同机器上的绝对耗时不等于本文原主批次。当前主对照为 B1/G3/C3，保留原 MPFR 拒绝判定，浮点候选不作为正式判定。

## 结果边界

主实验为7,200次正式主任务计时，406项任务另含辅助实验。整体优化降幅38.89%/26.21%与紧致化独立增量3.83%/6.87%不可混为一谈。重复出示增量区间跨零；服务摊销范围为三次生命周期的实际最小/最大值，各N共用序列前缀。有限回归不等于完整密码安全证明。

## 引用和版本

仓库：https://github.com/freakchan1212/lazer-credential-artifacts

本次整理拟发布标签为 `paper-artifacts-20261028`，引用元数据见 `CITATION.cff`。新版本的 Zenodo DOI 待发布归档后确认；本文件不预填未知 DOI。

首次归档版本 `paper-artifacts-20261027` 的 DOI 为 https://doi.org/10.5281/zenodo.23719548 。该 DOI 对应首次归档文件快照，不随 GitHub 后续修改自动更新。论文应引用与实际提交材料相对应的具体版本。

[访问与引用说明](docs/GitHub发布与论文引用.md) 给出版本关系；[本次整理核查](docs/整理核查报告.md) 记录修改范围和验证结果。第三方许可及自有内容授权状态见 [LICENSES.md](LICENSES.md)。正式发表后可补充论文的书目信息和论文 DOI。

## Windows 的检查方式

完整性检查仅使用 Python 标准库。在仓库根目录执行 `python -X utf8 tools/verify_artifacts.py`；命令启动后应显示 `PASSED` 和检查数量。应先确认 Python 解释器可用，安装 GitHub Desktop 并不等于安装了 Python。统计和绘图另需 `requirements-analysis.txt` 中的依赖；原生密码实现的完整复现环境仍以 Ubuntu 说明为准。

本仓库使用 `.gitattributes` 保留原文件字节，避免跨系统换行转换影响 SHA256。修改文件后应先复核变更范围再更新根目录清单，不能通过重写清单掩盖意外的实验材料改动。

## 使用 GitHub Desktop 完整上传

上游忽略规则会跳过部分已随包提供的头文件与第三方源码。复制整理包到已有本地仓库后，双击根目录 `stage_frozen_files.cmd`；辅助脚本先用PowerShell核对清单文件的SHA256，再将清单中的全部文件加入Git暂存区（包括被忽略的必要文件）。不需Python，不提交、不推送、不发布；之后在GitHub Desktop检查并提交。不要仅凭网页目录存在判断材料完整。该入口保留上游忽略规则及原源码不变，使用本机Git或GitHub Desktop内附Git。
