# 贡献指南

本项目采用 Markdown 直译模式、GitHub Pull Request 协作和 mdBook 发布。

## 文件结构

- `texts/`：翻译协作源文件目录，长期维护原文、译文、术语表和原文关联图片。
- `texts/<seminar>/original/lesson-xx.md`：按课时拆分的原文 Markdown，段落使用稳定 ID。
- `texts/<seminar>/translation/lesson-xx.md`：对应课时的译文 Markdown，段落 ID 应与原文保持对应。
- `texts/<seminar>/original/assets/`：原文引用的图片资源。
- `texts/<seminar>/glossary.md`：该期研讨班的独立术语表。
- `src/`：mdBook 发布展示层，原则上由 `texts/` 中的原文和译文合成。
- `src/SUMMARY.md`：维护站点目录。新增、删除或移动课次文件时同步更新。
- `src/glossary.md`：维护全站术语表入口。
- `src/<seminar>/lesson-xx.md`：mdBook 展示页，一个 Markdown 文件对应一节。
- `src/<seminar>/assets/`：发布页面引用的图片资源。
- `src/<seminar>/glossary.md`：维护该研讨班的独立术语表。
- `book.toml`：维护 mdBook 配置。
- `book/`：mdBook 生成结果，不提交到仓库。

## 原文与分段

1. 共同翻译原文以 Staferla 的 Word/DOCX 文本为准。
2. 图片内容、图注和图片在正文中的相对位置以 Word/DOCX 导出的 Markdown 为准。
3. Word/DOCX 中已经以图片形式存在的公式、图形和符号继续保留为图片引用；
4. 段落 ID 是原文和译文对齐、讨论和审阅的锚点。


## 公式写法

`book.toml` 启用了 mdBook 的 `mathjax-support = true`，因此 LaTeX 公式按 mdBook/MathJax 方式书写：

- 行内公式使用 `\\(...\\)`。
- 块级公式使用 `\\[...\\]`。
- 不使用 `$...$` 或 `$$...$$` 作为默认公式分隔符。
- 这条规则只适用于源码中已经是文本形式的 LaTeX；原 Word 中的公式图片仍按图片处理。

## PR 协作

1. 基于 `raw` 分支创建修改分支。
2. 只修改与本次校订相关的课次、图片和术语表，优先修改 `texts/` 中的协作源文件。
3. 涉及关键术语、句法判断、版本差异或大段重译时，在 PR 说明中写明理由。
4. 新增图片放入对应研讨班目录的 `assets/`，正文中使用相对路径，例如 `![](assets/example.png)`。
5. 新增课次时同时更新 `src/SUMMARY.md` 和对应研讨班的索引页。
6. 提交 PR 后等待 GitHub Actions 的 mdBook 构建检查。

## 本地预览

安装 mdBook 后运行：

```bash
mdbook serve --open
```

只检查构建时运行：

```bash
mdbook build
```
