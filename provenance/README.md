# 数据与实现来源

`input_archives.json`记录原输入归档的实际文件名、SHA-256与规模。文件名属于来源标识，不作为本仓库的材料版本号。`current_vs_legacy.json`和`current_to_legacy.diff`比较原主实验代码与较早参考实现：680个同路径文件相同，12个同路径文件不同；另有环境日志及旧构建产物等差异。

原主实验的`data/raw/`与完整归档保存同批记录的两种组织方式，不合并重复计数。`evidence/`中的原归档保留原始字节。当前主实验、7,800次补实验、此前4,200次补实验和九级历史表分别定位，见根目录README与补充材料S7。

`legacy_reference/`保存必要的较早源码差异和验证说明，仅供追溯，不是当前默认运行入口。`attachment2_original/`保留原图与数据附件的历史说明，原7图编号不适用于当前正文5图及补充3图；当前图号和数据关系见`figures/FIGURE_DATA_MAP.json`。

论文与补充材料的当前文件分别为`paper/manuscript.docx`及`supplement/supplement.docx`。早期输入包名、原始实验批次及固定随机币标识按原记录保留，以便复核归档身份。

历史核查JSON保留其原记录日期和作用域，不作为本材料版本的完成状态。当前仓库校验信息见`docs/release_verification.json`。
