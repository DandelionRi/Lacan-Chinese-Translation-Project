#!/usr/bin/env python3
"""Audit mdBook input pages against local Lacan PDF corpus.

The audit is intentionally conservative. It does not claim a perfect OCR-grade
alignment, but it checks the invariants that catch most build and conversion
damage:

- every build lesson page exists in mdBook,
- lesson dates and first original-text snippets can be found in the matching PDF,
- image references resolve to readable local files,
- PDF image inventory is recorded for comparison,
- reading toggles are present,
- HTML/sub/sup and common Markdown conversion artifacts are flagged.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "build"
BOOK_DIR = ROOT / "book"
PDF_DIR = ROOT / "pdf"
REPORT_DIR = ROOT / "reports"

SEMINARS = [
    ("S1", "s1-les-ecrits-techniques-de-freud", "S1 Ecrits techniques.pdf"),
    ("S2", "s2-le-moi-dans-la-theorie-et-dans-la-technique-psychanalytique", "S2 LE MOI.pdf"),
    ("S3", "s3-les-psychoses", "S3 PSYCHOSES.pdf"),
    ("S4", "s4-la-relation-d-objet", "S4 LA RELATION.pdf"),
    ("S5", "s5-les-formations-de-l-inconscient", "S5 FORMATIONS .pdf"),
    ("S6", "s6-le-desir-et-son-interpretation", "S6 LE DESIR.pdf"),
    ("S7", "s7-l-ethique-de-la-psychanalyse", "S7.pdf"),
    ("S8", "s8-le-transfert", "S8 LE TRANSFERT.pdf"),
    ("S9", "s9-l-identification", "S9 L_IDENTIFICATION.pdf"),
    ("S10", "s10-l-angoisse", "S10.pdf"),
    ("S11", "s11-les-quatre-concepts-fondamentaux-de-la-psychanalyse", "S11.pdf"),
    ("S12", "s12-problemes-cruciaux-pour-la-psychanalyse", "S12 PROBLEMES.pdf"),
    ("S13", "s13-l-objet-de-la-psychanalyse", "S13.pdf"),
    ("S14", "s14-la-logique-du-fantasme", "S14.pdf"),
    ("S15", "s15-l-acte-psychanalytique", "S15.pdf"),
    ("S16", "s16-d-un-autre-a-l-autre", "S16 D_UN AUTRE... .pdf"),
    ("S17", "s17-l-envers-de-la-psychanalyse", "S17 L_ENVERS.pdf"),
    ("S18", "s18-d-un-discours-qui-ne-serait-pas-du-semblant", "S18.pdf"),
    ("S19", "s19-ou-pire", "S19.pdf"),
    ("S19b", "s19b-le-savoir-du-psychanalyste", "S19b Le savoir du psychanalyste.pdf"),
    ("S20", "s20-encore", "S20.pdf"),
    ("S21", "s21-les-non-dupes-errent", "S21.pdf"),
    ("S22", "s22-r-s-i", "S22.pdf"),
    ("S23", "s23-le-sinthome", "S23.pdf"),
    ("S24", "s24-l-insu-que-sait-de-l-une-bevue-s-aile-a-mourre", "S24.pdf"),
    ("S25", "s25-le-moment-de-conclure", "S25.pdf"),
    ("S26", "s26-la-topologie-et-le-temps", "S26 La topologie et le temps.pdf"),
    ("S27", "s27-dissolution", "S27 Dissolution.pdf"),
]

TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
LESSON_FILE_RE = re.compile(r"^(?:Leçon|Lecon|lesson)-(\d+)\.md$", re.IGNORECASE)
PARA_RE = re.compile(
    r'<div class="original-paragraph" data-paragraph-id="([^"]+)">\s*(.*?)\s*</div>',
    re.DOTALL,
)
SECTION_RE = re.compile(r'<section class="parallel-paragraph" data-paragraph-ids="([^"]+)">')
IMG_RE = re.compile(r'<img\b[^>]*\bsrc="([^"]+)"[^>]*>', re.IGNORECASE)
HTML_IMG_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)
TOGGLE_RE = re.compile(r'data-lacan-toggle="([^"]+)"')
SUBSUP_TAGS = ("sub", "sup")

SOURCE_MARKER_PATTERNS = [
    ("star_dash_star", re.compile(r"\*-\*")),
    ("star_punct_star", re.compile(r"\*[.,;:!?]\*")),
    ("diamond_star", re.compile(r"(?:\*\*◊|◊\*\*|S\*\*◊|◊\*\*\*|\*\*\*a|a\*\*)")),
    ("sub_star", re.compile(r"<(?:sub|sup)>[^<]*\*[^<]*</(?:sub|sup)>")),
]

RENDERED_MARKER_PATTERNS = [
    ("rendered_double_star", re.compile(r"\*\*")),
    ("rendered_triple_star", re.compile(r"\*\*\*")),
    ("rendered_star_dash_star", re.compile(r"\*-\*")),
    ("rendered_diamond_star", re.compile(r"(?:\*\*◊|◊\*\*|S\*\*◊|◊\*\*\*|\*\*\*a|a\*\*)")),
]

FRENCH_MONTHS = {
    "janvier": "01",
    "fevrier": "02",
    "février": "02",
    "mars": "03",
    "avril": "04",
    "mai": "05",
    "juin": "06",
    "juillet": "07",
    "novembre": "11",
    "decembre": "12",
    "décembre": "12",
    "septembre": "09",
    "octobre": "10",
}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "svg"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "svg"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


@dataclass
class LessonAudit:
    lesson: str
    title: str
    date: str
    build_path: str
    html_path: str
    date_pdf_page: int | None = None
    text_pdf_page: int | None = None
    first_text: str = ""
    first_text_score: int = 0
    paragraphs_total: int = 0
    paragraphs_checked: int = 0
    paragraphs_matched: int = 0
    unmatched_paragraphs: list[dict[str, Any]] = field(default_factory=list)
    html_exists: bool = False
    images: int = 0
    missing_images: list[str] = field(default_factory=list)
    toggles_ok: bool = False
    marker_hits: list[dict[str, Any]] = field(default_factory=list)
    subsup_imbalances: list[str] = field(default_factory=list)


def run_cmd(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return ""


def pdf_page_count(pdf: Path) -> int | None:
    out = run_cmd(["pdfinfo", str(pdf)])
    match = re.search(r"^Pages:\s+(\d+)", out, re.MULTILINE)
    return int(match.group(1)) if match else None


def pdf_image_count(pdf: Path) -> int:
    out = run_cmd(["pdfimages", "-list", str(pdf)])
    lines = [line for line in out.splitlines() if re.match(r"^\s*\d+\s+\d+\s+image\b", line)]
    return len(lines)


def pdf_pages_text(pdf: Path) -> list[str]:
    out = run_cmd(["pdftotext", "-layout", str(pdf), "-"])
    return out.split("\f") if out else []


def strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def normalize_text(text: str) -> str:
    text = html.unescape(text)
    text = strip_accents(text).lower()
    text = text.replace("œ", "oe").replace("æ", "ae")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[*_`~\\\[\]{}()<>|]", " ", text)
    text = re.sub(r"[^a-z0-9α-ωϕφψχβγδεζηικλμνξοπρστυςàâçéèêëîïôûùüÿñæœ]+", " ", text)
    return " ".join(text.split())


def normalize_date_key(date: str) -> str:
    text = strip_accents(date).lower()
    text = text.replace("1er", "1")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    parts = text.split()
    day = month = year = None
    for part in parts:
        if part.isdigit() and len(part) == 4:
            year = part
        elif part.isdigit() and day is None:
            day = str(int(part))
        elif part in FRENCH_MONTHS:
            month = part
    return " ".join(x for x in [day, month, year] if x)


def date_page(date: str, normalized_pages: list[str]) -> int | None:
    key = normalize_date_key(date)
    if not key:
        return None
    for index, page in enumerate(normalized_pages, start=1):
        if key in page:
            return index
    return None


def strip_html_to_text(source: str) -> str:
    source = re.sub(r"<img\b[^>]*>", " ", source, flags=re.IGNORECASE)
    parser = TextExtractor()
    parser.feed(source)
    return parser.text()


def strip_markdown_to_text(source: str) -> str:
    text = strip_html_to_text(source)
    text = re.sub(r"\[\^?\d+\]", " ", text)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", text)
    text = re.sub(r"[*_`>#\\]", " ", text)
    return " ".join(text.split())


def first_original_text(source: str) -> str:
    for _, block in PARA_RE.findall(source):
        text = strip_markdown_to_text(block)
        if not text:
            continue
        if text.startswith("[无对应译文]"):
            continue
        if len(normalize_text(text)) >= 35:
            return text[:500]
    return ""


def original_paragraph_texts(source: str) -> list[tuple[str, str]]:
    paragraphs: list[tuple[str, str]] = []
    for paragraph_id, block in PARA_RE.findall(source):
        text = strip_markdown_to_text(block)
        text = re.sub(r"^\[?无对应译文\]?\s*", "", text)
        text = " ".join(text.split())
        paragraphs.append((paragraph_id, text))
    return paragraphs


def build_phrase_sets(normalized_pages: list[str]) -> dict[int, set[str]]:
    tokens = " ".join(normalized_pages).split()
    phrase_sets: dict[int, set[str]] = {}
    for window_size in (12, 10, 8, 6):
        if len(tokens) < window_size:
            phrase_sets[window_size] = set()
            continue
        phrase_sets[window_size] = {
            " ".join(tokens[index : index + window_size])
            for index in range(0, len(tokens) - window_size + 1)
        }
    return phrase_sets


def paragraph_match(
    text: str,
    pdf_phrase_sets: dict[int, set[str]],
    page_word_sets: list[set[str]],
) -> tuple[bool, int]:
    normalized = normalize_text(text)
    tokens = [token for token in normalized.split() if len(token) >= 3]
    if len(tokens) < 4:
        return False, 0

    for window_size in (12, 10, 8, 6):
        if len(tokens) < window_size:
            continue
        starts = {0, max(0, (len(tokens) - window_size) // 2), max(0, len(tokens) - window_size)}
        for start in starts:
            phrase = " ".join(tokens[start : start + window_size])
            if phrase in pdf_phrase_sets.get(window_size, set()):
                return True, window_size

    significant = [token for token in tokens if len(token) >= 4][:18]
    token_set = set(significant)
    if len(token_set) < 5:
        return False, len(token_set)
    best_score = 0
    for page_words in page_word_sets:
        score = len(token_set & page_words)
        if score > best_score:
            best_score = score
    threshold = max(5, min(len(token_set), int(len(token_set) * 0.72)))
    return best_score >= threshold, best_score


def paragraph_match_stats(
    source: str,
    pdf_phrase_sets: dict[int, set[str]],
    page_word_sets: list[set[str]],
) -> dict[str, Any]:
    total = checked = matched = 0
    unmatched: list[dict[str, Any]] = []
    for paragraph_id, text in original_paragraph_texts(source):
        total += 1
        normalized = normalize_text(text)
        if len(normalized) < 24 or not re.search(r"[a-zα-ω]", normalized):
            continue
        checked += 1
        ok, score = paragraph_match(text, pdf_phrase_sets, page_word_sets)
        if ok:
            matched += 1
        elif len(unmatched) < 40:
            unmatched.append({"id": paragraph_id, "score": score, "text": text[:180]})
    return {
        "total": total,
        "checked": checked,
        "matched": matched,
        "unmatched": unmatched,
    }


def text_page(first_text: str, normalized_pages: list[str]) -> tuple[int | None, int]:
    normalized = normalize_text(first_text)
    tokens = [token for token in normalized.split() if len(token) >= 4]
    tokens = tokens[:14]
    if len(tokens) < 4:
        return None, 0
    phrase = " ".join(tokens[:8])
    for index, page in enumerate(normalized_pages, start=1):
        if phrase and phrase in page:
            return index, len(tokens)
    best_page = None
    best_score = 0
    token_set = set(tokens)
    for index, page in enumerate(normalized_pages, start=1):
        words = set(page.split())
        score = len(token_set & words)
        if score > best_score:
            best_score = score
            best_page = index
    if best_score >= max(5, min(9, len(tokens) - 2)):
        return best_page, best_score
    return None, best_score


def lesson_number(path: Path) -> int:
    match = LESSON_FILE_RE.match(path.name)
    return int(match.group(1)) if match else 0


def lesson_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        (path for path in directory.glob("*.md") if LESSON_FILE_RE.match(path.name)),
        key=lesson_number,
    )


def extract_title_and_date(source: str, fallback: Path) -> tuple[str, str]:
    match = TITLE_RE.search(source)
    if not match:
        return fallback.stem, ""
    title = match.group(1).strip()
    parts = [part.strip() for part in title.split("|", 1)]
    return title, parts[1] if len(parts) == 2 else ""


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def marker_hits(text: str, rendered_text: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for name, pattern in SOURCE_MARKER_PATTERNS:
        for match in pattern.finditer(text):
            hits.append({"kind": name, "line": line_number(text, match.start()), "sample": sample_line(text, match.start())})
            if len(hits) >= 20:
                return hits
    for name, pattern in RENDERED_MARKER_PATTERNS:
        for match in pattern.finditer(rendered_text):
            hits.append({"kind": name, "line": None, "sample": rendered_text[max(0, match.start()-80):match.start()+120]})
            if len(hits) >= 20:
                return hits
    return hits


def sample_line(text: str, offset: int) -> str:
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    if end == -1:
        end = len(text)
    return text[start:end].strip()[:240]


def subsup_imbalances(text: str) -> list[str]:
    issues = []
    for tag in SUBSUP_TAGS:
        opens = text.count(f"<{tag}>")
        closes = text.count(f"</{tag}>")
        if opens != closes:
            issues.append(f"{tag}: open={opens} close={closes}")
    return issues


def rendered_text_from_html(html_text: str) -> str:
    parser = TextExtractor()
    parser.feed(html_text)
    return parser.text()


def audit_lesson(
    build_path: Path,
    slug: str,
    normalized_pages: list[str],
    pdf_phrase_sets: dict[int, set[str]],
    page_word_sets: list[set[str]],
) -> LessonAudit:
    build_text = build_path.read_text(encoding="utf-8", errors="ignore")
    title, date = extract_title_and_date(build_text, build_path)
    lesson = build_path.stem
    html_path = BOOK_DIR / slug / f"{lesson}.html"
    audit = LessonAudit(
        lesson=lesson,
        title=title,
        date=date,
        build_path=str(build_path.relative_to(ROOT)),
        html_path=str(html_path.relative_to(ROOT)),
    )
    audit.first_text = first_original_text(build_text)
    audit.date_pdf_page = date_page(date, normalized_pages)
    audit.text_pdf_page, audit.first_text_score = text_page(audit.first_text, normalized_pages)
    paragraph_stats = paragraph_match_stats(build_text, pdf_phrase_sets, page_word_sets)
    audit.paragraphs_total = paragraph_stats["total"]
    audit.paragraphs_checked = paragraph_stats["checked"]
    audit.paragraphs_matched = paragraph_stats["matched"]
    audit.unmatched_paragraphs = paragraph_stats["unmatched"]
    audit.subsup_imbalances = subsup_imbalances(build_text)

    html_text = ""
    rendered_text = ""
    if html_path.exists():
        audit.html_exists = True
        html_text = html_path.read_text(encoding="utf-8", errors="ignore")
        rendered_text = rendered_text_from_html(html_text)
        toggles = set(TOGGLE_RE.findall(html_text))
        audit.toggles_ok = toggles == {"original", "notes", "commentary"}
        for image_ref in HTML_IMG_RE.findall(html_text):
            audit.images += 1
            if image_ref.startswith(("http://", "https://", "data:", "#", "mailto:")):
                continue
            target = (html_path.parent / unquote(image_ref.split("#", 1)[0].split("?", 1)[0])).resolve()
            if not target.exists() or target.stat().st_size == 0:
                audit.missing_images.append(image_ref)
    audit.marker_hits = marker_hits(build_text, rendered_text)
    return audit


def audit_seminar(code: str, slug: str, pdf_name: str) -> dict[str, Any]:
    build_dir = BUILD_DIR / slug
    pdf = PDF_DIR / pdf_name
    lessons = lesson_files(build_dir)
    pages = pdf_pages_text(pdf) if pdf.exists() else []
    normalized_pages = [normalize_text(page) for page in pages]
    pdf_phrase_sets = build_phrase_sets(normalized_pages)
    page_word_sets = [set(page.split()) for page in normalized_pages]
    lesson_audits = [
        audit_lesson(path, slug, normalized_pages, pdf_phrase_sets, page_word_sets)
        for path in lessons
    ]
    missing_html = [lesson.lesson for lesson in lesson_audits if not lesson.html_exists]
    missing_images = [
        {"lesson": lesson.lesson, "images": lesson.missing_images[:10]}
        for lesson in lesson_audits
        if lesson.missing_images
    ]
    unmatched_dates = [lesson.lesson for lesson in lesson_audits if lesson.date and lesson.date_pdf_page is None]
    unmatched_text = [
        {"lesson": lesson.lesson, "score": lesson.first_text_score, "text": lesson.first_text[:140]}
        for lesson in lesson_audits
        if lesson.first_text and lesson.text_pdf_page is None
    ]
    marker_lessons = [
        {"lesson": lesson.lesson, "hits": lesson.marker_hits[:5]}
        for lesson in lesson_audits
        if lesson.marker_hits
    ]
    rendered_marker_lessons = [
        {
            "lesson": lesson.lesson,
            "hits": [hit for hit in lesson.marker_hits if hit["kind"].startswith("rendered_")][:5],
        }
        for lesson in lesson_audits
        if any(hit["kind"].startswith("rendered_") for hit in lesson.marker_hits)
    ]
    source_marker_lessons = [
        {
            "lesson": lesson.lesson,
            "hits": [hit for hit in lesson.marker_hits if not hit["kind"].startswith("rendered_")][:5],
        }
        for lesson in lesson_audits
        if any(not hit["kind"].startswith("rendered_") for hit in lesson.marker_hits)
    ]
    subsup_lessons = [
        {"lesson": lesson.lesson, "issues": lesson.subsup_imbalances}
        for lesson in lesson_audits
        if lesson.subsup_imbalances
    ]
    unmatched_paragraphs = [
        {
            "lesson": lesson.lesson,
            "unmatched": lesson.paragraphs_checked - lesson.paragraphs_matched,
            "samples": lesson.unmatched_paragraphs[:8],
        }
        for lesson in lesson_audits
        if lesson.paragraphs_checked > lesson.paragraphs_matched
    ]
    return {
        "code": code,
        "slug": slug,
        "pdf": pdf_name,
        "pdf_exists": pdf.exists(),
        "pdf_pages": pdf_page_count(pdf) if pdf.exists() else None,
        "pdf_images": pdf_image_count(pdf) if pdf.exists() else None,
        "lessons": len(lesson_audits),
        "html_pages": sum(1 for lesson in lesson_audits if lesson.html_exists),
        "date_matches": sum(1 for lesson in lesson_audits if lesson.date_pdf_page is not None),
        "text_matches": sum(1 for lesson in lesson_audits if lesson.text_pdf_page is not None),
        "paragraphs_total": sum(lesson.paragraphs_total for lesson in lesson_audits),
        "paragraphs_checked": sum(lesson.paragraphs_checked for lesson in lesson_audits),
        "paragraphs_matched": sum(lesson.paragraphs_matched for lesson in lesson_audits),
        "unmatched_paragraph_count": sum(
            lesson.paragraphs_checked - lesson.paragraphs_matched for lesson in lesson_audits
        ),
        "unmatched_paragraphs": unmatched_paragraphs[:80],
        "html_images": sum(lesson.images for lesson in lesson_audits),
        "missing_html": missing_html,
        "missing_images": missing_images,
        "toggle_failures": [lesson.lesson for lesson in lesson_audits if lesson.html_exists and not lesson.toggles_ok],
        "unmatched_dates": unmatched_dates,
        "unmatched_text": unmatched_text[:40],
        "unmatched_text_count": len(unmatched_text),
        "marker_lessons": marker_lessons[:60],
        "marker_lesson_count": len(marker_lessons),
        "rendered_marker_lessons": rendered_marker_lessons[:60],
        "rendered_marker_lesson_count": len(rendered_marker_lessons),
        "source_marker_lessons": source_marker_lessons[:60],
        "source_marker_lesson_count": len(source_marker_lessons),
        "subsup_lessons": subsup_lessons,
        "lesson_details": [lesson.__dict__ for lesson in lesson_audits],
    }


def render_markdown(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Full mdBook/PDF Audit",
        "",
        "Scope: S1-S27, including S19b because the corpus contains a separate S19b PDF and mdBook section.",
        "",
        "## Summary",
        "",
        "| Seminar | Lessons | PDF pages | Date matches | First text matches | Paragraph matches | HTML images | Missing images | Rendered marker pages | Source marker candidates | Toggle failures |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r['code']} | {r['lessons']} | {r['pdf_pages'] or 0} | "
            f"{r['date_matches']}/{r['lessons']} | {r['text_matches']}/{r['lessons']} | "
            f"{r['paragraphs_matched']}/{r['paragraphs_checked']} | "
            f"{r['html_images']} | {len(r['missing_images'])} | {r['rendered_marker_lesson_count']} | "
            f"{r['source_marker_lesson_count']} | {len(r['toggle_failures'])} |"
        )

    lines += ["", "## Ordered Findings", ""]
    for r in results:
        issues = []
        if not r["pdf_exists"]:
            issues.append(f"missing PDF `{r['pdf']}`")
        if r["missing_html"]:
            issues.append(f"missing HTML lessons: {', '.join(r['missing_html'][:12])}")
        if r["missing_images"]:
            issues.append(f"missing image pages: {len(r['missing_images'])}")
        if r["toggle_failures"]:
            issues.append(f"toggle failures: {', '.join(r['toggle_failures'][:12])}")
        if r["unmatched_dates"]:
            issues.append(f"date not found in PDF: {len(r['unmatched_dates'])}")
        if r["unmatched_text_count"]:
            issues.append(f"first text not confidently found in PDF: {r['unmatched_text_count']}")
        if r["unmatched_paragraph_count"]:
            issues.append(
                f"paragraphs not confidently found in PDF: "
                f"{r['unmatched_paragraph_count']}/{r['paragraphs_checked']}"
            )
        if r["subsup_lessons"]:
            issues.append(f"sub/sup imbalance pages: {len(r['subsup_lessons'])}")
        if r["rendered_marker_lesson_count"]:
            issues.append(f"visible rendered Markdown/formula markers: {r['rendered_marker_lesson_count']}")
        if r["source_marker_lesson_count"]:
            issues.append(f"source Markdown/formula marker candidates: {r['source_marker_lesson_count']}")
        status = "OK" if not issues else "; ".join(issues)
        lines.append(f"### {r['code']} `{r['slug']}`")
        lines.append(status)
        if r["unmatched_dates"]:
            lines.append(f"- Unmatched dates: {', '.join(r['unmatched_dates'][:30])}")
        if r["unmatched_text"]:
            sample = "; ".join(f"{x['lesson']} score={x['score']}" for x in r["unmatched_text"][:12])
            lines.append(f"- Text-match review sample: {sample}")
        if r["unmatched_paragraphs"]:
            sample_parts = []
            for item in r["unmatched_paragraphs"][:8]:
                first = item["samples"][0] if item["samples"] else {"id": "n/a", "score": 0}
                sample_parts.append(f"{item['lesson']} unmatched={item['unmatched']} first={first['id']} score={first['score']}")
            lines.append(f"- Paragraph review sample: {'; '.join(sample_parts)}")
        if r["rendered_marker_lessons"]:
            sample_parts = []
            for item in r["rendered_marker_lessons"][:10]:
                hit = item["hits"][0]
                loc = f":{hit['line']}" if hit.get("line") else ""
                sample_parts.append(f"{item['lesson']}{loc} {hit['kind']}")
            lines.append(f"- Rendered marker sample: {'; '.join(sample_parts)}")
        if r["source_marker_lessons"]:
            sample_parts = []
            for item in r["source_marker_lessons"][:10]:
                hit = item["hits"][0]
                loc = f":{hit['line']}" if hit.get("line") else ""
                sample_parts.append(f"{item['lesson']}{loc} {hit['kind']}")
            lines.append(f"- Source marker candidate sample: {'; '.join(sample_parts)}")
        if r["missing_images"]:
            sample = "; ".join(f"{x['lesson']} ({len(x['images'])})" for x in r["missing_images"][:10])
            lines.append(f"- Missing image sample: {sample}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=str(REPORT_DIR / "full_site_pdf_audit.json"))
    parser.add_argument("--markdown", default=str(REPORT_DIR / "full_site_pdf_audit.md"))
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    results = [audit_seminar(*seminar) for seminar in SEMINARS]
    Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.markdown).write_text(render_markdown(results), encoding="utf-8")
    print(json.dumps(
        {
            "seminars": len(results),
            "lessons": sum(r["lessons"] for r in results),
            "missing_images": sum(len(r["missing_images"]) for r in results),
            "paragraphs_checked": sum(r["paragraphs_checked"] for r in results),
            "paragraphs_matched": sum(r["paragraphs_matched"] for r in results),
            "unmatched_paragraph_count": sum(r["unmatched_paragraph_count"] for r in results),
            "marker_lesson_count": sum(r["marker_lesson_count"] for r in results),
            "rendered_marker_lesson_count": sum(r["rendered_marker_lesson_count"] for r in results),
            "source_marker_lesson_count": sum(r["source_marker_lesson_count"] for r in results),
            "report": args.markdown,
            "json": args.json,
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
