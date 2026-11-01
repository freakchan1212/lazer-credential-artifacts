# GitHub上传与Zenodo归档

仓库地址：https://github.com/freakchan1212/lazer-credential-artifacts

本材料版本标识与建议Release标签：`2026.11.01`。发布标题：`LaZer Anonymous Credential Implementation Optimization 2026.11.01`。归档软件的题名、作者与版本信息来自根目录`CITATION.cff`。

## 上传仓库内容

解压`lazer_artifacts.zip`后，`lazer-credential-artifacts/`是仓库根目录，包含README、代码、数据、补充材料及图。上传的是目录内文件，而不是只把ZIP放进仓库。单个最大文件约10.9 MB，无需为本材料配置Git LFS；文件数量较多，建议使用Git或GitHub Desktop。

### 更新现有仓库

以下命令适用于Linux终端或Windows Git Bash。先把ZIP放在Downloads或下载目录并解压。把终端切换到解压目录的上一级，确认此处能看到`lazer-credential-artifacts/`。Git及Python须已安装；Windows中若Python命令是`python`，将下面`python3`改为`python`。

```bash
TASK_PAYLOAD="$PWD/lazer-credential-artifacts"
git clone https://github.com/freakchan1212/lazer-credential-artifacts.git lazer-publish-20261101
cd lazer-publish-20261101
git config user.name "Shuai Chen"
git config user.email "241210704101@stu.just.edu.cn"
git rm -r --ignore-unmatch .
cp -R "$TASK_PAYLOAD/." .
python3 tools/verify_submission.py
python3 tools/recompute_comparison.py --output ../lazer-recomputed-20261101
git add -f -A .
git diff --cached --stat
git commit -m "Archive LaZer credential implementation artifacts 2026.11.01"
git push origin HEAD
```

这里的清理发生在新建的`lazer-publish-20261101`克隆副本中，先移除旧跟踪文件再复制完整快照，避免覆盖后残留旧草稿文件。`.git`保留，已有提交和Release历史不重写，命令不使用force push。首次push可能需要GitHub身份验证。若此克隆目录已存在，使用另一个新的目录名，不复用含未提交工作的目录。

这里对新副本使用`git add -f -A .`，是为了把第三方目录中被其自身.gitignore忽略的已归档构建证据一并提交。核验输出已写在仓库外，不会混入本次提交。

上传后在网页核对README、`paper/`、`supplement/`、`figures/`、`comparison_data/`等目录，尤其确认当前补充材料和两套外部适配数据都已在仓库内。`.gitattributes`保持指纹所需的原始换行字节，不能用编辑器批量转换CSV/JSONL换行。

## 生成DOI

### 原归档通过GitHub集成建立时

1. 登录Zenodo，在GitHub设置中Sync now，并确认同一仓库已启用集成。
2. 在GitHub该仓库建立新的正式Release，标签使用`2026.11.01`，目标为刚上传的提交。Release说明可复制`RELEASE_NOTES.md`。
3. 发布Release后等待Zenodo处理，在Zenodo核对新记录的题名、作者、版本、文件及关联版本。DOI由Zenodo生成，不手工修改旧DOI数字。
4. 若原仓库已与旧Zenodo记录关联，检查新记录进入同一版本链；不要同时另建一条不相关记录。

### 原归档是手工上传时

打开原Zenodo记录并选择New version，在同一版本链创建草稿，预留新版本DOI。拿到预留号后同步论文引用与本归档引用信息，再上传最终文件和发布。不要另外启动GitHub自动归档来重复注册同一份内容。

两条路线择一，以原记录的建立方式为准。既有固定版本`paper-artifacts-20261028`及其DOI标识旧档，不能改写成已包含本版本补实验。

## DOI生成后的文稿同步

当前正文4.1提供指向仓库的可点击入口；补充材料S7给出仓库地址、目录及版本2026.11.01，未填入尚未生成的DOI。新版本DOI确定后，将其作为固定归档引用同步到补充材料S7、仓库引用信息及投稿说明，核对其与实际发布文件一致。

若通过GitHub自动归档，DOI生成后可以更新仓库引用元数据及另行提交的论文引用；已归档Release保持固定身份。若仍需把修改后的Word也纳入同一归档文件，优先使用先预留DOI再上传的手工新版本流程，避免发布后替换已有归档文件。只补DOI不改变实验数据或比较结论。

修改CITATION.cff、Word或PDF后，也要更新相应文档校验记录及根目录SHA256清单，并重新核验与排版；当前清单只覆盖本次交付快照。不得通过批量重写原始数据的哈希来消除异常。

本目录不含虚构的新DOI、DOI徽章或待替换的号码。尚未填写的doi字段直接省略，避免Zenodo把旧号误认作本版本标识。

## 许可与元数据

`CITATION.cff`提供GitHub引用入口，Zenodo支持从其导入软件元数据。本仓库未放置覆盖它的`.zenodo.json`。作者自有材料未附加新的统一开放许可证，发布时应核对Zenodo许可字段与文件实际许可，不将第三方代码整体改为另一种许可。第三方许可入口见`LICENSES.md`。

官方操作依据（2026-11-01核对）：

- https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github
- https://help.zenodo.org/docs/github/enable-repository/
- https://help.zenodo.org/docs/github/describe-software/citation-file/
- https://help.zenodo.org/docs/github/archive-software/github-upload/
- https://help.zenodo.org/docs/deposit/manage-versions/
