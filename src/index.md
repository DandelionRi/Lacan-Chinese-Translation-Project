# 拉康开放翻译计划

拉康开放翻译计划是一个面向中文使用者的开放翻译项目，旨在整理、翻译、校订和维护雅克·拉康研讨班及相关文本的中文材料。

本项目只处理已经处于公共领域的原始文本。项目中的译文、注释、术语表、导读和校订说明等文本内容，供中文读者在非商业目的下阅读、复制、传播、修改、整理和再发布。

## 当前内容

- 研讨班 VIII：*Le transfert*（更新中）
- 研讨班 XVII：*L'envers de la psychanalyse*（待校订）
- 研讨班 XIXb：*Le savoir du psychanalyste*（待校订）

## 文本来源

本项目整理和翻译的研讨班原始文本主要来自 [Staferla](http://staferla.free.fr/)。

## 分支说明

- `main`：保留完整整理稿，包括译文、注释、术语说明、导读、校订说明和个人解读等内容。
- `raw`：保留译文正文、图片和注释，清理 markdown 引用区块中的个人解读，适合作为基础译文文本阅读和校订。

`raw` 分支中的注释识别规则：markdown 引用区块可能包含多行；每个连续引用区块中，去掉 `>` 和空白后，第一条非空内容以 `注` 开头（包括 `【注】`、`[注]`、`注：` 等形式），则整个引用区块视为注释并保留；否则视为个人解读并清理。

## 参与方式

欢迎通过 GitHub Pull Request 修正译文、补充术语、报告图片缺失、改进格式和排版。如果提交较大的译文修改，请尽量说明修改理由，尤其是涉及关键术语、句法判断或版本差异的地方。

## 许可证

本项目采用双许可证：

- 文本内容：[Creative Commons Attribution-NonCommercial 4.0 International（CC BY-NC 4.0）](https://github.com/kotoba-rin/Lacan-Chinese-Translation-Project/blob/raw/LICENSE-CONTENT.md)
- 代码、脚本、模板、构建工具：[MIT License](https://github.com/kotoba-rin/Lacan-Chinese-Translation-Project/blob/raw/LICENSE-CODE.md)

文本内容包括译文、注释、术语表、导读、校订说明等。完整许可证声明见 [LICENSE.md](https://github.com/kotoba-rin/Lacan-Chinese-Translation-Project/blob/raw/LICENSE.md)。
