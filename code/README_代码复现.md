# 第二篇论文代码复现附件

本包对应《面向重复出示与选择性披露的 LaZer 匿名凭证实现优化》，与电子设计工程_附件2_中文图与主实验数据.zip、电子设计工程_附件3_主实验与专项回归证据.zip配套。源代码、参数、变体补丁与输入包逐字节保持一致；本包不含原实验计时结果，读取既有结果应使用附件2，而不是重新运行full。

## Ubuntu x86-64运行

1. 解压本包并进入根目录。安装GCC/G++、CMake、Python、GMP/MPFR开发依赖及构建所需第三方组件；原主实验为Ubuntu环境、i5-13400F/AVX2、Python 3.10、GCC 11.4。构建和依赖详见source/project/脚本。
2. 查看参数：`python3 source/run_e4.py --help`。
3. 最小功能运行：`python3 source/run_e4.py --mode smoke --cpu 0 --no-plots`。CPU编号应改为本机可用亲和性集合内编号。
4. smoke通过后再选`--mode pilot`；`--mode full`会重新运行7,200次主实验计时及辅助实验，不是读取现有数据。其他机器的绝对耗时不得与原E4批次混同。
5. 地址复用测试：`python3 regression/check_pointer_reuse.py --root source --cycles 80 --out pointer_reuse_new.json`。须先按原构建入口编译C3，确保source/project/ACTIVE_VARIANT.json选中C3并加载对应库；仅查看选项可使用`--help`。原既有结果位于附件3，不要写入原始证据文件。

source/project/pristine/upstream_snapshot.zip、变体补丁、参数和完整性清单保留。当前选定变体为C3，原MPFR判定开启，候选浮点快速判定不用于主对照。source/project/中部分说明属于历史基线文档；当前主实验批次、证据位置及包间关系见附件导航。

## 历史留档与本轮核查

原source/下PAPER_TARGET.json、PAPER_REVISION_CHANGES.json、REVISION_NOTES_ZH.md及LOCAL_VALIDATION.json已原样移入history/20261018_pre_full/，不作为当前主实验完成状态。原release_original/清单与实际源码作用域清单保留。

本轮核对了E4原档列明的14项脚本/输入指纹、输入包覆盖文件哈希及运行器帮助入口，排除参数填写模板后对Python程序做语法核查。本轮没有重新编译C/HEXL/MPFR原生库，也没有重跑smoke/pilot/full；不能据此宣称已在当前机器完成原生复现。历史验收与本轮静态检查分别记载。
