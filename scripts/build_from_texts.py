#!/usr/bin/env python3
"""Build mdBook input pages from canonical texts.

The texts directory is the editable source of truth:

  texts/index.md
  texts/<seminar>/original/Leçon-xx.md
  texts/<seminar>/translation/Leçon-xx.md

This script combines the original French paragraphs and the Chinese
translation blocks into build/<seminar>/Leçon-xx.md. Translation blocks may
declare either a single id:

  <!-- id: s8-01-0001 -->

or a grouped alignment:

  <!-- id: s8-01-0001 -->
  <!-- ids: s8-01-0001 s8-01-0002 -->

Grouped alignments are rendered once with all corresponding original
paragraphs. Each rendered block is ordered as original, translation, notes,
and commentary. Quote blocks in translation content are classified as notes
when their first visible text starts with "注"; other quote blocks are
rendered as commentary.
"""

from __future__ import annotations

import argparse
import re
import shutil
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
TEXTS_DIR = ROOT / "texts"
TEXTS_INDEX = TEXTS_DIR / "index.md"
BUILD_DIR = ROOT / "build"

ID_RE = re.compile(r"<!--\s*id:\s*([^>\s]+)\s*-->")
IDS_RE = re.compile(r"<!--\s*ids:\s*([^>]+?)\s*-->")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
LESSON_FILE_RE = re.compile(r"^(?:Leçon|Lecon|lesson)-(\d+)\.md$", re.IGNORECASE)
CANONICAL_LESSON_PREFIX = "Leçon"
NOTE_HEADING_RE = re.compile(r"^##\s+Notes\s*$", re.MULTILINE)
INLINE_STRONG_RE = re.compile(r"\*\*([^*\n]+?)\*\*")
OBSIDIAN_IMAGE_RE = re.compile(r"!\[\[([^\]\n]+?)\]\]")
OBSIDIAN_IMAGE_SIZE_RE = re.compile(r"^(\d+)(?:x(\d+))?$", re.IGNORECASE)
INLINE_CODE_SPAN_RE = re.compile(r"(`+)(.*?)(\1)")
ASSET_DIR_NAMES = {"original", "translation"}


@dataclass
class Paragraph:
    paragraph_id: str
    content: str


@dataclass
class Lesson:
    title: str
    intro: str
    paragraphs: list[Paragraph]
    notes: str = ""


@dataclass
class TranslationEntry:
    anchor_id: str
    paragraph_ids: list[str]
    content: str
    untranslated: bool = False


@dataclass
class RenderedTranslation:
    body: str = ""
    notes: str = ""
    commentary: str = ""


@dataclass
class BuildStats:
    lessons: int = 0
    aligned_blocks: int = 0
    untranslated_blocks: int = 0
    missing_translations: int = 0
    seminars: set[str] = field(default_factory=set)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def clean_block(text: str) -> str:
    return text.strip("\n")


def normalize_source_markdown(text: str, source_path: Path) -> str:
    """Convert Obsidian-only markdown that mdBook cannot render directly."""
    text = convert_obsidian_image_embeds(text, source_path)
    return convert_obsidian_latex_math(text)


def convert_obsidian_image_embeds(text: str, source_path: Path) -> str:
    """Convert Obsidian image embeds to mdBook-compatible HTML images.

    Obsidian accepts embeds such as:

      ![[texts/s8-le-transfert/original/assets/image5.jpeg|268]]

    mdBook does not understand that form. The build directory flattens each
    seminar's original/translation assets into build/<seminar>/assets, so the
    generated reference should point at assets/<name>.
    """
    lines = text.splitlines(keepends=True)
    converted: list[str] = []
    in_fence = False
    fence_marker = ""

    for line in lines:
        stripped = line.lstrip()
        fence_match = re.match(r"(```+|~~~+)", stripped)
        if fence_match:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker[:3]
            elif marker.startswith(fence_marker):
                in_fence = False
                fence_marker = ""
            converted.append(line)
            continue

        if in_fence:
            converted.append(line)
        else:
            converted.append(OBSIDIAN_IMAGE_RE.sub(lambda match: render_obsidian_image(match, source_path), line))

    return "".join(converted)


