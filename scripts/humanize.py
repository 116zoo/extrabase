#!/usr/bin/env python3
"""
humanize.py — Python port of Humanizer for SEO-GEO-AEO text processing.

Inspired by https://github.com/Humanizr/Humanizer (MIT).

Features:
  - Slug → readable title   (URL slugs to human text)
  - Title Case (FR/EN)      (French stop-word aware)
  - Sentence case
  - Smart truncation        (word-boundary, char or word count)
  - DateTime humanization   (French relative: "il y a 2 heures", "hier")
  - Number formatting       (1 234 567, 1,2M, ordinals FR)
  - SEO title optimizer     (truncate + keyword position check)
  - SEO meta optimizer      (truncate + CTA check)
  - Batch mode              (process list from JSON)

Usage:
  python scripts/humanize.py --mode slug "hypnose-paris-15e"
  python scripts/humanize.py --mode title-case "hypnose thérapeutique à paris"
  python scripts/humanize.py --mode truncate --max-chars 65 "Very long title text..."
  python scripts/humanize.py --mode optimize-title --keyword "hypnose paris" --max-chars 65 "My title"
  python scripts/humanize.py --mode optimize-meta --max-chars 165 "My meta description..."
  python scripts/humanize.py --mode date "2026-05-28T10:00:00"
  python scripts/humanize.py --mode number 1234567
  python scripts/humanize.py --mode batch --input data.json

Output: JSON to stdout
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone


# ─────────────────────────────────────────────────────────────────
# French stop words (not capitalized in Title Case)
# ─────────────────────────────────────────────────────────────────

FR_STOP_WORDS = {
    "à", "au", "aux", "avec", "ce", "ces", "cet", "cette", "dans", "de",
    "des", "du", "en", "et", "la", "le", "les", "leur", "leurs", "ni",
    "ou", "où", "par", "pas", "pour", "qu", "que", "qui", "sans", "se",
    "si", "son", "sur", "une", "un", "y",
}

EN_STOP_WORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "from", "if", "in",
    "nor", "of", "on", "or", "so", "the", "to", "up", "via", "with", "yet",
}


# ─────────────────────────────────────────────────────────────────
# Slug humanization
# ─────────────────────────────────────────────────────────────────

_ORDINAL_FR = re.compile(r"^(\d+)(eme?|ème?|ère?|er)$", re.I)
_ORDINAL_SUFFIX = {
    "er": "ᵉʳ", "ère": "ʳᵉ",
    "eme": "ᵉ", "ème": "ᵉ", "em": "ᵉ", "èm": "ᵉ",
}


def humanize_slug(slug: str, lang: str = "fr") -> str:
    """
    Convert a URL slug to human-readable title.

    Examples:
      "hypnose-paris-15e"      → "Hypnose Paris 15ᵉ"
      "therapie-breve-anxiete" → "Thérapie Brève Anxiété"
      "about-us"               → "About Us"
      "my_page_title"          → "My Page Title"
    """
    # Normalize separators
    text = slug.strip().replace("_", "-").replace("%20", " ")
    # Split on dashes and spaces
    words = re.split(r"[-\s]+", text)
    result = []
    stop_words = FR_STOP_WORDS if lang == "fr" else EN_STOP_WORDS

    for i, word in enumerate(words):
        if not word:
            continue
        # Handle ordinal suffixes: 15e → 15ᵉ
        m = _ORDINAL_FR.match(word)
        if m:
            num, suffix = m.group(1), m.group(2).lower()
            sup = _ORDINAL_SUFFIX.get(suffix, "ᵉ")
            result.append(f"{num}{sup}")
            continue
        # First word always capitalized; stop words lowercase in middle
        if i > 0 and word.lower() in stop_words:
            result.append(word.lower())
        else:
            result.append(word.capitalize())

    return " ".join(result)


# ─────────────────────────────────────────────────────────────────
# Casing
# ─────────────────────────────────────────────────────────────────

def to_title_case(text: str, lang: str = "fr") -> str:
    """
    Apply Title Case with language-aware stop words.
    First and last word always capitalized.

    Example (FR): "hypnose thérapeutique à paris 15e"
                → "Hypnose Thérapeutique à Paris 15ᵉ"
    """
    words = text.strip().split()
    if not words:
        return text
    stop_words = FR_STOP_WORDS if lang == "fr" else EN_STOP_WORDS
    result = []
    for i, word in enumerate(words):
        is_first = i == 0
        is_last = i == len(words) - 1
        # Handle ordinal suffixes
        m = _ORDINAL_FR.match(word)
        if m:
            num, suffix = m.group(1), m.group(2).lower()
            sup = _ORDINAL_SUFFIX.get(suffix, "ᵉ")
            result.append(f"{num}{sup}")
            continue
        if is_first or is_last or word.lower() not in stop_words:
            result.append(word.capitalize())
        else:
            result.append(word.lower())
    return " ".join(result)


def to_sentence_case(text: str) -> str:
    """
    Apply sentence case: capitalize first letter only.
    Preserves existing uppercase sequences (acronyms).

    Example: "SEO AUDIT des métadonnées" → "SEO audit des métadonnées"
    """
    text = text.strip()
    if not text:
        return text
    # Find first alphabetic character
    for i, ch in enumerate(text):
        if ch.isalpha():
            return text[:i] + text[i].upper() + text[i + 1:].lower()
    return text


def to_lower_case(text: str) -> str:
    return text.lower()


def to_upper_case(text: str) -> str:
    return text.upper()


def pascalize(text: str) -> str:
    """
    Convert slug/sentence to PascalCase.
    "some-title for something" → "SomeTitleForSomething"
    """
    words = re.split(r"[-_\s]+", text.strip())
    return "".join(w.capitalize() for w in words if w)


def camelize(text: str) -> str:
    """
    Convert slug/sentence to camelCase.
    "some-title for something" → "someTitleForSomething"
    """
    pascal = pascalize(text)
    return pascal[0].lower() + pascal[1:] if pascal else pascal


def underscore(text: str) -> str:
    """PascalCase/camelCase → snake_case."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower().replace("-", "_")


