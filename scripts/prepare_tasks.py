#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prepare per-lesson task files for translation agents."""
import json
import os
import re
import io
import sys

# Force UTF-8 stdout for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = r'C:\projects\LCTP'
TEXTS_DIR = os.path.join(ROOT, 'texts')
TASKS_DIR = os.path.join(ROOT, 'temp_tasks')

LESSON_FILE_RE = re.compile(r'^(?:Leçon|Lecon|lesson)-(\d+)\.md$', re.IGNORECASE)
ID_RE = re.compile(r'<!--\s*id:\s*([^\s>]+)\s*-->')
IDS_RE = re.compile(r'<!--\s*ids:\s*([^>]+?)\s*-->')

def get_all_ids(text):
    ids = []
    for m in re.finditer(r'<!--\s*id(?:s)?:\s*([^\s>]+)', text):
        ids.append(m.group(1))
    return ids

def extract_block_content(orig_text, target_id):
    pattern = re.compile(r'<!--\s*id:\s*' + re.escape(target_id) + r'\s*-->')
    match = pattern.search(orig_text)
    if not match:
        return None
    start = match.end()
    next_pat = re.compile(r'<!--\s*id(?:s)?:\s*')
    next_match = next_pat.search(orig_text, start)
    end = next_match.start() if next_match else len(orig_text)
    return orig_text[start:end].rstrip()

os.makedirs(TASKS_DIR, exist_ok=True)

# Scan all seminars
task_count = 0
total_blocks = 0
for sem_name in sorted(os.listdir(TEXTS_DIR)):
    sem_path = os.path.join(TEXTS_DIR, sem_name)
    if not os.path.isdir(sem_path):
        continue
    orig_dir = os.path.join(sem_path, 'original')
    trans_dir = os.path.join(sem_path, 'translation')
    if not os.path.isdir(orig_dir):
        continue

    lesson_files = []
    for f in os.listdir(orig_dir):
        m = LESSON_FILE_RE.match(f)
        if m:
            lesson_files.append((int(m.group(1)), f))
    lesson_files.sort()

    for num, fname in lesson_files:
        orig_path = os.path.join(orig_dir, fname)
        trans_path = os.path.join(trans_dir, fname)
        if not os.path.exists(trans_path):
            continue

        with open(orig_path, encoding='utf-8') as f:
            orig_text = f.read()
        with open(trans_path, encoding='utf-8') as f:
            trans_text = f.read()

        orig_ids = set()
        for m in re.finditer(r'<!--\s*id:\s*([^\s>]+)\s*-->', orig_text):
            orig_ids.add(m.group(1))
        for ids_match in IDS_RE.findall(orig_text):
            for pid in ids_match.split():
                orig_ids.add(pid)

        trans_ids = set()
        for m in re.finditer(r'<!--\s*id:\s*([^\s>]+)\s*-->', trans_text):
            trans_ids.add(m.group(1))
        for ids_match in IDS_RE.findall(trans_text):
            for pid in ids_match.split():
                trans_ids.add(pid)

        missing = sorted(orig_ids - trans_ids)
        if not missing:
            continue

        blocks = []
        for mid in missing:
            content = extract_block_content(orig_text, mid) or ''
            blocks.append({'id': mid, 'content': content})

        # Save task file (chunk if > 100 blocks)
        n = len(blocks)
        if n <= 100:
            path = os.path.join(TASKS_DIR, f'{sem_name}__L{num:02d}.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({
                    'seminar': sem_name,
                    'lesson': num,
                    'filename': fname,
                    'blocks': blocks
                }, f, ensure_ascii=False, indent=2)
            task_count += 1
        else:
            chunks = (n + 99) // 100
            for i in range(chunks):
                chunk = blocks[i*100:(i+1)*100]
                path = os.path.join(TASKS_DIR, f'{sem_name}__L{num:02d}_p{i+1}.json')
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'seminar': sem_name,
                        'lesson': num,
                        'filename': fname,
                        'part': i+1,
                        'total_parts': chunks,
                        'blocks': chunk
                    }, f, ensure_ascii=False, indent=2)
                task_count += 1
        total_blocks += n

print(f'Total task files: {task_count}')
print(f'Total blocks: {total_blocks}')
print(f'Tasks dir: {TASKS_DIR}')
