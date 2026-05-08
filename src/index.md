# 拉康开放翻译计划

拉康开放翻译计划是一个面向中文使用者的开放翻译项目，旨在整理、翻译、校订和维护雅克·拉康研讨班及相关文本的中文材料。

本仓库现在采用 Markdown 直译模式、GitHub Pull Request 协作、mdBook 构建和 GitHub Actions 发布到 GitHub Pages。

## 当前内容

- `src/s8-le-transfert`：研讨班 VIII，*Le transfert*（更新中）
- `src/s17-l-envers-de-la-psychanalyse`：研讨班 XVII，*L'envers de la psychanalyse*（待校订）
- `src/s19b-le-savoir-du-psychanalyste`：研讨班 XIXb，*Le savoir du psychanalyste*（待校订）

## 文本来源

本项目整理和翻译的研讨班原始文本主要来自 [Staferla](http://staferla.free.fr/)。

## 项目目标

- 为中文读者提供可读、可校订、可持续维护的拉康相关文本译稿。
- 保留必要的译注、术语讨论、导读、校订说明和修订痕迹。
- 使用适合 GitHub 浏览、引用、勘误和再整理的文件结构。
- 鼓励复制、传播、修订、注释和再发布。

## 分支说明

- `main`：保留完整整理稿，包括译文、注释、术语说明、导读、校订说明和个人解读等内容。
- `raw`：保留译文正文、图片和注释，清理 markdown 引用区块中的个人解读，适合作为基础译文文本阅读和校订。

`raw` 分支中的注释识别规则：markdown 引用区块可能包含多行；每个连续引用区块中，去掉 `>` 和空白后，第一条非空内容以 `注` 开头（包括 `【注】`、`[注]`、`注：` 等形式），则整个引用区块视为注释并保留；否则视为个人解读并清理。

## 参与方式

欢迎通过 Pull Request 参与：

- 修正译文错误
- 提出术语建议
- 补充注释、导读或读书笔记
- 上传其他研讨班的翻译文本
- 改进校对、格式和排版
- 报告图片缺失、链接错误或段落不清等问题

如果提交较大的译文修改，请尽量说明修改理由，尤其是涉及关键术语、句法判断或版本差异的地方。

## 许可证

本项目采用 [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.zh-hans) 许可证，您可以在这里找到完整说明：

- [署名 4.0 协议国际版 CC BY 4.0 Deed](https://creativecommons.org/licenses/by/4.0/deed.zh-hans)
- [Attribution 4.0 International CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.en)

## 版权声明

本项目只针对已经处于公共领域的原始文本进行翻译工作。

开源证书声明仅针对项目内翻译文本以及相关构建脚本，不涉及原始文本。