def convert_obsidian_latex_math(text: str) -> str:
    """Convert Obsidian dollar-delimited math to MathJax default delimiters.

    Obsidian commonly uses `$...$` for inline math and `$$...$$` for display
    math. mdBook's MathJax integration expects the generated Markdown source
    to contain double-backslash delimiters such as `\\(` and `\\[`.
    """
    lines = text.splitlines(keepends=True)
    converted: list[str] = []
    in_fence = False
    fence_marker = ""
    display_math_lines: list[str] | None = None

    for line in lines:
        stripped = line.lstrip()
        fence_match = re.match(r"(```+|~~~+)", stripped)
        if fence_match and display_math_lines is None:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker[:3]
            elif marker.startswith(fence_marker):
                in_fence = False
                fence_marker = ""
            converted.append(line)
            continue

        if in_fence:
            converted.append(line)
            continue

        if display_math_lines is not None:
            if stripped.strip() == "$$":
                converted.append("\\\\[\n")
                converted.extend(display_math_lines)
                converted.append("\\\\]\n")
                display_math_lines = None
            else:
                display_math_lines.append(line)
            continue

        if stripped.strip() == "$$":
            display_math_lines = []
            continue

        converted.append(convert_inline_obsidian_math(line))

    if display_math_lines is not None:
        converted.append("$$\n")
        converted.extend(display_math_lines)

    return "".join(converted)


def convert_inline_obsidian_math(line: str) -> str:
    return transform_outside_inline_code(line, convert_inline_math_segment)


def transform_outside_inline_code(line: str, transform) -> str:
    parts: list[str] = []
    cursor = 0
    for match in INLINE_CODE_SPAN_RE.finditer(line):
        parts.append(transform(line[cursor : match.start()]))
        parts.append(match.group(0))
        cursor = match.end()
    parts.append(transform(line[cursor:]))
    return "".join(parts)


def convert_inline_math_segment(segment: str) -> str:
    out: list[str] = []
    cursor = 0
    length = len(segment)

    while cursor < length:
        char = segment[cursor]
        if char != "$" or is_escaped(segment, cursor):
            out.append(char)
            cursor += 1
            continue

        if cursor + 1 < length and segment[cursor + 1] == "$":
            end = find_unescaped_dollars(segment, cursor + 2, "$$")
            if end is None:
                out.append("$$")
                cursor += 2
                continue
            math = segment[cursor + 2 : end].strip()
            if math:
                out.append(f"\\\\[{math}\\\\]")
            else:
                out.append("$$$$")
            cursor = end + 2
            continue

        end = find_unescaped_dollars(segment, cursor + 1, "$")
        if end is None:
            out.append(char)
            cursor += 1
            continue

        math = segment[cursor + 1 : end].strip()
        if should_convert_inline_math(math):
            out.append(f"\\\\({math}\\\\)")
        else:
            out.append(segment[cursor : end + 1])
        cursor = end + 1

    return "".join(out)


def find_unescaped_dollars(text: str, start: int, marker: str) -> int | None:
    cursor = start
    while cursor < len(text):
        index = text.find(marker, cursor)
        if index == -1:
            return None
        if not is_escaped(text, index):
            return index
        cursor = index + len(marker)
    return None


def is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def should_convert_inline_math(math: str) -> bool:
    if not math or "\n" in math:
        return False
    return True


def render_obsidian_image(match: re.Match[str], source_path: Path) -> str:
    target, options = split_obsidian_embed(match.group(1))
    if not target:
        return match.group(0)

    width = ""
    height = ""
    alt = ""
    for option in options:
        size_match = OBSIDIAN_IMAGE_SIZE_RE.match(option)
        if size_match:
            width = size_match.group(1)
            height = size_match.group(2) or ""
        elif not alt:
            alt = option

    src = resolve_obsidian_asset_path(target, source_path)
    alt = alt or Path(target.split("#", 1)[0]).name or target
    attrs = [
        f'src="{escape(src, quote=True)}"',
        f'alt="{escape(alt, quote=True)}"',
    ]
    if width:
        attrs.append(f'width="{escape(width, quote=True)}"')
    if height:
        attrs.append(f'height="{escape(height, quote=True)}"')
    return f"<img {' '.join(attrs)} />"


