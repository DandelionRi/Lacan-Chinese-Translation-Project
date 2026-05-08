# Lacan-Chinese-Translation-Project

**拉康开放翻译计划**

拉康开放翻译计划是一个面向中文使用者的开放翻译项目，旨在整理、翻译、校订和维护雅克·拉康研讨班及相关文本的中文材料。

本仓库现在采用 Markdown 直译模式、GitHub Pull Request 协作、mdBook 构建和 GitHub Actions 发布到 GitHub Pages。

## 目录结构

- `texts/`：翻译协作源文件目录，保留原文、译文、术语表和原文关联图片，是长期维护的内容层。
- `texts/<seminar>/original/lesson-xx.md`：每一期研讨班按课时拆分的原文 Markdown；段落使用稳定 ID 标记，作为共同翻译基准。
- `texts/<seminar>/translation/lesson-xx.md`：对应课时的译文 Markdown；段落 ID 应与原文保持对应，方便校对、讨论和 PR 审阅。
- `texts/<seminar>/original/assets/`：该期研讨班原文引用的图片资源。
- `texts/<seminar>/glossary.md`：该期研讨班的独立术语表。
- `src/`：mdBook 源目录，也就是发布展示层；原则上由 `texts/` 中的原文和译文合成，放置最终可读正文、目录、术语表入口和发布所需图片。
- `src/SUMMARY.md`：维护 mdBook 目录。
- `src/glossary.md`：维护全站术语表入口。
- `src/<seminar>/lesson-xx.md`：mdBook 展示页，一个 Markdown 文件对应一节；可由同编号的原文和译文按段落 ID 合成。
- `src/<seminar>/assets/`：发布页面引用的图片资源。
- `src/<seminar>/glossary.md`：发布页面中的该研讨班术语表。
- `book.toml`：维护 mdBook 配置。
- `book/`：mdBook 生成结果，已加入 `.gitignore`。

## 文本分层规则

本项目采用“协作源文件”和“发布展示层”分离的方式维护文本。

协作者主要编辑 `texts/`：

- 原文放在 `texts/<seminar>/original/`。
- 译文放在 `texts/<seminar>/translation/`。
- 原文和译文都按课时拆分为 `lesson-xx.md`。
- 段落使用稳定 ID 对齐，例如同一段原文和译文都保留 `s8-01-0001` 这样的 ID。
- 每期研讨班的术语表维护在 `texts/<seminar>/glossary.md`。

`src/` 只作为 mdBook 的发布入口。构建发布页面时，应把同一课的原文和译文按段落 ID 合成为 `src/<seminar>/lesson-xx.md`。这样可以在 GitHub Pages 上同时打包原文和译文，并通过页面脚本提供“显示原文 / 隐藏原文”的阅读开关。

因此，日常翻译 PR 应优先修改 `texts/`；`src/` 中的双语展示页可以由构建脚本重新生成，避免把协作源文件和发布格式混在一起。

## 生成发布展示层

从 `texts/` 生成 mdBook 使用：

```bash
python3 scripts/build_src_from_texts.py
```

只生成某一期研讨班时使用：

```bash
python3 scripts/build_src_from_texts.py --seminar s8-le-transfert
```

脚本会按段落 ID 合并原文和译文；译文中的连续引用区块如果以 `注` 开头会归为注释，否则归为个人解读评论。生成后的页面通过 mdBook 额外加载的 CSS/JS 提供“原文 / 注释 / 个人解读评论”三个显示开关。

## 原文整理规则

原文整理采用“Word 内容优先，PDF 分段优先”的规则：

- 正文文字以 Staferla 的 Word/DOCX 文件为共同翻译原文，不按 PDF 重新 OCR 或重录。
- 图片、图注和图片在正文中的相对位置以 Word/DOCX 导出的 Markdown 为准。
- Word/DOCX 中已经以图片形式存在的公式、图形和符号继续保留为图片引用；不要为了重写 LaTeX 而替换图片内容。
- 段落边界以对应 PDF 的视觉分段为主要依据；Word 导出时因软换行造成的碎段应合并回同一段。
- 每个段落保留一个稳定 ID，例如 `<!-- id: s8-01-0001 -->`；合并碎段的中间状态可以保留首段 ID 并出现跳号。
- 一轮批量合并全部完成后，再按每个 `lesson-xx.md` 从 `0001` 开始统一重排 ID，使同一课内部编号连续。
- 修复局部问题时只修改受影响课次，避免无关文件重新生成造成 PR 噪音。

