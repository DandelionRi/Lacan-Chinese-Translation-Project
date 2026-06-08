#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LCTP terminology batch replacement script.

Replaces core terminology in translation/ files of given seminars.
- 简体"欲望" → 繁体"慾望"
- "力比多" → "欲力"
- "客体" → "对象" (保留"客体关系")
- "符号界" → "象征界"
- "移情" → "转移" (保留"transitivism[移情作用]"中的移情, 因transitivisme≠transfert)
- "反移情" → "反转移"
- "鲍桑尼阿斯" → "鲍萨尼亚斯"
- "性欲力" → "欲力"

Idempotent: safe to run multiple times.

Usage:
    python lctp_terminology.py                          # all seminars
    python lctp_terminology.py s5-les-formations... s12...  # specific seminars
"""

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXTS = ROOT / "texts"

# Replacement rules (find -> replace). Order matters: longer phrases first.
RULES = [
    # === PROTECT: terms that should NOT be affected by later rules ===
    # Protect transitivisme context (移情作用 translates transitivisme, NOT transfert)
    ("transitivism[移情作用]", "\x00TRANSITIVISM\x00"),
    # Protect compound terms
    ("客体关系", "\x00KEEP_OBJECT_RELATION\x00"),
    # === TERM REPLACEMENTS ===
    # Wider term first (反移情→反转移 before bare 移情→转移)
    ("反移情", "反转移"),
    # Core terminology
    ("客体", "对象"),
    ("符号界", "象征界"),
    ("鲍桑尼阿斯", "鲍萨尼亚斯"),
    ("性欲力", "欲力"),
    # 移情→转移 (catches general transfert usages, must come after protections)
    ("移情", "转移"),
    # === RESTORE protected terms ===
    ("\x00TRANSITIVISM\x00", "transitivism[移情作用]"),  # transitivisme ≠ transfert
    ("\x00KEEP_OBJECT_RELATION\x00", "客体关系"),
]

# Unicode-based replacements (need careful handling for 慾 vs 欲)
UNICODE_RULES = [
    # 简体"欲望" (\u6B32\u671B) -> 繁体"慾望" (\u6158\u671B)
    ("\u6B32\u671B", "\u6158\u671B"),
    # "力比多" -> "欲力"
    ("\u529B\u6BD4\u591A", "\u6158\u529B"),  # uses same 慾 to be consistent
    # Wait, 欲力 should be \u6B32\u529B, not \u6158\u529B
]

# Correction: 欲力 = 欲 (\u6B32) + 力 (\u529B), same as 简体"欲"
# The user said: Libidinal Force → 欲力 (where 欲 is the same 欲 used in 简体 欲)
# So 欲力 = \u6B32\u529B (use 欲, not 慾)
# 慾望 uses 慾 (\u6158) for 欲望 distinction
UNICODE_RULES = [
    ("\u6B32\u671B", "\u6158\u671B"),   # 欲望 -> 慾望
    ("\u529B\u6BD4\u591A", "\u6B32\u529B"),  # 力比多 -> 欲力
]


def get_target_seminars():
    """Find seminars with non-zero missing (i.e., need work)."""
    ID_RE = re.compile(r"<!--\s*id:\s*([^>\s]+)\s*-->")
    IDS_RE = re.compile(r"<!--\s*ids:\s*([^>]+?)\s*-->")
    targets = []
    for sem_path in sorted(TEXTS.iterdir()):
        if not sem_path.is_dir() or not sem_path.name.startswith("s"):
            continue
        sem = sem_path.name
        total_missing = 0
        for orig in sem_path.glob("original/Le*.md"):
            trans = sem_path / "translation" / orig.name
            if not trans.exists():
                continue
            o = orig.read_text(encoding="utf-8")
            t = trans.read_text(encoding="utf-8")
            aligned = set(ID_RE.findall(t))
            for m in IDS_RE.finditer(t):
                for tid in m.group(1).split():
                    aligned.add(tid)
            miss = [i for i in ID_RE.findall(o) if i not in aligned]
            total_missing += len(miss)
        if total_missing > 0:
            targets.append(sem)
    return targets


def process_seminar(sem):
    """Apply all terminology rules to a seminar's translation files."""
    trans_dir = TEXTS / sem / "translation"
    if not trans_dir.exists():
        return 0
    total_changes = 0
    files_modified = 0
    for f in sorted(trans_dir.glob("Le*.md")):
        t = f.read_text(encoding="utf-8")
        orig = t
        file_changes = 0
        for find, repl in RULES:
            if find in t:
                n = t.count(find)
                t = t.replace(find, repl)
                file_changes += n
        for find, repl in UNICODE_RULES:
            if find in t:
                n = t.count(find)
                t = t.replace(find, repl)
                file_changes += n
        if t != orig:
            f.write_text(t, encoding="utf-8")
            files_modified += 1
            total_changes += file_changes
    return files_modified, total_changes


def main():
    if len(sys.argv) > 1:
        targets = sys.argv[1:]
    else:
        # Process ALL seminars for terminology normalization
        targets = sorted([
            p.name for p in TEXTS.iterdir()
            if p.is_dir() and p.name.startswith("s")
            and (p / "translation").exists()
        ])
    if not targets:
        print("No seminars to process.")
        return
    print(f"Processing {len(targets)} seminar(s):")
    grand_files = 0
    grand_changes = 0
    for sem in targets:
        files, changes = process_seminar(sem)
        grand_files += files
        grand_changes += changes
        print(f"  {sem}: {files} files, {changes} changes")
    print(f"\nTotal: {grand_files} files, {grand_changes} changes")


if __name__ == "__main__":
    main()