def split_obsidian_embed(raw: str) -> tuple[str, list[str]]:
    parts = [part.strip() for part in raw.split("|")]
    target = parts[0].strip()
    return target, [part for part in parts[1:] if part]


def resolve_obsidian_asset_path(target: str, source_path: Path) -> str:
    target = target.strip().replace("\\", "/")
    path_without_fragment = target.split("#", 1)[0].split("?", 1)[0].strip()
    if not path_without_fragment:
        return target

    normalized = path_without_fragment.lstrip("/")
    parts = [part for part in normalized.split("/") if part and part != "."]
    assets_index = asset_path_index(parts)
    if assets_index is not None:
        return "/".join(["assets", *parts[assets_index + 1 :]])

    relative_candidate = (source_path.parent / normalized).resolve()
    try:
        relative_parts = list(relative_candidate.relative_to(TEXTS_DIR.resolve()).parts)
    except ValueError:
        relative_parts = []
    assets_index = asset_path_index(relative_parts)
    if assets_index is not None:
        return "/".join(["assets", *relative_parts[assets_index + 1 :]])

    same_folder_asset = source_path.parent / "assets" / normalized
    if same_folder_asset.exists():
        return f"assets/{normalized}"

    seminar_dir = source_path.parents[1] if len(source_path.parents) > 1 else source_path.parent
    for folder in ("original", "translation"):
        seminar_asset = seminar_dir / folder / "assets" / normalized
        if seminar_asset.exists():
            return f"assets/{normalized}"

    return normalized


def asset_path_index(parts: list[str]) -> int | None:
    for index, part in enumerate(parts):
        if part != "assets":
            continue
        if index >= 1 and parts[index - 1] in ASSET_DIR_NAMES and index + 1 < len(parts):
            return index
        if index == 0 and index + 1 < len(parts):
            return index
    return None


def split_notes(text: str) -> tuple[str, str]:
    match = NOTE_HEADING_RE.search(text)
    if not match:
        return text, ""
    return text[: match.start()].rstrip(), text[match.start() :].strip()


def parse_lesson(path: Path) -> Lesson:
    text = normalize_source_markdown(read_text(path), path)
    body, notes = split_notes(text)
    matches = list(ID_RE.finditer(body))

    if not matches:
        lines = body.splitlines()
        title = lines[0].strip() if lines else f"# {path.stem}"
        return Lesson(title=title, intro="", paragraphs=[], notes=notes)

    title_source = body[: matches[0].start()].strip()
    title = first_markdown_heading(title_source) or f"# {path.stem}"
    intro = title_source

    paragraphs: list[Paragraph] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        paragraphs.append(
            Paragraph(
                paragraph_id=match.group(1).strip(),
                content=clean_block(body[start:end]),
            )
        )

    return Lesson(title=title, intro=intro, paragraphs=paragraphs, notes=notes)


