#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import legacy Chinese translations into texts/*/translation.

The legacy files under src.bk are Chinese-first reading files without stable
paragraph IDs. This importer uses a monotonic semantic alignment: it extracts
French source concepts, Chinese translation concepts, proper names, formulas and
number tokens, then aligns contiguous translation blocks to contiguous original
paragraph IDs. Layout and length are secondary tie breakers, not the primary
matching signal.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ID_RE = re.compile(r"<!--\s*id:\s*([^>\s]+)\s*-->")
LESSON_RE = re.compile(r"(?:Leçon|Lecon)\s+(\d+)", re.IGNORECASE)
IMG_MD_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)(?:\{[^}]*\})?")
IMG_HTML_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)

IMPORTS = [
    {
        "slug": "s17-l-envers-de-la-psychanalyse",
        "seminar": "s17",
        "legacy": ROOT / "src.bk" / "S17 L'envers de la psychanalyse",
        "title": "S17 L'envers de la psychanalyse",
        "max_source_group": 80,
        "max_target_group": 10,
        "target_len_factor": 0.48,
        "target_len_factors": {
            1: 0.47,
            2: 0.38,
            3: 0.37,
            4: 0.42,
            5: 0.54,
            6: 0.42,
            7: 0.38,
            8: 0.42,
            9: 0.54,
            10: 0.38,
            11: 0.50,
            12: 0.38,
            13: 0.45,
        },
    },
    {
        "slug": "s19b-le-savoir-du-psychanalyste",
        "seminar": "s19b",
        "legacy": ROOT / "src.bk" / "S19b Le savoir du psychanalyste",
        "title": "S19b Le savoir du psychanalyste",
        "max_source_group": 120,
        "max_target_group": 4,
        "target_len_factor": 0.40,
    },
]


