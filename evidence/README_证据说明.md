# 主实验与专项回归证据附件

本包保留当前论文主实验和独立回归的既有原始证据；没有新跑实验。新增完整E4原档及固定种子便捷副本，因此比原“专项回归证据.zip”体积增加。图与主计时数据的便捷入口见电子设计工程_附件2_中文图与主实验数据.zip，源码见电子设计工程_附件1_精简代码复现包.zip。

## 内容

- results/E4_MAIN_FULL_ORIGINAL.tar.gz：完整E4主批次，解包根目录e4_full_20261018_121816_c2df8c。原始raw、回执、规格、源码/构建留档及验证记录保持原样。
- main_verification/：从上述主档verification/原样提取的验证记录和回执，另含specs/fixed_*.json及便捷表fixed_sizes.csv。固定种子1/2/3的修正基线及填充证明分别为29,118/29,107/29,109 B，紧致为28,501/28,484/28,474 B，减少617/623/635 B。对应补充表S14，不以独立smoke的单种子记录代替。
- results/E4_SMOKE_20261020_ORIGINAL.tar.gz：原独立smoke，48份raw JSONL、9份验证JSONL；36次主路径正式会话，单独于7,200次full主实验。
- results/e4_cache_pointer_stress_evidence.tar.gz：原pointer_reuse_original.tar.gz，仅调整外部文件名，字节不变；包含80轮、320次严格接受、80次篡改拒绝及65次先前释放地址再现事件的既有JSON和日志。regression/另放便捷副本。65不是不同地址数。

补充材料中的results/E4_MAIN_FULL_ORIGINAL.tar.gz与results/E4_SMOKE_20261020_ORIGINAL.tar.gz均可在本包按同一路径找到；旧文档中省略目录的e4_cache_pointer_stress_evidence.tar.gz位于results/。旧独立证据包内的pointer_reuse_result.json和pointer_reuse_stdout.log现位于regression/。

主档raw/及回执与附件2的data/raw/全部812个文件逐字节相同。这是同一批次的两种组织方式，不是额外样本。完整主档和便捷固定种子副本也不是新的实验。保留完整原档用于核查原编译环境与留档对象；历史E3 full并未因本次整理而补齐。有限回归不构成整协议安全证明。