def first_markdown_heading(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.strip()
    return None


def strip_metadata_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("<!--") and (
            "source:" in stripped
            or "imported:" in stripped
            or "translation:" in stripped
            or "align" in stripped
        ):
            continue
        lines.append(line)
    return "\n".join(lines).strip("\n")


def parse_translation(path: Path) -> list[TranslationEntry]:
    if not path.exists():
        return []

    text = normalize_source_markdown(read_text(path), path)
    matches = list(ID_RE.finditer(text))
    entries: list[TranslationEntry] = []

    for index, match in enumerate(matches):
        anchor_id = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[start:end].strip("\n")

        ids_match = IDS_RE.search(block)
        if ids_match:
            paragraph_ids = ids_match.group(1).split()
            block = IDS_RE.sub("", block, count=1)
        else:
            paragraph_ids = [anchor_id]

        untranslated = "<!-- untranslated -->" in block
        block = block.replace("<!-- untranslated -->", "")
        block = HTML_COMMENT_RE.sub("", block)
        block = strip_metadata_comments(block)

        entries.append(
            TranslationEntry(
                anchor_id=anchor_id,
                paragraph_ids=paragraph_ids,
                content=block.strip(),
                untranslated=untranslated,
            )
        )

    return entries


def note_like_quote(lines: list[str]) -> bool:
    visible_lines = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith(">"):
            stripped = stripped[1:].strip()
        if stripped:
            visible_lines.append(stripped)

    if not visible_lines:
        return False

    first = visible_lines[0].lstrip("【[（(").strip()
    return first.startswith("注")


def split_translation_chunks(content: str) -> list[tuple[str, list[str]]]:
    lines = content.splitlines()
    chunks: list[tuple[str, list[str]]] = []
    normal: list[str] = []
    index = 0

    def flush_normal() -> None:
        nonlocal normal
        if normal and any(line.strip() for line in normal):
            chunks.append(("normal", trim_blank_lines(normal)))
        normal = []

    while index < len(lines):
        line = lines[index]
        if line.lstrip().startswith(">"):
            flush_normal()
            quote: list[str] = []
            while index < len(lines) and lines[index].lstrip().startswith(">"):
                quote.append(lines[index])
                index += 1
            kind = "note" if note_like_quote(quote) else "commentary"
            chunks.append((kind, trim_blank_lines(quote)))
            continue

        normal.append(line)
        index += 1

    flush_normal()
    return [(kind, chunk) for kind, chunk in chunks if chunk]


def trim_blank_lines(lines: list[str]) -> list[str]:
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def grouped_entries(entries: Iterable[TranslationEntry]) -> tuple[dict[str, list[TranslationEntry]], set[str]]:
    by_anchor: dict[str, list[TranslationEntry]] = {}
    covered_non_anchor: set[str] = set()

    for entry in entries:
        anchor = entry.anchor_id
        by_anchor.setdefault(anchor, []).append(entry)
        for paragraph_id in entry.paragraph_ids:
            if paragraph_id != anchor:
                covered_non_anchor.add(paragraph_id)

    return by_anchor, covered_non_anchor


def render_translation_entry(entry: TranslationEntry) -> RenderedTranslation:
    if entry.untranslated or not entry.content.strip():
        return RenderedTranslation(body='<p class="translation-missing">[未译]</p>')

    body: list[str] = []
    notes: list[str] = []
    commentary: list[str] = []
    for kind, lines in split_translation_chunks(entry.content):
        text = render_translation_inline_markup("\n".join(lines).strip())
        if not text:
            continue
        if kind == "note":
            notes.extend(['<div class="note-block">', "", text, "", "</div>", ""])
        elif kind == "commentary":
            commentary.extend(['<div class="commentary-block">', "", text, "", "</div>", ""])
        else:
            body.extend([text, ""])

    return RenderedTranslation(
        body="\n".join(body).strip(),
        notes="\n".join(notes).strip(),
        commentary="\n".join(commentary).strip(),
    )


def render_translation_inline_markup(text: str) -> str:
    """Keep translation emphasis from leaking as literal Markdown markers."""
    return INLINE_STRONG_RE.sub(r"<strong>\1</strong>", text)


def render_original_blocks(blocks: list[Paragraph]) -> str:
    out: list[str] = []
    for block in blocks:
        out.append(f'<div class="original-paragraph" data-paragraph-id="{block.paragraph_id}">')
        out.append("")
        out.append(block.content.strip() or "&nbsp;")
        out.append("")
        out.append("</div>")
        out.append("")
    return "\n".join(out).strip()


def render_lesson(original_path: Path, translation_path: Path | None) -> tuple[str, BuildStats]:
    lesson = parse_lesson(original_path)
    entries = parse_translation(translation_path) if translation_path else []
    by_anchor, covered_non_anchor = grouped_entries(entries)
    by_id = {paragraph.paragraph_id: paragraph for paragraph in lesson.paragraphs}

    out: list[str] = []
    out.append(lesson.title)
    out.append("")
    out.extend(render_controls())
    out.append("")
    out.append('<div class="parallel-text">')
    out.append("")

    stats = BuildStats(lessons=1)
    consumed: set[str] = set()

    for paragraph in lesson.paragraphs:
        paragraph_id = paragraph.paragraph_id
        if paragraph_id in consumed or paragraph_id in covered_non_anchor:
            continue

        entries_for_id = by_anchor.get(paragraph_id, [])
        if entries_for_id:
            for entry in entries_for_id:
                paragraph_ids = [pid for pid in entry.paragraph_ids if pid in by_id]
                if not paragraph_ids:
                    paragraph_ids = [paragraph_id]
                original_blocks = [by_id[pid] for pid in paragraph_ids if pid in by_id]
                consumed.update(paragraph_ids)
                stats.aligned_blocks += 1
                if entry.untranslated:
                    stats.untranslated_blocks += 1
                out.extend(render_parallel_block(paragraph_ids, original_blocks, render_translation_entry(entry)))
        else:
            consumed.add(paragraph_id)
            stats.missing_translations += 1
            out.extend(
                render_parallel_block(
                    [paragraph_id],
                    [paragraph],
                    RenderedTranslation(body='<p class="translation-missing">[无对应译文]</p>'),
                )
            )

    out.append("</div>")
    out.append("")

    if lesson.notes:
        out.append('<section class="note-block original-notes">')
        out.append("")
        out.append(lesson.notes)
        out.append("")
        out.append("</section>")
        out.append("")

    return "\n".join(out).rstrip() + "\n", stats


def render_controls() -> list[str]:
    return [
        '<div class="reading-controls lacan-tool-panel" role="group" aria-label="页面功能区">',
        '  <div class="lacan-toggle-group" aria-label="显示选项">',
        '    <label><input type="checkbox" data-lacan-toggle="original" checked> 原文</label>',
        '    <label><input type="checkbox" data-lacan-toggle="notes" checked> 注释</label>',
        '    <label><input type="checkbox" data-lacan-toggle="commentary" checked> 建言</label>',
        "  </div>",
        '  <form class="lacan-tool-search" role="search">',
        '    <input class="lacan-tool-search-input" type="search" placeholder="搜索全文" aria-label="搜索全文">',
        '    <button class="lacan-tool-button" type="submit" title="搜索">搜索</button>',
        "  </form>",
        '  <button class="lacan-tool-button lacan-back-to-top" type="button" title="回到页面最上方" aria-label="回到页面最上方">↑</button>',
        "</div>",
    ]


def render_parallel_block(
    paragraph_ids: list[str],
    original_blocks: list[Paragraph],
    translation: RenderedTranslation,
) -> list[str]:
    ids_text = " ".join(paragraph_ids)
    ids_label = ", ".join(escape(paragraph_id) for paragraph_id in paragraph_ids)
    anchor_id = escape(paragraph_ids[0], quote=True)
    ids_attr = escape(ids_text, quote=True)
    out = [
        f'<section id="{anchor_id}" class="parallel-paragraph" data-paragraph-ids="{ids_attr}">',
    ]

    for paragraph_id in paragraph_ids[1:]:
        out.append(
            f'<span id="{escape(paragraph_id, quote=True)}" class="paragraph-anchor-alias" aria-hidden="true"></span>'
        )

    out.extend([
        f'<div class="paragraph-id">{ids_label}</div>',
        '<details class="original-block" open>',
        f"<summary>原文 · {ids_label}</summary>",
        "",
        render_original_blocks(original_blocks),
        "",
        "</details>",
    ])

    if translation.body:
        out.extend(["<div class=\"translation-block\">", "", translation.body, "", "</div>"])
    if translation.notes:
        out.extend(["", translation.notes])
    if translation.commentary:
        out.extend(["", translation.commentary])

    out.extend(["</section>", ""])
    return out


def lesson_number(path: Path) -> int | None:
    match = LESSON_FILE_RE.match(path.name)
    if match:
        return int(match.group(1))
    return None


def lesson_filename(number: int) -> str:
    return f"{CANONICAL_LESSON_PREFIX}-{number:02d}.md"


def lesson_sort_key(path: Path) -> tuple[int, str]:
    number = lesson_number(path)
    return number if number is not None else 9999, path.name


def lesson_markdown_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        (path for path in directory.glob("*.md") if lesson_number(path) is not None),
        key=lesson_sort_key,
    )