def dasherize(text: str) -> str:
    """snake_case → kebab-case."""
    return underscore(text).replace("_", "-")


def humanize_identifier(text: str) -> str:
    """
    PascalCase or snake_case or kebab-case → human sentence.
    "PascalCaseInput" → "Pascal case input"
    "some_snake_field" → "Some snake field"
    "kebab-case-text" → "Kebab case text"
    """
    # Handle PascalCase / camelCase
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1 \2", s)
    # Replace separators
    s = re.sub(r"[-_]+", " ", s)
    return to_sentence_case(s)


# ─────────────────────────────────────────────────────────────────
# Truncation
# ─────────────────────────────────────────────────────────────────

def truncate(
    text: str,
    max_length: int,
    *,
    by: str = "chars",
    suffix: str = "…",
    from_left: bool = False,
) -> str:
    """
    Smart truncation at word boundary.

    Args:
        text:       Input string
        max_length: Max chars or max words
        by:         "chars" (default) or "words"
        suffix:     Appended when truncated (default "…")
        from_left:  Truncate from left instead of right

    Examples:
        truncate("Long text to truncate", 10)          → "Long text…"
        truncate("Long text to truncate", 2, by="words") → "Long text…"
        truncate("Long text to truncate", 10, from_left=True) → "… truncate"
    """
    text = text.strip()

    if by == "words":
        words = text.split()
        if len(words) <= max_length:
            return text
        if from_left:
            kept = words[-max_length:]
            return suffix + " " + " ".join(kept)
        kept = words[:max_length]
        return " ".join(kept) + suffix

    # by chars
    if len(text) <= max_length:
        return text

    suffix_len = len(suffix)
    target = max_length - suffix_len

    if from_left:
        # Find word boundary from left
        chunk = text[-target:]
        space_idx = chunk.find(" ")
        if space_idx != -1:
            chunk = chunk[space_idx + 1:]
        return suffix + " " + chunk

    # Truncate from right at word boundary
    chunk = text[:target]
    last_space = chunk.rfind(" ")
    if last_space > 0:
        chunk = chunk[:last_space]
    return chunk.rstrip(",.;:!?-") + suffix


