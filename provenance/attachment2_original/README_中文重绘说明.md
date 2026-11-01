# 中文图包来源与矢量化核验

本包保留7张中文图、21个图文件，均与输入图包逐字节一致。以下来源说明中的V2指机制图形成时的版本；已核对这7张PNG与当前正文嵌图一致。图1/2为按V2当前语义及源码边界重绘的机制图；图3—7来自上传E4主批次原始记录。新smoke的AMD计时没有加入绘图。

| 图 | 内容 | 可追溯数据 | 矢量检查 |
| --- | --- | --- | --- |
| 1 | 图1 声明状态的准备、复用与失效边界。静态矩阵不变时复用；更新声明或清理对象时重建或失效。 | 不适用：机制图 | SVG image=0、path=143；PDF image=0 |
| 2 | 图2 填充与紧致见证的对应。公开属性数k；代码记号m1对应图内和正文的mint，即加入范数余量后的内部维度；napp为加入余量前的应用矩阵列数。 | 不适用：机制图 | SVG image=0、path=100；PDF image=0 |
| 3 | 图3 严格验证下生成与验证均值。每组合600次，堆叠为本地出示耗时。 | data/derived/main_summary.csv | SVG image=0、path=78；PDF image=0 |
| 4 | 图4 生成预测（上，K=5.5）与紧致化分块降幅（下）。绿为变快，橙红为变慢，虚线分批。 | data/derived/main_summary.csv; data/derived/block_effects.csv | SVG image=0、path=167；PDF image=0 |
| 5 | 图5 严格验证下出示耗时经验分布。每组合600次，保留完整尾部。 | data/derived/samples.csv | SVG image=0、path=84；PDF image=0 |
| 6 | 图6 含用户/验证者初始化的服务摊销。同对象累计出示，点为三次均值、范围为最小/最大值。 | data/derived/reuse.csv | SVG image=0、path=144；PDF image=0 |
| 7 | 图7 同披露数量的证明大小。每方案每数量30个新鲜证明；点为均值，范围为实际最小/最大值。 | data/derived/k_sweep.csv | SVG image=0、path=87；PDF image=0 |

## 一致性和限定

- SVG中文字转路径，PDF保留矢量线条和嵌入字体；所有SVG无image元素，所有PDF无Image XObject。PNG为高分辨率导出。三格式由同一matplotlib Figure在同轮导出，非PNG改扩展名。
- 图4下半部保留负收益块，未只选择正收益；OLS上半部为K=5.5描述性预测，不是因果效应。
- 图5保留每组合600条严格验证记录完整尾部，没有截断长尾。
- 图6范围为三条生命周期的实际最小/最大值，非95%CI；各N来自同三条序列前缀，不作独立样本。
- 图7对相同k比较，范围是30个证明的实际最小/最大值。k变化会改变任务，跨k不当作相同任务压缩比；k0差异为独立采样波动。
- 图2用n_app表示应用声明列数，m_int表示含Z=2余量内部维度；避免正文“代码m1”泛称歧义。本图仅表达应用关系见证存在性，不是新协议匿名性证明。
- 本包不分发字体文件；重绘需安装可用中文字体，或通过LAZER_CJK_FONT指定兼容中文及数学符号的字体。SVG字形可放大，但文本转路径后不适合直接文本编辑，需修改脚本重绘。

## 文件和入口

SVG/、PDF/、PNG/各7文件；plot_sources/有V2机制图源、数据图源、独立统计程序；data/raw有406个任务的JSONL及对应回执，data/derived有绘图CSV，data/independent_checks有独立主统计、配对块及Bootstrap结果。figures_manifest.csv逐图记录正文位置/源/脚本/格式/矢量检查；SHA256_MANIFEST.json固定交付版本。

解压后运行python replot.py重绘全部图，python plot_sources/independent_recompute.py独立重算统计。两入口已在既有数据副本上完成运行检查；重绘外观仍取决于本机字体。需要numpy及matplotlib；不需要LaZer原生库。输入数据不作编辑。

## 限制

本轮未从历史E3缺失原始数据生成新的历史图；未伪造未提供的80轮地址复用压力图。图1/2是依据机制内容绘制的布局，非逐像素恢复早期Word嵌图；当前提供的PNG已与最新电子设计工程正文嵌图逐字节核对一致；本轮整理未修改正文或图像内容。
