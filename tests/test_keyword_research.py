"""Tests for keyword_research.py — no network calls required (no --serp-key)."""
import importlib.util
import os


# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

def load_module():
    # Resolve path relative to this test file so it works from any cwd
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(base_dir, "scripts", "keyword_research.py")
    spec = importlib.util.spec_from_file_location("keyword_research", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_returns_required_keys():
    """Output dict must contain 'keywords', 'clusters', and 'gaps'."""
    mod = load_module()
    result = mod.keyword_research(
        keywords=["hypnose"],
        domain="hypnotherapie-hypnose.fr",
    )
    assert "keywords" in result, "Missing key: keywords"
    assert "clusters" in result, "Missing key: clusters"
    assert "gaps" in result, "Missing key: gaps"


def test_generates_variations():
    """A single seed keyword should produce multiple keyword variations."""
    mod = load_module()
    result = mod.keyword_research(
        keywords=["hypnose"],
        domain="hypnotherapie-hypnose.fr",
    )
    seed_count = sum(1 for k in result["keywords"] if k["source"] == "seed")
    generated_count = sum(1 for k in result["keywords"] if k["source"] == "generated")
    assert seed_count >= 1, "Seed keyword not present"
    assert generated_count > 1, "Expected multiple generated variations"


def test_clusters_by_intent():
    """'prix hypnose' should be placed in a transactional cluster."""
    mod = load_module()
    result = mod.keyword_research(
        keywords=["prix hypnose"],
        domain="hypnotherapie-hypnose.fr",
    )
    transactional_clusters = [
        c for c in result["clusters"] if c["intent"] == "transactional"
    ]
    assert transactional_clusters, "No transactional cluster found"
    all_kws_in_transactional = [
        kw for c in transactional_clusters for kw in c["keywords"]
    ]
    assert any("prix" in kw for kw in all_kws_in_transactional), (
        "'prix hypnose' not found in transactional cluster"
    )


def test_informational_intent():
    """'comment fonctionne hypnose' should be classified as informational."""
    mod = load_module()
    result = mod.keyword_research(
        keywords=["comment fonctionne hypnose"],
        domain="hypnotherapie-hypnose.fr",
    )
    kw_items = result["keywords"]
    seed = next((k for k in kw_items if k["source"] == "seed"), None)
    assert seed is not None, "Seed keyword not found in output"
    assert seed["intent"] == "informational", (
        f"Expected 'informational', got '{seed['intent']}'"
    )


def test_local_intent():
    """'hypnose paris' should be classified as local intent."""
    mod = load_module()
    result = mod.keyword_research(
        keywords=["hypnose paris"],
        domain="hypnotherapie-hypnose.fr",
    )
    kw_items = result["keywords"]
    seed = next((k for k in kw_items if k["source"] == "seed"), None)
    assert seed is not None, "Seed keyword not found in output"
    assert seed["intent"] == "local", (
        f"Expected 'local', got '{seed['intent']}'"
    )


def test_no_duplicates_in_keywords():
    """No keyword string should appear more than once in the output list."""
    mod = load_module()
    result = mod.keyword_research(
        keywords=["hypnose", "hypnose paris", "hypnothérapie"],
        domain="hypnotherapie-hypnose.fr",
    )
    kw_strings = [item["keyword"] for item in result["keywords"]]
    assert len(kw_strings) == len(set(kw_strings)), (
        f"Duplicate keywords found: "
        f"{[kw for kw in kw_strings if kw_strings.count(kw) > 1]}"
    )