# ─────────────────────────────────────────────────────────────────
# DateTime humanization (French)
# ─────────────────────────────────────────────────────────────────

def humanize_datetime(dt_input, *, lang: str = "fr", reference: datetime = None) -> str:
    """
    Relative datetime in French (or English).

    Examples (FR):
      now - 30s   → "à l'instant"
      now - 2min  → "il y a 2 minutes"
      now - 2h    → "il y a 2 heures"
      now - 1d    → "hier"
      now - 3d    → "il y a 3 jours"
      now - 2w    → "il y a 2 semaines"
      now - 2mo   → "il y a 2 mois"
      now + 2h    → "dans 2 heures"
    """
    if isinstance(dt_input, str):
        try:
            dt = datetime.fromisoformat(dt_input.replace("Z", "+00:00"))
        except ValueError:
            return dt_input
    else:
        dt = dt_input

    now = reference or datetime.now(tz=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    delta = now - dt
    future = delta.total_seconds() < 0
    seconds = abs(delta.total_seconds())

    def _fr(seconds, future):
        if seconds < 45:
            return "à l'instant" if not future else "dans quelques secondes"
        if seconds < 90:
            return "dans 1 minute" if future else "il y a 1 minute"
        if seconds < 2700:  # 45 min
            m = round(seconds / 60)
            return f"dans {m} minutes" if future else f"il y a {m} minutes"
        if seconds < 5400:  # 1.5h
            return "dans 1 heure" if future else "il y a 1 heure"
        if seconds < 79200:  # 22h
            h = round(seconds / 3600)
            return f"dans {h} heures" if future else f"il y a {h} heures"
        if seconds < 172800:  # 48h → yesterday / tomorrow
            return "demain" if future else "hier"
        if seconds < 561600:  # 6.5 days
            d = round(seconds / 86400)
            return f"dans {d} jours" if future else f"il y a {d} jours"
        if seconds < 1209600:  # 14 days
            return "la semaine prochaine" if future else "la semaine dernière"
        if seconds < 3888000:  # 45 days
            w = round(seconds / 604800)
            return f"dans {w} semaines" if future else f"il y a {w} semaines"
        if seconds < 5184000:  # 60 days
            return "le mois prochain" if future else "le mois dernier"
        if seconds < 31536000:  # 365 days
            mo = round(seconds / 2592000)
            return f"dans {mo} mois" if future else f"il y a {mo} mois"
        y = round(seconds / 31536000)
        if y == 1:
            return "l'année prochaine" if future else "l'année dernière"
        return f"dans {y} ans" if future else f"il y a {y} ans"

    def _en(seconds, future):
        if seconds < 45:
            return "just now"
        if seconds < 90:
            return "in 1 minute" if future else "a minute ago"
        if seconds < 2700:
            m = round(seconds / 60)
            return f"in {m} minutes" if future else f"{m} minutes ago"
        if seconds < 5400:
            return "in 1 hour" if future else "an hour ago"
        if seconds < 79200:
            h = round(seconds / 3600)
            return f"in {h} hours" if future else f"{h} hours ago"
        if seconds < 129600:
            return "tomorrow" if future else "yesterday"
        if seconds < 561600:
            d = round(seconds / 86400)
            return f"in {d} days" if future else f"{d} days ago"
        if seconds < 1209600:
            return "next week" if future else "last week"
        if seconds < 3888000:
            w = round(seconds / 604800)
            return f"in {w} weeks" if future else f"{w} weeks ago"
        mo = round(seconds / 2592000)
        return f"in {mo} months" if future else f"{mo} months ago"

    return _fr(seconds, future) if lang == "fr" else _en(seconds, future)


def humanize_duration(seconds: float, *, lang: str = "fr", precision: int = 1) -> str:
    """
    Human-readable duration.

    Examples (FR, precision=1):
      90s   → "1 minute"
      3661s → "1 heure"
      90000s → "1 jour"

    precision=2:
      3661s → "1 heure, 1 minute"
    """
    units_fr = [
        (604800, "semaine", "semaines"),
        (86400, "jour", "jours"),
        (3600, "heure", "heures"),
        (60, "minute", "minutes"),
        (1, "seconde", "secondes"),
    ]
    units_en = [
        (604800, "week", "weeks"),
        (86400, "day", "days"),
        (3600, "hour", "hours"),
        (60, "minute", "minutes"),
        (1, "second", "seconds"),
    ]
    units = units_fr if lang == "fr" else units_en
    parts = []
    remaining = int(abs(seconds))

    for divisor, singular, plural in units:
        if remaining >= divisor:
            count = remaining // divisor
            remaining %= divisor
            parts.append(f"{count} {singular if count == 1 else plural}")
            if len(parts) == precision:
                break

    return ", ".join(parts) if parts else ("0 seconde" if lang == "fr" else "0 seconds")


# ─────────────────────────────────────────────────────────────────
# Number humanization
# ─────────────────────────────────────────────────────────────────

def humanize_number(n: int | float, *, lang: str = "fr", style: str = "grouped") -> str:
    """
    Format numbers in human-readable form.

    Styles:
      "grouped"  → 1 234 567   (FR space-grouped) / 1,234,567 (EN)
      "compact"  → 1,2M / 45k / 3,5Md
      "words"    → "un million deux cent trente-quatre mille..."  (FR, basic)
      "ordinal"  → "1er", "2e", "21e"  (FR) / "1st", "2nd" (EN)
    """
    if style == "grouped":
        if lang == "fr":
            return f"{n:,.0f}".replace(",", "\u202f")  # narrow no-break space
        return f"{n:,.0f}"

    if style == "compact":
        abs_n = abs(n)
        sign = "-" if n < 0 else ""
        if abs_n >= 1_000_000_000:
            v = abs_n / 1_000_000_000
            s = f"{v:.1f}".rstrip("0").rstrip(".")
            label = "Md" if lang == "fr" else "B"
            return f"{sign}{s}{label}"
        if abs_n >= 1_000_000:
            v = abs_n / 1_000_000
            s = f"{v:.1f}".rstrip("0").rstrip(".")
            return f"{sign}{s}M"
        if abs_n >= 1_000:
            v = abs_n / 1_000
            s = f"{v:.1f}".rstrip("0").rstrip(".")
            return f"{sign}{s}k"
        return str(n)

    if style == "ordinal":
        n = int(n)
        if lang == "fr":
            if n == 1:
                return "1ᵉʳ"
            return f"{n}ᵉ"
        # English ordinals
        if 11 <= (n % 100) <= 13:
            return f"{n}th"
        return {1: f"{n}st", 2: f"{n}nd", 3: f"{n}rd"}.get(n % 10, f"{n}th")

    if style == "words":
        # Basic FR words (up to billions)
        return _number_to_words_fr(int(n))

    return str(n)


_ONES_FR = [
    "", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf",
    "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize",
    "dix-sept", "dix-huit", "dix-neuf",
]
_TENS_FR = [
    "", "dix", "vingt", "trente", "quarante", "cinquante",
    "soixante", "soixante", "quatre-vingt", "quatre-vingt",
]


def _number_to_words_fr(n: int) -> str:
    if n < 0:
        return "moins " + _number_to_words_fr(-n)
    if n == 0:
        return "zéro"
    if n < 20:
        return _ONES_FR[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        if tens == 7:  # 70-79
            return _TENS_FR[6] + ("-" if ones else "") + (_ONES_FR[10 + ones] if ones else "-dix")
        if tens == 9:  # 90-99
            return _TENS_FR[8] + ("-" if ones else "s") + (_ONES_FR[10 + ones] if ones else "")
        base = _TENS_FR[tens]
        if ones == 0:
            return base + ("s" if tens == 8 else "")
        et = "-et-" if ones == 1 and tens < 8 else "-"
        return base + et + _ONES_FR[ones]
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        prefix = ("" if hundreds == 1 else _ONES_FR[hundreds] + " ") + "cent"
        suffix = (" " + _number_to_words_fr(rest)) if rest else ("s" if hundreds > 1 else "")
        return prefix + suffix
    if n < 1_000_000:
        thousands, rest = divmod(n, 1000)
        prefix = ("mille" if thousands == 1 else _number_to_words_fr(thousands) + " mille")
        suffix = (" " + _number_to_words_fr(rest)) if rest else ""
        return prefix + suffix
    if n < 1_000_000_000:
        millions, rest = divmod(n, 1_000_000)
        prefix = _number_to_words_fr(millions) + " million" + ("s" if millions > 1 else "")
        suffix = (" " + _number_to_words_fr(rest)) if rest else ""
        return prefix + suffix
    billions, rest = divmod(n, 1_000_000_000)
    prefix = _number_to_words_fr(billions) + " milliard" + ("s" if billions > 1 else "")
    suffix = (" " + _number_to_words_fr(rest)) if rest else ""
    return prefix + suffix


# ─────────────────────────────────────────────────────────────────
# SEO-specific optimizers
# ─────────────────────────────────────────────────────────────────

CTA_PATTERN = re.compile(
    r"\b(réserver|prenez|prendre|découvrez|contactez|essayez|commencez|"
    r"obtenez|téléchargez|consultez|réservez|book|buy|get|try|start|learn|"
    r"appeler|appelez|voir|voir|accéder)\b",
    re.IGNORECASE,
)


def optimize_title(
    title: str,
    *,
    keyword: str = None,
    max_chars: int = 65,
    min_chars: int = 50,
    lang: str = "fr",
    apply_title_case: bool = True,
) -> dict:
    """
    SEO title optimizer.

    Returns:
        {
          "original": str,
          "optimized": str,
          "length": int,
          "keyword_position": int | None,   # char index of keyword in optimized
          "keyword_in_first_30": bool,
          "length_ok": bool,
          "truncated": bool,
          "issues": list[str],
          "suggestions": list[str],
        }
    """
    result = {
        "original": title,
        "optimized": title,
        "length": len(title),
        "keyword_position": None,
        "keyword_in_first_30": False,
        "length_ok": False,
        "truncated": False,
        "issues": [],
        "suggestions": [],
    }

    text = title.strip()

    # Apply title case
    if apply_title_case:
        text = to_title_case(text, lang=lang)

    # Truncate if too long
    if len(text) > max_chars:
        text = truncate(text, max_chars)
        result["truncated"] = True
        result["issues"].append(f"Titre trop long ({len(title)} chars) — tronqué à {max_chars}")

    result["optimized"] = text
    result["length"] = len(text)
    result["length_ok"] = min_chars <= len(text) <= max_chars

    if len(text) < min_chars:
        result["issues"].append(f"Titre trop court ({len(text)} chars) — cible {min_chars}-{max_chars}")
        result["suggestions"].append("Enrichir le titre avec la ville, l'année ou un qualificatif")

    # Keyword position
    if keyword:
        kw_lower = keyword.lower()
        text_lower = text.lower()
        pos = text_lower.find(kw_lower)
        if pos == -1:
            result["issues"].append(f"Mot-clé '{keyword}' absent du titre")
            result["suggestions"].append(f"Insérer '{keyword}' en début de titre")
        else:
            result["keyword_position"] = pos
            result["keyword_in_first_30"] = pos < 30
            if pos >= 30:
                result["suggestions"].append(f"Déplacer '{keyword}' avant le caractère 30 pour meilleur CTR")

    return result


def optimize_meta(
    text: str,
    *,
    keyword: str = None,
    max_chars: int = 165,
    min_chars: int = 140,
    apply_sentence_case: bool = True,
) -> dict:
    """
    SEO meta description optimizer.

    Returns:
        {
          "original": str,
          "optimized": str,
          "length": int,
          "has_cta": bool,
          "keyword_present": bool,
          "length_ok": bool,
          "truncated": bool,
          "issues": list[str],
          "suggestions": list[str],
        }
    """
    result = {
        "original": text,
        "optimized": text,
        "length": len(text),
        "has_cta": False,
        "keyword_present": False,
        "length_ok": False,
        "truncated": False,
        "issues": [],
        "suggestions": [],
    }

    t = text.strip()

    if apply_sentence_case:
        t = to_sentence_case(t)

    if len(t) > max_chars:
        t = truncate(t, max_chars)
        result["truncated"] = True
        result["issues"].append(f"Meta description trop longue ({len(text)} chars) — tronquée à {max_chars}")

    # Ensure ends with period or CTA
    if t and not t[-1] in ".!?":
        t = t.rstrip(",;:") + "."

    result["optimized"] = t
    result["length"] = len(t)
    result["length_ok"] = min_chars <= len(t) <= max_chars

    if len(t) < min_chars:
        result["issues"].append(f"Meta trop courte ({len(t)} chars) — cible {min_chars}-{max_chars}")
        result["suggestions"].append("Enrichir avec bénéfice + CTA (ex: 'Prenez RDV en ligne.')")

    result["has_cta"] = bool(CTA_PATTERN.search(t))
    if not result["has_cta"]:
        result["issues"].append("Aucun CTA détecté dans la meta description")
        result["suggestions"].append("Ajouter un verbe d'action : 'Découvrez', 'Prenez RDV', 'Contactez-nous'")

    if keyword:
        result["keyword_present"] = keyword.lower() in t.lower()
        if not result["keyword_present"]:
            result["issues"].append(f"Mot-clé '{keyword}' absent de la meta description")
            result["suggestions"].append(f"Mentionner '{keyword}' naturellement dans la meta")

    return result


# ─────────────────────────────────────────────────────────────────
# Pluralization (English, basic)
# ─────────────────────────────────────────────────────────────────

_IRREGULAR_EN = {
    "man": "men", "woman": "women", "child": "children", "person": "people",
    "tooth": "teeth", "foot": "feet", "mouse": "mice", "goose": "geese",
}
_IRREGULAR_EN_INV = {v: k for k, v in _IRREGULAR_EN.items()}


def pluralize(word: str, count: int = 2) -> str:
    """Basic English pluralization."""
    if count == 1:
        return word
    w = word.lower()
    if w in _IRREGULAR_EN:
        return _IRREGULAR_EN[w]
    if w.endswith(("s", "sh", "ch", "x", "z")):
        return word + "es"
    if w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou":
        return word[:-1] + "ies"
    if w.endswith("f"):
        return word[:-1] + "ves"
    if w.endswith("fe"):
        return word[:-2] + "ves"
    return word + "s"


def singularize(word: str) -> str:
    """Basic English singularization."""
    w = word.lower()
    if w in _IRREGULAR_EN_INV:
        return _IRREGULAR_EN_INV[w]
    if w.endswith("ies"):
        return word[:-3] + "y"
    if w.endswith("ves"):
        return word[:-3] + "f"
    # Consonant clusters: "sses/shes/ches/xes/zes" → remove "es" (glass→glasses, dish→dishes)
    for suffix in ("sses", "shes", "ches", "xes", "zes"):
        if w.endswith(suffix):
            return word[:-2]
    if w.endswith("s") and not w.endswith("ss"):
        return word[:-1]
    return word


def to_quantity(word: str, count: int, *, show_as: str = "number") -> str:
    """
    Format a word with its quantity.
    show_as: "number" → "2 cases", "words" → "two cases", "none" → "cases"
    """
    plural = pluralize(word, count)
    if show_as == "none":
        return plural
    if show_as == "words":
        count_str = _number_to_words_fr(count)  # fallback to FR words
        return f"{count_str} {plural}"
    return f"{count} {plural}"


# ─────────────────────────────────────────────────────────────────
# Batch processing
# ─────────────────────────────────────────────────────────────────

def batch_humanize(items: list, mode: str, **kwargs) -> list:
    """
    Apply a humanize function to a list of strings.

    mode: "slug" | "title-case" | "sentence-case" | "truncate" | "identifier"
    """
    results = []
    for item in items:
        if mode == "slug":
            results.append({"input": item, "output": humanize_slug(item, **kwargs)})
        elif mode == "title-case":
            results.append({"input": item, "output": to_title_case(item, **kwargs)})
        elif mode == "sentence-case":
            results.append({"input": item, "output": to_sentence_case(item)})
        elif mode == "truncate":
            results.append({"input": item, "output": truncate(item, **kwargs)})
        elif mode == "identifier":
            results.append({"input": item, "output": humanize_identifier(item)})
        elif mode == "optimize-title":
            results.append(optimize_title(item, **kwargs))
        elif mode == "optimize-meta":
            results.append(optimize_meta(item, **kwargs))
        else:
            results.append({"input": item, "output": item})
    return results


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Humanizer — SEO text transformations")
    parser.add_argument("input", nargs="?", help="Input text or number")
    parser.add_argument("--mode", required=True, choices=[
        "slug", "title-case", "sentence-case", "lower", "upper",
        "truncate", "identifier", "pascalize", "camelize", "underscore", "dasherize",
        "date", "duration", "number",
        "optimize-title", "optimize-meta",
        "pluralize", "singularize", "quantity",
        "batch",
    ])
    parser.add_argument("--lang", default="fr", choices=["fr", "en"])
    parser.add_argument("--max-chars", type=int, default=65)
    parser.add_argument("--min-chars", type=int, default=50)
    parser.add_argument("--max-words", type=int)
    parser.add_argument("--keyword", default=None)
    parser.add_argument("--style", default="grouped", choices=["grouped", "compact", "words", "ordinal"])
    parser.add_argument("--precision", type=int, default=1)
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--suffix", default="…")
    parser.add_argument("--from-left", action="store_true")
    parser.add_argument("--input-file", "--input", dest="input_file", default=None,
                        help="JSON file with list of inputs for batch mode")
    parser.add_argument("--batch-mode", default="slug",
                        help="Sub-mode for --mode batch")
    args = parser.parse_args()

    text = args.input or ""

    if args.mode == "slug":
        out = humanize_slug(text, lang=args.lang)
    elif args.mode == "title-case":
        out = to_title_case(text, lang=args.lang)
    elif args.mode == "sentence-case":
        out = to_sentence_case(text)
    elif args.mode == "lower":
        out = to_lower_case(text)
    elif args.mode == "upper":
        out = to_upper_case(text)
    elif args.mode == "identifier":
        out = humanize_identifier(text)
    elif args.mode == "pascalize":
        out = pascalize(text)
    elif args.mode == "camelize":
        out = camelize(text)
    elif args.mode == "underscore":
        out = underscore(text)
    elif args.mode == "dasherize":
        out = dasherize(text)
    elif args.mode == "truncate":
        by = "words" if args.max_words else "chars"
        limit = args.max_words or args.max_chars
        out = truncate(text, limit, by=by, suffix=args.suffix, from_left=args.from_left)
    elif args.mode == "date":
        out = humanize_datetime(text, lang=args.lang)
    elif args.mode == "duration":
        out = humanize_duration(float(text), lang=args.lang, precision=args.precision)
    elif args.mode == "number":
        out = humanize_number(float(text), lang=args.lang, style=args.style)
    elif args.mode == "pluralize":
        out = pluralize(text, args.count)
    elif args.mode == "singularize":
        out = singularize(text)
    elif args.mode == "quantity":
        out = to_quantity(text, args.count)
    elif args.mode == "optimize-title":
        out = optimize_title(
            text,
            keyword=args.keyword,
            max_chars=args.max_chars,
            min_chars=args.min_chars,
            lang=args.lang,
        )
    elif args.mode == "optimize-meta":
        out = optimize_meta(
            text,
            keyword=args.keyword,
            max_chars=args.max_chars,
            min_chars=args.min_chars,
        )
    elif args.mode == "batch":
        if args.input_file:
            import json as _json
            with open(args.input_file) as f:
                items = _json.load(f)
        else:
            items = [text]
        out = batch_humanize(items, args.batch_mode, lang=args.lang)
    else:
        out = text

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
