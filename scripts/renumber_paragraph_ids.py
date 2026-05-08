#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


ID_RE = re.compile(r"<!-- id: ([^ ]+) -->")
SEMINAR_RE = re.compile(r"^<!-- seminar: ([^ ]+) -->$", re.M)
LESSON_RE = re.compile(r"^<!-- lesson: ([0-9]{2}) -->$", re.M)


def collect_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("lesson-*.md")))
        else:
            files.append(path)
    return sorted(set(files))


def expected_prefix(text: str, path: Path) -> str:
    seminar = SEMINAR_RE.search(text)
    lesson = LESSON_RE.search(text)
    if not seminar or not lesson:
        first_id = ID_RE.search(text)
        if first_id:
            parts = first_id.group(1).split("-")
            if len(parts) >= 3:
                return "-".join(parts[:2])
        raise ValueError(f"{path}: missing seminar/lesson metadata and no usable id")
    return f"{seminar.group(1)}-{lesson.group(1)}"


def renumber_file(path: Path, dry_run: bool) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8")
    prefix = expected_prefix(text, path)
    count = 0
    changed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count, changed
        count += 1
        new_id = f"{prefix}-{count:04d}"
        if match.group(1) != new_id:
            changed += 1
        return f"<!-- id: {new_id} -->"

    new_text = ID_RE.sub(replace, text)
    if changed and not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return count, changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Renumber paragraph IDs within lesson Markdown files.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = collect_files(args.paths)
    total_ids = 0
    total_changed = 0
    for path in files:
        ids, changed = renumber_file(path, args.dry_run)
        total_ids += ids
        total_changed += changed
        if changed:
            print(f"{path}: ids={ids} changed={changed}")
    print(f"files={len(files)} ids={total_ids} changed={total_changed}")


if __name__ == "__main__":
    main()
