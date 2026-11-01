# 主实验代码与回归入口

本目录保存LaZer匿名凭证重复出示与选择性披露优化的原主实验代码、参数、变体补丁及回归脚本。实验记录位于仓库`data/`，完整现场与专项证据位于`evidence/`；补充材料S7给出源码与批次定位。

## 重新运行主实验

原测试环境为Ubuntu x86-64、i5-13400F、AVX2、Python3.10和GCC11.4。依赖与构建入口见`source/project/`中的脚本。进入本目录后：

```bash
python3 source/run_e4.py --help
python3 source/run_e4.py --mode smoke --cpu 0 --no-plots
```

先编译所需原生库并通过流程检查，再选择pilot或full。full会重新执行7,200次主会话与辅助任务，不是读取现有数据；绑核编号应属于本机允许集合，新结果不得覆盖已归档文件。

## 回归

```bash
python3 regression/check_pointer_reuse.py --root source --cycles 80 --out pointer_reuse_new.json
```

地址复用测试需要已编译C3及对应库，选择状态见`source/project/ACTIVE_VARIANT.json`。仅查看参数可加`--help`。

当前原主版本选中C3，保留原MPFR判定；候选浮点判定只用于影子诊断。`source/project/pristine/upstream_snapshot.zip`及变体补丁保留原来源。历史准备期说明位于`history/20261018_pre_full/`，不替代正式主实验记录。

现有数据的只读复算应从仓库根目录调用`tools/recompute_statistics.py`，它把输出写到仓库外；不直接在原派生数据目录运行历史整理脚本。跨编译器和外部适配实验入口另见`../comparison/README_ZH.md`。
