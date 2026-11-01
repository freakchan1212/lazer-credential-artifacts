# LaZer返修补实验：第二项与第三项联合执行包

本包以用户上传的 `LaZer_E4_Supplement(3).zip` 为源码母本，增加独立补实验入口；原包和原主实验数据不覆盖。代码结构及修改依据见 `结构分析与修改说明.md`。

## 先明确这轮做什么

- 第二项：同一台i5-13400F，GCC/Clang各构建B1/G3/C3，严格验证，重复出示/会话重建两负载。full每格300次，合计3600次。
- 第三项：独立pqzk-blns实现，固定上游提交，8属性、披露集合[0,4,5]、盲签发；Clang构建，两负载各300次，额外600次。同本轮LaZer任务按块交错。
- 两套实现的编码、nonce绑定、证明参数与安全口径有差异。默认输出是“同机任务适配后的原生配置参照”，不是相同安全级别加速比。该限制不能靠程序自动消除，也不表示已完全满足审稿要求的相同参数比较。
- 第一项的旧数据分析独立进行；本轮不会用新结果覆盖旧批次，也不把原包的历史测量混入。

## 1. 解压、安装依赖

使用新的英文目录。不要将文件覆盖到旧实验目录。

```bash
unzip LaZer_Revision23.zip
cd LaZer_Revision23
sudo apt update
sudo apt install build-essential clang libgmp-dev libmpfr-dev libntl-dev python3-dev python3-venv patch
python3 -m venv .venv
source .venv/bin/activate
python -m pip install 'cffi>=1.15,<3' 'setuptools>=68,<83' wheel
python verify_package.py
python preflight.py > preflight.txt
```

首次构建所需的LaZer、Falcon、HEXL、cpu_features与pqzk-blns源码已随包提供；构建脚本不在线拉取代码。不需要AVX-512、Sage或Docker；不自动更改调频策略。

preflight打印CPU拓扑与允许的CPU。选择空闲的可用核心，检查同核线程是否空闲。原稿绑定CPU 0，但CPU 0不被默认当作P核。下面命令以CPU 0为例；不可用时替换为preflight列出的编号，整轮保持一致。

## 2. 构建六套LaZer与一个独立BLNS

```bash
python build_revision.py --workspace "$PWD/builds" --external
```

同一工作区重复运行可续建未完成的构建；已完成产物必须通过哈希检查。源码、构建脚本、编译器或参数改变时使用新目录，例如`--workspace "$PWD/builds_v2"`。不要改写已有build_config绕过校验。

日志在`builds/logs/`。构建可能需要数分钟或更久，不承诺15分钟完成。默认使用PATH里的gcc/g++和clang/clang++。可用`REV_GCC_CC`、`REV_GCC_CXX`、`REV_CLANG_CC`、`REV_CLANG_CXX`指定完整编译器路径。

HEXL/cpu_features、Falcon、LaZer及CFFI全部按各编译器重建；系统GMP/MPFR/NTL二进制不重编。HEXL采用原包已有的无CMake通用后端，双方保持一致并禁AVX-512。因此本轮与旧CMake构建的绝对时间不直接拼接。

## 3. 先做smoke，再做正式补实验

```bash
python run_revision.py --workspace "$PWD/builds" --mode smoke --cpu 0
```

先进行22个固定币探针（3种子、跨编译器与回退），之后smoke含6套LaZer各9个披露子集与对象重建检查（含适用的篡改拒绝），再做24条LaZer正式格式计时与4条外部计时，预热另计。这里的“正式格式”仅指不固定随机币；smoke不作为论文性能证据。

独立实现每块还在计时外检查错误nonce被拒绝。不会声称外部验证接口与LaZer strict完全相同。

见到末尾`COMPLETE — return this file:`后，可直接运行full；pilot是可选的流程试跑，不必每档都跑：

```bash
python run_revision.py --workspace "$PWD/builds" --mode full --cpu 0
```

full：3批×每批5块×每块20次；每块随机排列14组合；共210个子进程任务、4200条正式会话，另有每任务2次预热。两负载都在进程开始时生成密钥；fresh每次重建对象并签发，但计时仍仅为本地出示生成/验证，不含签发和初始化。

外部编码为每个8字节随机输入属性经过原生HM映射；LaZer直接使用二进制属性，因此不能把输入字节数相同当作数学关系相同。

若外部构建失败，可显式先完成第二项：

```bash
python build_revision.py --workspace "$PWD/builds_lazer_only"
python run_revision.py --workspace "$PWD/builds_lazer_only" --mode smoke --cpu 0 --without-external
```

这种模式明确标记第三项NOT_RUN，不会静默跳过外部实现。不能将其回复为“已完成独立对比”。

## 4. 结果、失败与续跑

- 每块JSONL、哈希回执、spec与加载库证明分开保存。失败留下partial和日志，未完成块整块重新跑。
- 程序不删除慢样本、负收益块或失败任务；诚实证明失败直接停止。
- 已完成块验证哈希、数量和字段后跳过；源码/配置/产物变化拒绝续接。

```bash
python run_revision.py --workspace "$PWD/builds" --mode full --cpu 0 --resume "$PWD/results/原来的批次名"
```

模式、CPU、外部开关必须与原批次一致。新进程恢复时，继续使用本次安装依赖的同一个venv，不要切换Python。

完成后回传程序打印的结果`.tar.gz`，无需回传整个builds。结果包含实际动态库/CFFI、外部二进制、参数差异及其哈希、源码配置、环境、日志、逐会话记录与统计。结果同时保存构建命令日志；构建工作区另保留依赖对象及完整库。

`derived/summary.csv`列生成/验证/合计、证明大小及进程峰值RSS；`effects.csv`给出各编译器内部B1→G3、B1→C3、G3→C3的分层Bootstrap区间与改善块数；`blocks.csv`保留K差异和耗时差异，只有描述性关联；`RESULTS_ZH.md`为结果阅读入口。

RSS包括进程运行时、签发、初始化及预热，不是缓存增量或纯证明器内存。每块环境快照不是连续频率监测。外部对照不生成自动性能倍率。

## 5. 完整性与边界

- `base_project/`保留原源码、变体生成器和原有校验文件；旧构建脚本仅作来源保留，新实验不调用旧快速缓存。
- `vendor/pqzk-blns/`为固定提交b622225950bd1b486d96bf191eb835e60eff775f的原始源码及Apache-2.0许可证。
- 任务适配只在builds副本修改params.h和ISIS.cc；另修正Com.cc的盲签发重复释放错误；`REVISION.diff`记录完整差异。ISIS改动只在分配处记录实际序列化长度，数学证明逻辑不改。外部原盲签发路径在Verify_Com和I_VerCred重复释放同一证明；补丁让调用方统一释放，单独记录，不作为性能优化。
- LaZer沿用原E4生成器，不引入候选浮点判定；B1是经正确性修正的上游基线。
- 交付前实际测试范围见`VALIDATION.json`。云端功能验证不能替代你的i5正式性能数据。