def matching_lesson_file(directory: Path, number: int | None, preferred_name: str) -> Path:
    candidates = [directory / preferred_name]
    if number is not None:
        candidates.extend(
            [
                directory / lesson_filename(number),
                directory / f"lesson-{number:02d}.md",
                directory / f"Lecon-{number:02d}.md",
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def remove_build_lesson_files(output_dir: Path) -> None:
    for path in lesson_markdown_files(output_dir):
        path.unlink()


def seminar_title(slug: str, seminar_dir: Path) -> str:
    readme = seminar_dir / "original" / "README.md"
    if readme.exists():
        readme_text = read_text(readme)
        source_title = re.search(r"^\s*-\s*标题[:：]\s*(.+?)\s*$", readme_text, re.MULTILINE)
        if source_title:
            return f"{seminar_label(slug)}：{source_title.group(1).strip()}"

        title = first_markdown_heading(readme_text)
        if title:
            clean_title = title.lstrip("#").strip()
            if clean_title.endswith("原文"):
                return seminar_label(slug)
            return clean_title

    lessons = lesson_markdown_files(seminar_dir / "original")
    if lessons:
        title = parse_lesson(lessons[0]).title
        if "|" in title:
            return title.lstrip("#").split("|", 1)[0].strip()
        return title.lstrip("#").strip()

    return slug


def seminar_label(slug: str) -> str:
    first = slug.split("-", 1)[0]
    if re.match(r"^s\d+[a-z]?$", first):
        return first.upper()
    return slug


def seminar_sort_key(slug: str) -> tuple[int, str, str]:
    match = re.match(r"^s(\d+)([a-z]?)(?:-|$)", slug)
    if match:
        return int(match.group(1)), match.group(2), slug
    return 9999, "", slug


def build_seminar(slug: str) -> BuildStats:
    seminar_dir = TEXTS_DIR / slug
    original_dir = seminar_dir / "original"
    translation_dir = seminar_dir / "translation"
    output_dir = BUILD_DIR / slug
    stats = BuildStats(seminars={slug})

    if not original_dir.exists():
        raise FileNotFoundError(f"Missing original directory: {original_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    remove_build_lesson_files(output_dir)
    write_text(output_dir / "README.md", render_seminar_readme(slug, seminar_dir))

    for lesson_path in lesson_markdown_files(original_dir):
        number = lesson_number(lesson_path)
        output_name = lesson_filename(number) if number is not None else lesson_path.name
        translation_path = matching_lesson_file(translation_dir, number, lesson_path.name)
        rendered, lesson_stats = render_lesson(
            lesson_path,
            translation_path if translation_path.exists() else None,
        )
        write_text(output_dir / output_name, rendered)
        stats.lessons += lesson_stats.lessons
        stats.aligned_blocks += lesson_stats.aligned_blocks
        stats.untranslated_blocks += lesson_stats.untranslated_blocks
        stats.missing_translations += lesson_stats.missing_translations

    copy_assets(original_dir / "assets", output_dir / "assets")
    copy_assets(translation_dir / "assets", output_dir / "assets")

    glossary = seminar_dir / "glossary.md"
    if glossary.exists():
        shutil.copy2(glossary, output_dir / "glossary.md")

    return stats


def render_seminar_readme(slug: str, seminar_dir: Path) -> str:
    title = seminar_title(slug, seminar_dir)
    lines = [f"# {title}", ""]

    if (seminar_dir / "glossary.md").exists() or (BUILD_DIR / slug / "glossary.md").exists():
        lines.append("- [术语表](glossary.md)")
        lines.append("")

    original_dir = seminar_dir / "original"
    lessons = lesson_markdown_files(original_dir)
    if lessons:
        lines.append("## 课时目录")
        lines.append("")
        for lesson in lessons:
            number = lesson_number(lesson)
            output_name = lesson_filename(number) if number is not None else lesson.name
            lesson_title = parse_lesson(lesson).title.lstrip("#").strip()
            lines.append(f"- [{lesson_title}]({output_name})")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def copy_assets(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    destination.mkdir(parents=True, exist_ok=True)
    for path in source.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def discover_text_seminars() -> list[str]:
    if not TEXTS_DIR.exists():
        return []
    seminars = []
    for path in TEXTS_DIR.iterdir():
        if path.is_dir() and (path / "original").exists():
            seminars.append(path.name)
    return sorted(seminars, key=seminar_sort_key)


def discover_build_seminars() -> list[str]:
    if not BUILD_DIR.exists():
        return []
    seminars = []
    for path in BUILD_DIR.iterdir():
        if path.is_dir() and (path / "README.md").exists():
            seminars.append(path.name)
    return sorted(seminars, key=seminar_sort_key)


def write_summary() -> None:
    lines = ["# Summary", ""]

    index = BUILD_DIR / "index.md"
    if TEXTS_INDEX.exists():
        write_text(index, read_text(TEXTS_INDEX).rstrip() + "\n")
        lines.append("- [首页](index.md)")
    elif index.exists():
        lines.append("- [首页](index.md)")
    else:
        write_text(index, "# 拉康开放翻译计划\n")
        lines.append("- [首页](index.md)")

    glossary = BUILD_DIR / "glossary.md"
    if glossary.exists():
        lines.append("- [全局术语表](glossary.md)")

    for slug in discover_build_seminars():
        readme = BUILD_DIR / slug / "README.md"
        title = first_markdown_heading(read_text(readme)) or f"# {slug}"
        lines.append(f"- [{title.lstrip('#').strip()}]({slug}/README.md)")

        glossary = BUILD_DIR / slug / "glossary.md"
        if glossary.exists():
            lines.append(f"  - [术语表]({slug}/glossary.md)")

        for lesson in lesson_markdown_files(BUILD_DIR / slug):
            lesson_title = first_markdown_heading(read_text(lesson))
            label = lesson_title.lstrip("#").strip() if lesson_title else lesson.stem
            lines.append(f"  - [{label}]({slug}/{lesson.name})")

    write_text(BUILD_DIR / "SUMMARY.md", "\n".join(lines).rstrip() + "\n")


def combine_stats(stats: Iterable[BuildStats]) -> BuildStats:
    combined = BuildStats()
    for item in stats:
        combined.lessons += item.lessons
        combined.aligned_blocks += item.aligned_blocks
        combined.untranslated_blocks += item.untranslated_blocks
        combined.missing_translations += item.missing_translations
        combined.seminars.update(item.seminars)
    return combined


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build mdBook input pages from texts.")
    parser.add_argument(
        "--seminar",
        action="append",
        help="Seminar slug to build. May be used multiple times. Defaults to every texts/*/original directory.",
    )
    parser.add_argument(
        "--skip-summary",
        action="store_true",
        help="Do not regenerate build/SUMMARY.md.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seminars = args.seminar or discover_text_seminars()
    if not seminars:
        raise SystemExit("No seminar directories found under texts/")

    stats = combine_stats(build_seminar(slug) for slug in seminars)
    if not args.skip_summary:
        write_summary()

    seminar_list = ", ".join(sorted(stats.seminars))
    print(f"Built seminars: {seminar_list}")
    print(f"Lessons: {stats.lessons}")
    print(f"Aligned translation blocks: {stats.aligned_blocks}")
    print(f"Untranslated blocks: {stats.untranslated_blocks}")
    print(f"Missing translation blocks: {stats.missing_translations}")


if __name__ == "__main__":
    main()
