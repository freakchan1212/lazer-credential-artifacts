# LaZer与独立实现对照运行说明

本目录提供LaZer B1/G3/C3、Argo及PQZK-BLNS的构建与计时入口，包含源码、依赖源码、任务计划和统计程序。

运行入口依次执行文件校验、驱动测试、依赖检查、构建、流程检查和正式实验。实验数据串行测量，避免进程争用CPU；构建阶段可并行。源码和依赖源码归档均包含在包内，系统及Python依赖首次安装需要网络。

## 最简运行

解压并进入本包目录后执行 `bash RUN_UBUNTU.sh`。脚本自动安装依赖、创建虚拟环境，先运行smoke，再运行full；默认CPU0、构建并发4。

启动脚本会按所选系统Python的实际主次版本安装对应的-dev和-venv包，避免python3-venv元包的版本依赖冲突。

以下是Ubuntu22.04/Python3.10的展开命令，二选一执行即可；Ubuntu24.04请直接使用启动脚本自动识别版本。

## Ubuntu 22.04/24.04 完整命令

将ZIP保存到下载目录，再完整复制以下命令。使用独立工作目录保存新的测量，避免覆盖已归档实验。

```bash
bash <<'RUN'
set -euo pipefail
TASK_DOWNLOAD_DIR="$(xdg-user-dir DOWNLOAD 2>/dev/null || true)"
if [ -z "$TASK_DOWNLOAD_DIR" ]; then
  if [ -d "$HOME/下载" ]; then TASK_DOWNLOAD_DIR="$HOME/下载"; else TASK_DOWNLOAD_DIR="$HOME/Downloads"; fi
fi
cd "$TASK_DOWNLOAD_DIR"
unzip -q -n lazer_artifacts.zip
cd lazer-credential-artifacts/comparison
sudo apt-get update
sudo apt-get install -y build-essential clang cmake autoconf automake libtool m4 \
  libgmp-dev libmpfr-dev libntl-dev libffi-dev python3.10-dev python3.10-venv unzip patch
/usr/bin/python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install 'cffi>=1.15,<3' 'setuptools>=68,<83' wheel
python run_two_baselines.py --mode full --jobs 4 --cpu 0
RUN
```

正式测量绑定CPU0，与原实验设置保持一致。若CPU0不在允许列表，可去掉 `--cpu 0`，程序会选择允许的逻辑核。不要同时启动多个测量进程，保持该核和其超线程同胞空闲。

要求x86_64及AVX2/AES/FMA，不要求AVX-512；不需要SageMath或NumPy。Ubuntu22.04默认GCC11.4与已归档主平台相近；其他系统的编译器版本可能不同，以结果中的实际环境记录为准。

原来的入口也兼容：`python run_reviewed.py --mode full --jobs 4 --cpu 0`。

## 实验条件

| 实现 | 变体 | 生命周期 | 编译器 |
|---|---|---|---|
| LaZer | B1 / G3 / C3 | steady、fresh | GCC和Clang |
| pqzk-blns | 原生HM / 输入按位映射PADDED / COMPACT | steady、fresh | GCC |
| pqzk-blns | PADDED_NOCACHE | steady | GCC |
| Argo | NATIVE / PADDED / COMPACT | steady、fresh | GCC |
| Argo | PADDED_NOCACHE | steady | GCC |

总共26个条件。full为3轮×5块×20次，共7,800个非预热测量；另有每块2次预热和功能验证。smoke为52个非预热测量，仅检验流程，不能用来代替正式统计。

适配组采用8属性、每属性8 B、披露D={0,4,5}。Argo NATIVE保留10×32 B、无披露的原生配置，仅作为原生配置参照，不能与适配组混称相同任务。

steady在各组内重复使用同一凭证，fresh每次重新签发；签发在出示计时外。PADDED_NOCACHE仍使用steady凭证，但每次重建预处理，用于单独观察缓存。不同条件的凭证独立随机生成，轮/块配对不是逐字相同凭证配对。B1→G3还包含多项内部优化，不能将fresh→steady直接当作完整G3收益。

## 输出

结果在 `results/dual_full_时间/`，结束后会打印同名 `.tar.gz` 文件路径。完整归档用于复核实验条件、记录与统计。

- `derived/RESULTS_ZH.md`、`summary.csv`：生成、验证、合计时间，证明大小及进程峰值内存。
- `derived/effects.csv`、`blocks.csv`：方案内缓存/裁剪收益、改善块及Bootstrap区间。
- `derived/samples.csv`、`raw/`：原始样本及校验回执。
- `config.json`、`qualification.json`：条件、编译器、来源指纹及比较范围。
- `checks/`、`equivalence/`：披露子集、异常输入、固定随机币一致性检查。
- `environment_*.json`、`build_logs/`、`artifacts/`：运行环境与构建证据。
- `COMPLETE.json`：全部所选测量完成后才生成。

若失败，程序停止并保留日志；已建立的测量批次会输出 `_FAILED.tar.gz`。构建错误查看 `builds_dual/logs/`。默认结果目录有独立时间戳，已有目录不会被覆盖。

改过源码后应使用新构建目录，例如 `--workspace "$PWD/builds_dual_v2"`。相同源码/工具链的未完成批次可以使用：

```bash
python run_revision.py --workspace "$PWD/builds_dual" --mode full --cpu 0 \
  --all-baselines --resume "/完整路径/原结果目录"
```

## 结果解释

Argo使用实际可解码固定宽度编码，pqzk-blns/LaZer使用各自编码，证明大小差异包含编码影响。RSS是含初始化、签发、预热及证明/验证状态的整个进程峰值。

两套外部实现可以提供真实的原生配置参照和任务适配实测。各协议模数、见证结构、证明谓词和安全依据仍存在差异；本包不会把“测量成功”写成“严格同参数、同安全等级已经全部完成”。详见 `../docs/COMPARISON_SCOPE_ZH.md`。这些说明不会阻止双对照运行。
