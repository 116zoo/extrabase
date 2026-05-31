"""Tests for humanize.py — Python Humanizer port for SEO-GEO-AEO."""
import importlib.util
from datetime import datetime, timezone, timedelta


def load_module():
    spec = importlib.util.spec_from_file_location("humanize", "scripts/humanize.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ─────────────────────────────────────────────────────────────────
# Slug humanization
# ─────────────────────────────────────────────────────────────────

def test_slug_basic():
    mod = load_module()
    assert mod.humanize_slug("hypnose-paris") == "Hypnose Paris"


def test_slug_ordinal_15e():
    mod = load_module()
    result = mod.humanize_slug("paris-15e")
    assert "15" in result
    assert "Paris" in result


def test_slug_stop_words_not_first():
    mod = load_module()
    result = mod.humanize_slug("therapie-de-la-peur")
    # "de" and "la" should not be capitalized in middle
    assert result.startswith("Thérapie") or result.startswith("Therapie")
    assert " de " in result.lower() or " De " not in result


def test_slug_underscores():
    mod = load_module()
    assert mod.humanize_slug("my_page_title") == "My Page Title"


def test_slug_english():
    mod = load_module()
    result = mod.humanize_slug("about-us", lang="en")
    assert result == "About Us"


def test_slug_single_word():
    mod = load_module()
    assert mod.humanize_slug("contact") == "Contact"


# ─────────────────────────────────────────────────────────────────
# Casing
# ─────────────────────────────────────────────────────────────────

def test_title_case_fr_stop_words():
    mod = load_module()
    result = mod.to_title_case("hypnose à paris et en france")
    # "à", "et", "en" should be lowercase in middle
    assert "À Paris" in result or "à Paris" in result  # "à" mid-sentence
    assert result.startswith("Hypnose")


def test_title_case_first_word_always_capitalized():
    mod = load_module()
    result = mod.to_title_case("le guide complet")
    assert result.startswith("Le")


def test_title_case_last_word_always_capitalized():
    mod = load_module()
    result = mod.to_title_case("guide de la santé")
    assert result.endswith("Santé")


def test_sentence_case_basic():
    mod = load_module()
    assert mod.to_sentence_case("HELLO WORLD") == "Hello world"
    assert mod.to_sentence_case("hello world") == "Hello world"


def test_sentence_case_preserves_content():
    mod = load_module()
    result = mod.to_sentence_case("découvrez notre cabinet")
    assert result[0].isupper()


def test_identifier_pascal_case():
    mod = load_module()
    result = mod.humanize_identifier("PascalCaseInput")
    assert "pascal" in result.lower()
    assert "case" in result.lower()
    assert "input" in result.lower()


def test_identifier_snake_case():
    mod = load_module()
    result = mod.humanize_identifier("has_faqpage_schema")
    assert "faqpage" in result.lower()


def test_identifier_kebab():
    mod = load_module()
    result = mod.humanize_identifier("local-business-schema")
    assert "local" in result.lower()


def test_pascalize():
    mod = load_module()
    assert mod.pascalize("some-title for something") == "SomeTitleForSomething"


def test_camelize():
    mod = load_module()
    result = mod.camelize("some_title_here")
    assert result[0].islower()
    assert "Title" in result or "title" in result.lower()


def test_underscore():
    mod = load_module()
    assert mod.underscore("LocalBusiness") == "local_business"


def test_dasherize():
    mod = load_module()
    assert mod.dasherize("LocalBusiness") == "local-business"


# ─────────────────────────────────────────────────────────────────
# Truncation
# ─────────────────────────────────────────────────────────────────

def test_truncate_by_chars_word_boundary():
    mod = load_module()
    result = mod.truncate("Long text to truncate here", 10)
    assert result.endswith("…")
    assert len(result) <= 10
    # Must not cut mid-word
    text_part = result[:-1]  # without suffix
    assert not text_part.endswith(" ")


def test_truncate_no_change_if_short_enough():
    mod = load_module()
    text = "Short text"
    assert mod.truncate(text, 50) == text


def test_truncate_by_words():
    mod = load_module()
    result = mod.truncate("one two three four five", 3, by="words")
    assert result == "one two three…"


def test_truncate_from_left():
    mod = load_module()
    result = mod.truncate("Long text to truncate", 10, from_left=True)
    assert result.startswith("…")


def test_truncate_suffix_custom():
    mod = load_module()
    result = mod.truncate("Hello world here", 8, suffix="...")
    assert result.endswith("...")


def test_truncate_preserves_exact_boundary():
    mod = load_module()
    text = "ab cd ef gh"  # 11 chars
    result = mod.truncate(text, 7)  # "ab cd…" = 6 chars
    assert "…" in result
    assert len(result) <= 7


# ─────────────────────────────────────────────────────────────────
# SEO Title optimizer
# ─────────────────────────────────────────────────────────────────

def test_optimize_title_length_ok():
    mod = load_module()
    title = "Hypnothérapeute à Paris 15e — Cabinet"  # ~38 chars
    result = mod.optimize_title(title, max_chars=65, min_chars=30)
    assert result["length_ok"] is True
    assert result["truncated"] is False


def test_optimize_title_too_long_truncated():
    mod = load_module()
    long_title = "Hypnothérapeute certifié à Paris 15e arrondissement — Thérapie brève anxiété phobies"
    result = mod.optimize_title(long_title, max_chars=65)
    assert result["truncated"] is True
    assert result["length"] <= 65


def test_optimize_title_keyword_detection():
    mod = load_module()
    result = mod.optimize_title("Hypnose Paris — Mon Cabinet", keyword="hypnose paris")
    assert result["keyword_position"] is not None
    assert result["keyword_position"] >= 0


def test_optimize_title_keyword_missing():
    mod = load_module()
    result = mod.optimize_title("Mon Cabinet de Thérapie", keyword="hypnose paris")
    assert "hypnose paris" in " ".join(result["issues"]).lower()
    assert len(result["suggestions"]) > 0


def test_optimize_title_has_required_keys():
    mod = load_module()
    result = mod.optimize_title("Test title")
    for key in ["original", "optimized", "length", "keyword_position",
                "keyword_in_first_30", "length_ok", "truncated", "issues", "suggestions"]:
        assert key in result


# ─────────────────────────────────────────────────────────────────
# SEO Meta optimizer
# ─────────────────────────────────────────────────────────────────

def test_optimize_meta_detects_cta():
    mod = load_module()
    result = mod.optimize_meta(
        "Découvrez notre cabinet d'hypnothérapie à Paris. Prenez RDV en ligne."
    )
    assert result["has_cta"] is True


def test_optimize_meta_no_cta_issues():
    mod = load_module()
    result = mod.optimize_meta("Notre cabinet propose des séances d'hypnose à Paris.")
    assert result["has_cta"] is False
    assert any("CTA" in i or "cta" in i.lower() for i in result["issues"])


def test_optimize_meta_too_long_truncated():
    mod = load_module()
    long_meta = "A" * 200
    result = mod.optimize_meta(long_meta, max_chars=165)
    assert result["truncated"] is True
    assert result["length"] <= 166  # +1 for possible trailing period


def test_optimize_meta_keyword_present():
    mod = load_module()
    result = mod.optimize_meta(
        "Hypnose Paris — Cabinet Thérapeutique. Prenez RDV.",
        keyword="hypnose paris"
    )
    assert result["keyword_present"] is True


def test_optimize_meta_has_required_keys():
    mod = load_module()
    result = mod.optimize_meta("Test meta description. Prenez rendez-vous.")
    for key in ["original", "optimized", "length", "has_cta",
                "keyword_present", "length_ok", "truncated", "issues", "suggestions"]:
        assert key in result


# ─────────────────────────────────────────────────────────────────
# DateTime humanization
# ─────────────────────────────────────────────────────────────────

def test_humanize_datetime_past_hours():
    mod = load_module()
    now = datetime.now(tz=timezone.utc)
    two_hours_ago = (now - timedelta(hours=2)).isoformat()
    result = mod.humanize_datetime(two_hours_ago, reference=now)
    assert "heure" in result or "hour" in result


def test_humanize_datetime_yesterday():
    mod = load_module()
    now = datetime.now(tz=timezone.utc)
    yesterday = (now - timedelta(hours=36)).isoformat()
    result = mod.humanize_datetime(yesterday, reference=now)
    assert "hier" in result


def test_humanize_datetime_future():
    mod = load_module()
    now = datetime.now(tz=timezone.utc)
    future = (now + timedelta(hours=3)).isoformat()
    result = mod.humanize_datetime(future, reference=now)
    assert "dans" in result


def test_humanize_datetime_just_now():
    mod = load_module()
    now = datetime.now(tz=timezone.utc)
    just_now = (now - timedelta(seconds=10)).isoformat()
    result = mod.humanize_datetime(just_now, reference=now)
    assert "instant" in result or "now" in result


def test_humanize_duration_basic():
    mod = load_module()
    assert "heure" in mod.humanize_duration(3600)
    assert "minute" in mod.humanize_duration(60)
    assert "seconde" in mod.humanize_duration(1)


def test_humanize_duration_precision():
    mod = load_module()
    result = mod.humanize_duration(3661, precision=2)
    assert "heure" in result
    assert "minute" in result


# ─────────────────────────────────────────────────────────────────
# Number formatting
# ─────────────────────────────────────────────────────────────────

def test_number_grouped_fr():
    mod = load_module()
    result = mod.humanize_number(1234567, lang="fr", style="grouped")
    assert "234" in result  # grouped with spaces


def test_number_compact_millions():
    mod = load_module()
    result = mod.humanize_number(1_200_000, style="compact")
    assert "M" in result
    assert "1" in result


def test_number_compact_thousands():
    mod = load_module()
    result = mod.humanize_number(45_000, style="compact")
    assert "k" in result


def test_number_ordinal_fr_first():
    mod = load_module()
    result = mod.humanize_number(1, lang="fr", style="ordinal")
    assert "1" in result
    assert "ʳ" in result or "er" in result.lower() or "ᵉ" in result


def test_number_ordinal_fr_other():
    mod = load_module()
    result = mod.humanize_number(5, lang="fr", style="ordinal")
    assert "5" in result


def test_number_words_fr():
    mod = load_module()
    assert mod.humanize_number(1, style="words") == "un"
    assert mod.humanize_number(100, style="words") == "cent"


# ─────────────────────────────────────────────────────────────────
# Pluralization
# ─────────────────────────────────────────────────────────────────

def test_pluralize_regular():
    mod = load_module()
    assert mod.pluralize("case", 2) == "cases"
    assert mod.pluralize("case", 1) == "case"


def test_pluralize_irregular():
    mod = load_module()
    assert mod.pluralize("man", 2) == "men"
    assert mod.pluralize("person", 2) == "people"


def test_singularize():
    mod = load_module()
    assert mod.singularize("cases") == "case"
    assert mod.singularize("men") == "man"


def test_to_quantity():
    mod = load_module()
    assert mod.to_quantity("case", 0) == "0 cases"
    assert mod.to_quantity("case", 1) == "1 case"
    assert mod.to_quantity("fix", 3) == "3 fixes"


# ─────────────────────────────────────────────────────────────────
# Batch mode
# ─────────────────────────────────────────────────────────────────

def test_batch_slug():
    mod = load_module()
    items = ["hypnose-paris", "contact", "qui-suis-je"]
    result = mod.batch_humanize(items, "slug")
    assert len(result) == 3
    assert result[0]["input"] == "hypnose-paris"
    assert result[0]["output"] == "Hypnose Paris"
    assert result[1]["output"] == "Contact"


def test_batch_title_case():
    mod = load_module()
    items = ["therapie breve", "anxiete et phobies"]
    result = mod.batch_humanize(items, "title-case")
    assert len(result) == 2
    assert result[0]["output"][0].isupper()


def test_batch_optimize_title():
    mod = load_module()
    items = ["Hypnose Paris Cabinet", "Thérapie Brève Anxiété"]
    result = mod.batch_humanize(items, "optimize-title", max_chars=65)
    assert len(result) == 2
    assert "optimized" in result[0]
    assert "issues" in result[0]
