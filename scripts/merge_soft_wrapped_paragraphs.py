#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


ID_RE = re.compile(r"^<!-- id: ([^ ]+) -->$")
IMAGE_RE = re.compile(r"^\s*(?:<img\b|!\[[^\]]*\]\()")
LIST_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
FOOTNOTE_RE = re.compile(r"^\[\^[^\]]+\]:")

WEAK_END_RE = re.compile(
    r"(?:[,;:،]|[-–—]|…|\\.\\.\\.|\\b(?:et|ou|de|du|des|d|l|la|le|les|un|une|"
    r"que|qui|dont|où|avec|dans|par|pour|sur|sous|sans|comme|ce|cette|ces|"
    r"notre|votre|leur|son|sa|ses|en|au|aux|à|a)\\s*)$",
    re.I,
)
STRONG_END_RE = re.compile(r"[.!?。！？][\"'»”’)\]]*$")


class Block:
    def __init__(self, block_id: str, content: list[str]) -> None:
        self.block_id = block_id
        self.content = strip_outer_blanks(content)

    def render(self) -> list[str]:
        return [f"<!-- id: {self.block_id} -->", "", *self.content, ""]


def strip_outer_blanks(lines: list[str]) -> list[str]:
    lines = list(lines)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def plain(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"[*_`~]+", "", text)
    text = text.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def first_text(block: Block) -> str:
    return plain(" ".join(line.strip() for line in block.content if line.strip()))


def last_text(block: Block) -> str:
    return first_text(block)


def first_line(block: Block) -> str:
    return block.content[0].strip() if block.content else ""


def is_heading(block: Block) -> bool:
    return first_line(block).startswith("#")


def is_image(block: Block) -> bool:
    return bool(IMAGE_RE.match(first_line(block)))


def is_table(block: Block) -> bool:
    return first_line(block).startswith("|")


def is_comment(block: Block) -> bool:
    return first_line(block).startswith("<!--")


def is_footnote(block: Block) -> bool:
    return bool(FOOTNOTE_RE.match(first_line(block)))


def is_list(block: Block) -> bool:
    return bool(LIST_RE.match(first_line(block)))


def is_quote(block: Block) -> bool:
    return first_line(block).startswith(">")


def protected(block: Block) -> bool:
    return is_heading(block) or is_image(block) or is_table(block) or is_comment(block) or is_footnote(block)


def starts_continuation(block: Block) -> bool:
    text = first_text(block)
    if not text:
        return False
    if text[0] in ",;:)]}»”’…":
        return True
    match = re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]", text)
    if not match:
        return False
    char = match.group(0)
    return char.isdigit() or char.islower()


def should_merge(prev: Block, cur: Block) -> bool:
    if protected(prev) or protected(cur):
        return False
    if is_quote(cur):
        return False
    if is_list(cur):
        return False
    prev_text = last_text(prev)
    cur_text = first_text(cur)
    if not prev_text or not cur_text:
        return False
    if is_list(prev):
        return starts_continuation(cur)
    if is_quote(prev):
        return starts_continuation(cur)
    if WEAK_END_RE.search(prev_text):
        return True
    if not STRONG_END_RE.search(prev_text) and starts_continuation(cur):
        return True
    return False


def merge_blocks(prev: Block, cur: Block) -> None:
    prev.content = strip_outer_blanks(prev.content)
    cur.content = strip_outer_blanks(cur.content)
    if not prev.content:
        prev.content = cur.content
        return
    if not cur.content:
        return
    joined = plain(cur.content[0])
    if joined:
        prev.content[-1] = prev.content[-1].rstrip() + " " + cur.content[0].lstrip()
    prev.content.extend(cur.content[1:])


def parse(lines: list[str]) -> tuple[list[str], list[Block], list[str]]:
    prefix: list[str] = []
    blocks: list[Block] = []
    suffix: list[str] = []
    i = 0
    while i < len(lines):
        match = ID_RE.match(lines[i])
        if match:
            break
        prefix.append(lines[i])
        i += 1
    while i < len(lines):
        if lines[i].strip() == "## Notes":
            suffix = lines[i:]
            break
        match = ID_RE.match(lines[i])
        if not match:
            prefix.append(lines[i])
            i += 1
            continue
        block_id = match.group(1)
        i += 1
        content: list[str] = []
        while i < len(lines):
            if lines[i].strip() == "## Notes" or ID_RE.match(lines[i]):
                break
            content.append(lines[i])
            i += 1
        blocks.append(Block(block_id, content))
    return prefix, blocks, suffix


def normalize_file(path: Path, dry_run: bool) -> tuple[int, int]:
    original = path.read_text(encoding="utf-8").splitlines()
    prefix, blocks, suffix = parse(original)
    merged: list[Block] = []
    removed = 0
    for block in blocks:
        if merged and should_merge(merged[-1], block):
            merge_blocks(merged[-1], block)
            removed += 1
        else:
            merged.append(block)
    if removed and not dry_run:
        out: list[str] = list(prefix)
        if out and out[-1] != "":
            out.append("")
        for block in merged:
            out.extend(block.render())
        if suffix:
            if out and out[-1] != "":
                out.append("")
            out.extend(suffix)
        while out and out[-1] == "":
            out.pop()
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return len(blocks), removed


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge Markdown blocks split by soft line wraps.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files: list[Path] = []
    for path in args.paths:
        if path.is_dir():
            files.extend(sorted(path.glob("lesson-*.md")))
        else:
            files.append(path)

    total_removed = 0
    for path in files:
        before, removed = normalize_file(path, args.dry_run)
        total_removed += removed
        if removed:
            print(f"{path}: {before} blocks, merged {removed}")
    print(f"files={len(files)} merged={total_removed}")


if __name__ == "__main__":
    main()