CONCEPTS = [
    ("assistance", ["assistance"], ["在场", "帮助", "出席"]),
    ("deplacement", ["déplacement", "déplacements"], ["迁移", "移动"]),
    ("pret", ["prêt"], ["借调", "借给"]),
    ("faculte_droit", ["faculté de droit"], ["法学院"]),
    ("hautes_etudes", ["hautes études"], ["高等研究"]),
    ("doyen", ["doyen"], ["院长"]),
    ("mercredi", ["mercredi"], ["星期三", "周三"]),
    ("vincennes", ["vincennes"], ["万森"]),
    ("seminaire", ["séminaire"], ["研讨课", "研讨班"]),
    ("impromptu", ["impromptu", "impromptus"], ["即兴"]),
    ("taxi", ["taxi"], ["出租车"]),
    ("velomoteur", ["vélomoteur"], ["轻便摩托", "摩托"]),
    ("remords", ["remords"], ["愧疚", "懊悔", "悔恨"]),
    ("exces", ["excès"], ["过度", "过分"]),
    ("psychanalyse", ["psychanalyse", "psychanalytique"], ["精神分析"]),
    ("envers", ["envers"], ["反面", "背面"]),
    ("ecrits", ["écrits"], ["书写", "选集"]),
    ("antecedents", ["antécédents"], ["前提", "前史"]),
    ("freud", ["freud", "freudien"], ["弗洛伊德"]),
    ("discours", ["discours"], ["话语"]),
    ("parole", ["parole"], ["言语", "说话"]),
    ("langage", ["langage"], ["语言"]),
    ("enonce", ["énoncé"], ["陈述", "命题"]),
    ("enonciation", ["énonciation"], ["言说", "表达", "宣告"]),
    ("surmoi", ["surmoi"], ["超我"]),
    ("structure", ["structure"], ["结构"]),
    ("signifiant", ["signifiant", "signifiants"], ["能指"]),
    ("sujet", ["sujet"], ["主体"]),
    ("autre", ["autre"], ["大他者", "他者"]),
    ("savoir", ["savoir"], ["知识"]),
    ("verite", ["vérité"], ["真理"]),
    ("jouissance", ["jouissance", "jouir"], ["享乐"]),
    ("plus_jouir", ["plus-de-jouir", "plus de jouir"], ["剩余享乐"]),
    ("desir", ["désir"], ["欲望"]),
    ("objet", ["objet"], ["对象", "客体"]),
    ("maitre", ["maître"], ["主人"]),
    ("hysterique", ["hystérique"], ["癔症"]),
    ("universitaire", ["universitaire"], ["大学"]),
    ("analyste", ["analyste", "psychanalyste"], ["分析师", "精神分析家"]),
    ("sainte_anne", ["sainte-anne", "sainte anne"], ["圣安娜"]),
    ("interne", ["interne", "internes"], ["实习医生", "实习生"]),
    ("asile", ["asile", "asiles"], ["疯人院", "收容所"]),
    ("hopital", ["hôpital psychiatrique", "hôpitaux psychiatriques"], ["精神病院"]),
    ("ignorance", ["ignorance"], ["无知", "无明"]),
    ("passion", ["passion"], ["激情", "执念"]),
    ("salle_garde", ["salle de garde"], ["值班室"]),
    ("medecine", ["médecine"], ["医学"]),
    ("docte", ["docte"], ["博学"]),
    ("nicolas", ["nicolas de cues", "cues"], ["尼古拉", "库萨"]),
    ("superstition", ["superstition"], ["迷信"]),
    ("henri_ey", ["henri ey"], ["亨利", "埃伊"]),
    ("civilisation", ["civilisation", "civilisateur"], ["文明", "文明化"]),
    ("malaise", ["malaise", "unbehagen"], ["不适", "不安"]),
    ("anti_psy", ["anti-psychiatrie", "anti psychiatrie"], ["反精神病学"]),
    ("psychiatrie", ["psychiatrie", "psychiatrerie"], ["精神病学", "精神病业"]),
    ("psychose", ["psychose", "psychoses"], ["精神病"]),
    ("liberation", ["libération"], ["解放"]),
    ("revolution", ["révolution"], ["革命", "回到出发点", "回归原点"]),
    ("non_savoir", ["non-savoir", "non savoir"], ["非知"]),
    ("lalangue", ["lalangue"], ["拉拉语", "语言体"]),
    ("grammaire", ["grammaire"], ["语法"]),
    ("logique", ["logique"], ["逻辑"]),
    ("resistance", ["résistance"], ["阻抗", "抵抗"]),
    ("copernic", ["copernic"], ["哥白尼"]),
    ("descartes", ["descartes", "cogito"], ["笛卡尔", "我思"]),
    ("hegel", ["hegel"], ["黑格尔"]),
    ("aristote", ["aristote"], ["亚里士多德"]),
    ("platon", ["platon"], ["柏拉图"]),
    ("socrate", ["socrate"], ["苏格拉底"]),
    ("gorgias", ["gorgias"], ["戈尔吉亚"]),
    ("kant", ["kant"], ["康德"]),
    ("marx", ["marx"], ["马克思"]),
    ("moise", ["moïse"], ["摩西"]),
    ("oedipe", ["œdipe", "oedipe"], ["俄狄浦斯"]),
    ("klein", ["klein"], ["克莱因"]),
    ("mur", ["mur", "murailles"], ["墙"]),
    ("amour", ["amour"], ["爱情", "爱"]),
    ("lettre", ["lettre"], ["字母", "信件", "情书"]),
]

COMMENT_MARKERS = [
    "拉康这里",
    "拉康接着",
    "这里需要注意",
    "这里要区分",
    "这里可以",
    "这里想说",
    "看到这里",
    "看到现在",
    "上面说",
    "前面提到",
    "这里要",
    "这意味着",
    "我觉得",
    "我想说",
    "我发现",
    "不得不说",
    "谐音梗",
    "词源",
    "对应的是",
    "语境",
    "民间俗语",
    "类似于",
    "可以理解",
    "可以看看",
    "需要划重点",
    "笑",
    "——>",
]


@dataclass
class SourceBlock:
    paragraph_id: str
    raw: str
    text: str
    tokens: set[str]
    image_only: bool = False


@dataclass
class TranslationUnit:
    text: str
    clean: str
    tokens: set[str]
    annotations: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Alignment:
    sources: list[SourceBlock]
    targets: list[TranslationUnit]
    score: float


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