## mdBook 公式规则

`book.toml` 已启用 `mathjax-support = true`。为兼容 mdBook 内置 MathJax 支持，Markdown 源码中的 LaTeX 公式按以下方式书写：

- 行内公式使用 `\\(...\\)`。
- 块级公式使用 `\\[...\\]`。
- 公式中的反斜线需要按 Markdown/MathJax 规则保留；非公式文本不要误写成公式块，例如舞台提示或校订提示应保持普通文本。
- 不使用 `$...$` 或 `$$...$$` 作为本项目的默认公式分隔符。
- 这条规则只适用于源码中已经是文本形式的 LaTeX；原 Word 中的公式图片仍按图片处理。

## 当前内容

- `src/s8-le-transfert`：研讨班 VIII，*Le transfert*（更新中）
- `src/s17-l-envers-de-la-psychanalyse`：研讨班 XVII，*L'envers de la psychanalyse*（待校订）
- `src/s19b-le-savoir-du-psychanalyste`：研讨班 XIXb，*Le savoir du psychanalyste*（待校订）

## 本地预览

安装 mdBook 后运行：

```bash
./bin/mdbook serve --open
```

只检查构建时运行：

```bash
./bin/mdbook build
```

## GitHub Pages 发布

`.github/workflows/mdbook.yml` 会在 PR 中构建检查 mdBook，并在 `raw` 分支推送后构建 `book/` 并发布到 GitHub Pages。

在仓库设置中需要将 Pages 的构建来源设置为 **GitHub Actions**。

## 文本来源

本项目整理和翻译的研讨班原始文本主要来自 [Staferla](http://staferla.free.fr/)。

## 分支说明

- `main`：保留完整整理稿，包括译文、注释、术语说明、导读、校订说明和个人解读等内容。
- `raw`：保留译文正文、图片和注释，清理 markdown 引用区块中的个人解读，适合作为基础译文文本阅读和校订。

`raw` 分支中的注释识别规则：markdown 引用区块可能包含多行；每个连续引用区块中，去掉 `>` 和空白后，第一条非空内容以 `注` 开头（包括 `【注】`、`[注]`、`注：` 等形式），则整个引用区块视为注释并保留；否则视为个人解读并清理。

## 项目目标

- 为中文读者提供可读、可校订、可持续维护的拉康相关文本译稿。
- 保留必要的译注、术语讨论、导读、校订说明和修订痕迹。
- 使用适合 GitHub 浏览、引用、勘误和再整理的文件结构。
- 鼓励非商业目的下的复制、传播、修订、注释和再发布。

## 参与方式

欢迎通过 Pull Request 参与：

- 修正译文错误
- 提出术语建议
- 补充注释、导读或读书笔记
- 上传其他研讨班的翻译文本
- 改进校对、格式和排版
- 报告图片缺失、链接错误或段落不清等问题

如果提交较大的译文修改，请尽量说明修改理由，尤其是涉及关键术语、句法判断或版本差异的地方。具体协作约定见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## 许可证

本项目采用双许可证：

- 文本内容：[Creative Commons Attribution-NonCommercial 4.0 International（CC BY-NC 4.0）](./LICENSE-CONTENT.md)
- 代码、脚本、模板、构建工具：[MIT License](./LICENSE-CODE.md)

文本内容包括译文、注释、术语表、导读、校订说明等。

任何人可以在非商业目的下自由复制、传播、修改、整理和再发布本项目文本内容。

完整许可证声明见 [LICENSE.md](./LICENSE.md)。

## 版权声明

本项目只处理已经处于公共领域的原始文本。

不得将本项目文本内容用于商业出版、付费电子书、收费课程材料、商业数据库、商业知识产品或其他以商业利益为主要目的的使用。
