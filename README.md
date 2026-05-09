# Lacan-Chinese-Translation-Project

**拉康开放翻译计划**

拉康开放翻译计划是一个面向中文使用者的开放翻译项目，旨在整理、翻译、校订和维护雅克·拉康研讨班及相关文本的中文材料。

本仓库现在采用 Markdown 直译模式、GitHub Pull Request 协作、mdBook 构建和 GitHub Actions 发布到 GitHub Pages。

## 文本来源

本项目整理和翻译的研讨班原始文本主要来自 [Staferla](http://staferla.free.fr/)。

## 分支说明

- `main`：主干分支，保留完整整理稿，包括译文、注释、术语说明、导读、校订说明和个人解读等内容。
- `DEV`：脚本开发分支，针对 mdBook 页面功能适配进行开发迭代，完成后合并至 `main` 分支。

## 项目目标

- 为中文读者提供可读、可校订、可持续维护的拉康相关文本译稿。
- 保留必要的译注、术语讨论、导读、校订说明和修订痕迹。
- 使用适合 GitHub 浏览、引用、勘误和再整理的文件结构。
- 鼓励复制、传播、修订、注释和再发布。

## 参与方式

欢迎通过 Pull Request 参与：

- 修正译文错误
- 提出术语建议
- 补充注释、导读或读书笔记
- 上传其他研讨班的翻译文本
- 改进校对、格式和排版
- 报告图片缺失、链接错误或段落不清等问题

如果提交较大的译文修改，请尽量说明修改理由，尤其是涉及关键术语、句法判断或版本差异的地方。具体协作约定见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## 目录结构

- `texts/`：翻译协作源文件目录，保留原文、译文、术语表和原文关联图片，是长期维护的内容层。
- `texts/<seminar>/original/Leçon-xx.md`：每一期研讨班按课时拆分的原文 Markdown；段落使用稳定 ID 标记，作为共同翻译基准。
- `texts/<seminar>/translation/Leçon-xx.md`：对应课时的译文 Markdown；段落 ID 应与原文保持对应，方便校对、讨论和 PR 审阅。
- `texts/<seminar>/original/assets/`：该期研讨班原文引用的图片资源。
- `texts/<seminar>/glossary.md`：该期研讨班的独立术语表。
- `texts/index.md`：mdBook 首页源文件，构建时生成到 `src/index.md`。
- `src/`：mdBook 源目录，也就是发布展示层；由 `texts/` 和 `scripts/build_src_from_texts.py` 生成，已加入 `.gitignore`，不作为长期维护内容提交。
- `scripts/requirements.txt`：Python 脚本依赖清单，CI 和本地环境使用同一个入口安装依赖。
- `book.toml`：维护 mdBook 配置。
- `book/`：mdBook 生成结果，已加入 `.gitignore`。

## 文本分层规则

本项目采用“协作源文件”和“发布展示层”分离的方式维护文本。

协作者主要编辑 `texts/`：

- 原文放在 `texts/<seminar>/original/`。
- 译文放在 `texts/<seminar>/translation/`。
- 原文和译文都按课时拆分为 `Leçon-xx.md`。
- 段落使用稳定 ID 对齐，例如同一段原文和译文都保留 `s8-01-0001` 这样的 ID。
- 每期研讨班的术语表维护在 `texts/<seminar>/glossary.md`。

`src/` 只作为 mdBook 的发布入口。构建发布页面时，脚本会把同一课的原文和译文按段落 ID 合成为 `src/<seminar>/Leçon-xx.md`。这样可以在 GitHub Pages 上同时打包原文和译文，并通过页面脚本提供“显示原文 / 隐藏原文”的阅读开关。

因此，日常翻译 PR 应修改 `texts/`；项目说明页修改根目录 `README.md`，贡献指南修改根目录 `CONTRIBUTING.md`，mdBook 首页修改 `texts/index.md`。`src/` 中的双语展示页由构建脚本重新生成，不提交到仓库，避免把协作源文件和发布格式混在一起。

## 分段 ID 说明

分段 ID 是本项目协作时引用具体段落的稳定锚点，格式通常类似 `s8-01-0001`，表示研讨班、课次和段落序号。原文与译文通过同一个分段 ID 对齐，构建脚本也依靠这些 ID 生成双语对照页面。

在评论、校验、交流和 Pull Request 审阅过程中，请尽量使用分段 ID 指明讨论对象。例如可以写“`s8-01-0001` 的术语建议”或“请核对 `s8-01-0002` 与原文的对应关系”。这样比只说“第三段”更稳定，因为页面展示、排序或上下文发生变化后，分段 ID 仍能定位到同一处文本。

维护文本时不要随意改动已有分段 ID。只有在原文分段结构确实需要调整时，才同步更新相关原文、译文、注释和 PR 说明，避免评论、校验记录和后续修订失去引用对象。

## mdBook 相关资源

- 项目地址：[rust-lang/mdBook](https://github.com/rust-lang/mdBook)
- 使用文档：[mdBook Documentation](https://rust-lang.github.io/mdBook/)
- 下载地址：[mdBook Releases](https://github.com/rust-lang/mdBook/releases)

本项目不提交 mdBook 二进制文件，也不提交生成后的 `src/` 和 `book/` 目录。`bin/` 是本地工具目录，已加入 `.gitignore`；GitHub Actions 会在 CI 中下载 Linux 版 mdBook。本地使用时，请先安装 `mdbook` 并确保它在 `PATH` 中：

```bash
mdbook --version
```

常见安装方式：

```bash
cargo install mdbook
```

也可以从 [mdBook Releases](https://github.com/rust-lang/mdBook/releases) 下载对应系统的预编译二进制文件，解压后放到本机 `PATH` 中。

Python 脚本依赖由 `scripts/requirements.txt` 维护。当前脚本只使用 Python 标准库，仍建议使用同一命令初始化环境，方便后续新增依赖：

```bash
python3 -m pip install -r scripts/requirements.txt
```

## 生成发布展示层

`scripts/build_src_from_texts.py` 用来把长期维护的 `texts/` 内容合成为 mdBook 使用的 `src/` 展示层。日常翻译、校对和分段调整应优先修改 `texts/`；修改完成后再运行这个脚本重新生成 `src/`。

### 基本命令

从全部 `texts/<seminar>/original/` 目录生成 `src/`：

```bash
python3 scripts/build_src_from_texts.py
```

只生成某一期研讨班：

```bash
python3 scripts/build_src_from_texts.py --seminar s8-le-transfert
```

一次只生成多期研讨班，可以重复传入 `--seminar`：

```bash
python3 scripts/build_src_from_texts.py \
  --seminar s8-le-transfert \
  --seminar s20-encore
```

只更新课文页面、不重写 `src/SUMMARY.md`：

```bash
python3 scripts/build_src_from_texts.py --seminar s8-le-transfert --skip-summary
```

生成 `src/` 后再打包 mdBook：

```bash
python3 scripts/build_src_from_texts.py
mdbook build
```

本地预览：

```bash
python3 scripts/build_src_from_texts.py
mdbook serve --open
```

### 输入目录约定

脚本读取以下文件：

- `texts/index.md`：可选。存在时会生成 `src/index.md`，作为 mdBook 首页。
- `texts/<seminar>/original/Leçon-xx.md`：必需。每个 `<!-- id: ... -->` 标记开始一个原文段落，直到下一个 ID 标记为止。
- `texts/<seminar>/translation/Leçon-xx.md`：可选。文件不存在时，该课原文仍会生成，译文位置显示 `[无对应译文]`。
- `texts/<seminar>/original/assets/`：可选。原文图片会复制到 `src/<seminar>/assets/`。
- `texts/<seminar>/translation/assets/`：可选。译文额外图片也会复制到 `src/<seminar>/assets/`。
- `texts/<seminar>/glossary.md`：可选。存在时会复制为 `src/<seminar>/glossary.md`。
- `texts/<seminar>/original/README.md`：可选。存在时脚本会优先用其中的标题生成 `src/<seminar>/README.md`。

`<seminar>` 必须使用目录 slug，例如 `s8-le-transfert`、`s20-encore`。`Leçon-xx.md` 的编号用于排序，建议保持两位数字，例如 `Leçon-01.md`。

### 原文格式

原文课文的基本结构如下：

```markdown
# Leçon 01 | 16 Novembre 1960

<!-- id: s8-01-0001 -->

原文第一段。

<!-- id: s8-01-0002 -->

原文第二段。
```

标题位于第一个段落 ID 之前。`## Notes` 及其后面的内容会被视为原文注释区，生成到页面底部的注释块里。

### 译文格式

译文同样使用 `<!-- id: ... -->` 标记。一个 ID 到下一个 ID 之间的内容是一个译文条目：

```markdown
<!-- id: s8-01-0001 -->

中文译文第一段。

<!-- id: s8-01-0002 -->

中文译文第二段。
```

译文分段规则：

- 两段之间有空行，视为不同 Markdown 段落。
- 只有换行但没有空行，仍视为同一个文本区块。
- 译文条目下方的引用区块会被视为对该译文条目的注释或个人解读。

如果一个中文译文条目对应多个原文段落，在译文 ID 后添加 `<!-- ids: ... -->`：

```markdown
<!-- id: s8-01-0001 -->
<!-- ids: s8-01-0001 s8-01-0002 s8-01-0003 -->

这一个中文译文区块对应上面三个原文段落。
```

其中 `id` 是该译文条目的锚点，`ids` 是它实际覆盖的原文段落 ID 列表。生成页面时，这些原文段落会合并显示在同一个对照区块里。

如果某段已经确认暂不翻译，可以标记：

```markdown
<!-- id: s8-01-0004 -->
<!-- untranslated -->
```

页面会显示 `[未译]`。如果完全没有对应译文文件或译文 ID，页面会显示 `[无对应译文]`。

### 注释和个人解读

译文条目中的连续引用区块会被单独分类：

```markdown
<!-- id: s8-01-0005 -->

这里是译文正文。

> 注：这里是译注。

> 这里是个人解读或评论。
```

识别规则：

- 连续引用区块的第一条非空内容，以 `注` 开头，或者以 `【注】`、`[注]`、`（注` 这类形式开头，则整个引用区块归为“注释”。
- 其他引用区块归为“个人解读评论”。
- 页面会提供“原文 / 注释 / 个人解读评论”三个开关，分别控制这些内容的显示。

### 注意事项

- `src/` 是展示层，可以由脚本重建；长期维护内容应放在 `texts/`。
- 修改 `texts/` 后，提交前建议运行 `python3 scripts/build_src_from_texts.py && mdbook build`。
- 只想降低 PR 噪音时，可以用 `--seminar` 限定本次修改涉及的研讨班。
- 如果修改了研讨班目录结构、课次文件、标题或术语表，通常不要使用 `--skip-summary`，让脚本同步更新 `src/SUMMARY.md`。

## mdBook 公式规则

`book.toml` 已启用 `mathjax-support = true`。为兼容 mdBook 内置 MathJax 支持，Markdown 源码中的 LaTeX 公式按以下方式书写：

- 行内公式使用 `\\(...\\)`。
- 块级公式使用 `\\[...\\]`。
- 公式中的反斜线需要按 Markdown/MathJax 规则保留；非公式文本不要误写成公式块，例如舞台提示或校订提示应保持普通文本。
- 不使用 `$...$` 或 `$$...$$` 作为本项目的默认公式分隔符。
- 这条规则只适用于源码中已经是文本形式的 LaTeX；原 Word 中的公式图片仍按图片处理。

## 当前内容

- `texts/s8-le-transfert`：研讨班 VIII，*Le transfert*（更新中）
- `texts/s17-l-envers-de-la-psychanalyse`：研讨班 XVII，*L'envers de la psychanalyse*（待校订）
- `texts/s19b-le-savoir-du-psychanalyste`：研讨班 XIXb，*Le savoir du psychanalyste*（待校订）

## 本地预览

生成 `src/` 后运行：

```bash
python3 scripts/build_src_from_texts.py
mdbook serve --open
```

只检查构建时运行：

```bash
python3 scripts/build_src_from_texts.py
mdbook build
```

## GitHub Pages 发布

`.github/workflows/mdbook.yml` 会在 PR 中构建检查 mdBook，并在 `main` 分支推送后构建 `book/` 并发布到 GitHub Pages。

在仓库设置中需要将 Pages 的构建来源设置为 **GitHub Actions**。

## 许可证

[![License: CC-BY 4.0](https://img.shields.io/github/license/kotoba-rin/Lacan-Chinese-Translation-Project?logo=opensourceinitiative&logoColor=green&color=slategray)](https://github.com/kotoba-rin/Lacan-Chinese-Translation-Project/blob/main/LICENSE)

本项目贡献者自行创作的中文译文、译注、术语表、导读、校订说明、读书笔记、项目文档，以及用于整理、构建和发布的脚本、模板、自动化配置，采用 [CC-BY 4.0](https://github.com/kotoba-rin/Lacan-Chinese-Translation-Project/blob/main/LICENSE) 许可证。适用范围和版权说明见 [NOTICE.md](./NOTICE.md)。

您可以在这里找到完整说明：

- [署名 4.0 协议国际版 CC BY 4.0 Deed](https://creativecommons.org/licenses/by/4.0/deed.zh-hans)
- [Attribution 4.0 International CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.en)

## 版权声明

本项目可能包含或引用原始法文文本、原文图片、扫描整理结果以及其他第三方材料。上述材料不因收录、引用、对照展示或构建发布而自动纳入本项目的 CC BY 4.0 授权范围。

本项目整理和对照使用的法语原文主要来自互联网上公开可访问资料，包括 Staferla（[http://staferla.free.fr/](http://staferla.free.fr/)）。

这些材料的权利状态以其来源、权利人声明和适用法律为准。本项目不对其版权归属、授权状态或可复用性作法律判断，也不改变其自身的版权状态。