NORMALIZED_CONCEPTS = [
    (key, [normalize(item) for item in french], chinese)
    for key, french, chinese in CONCEPTS
]


def strip_images(text: str) -> str:
    text = IMG_MD_RE.sub(" ", text)
    text = IMG_HTML_RE.sub(" ", text)
    return text


def remove_legacy_images(text: str) -> str:
    text = IMG_MD_RE.sub("", text)
    text = IMG_HTML_RE.sub("", text)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line.strip()).strip()


def clean_text(text: str) -> str:
    text = strip_images(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[*_`#>\[\]{}()\\]", " ", text)
    return " ".join(text.split())


def semantic_tokens(text: str) -> set[str]:
    raw = text
    normalized = normalize(clean_text(text))
    tokens: set[str] = set()

    for key, french_items, chinese_items in NORMALIZED_CONCEPTS:
        if any(item in normalized for item in french_items) or any(item in raw for item in chinese_items):
            tokens.add(key)

    for match in re.findall(r"\b(?:s\s*[12]|[a-z]\d?|[0-9]{1,4}|[A-Z][A-Za-z]{2,})\b", clean_text(text), re.I):
        token = normalize(match).replace(" ", "")
        if len(token) >= 2:
            tokens.add(f"lit:{token}")

    for marker in ("S₁", "S₂", "S1", "S2", "a", "$", "Φ", "φ"):
        if marker in raw:
            tokens.add(f"sym:{marker}")

    return tokens


def parse_original(path: Path) -> list[SourceBlock]:
    text = path.read_text(encoding="utf-8")
    matches = list(ID_RE.finditer(text))
    blocks: list[SourceBlock] = []

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        raw = text[start:end].strip()
        cleaned = clean_text(raw)
        image_only = bool(raw) and not cleaned
        if cleaned.startswith("Notes "):
            cleaned = ""
        blocks.append(
            SourceBlock(
                paragraph_id=match.group(1).strip(),
                raw=raw,
                text=cleaned,
                tokens=semantic_tokens(raw),
                image_only=image_only,
            )
        )

    return blocks


def lesson_number(path: Path) -> int | None:
    match = LESSON_RE.search(path.name)
    if match:
        return int(match.group(1))
    return None


def legacy_lessons(path: Path) -> dict[int, Path]:
    lessons: dict[int, Path] = {}
    for item in path.glob("*.md"):
        number = lesson_number(item)
        if number is not None:
            lessons[number] = item
    return lessons


def legacy_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []

    for line in text.splitlines():
        if line.startswith("#") and not blocks and not current:
            continue
        if not line.strip():
            if current and any(part.strip() for part in current):
                blocks.append("\n".join(current).strip())
                current = []
            continue
        current.append(line.rstrip())

    if current and any(part.strip() for part in current):
        blocks.append("\n".join(current).strip())

    return blocks


def image_only_legacy(block: str) -> bool:
    without_images = strip_images(block).strip()
    return bool(block.strip()) and not without_images


def split_quote_runs(block: str) -> list[tuple[bool, str]]:
    runs: list[tuple[bool, str]] = []
    current: list[str] = []
    current_quote: bool | None = None

    for line in block.splitlines():
        is_quote = line.lstrip().startswith(">")
        if current_quote is None:
            current_quote = is_quote
        if is_quote != current_quote:
            runs.append((current_quote, "\n".join(current).strip()))
            current = []
            current_quote = is_quote
        current.append(line)

    if current:
        runs.append((bool(current_quote), "\n".join(current).strip()))

    return [(is_quote, text) for is_quote, text in runs if text]


def strip_quote_prefix(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(">"):
            stripped = stripped[1:].strip()
        lines.append(stripped)
    return "\n".join(lines).strip()


def annotation_kind(text: str, from_quote: bool) -> str:
    visible = strip_quote_prefix(text) if from_quote else text.strip()
    first_line = next((line.strip() for line in visible.splitlines() if line.strip()), "")
    note_like = (
        first_line.startswith(("注", "【注", "[注", "（注"))
        or bool(re.match(r"^【[^】]{1,40}】", first_line))
        or bool(re.match(r"^\*\*[^*]{1,80}\*\*\s*[：:]", first_line))
        or bool(re.match(r"^[A-Za-zÀ-ÿ][\wÀ-ÿ\- /]{1,60}[：:]", first_line))
        or "参见" in first_line
    )
    personal = any(marker in visible for marker in COMMENT_MARKERS)
    return "commentary" if personal and not first_line.startswith(("注", "【注", "[注")) else ("note" if note_like else "commentary")


def quote_annotation(text: str, kind: str, from_quote: bool) -> str:
    visible = strip_quote_prefix(text) if from_quote else text.strip()
    if kind == "note":
        first = next((line.strip() for line in visible.splitlines() if line.strip()), "")
        if not first.startswith(("注", "【注", "[注", "（注")):
            visible = f"注：{visible}"
    return "\n".join(f"> {line}" if line.strip() else ">" for line in visible.splitlines()).strip()


def commentary_like(text: str) -> bool:
    clean = clean_text(text)
    if clean.startswith(("【", "[注", "注：", "注:")):
        return True
    if re.match(r"^[A-Za-zÀ-ÿ][\wÀ-ÿ\- /]{1,60}[：:]", clean):
        return True
    marker_hits = sum(1 for marker in COMMENT_MARKERS if marker in clean)
    if marker_hits >= 2:
        return True
    if marker_hits and len(clean) < 160:
        return True
    return False


def parse_legacy_translation(path: Path) -> list[TranslationUnit]:
    units: list[TranslationUnit] = []
    pending_annotations: list[tuple[str, str]] = []

    for block in legacy_blocks(path.read_text(encoding="utf-8")):
        if image_only_legacy(block):
            continue

        for from_quote, run in split_quote_runs(block):
            run = remove_legacy_images(run)
            if not clean_text(run):
                continue

            if from_quote or commentary_like(run):
                kind = annotation_kind(run, from_quote)
                annotation = quote_annotation(run, kind, from_quote)
                if units:
                    units[-1].annotations.append((kind, annotation))
                else:
                    pending_annotations.append((kind, annotation))
                continue

            unit = TranslationUnit(
                text=run.strip(),
                clean=clean_text(run),
                tokens=semantic_tokens(run),
            )
            if pending_annotations:
                unit.annotations.extend(pending_annotations)
                pending_annotations = []
            units.append(unit)

    if pending_annotations and units:
        units[-1].annotations.extend(pending_annotations)

    return [unit for unit in units if unit.clean]


def group_score(sources: list[SourceBlock], targets: list[TranslationUnit], target_len_factor: float) -> float:
    if not sources or not targets:
        return -10.0

    source_tokens: set[str] = set()
    target_tokens: set[str] = set()
    source_len = 0
    target_len = 0

    for source in sources:
        source_tokens.update(source.tokens)
        source_len += max(1, len(source.text))
    for target in targets:
        target_tokens.update(target.tokens)
        target_len += max(1, len(target.clean))

    shared = len(source_tokens & target_tokens)
    denom = max(1, min(len(source_tokens), len(target_tokens)))
    overlap = shared / denom

    # Chinese translation generally uses fewer characters than French source,
    # but the old files also include explanatory wording. Keep this broad.
    ideal_target_len = max(20.0, source_len * target_len_factor)
    ratio = target_len / ideal_target_len
    length_score = math.exp(-abs(math.log(max(0.05, ratio))))

    return 2.1 * overlap + 1.35 * length_score


def align_blocks(
    sources: list[SourceBlock],
    targets: list[TranslationUnit],
    max_source_group: int,
    max_target_group: int,
    target_len_factor: float,
) -> list[Alignment]:
    text_sources = [source for source in sources if source.text and not source.image_only]
    alignments: list[Alignment] = []
    i = 0
    j = 0

    while i < len(text_sources) and j < len(targets):
        best: tuple[float, int, int, float] | None = None
        for source_count in range(1, min(max_source_group, len(text_sources) - i) + 1):
            source_group = text_sources[i : i + source_count]
            for target_count in range(1, min(max_target_group, len(targets) - j) + 1):
                target_group = targets[j : j + target_count]
                score = group_score(source_group, target_group, target_len_factor)
                source_len = sum(max(1, len(source.text)) for source in source_group)
                target_len = sum(max(1, len(target.clean)) for target in target_group)
                ideal = max(20.0, source_len * target_len_factor)
                ratio_penalty = abs(math.log(max(0.05, target_len / ideal)))
                # Prefer semantic overlap first, then a plausible amount of text.
                value = (
                    score
                    - 0.7 * ratio_penalty
                    - 0.005 * (source_count - 1)
                    - 0.015 * (target_count - 1)
                )
                if best is None or value > best[0]:
                    best = (value, source_count, target_count, score)

        if best is None:
            break

        _, source_count, target_count, score = best
        source_group = text_sources[i : i + source_count]
        target_group = targets[j : j + target_count]
        alignments.append(Alignment(source_group, target_group, score))
        i += source_count
        j += target_count

    if j < len(targets) and alignments:
        for target in targets[j:]:
            alignments[-1].targets[-1].annotations.append(
                ("commentary", quote_annotation(target.text, "commentary", False))
            )
            alignments[-1].targets[-1].annotations.extend(target.annotations)

    return alignments


def render_alignment(alignment: Alignment) -> str:
    ids = [source.paragraph_id for source in alignment.sources]
    lines = [f"<!-- id: {ids[0]} -->"]
    if len(ids) > 1:
        lines.append(f"<!-- ids: {' '.join(ids)} -->")
    lines.append("")

    body_parts: list[str] = []
    for target in alignment.targets:
        body_parts.append(target.text.strip())
        for _, annotation in target.annotations:
            body_parts.append(annotation)

    lines.append("\n\n".join(part for part in body_parts if part.strip()))
    return "\n".join(lines).rstrip()


def render_translation_file(original_path: Path, alignments: list[Alignment], seminar: str) -> str:
    original = original_path.read_text(encoding="utf-8")
    title = next((line for line in original.splitlines() if line.startswith("#")), f"# {original_path.stem}")
    lesson = original_path.stem.rsplit("-", 1)[-1]
    chunks = [
        title,
        "",
        "<!-- source-translation: src.bk -->",
        f"<!-- seminar: {seminar} -->",
        f"<!-- lesson: {lesson} -->",
        "",
    ]
    chunks.extend(render_alignment(alignment) for alignment in alignments)
    return "\n\n".join(chunk.rstrip() for chunk in chunks if chunk.rstrip()) + "\n"


def import_seminar(config: dict) -> None:
    slug = config["slug"]
    seminar = config["seminar"]
    original_dir = ROOT / "texts" / slug / "original"
    translation_dir = ROOT / "texts" / slug / "translation"
    translation_dir.mkdir(parents=True, exist_ok=True)
    legacy_by_lesson = legacy_lessons(config["legacy"])

    print(f"== {slug}", flush=True)
    for original_path in sorted(original_dir.glob("lesson-*.md")):
        lesson = int(original_path.stem.rsplit("-", 1)[-1])
        legacy_path = legacy_by_lesson.get(lesson)
        if legacy_path is None:
            print(f"{original_path.name}: missing legacy translation", flush=True)
            continue

        sources = parse_original(original_path)
        targets = parse_legacy_translation(legacy_path)
        alignments = align_blocks(
            sources,
            targets,
            config["max_source_group"],
            config["max_target_group"],
            config.get("target_len_factors", {}).get(lesson, config["target_len_factor"]),
        )
        output = render_translation_file(original_path, alignments, seminar)
        output_path = translation_dir / original_path.name
        output_path.write_text(output, encoding="utf-8")

        covered_ids = sum(len(alignment.sources) for alignment in alignments)
        text_sources = sum(1 for source in sources if source.text and not source.image_only)
        print(
            f"{original_path.name}: legacy={legacy_path.name} "
            f"targets={len(targets)} aligned={len(alignments)} "
            f"source_ids={covered_ids}/{text_sources}",
            flush=True,
        )


def main() -> None:
    for config in IMPORTS:
        import_seminar(config)


if __name__ == "__main__":
    main()
