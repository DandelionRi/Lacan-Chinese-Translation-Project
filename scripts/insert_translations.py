#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper script to insert translated missing blocks into translation files.

Usage:
    python insert_translations.py <seminar> <lesson> <translations_json>

Where translations_json is a file like:
{
  "seminar": "s1-les-ecrits-techniques-de-freud",
  "lesson": 1,
  "filename": "Leçon-01.md",
  "translations": [
    {"id": "s1-01-0005", "content": "Translated content here..."}
  ]
}

The script:
1. Reads the original/Leçon-NN.md and translation/Leçon-NN.md
2. For each translation in input, finds the position in the translation file
   (after the preceding ID, or at end if no preceding ID)
3. Inserts the new block: `<!-- id: XXX -->\n\nTranslated content\n\n`
4. Writes the modified file back
"""
import sys
import json
import re
import io
from pathlib import Path

# Force UTF-8 stdout for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parents[1]
TEXTS_DIR = ROOT / "texts"

ID_RE = re.compile(r'<!--\s*id:\s*([^\s>]+)\s*-->')
IDS_RE = re.compile(r'<!--\s*ids:\s*([^>]+?)\s*-->')

def get_all_ids(text):
    """Get all id markers (both id: and ids:) in order."""
    ids = []
    for m in re.finditer(r'<!--\s*id(?:s)?:\s*([^\s>]+)', text):
        ids.append(m.group(1))
    return ids

def get_anchor_positions(text):
    """Get position of each id marker."""
    positions = {}
    for m in ID_RE.finditer(text):
        positions[m.group(1)] = m.start()
    for m in IDS_RE.finditer(text):
        first_id = m.group(1).split()[0]
        if first_id not in positions:
            positions[first_id] = m.start()
    return positions

def find_insertion_point(trans_text, missing_id, all_orig_ids):
    """Find the position to insert the new block in translation.

    Returns the character position where we should insert the new block
    (i.e., right before the next existing block in the translation).
    """
    # Get all anchor positions in translation
    trans_positions = get_anchor_positions(trans_text)

    # Determine the order: which IDs in the original come before/after the missing one
    # The missing id should be inserted after the closest preceding id that exists in translation
    orig_ids_list = sorted(all_orig_ids)
    missing_idx = orig_ids_list.index(missing_id)

    # Find the closest preceding ID that exists in translation
    preceding_trans_id = None
    for i in range(missing_idx - 1, -1, -1):
        if orig_ids_list[i] in trans_positions:
            preceding_trans_id = orig_ids_list[i]
            break

    if preceding_trans_id is None:
        # No preceding ID in translation - insert at the very beginning after frontmatter
        # Find the first content (after the last ---)
        frontmatter_end = trans_text.find('---', trans_text.find('---') + 3)
        if frontmatter_end == -1:
            return 0
        # Skip to after the YAML end
        after_yaml = trans_text.find('\n', frontmatter_end) + 1
        # Find first non-empty content
        return after_yaml

    # Find the next ID after the preceding_trans_id
    next_pos = len(trans_text)
    for i in range(missing_idx + 1, len(orig_ids_list)):
        if orig_ids_list[i] in trans_positions:
            next_pos = trans_positions[orig_ids_list[i]]
            break

    # Insert position: just before the next ID block
    return next_pos

def insert_blocks(trans_path, orig_path, translations):
    """Insert translated blocks into translation file."""
    orig_text = orig_path.read_text(encoding='utf-8')
    trans_text = trans_path.read_text(encoding='utf-8')

    # Get all original IDs
    all_orig_ids = get_all_ids(orig_text)
    existing_trans_ids = set(get_all_ids(trans_text))

    # Build new blocks: list of (insert_pos, text_to_insert)
    insertions = []
    skipped = 0
    for t in translations:
        tid = t['id']
        # Skip if already present (idempotent)
        if tid in existing_trans_ids:
            skipped += 1
            continue
        content = t['content'].strip()
        if not content:
            continue
        # Build the new block text
        new_block = f"\n\n<!-- id: {tid} -->\n\n{content}\n"
        pos = find_insertion_point(trans_text, tid, all_orig_ids)
        insertions.append((pos, new_block, tid))

    # Sort by position descending so we can insert without disturbing positions
    insertions.sort(key=lambda x: x[0], reverse=True)

    # Insert
    new_text = trans_text
    for pos, block_text, tid in insertions:
        new_text = new_text[:pos] + block_text + new_text[pos:]

    # Write back
    if insertions:
        trans_path.write_text(new_text, encoding='utf-8')
    return len(insertions), skipped

def main():
    if len(sys.argv) != 4:
        print("Usage: python insert_translations.py <seminar> <lesson> <translations_json>")
        sys.exit(1)

    seminar = sys.argv[1]
    lesson = int(sys.argv[2])
    json_path = sys.argv[3]

    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    sem_dir = TEXTS_DIR / seminar
    trans_path = sem_dir / "translation" / f"Leçon-{lesson:02d}.md"
    orig_path = sem_dir / "original" / f"Leçon-{lesson:02d}.md"

    if not trans_path.exists():
        print("ERROR: translation file not found: " + str(trans_path))
        sys.exit(1)
    if not orig_path.exists():
        print("ERROR: original file not found: " + str(orig_path))
        sys.exit(1)

    translations = data.get('translations', [])
    if not translations:
        print("No translations to insert")
        return

    count, skipped = insert_blocks(trans_path, orig_path, translations)
    print("Inserted " + str(count) + " blocks into " + trans_path.name + " (skipped " + str(skipped) + " already-present)")

if __name__ == "__main__":
    main()
