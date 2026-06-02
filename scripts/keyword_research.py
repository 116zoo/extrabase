"""
Keyword research and semantic variation generator.

Usage:
    python scripts/keyword_research.py --keywords "hypnose paris,hypnothérapie" \
        --domain hypnotherapie-hypnose.fr [--serp-key SERPER_KEY]

Output: JSON with keys "keywords", "clusters", "gaps"
"""

import argparse
import json
import re
import subprocess
import sys


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

INTENT_RULES = [
    ("informational", [
        "comment", "qu'est-ce", "pourquoi", "c'est quoi", "définition",
        "guide", "tutoriel", "explication", "comprendre", "savoir",
    ]),
    ("transactional", [
        "prix", "tarif", "devis", "réservation", "réserver", "acheter",
        "commander", "contacter", "consultation", "séance", "rendez-vous",
        "booking",
    ]),
    ("commercial", [
        "avis", "meilleur", "comparatif", "top", "test", "recommandé",
        "recommande", "comparaison", "vs", "versus", "alternative",
        "review",
    ]),
    ("local", [
        "paris", "lyon", "bordeaux", "marseille", "toulouse", "nice",
        "nantes", "strasbourg", "montpellier", "rennes", "lille",
        "proche", "près de", "pres de", "arrondissement", "quartier",
        "france", "région", "departement",
    ]),
]


def detect_intent(keyword: str) -> str:
    """Return the intent of a keyword based on signal words."""
    kw_lower = keyword.lower()
    for intent, signals in INTENT_RULES:
        for signal in signals:
            if signal in kw_lower:
                return intent
    return "informational"


# ---------------------------------------------------------------------------
# Variation generation
# ---------------------------------------------------------------------------

PREFIXES = ["comment", "prix", "meilleur", "avis", "c'est quoi"]

SUFFIXES = ["paris", "france", "professionnel", "pas cher"]

SECTOR_SYNONYMS = {
    "sante": ["thérapeute", "séance", "consultation", "praticien", "cabinet"],
    "ecommerce": ["boutique", "achat", "livraison", "soldes"],
    "saas": ["logiciel", "outil", "plateforme", "essai gratuit"],
    "local": ["cabinet", "bureau", "adresse", "horaires"],
    "default": ["service", "professionnel", "expert", "avis"],
}


def generate_variations(keyword: str, sector: str = "default") -> list:
    """Generate semantic variations for a single keyword."""
    variations = []

    # Prefix variations
    for prefix in PREFIXES:
        variations.append(f"{prefix} {keyword}")

    # Suffix variations
    for suffix in SUFFIXES:
        variations.append(f"{keyword} {suffix}")

    # Sector synonym appends
    synonyms = SECTOR_SYNONYMS.get(sector, SECTOR_SYNONYMS["default"])
    for synonym in synonyms:
        variations.append(f"{keyword} {synonym}")

    return variations


def detect_sector_from_keywords(keywords: list) -> str:
    """Guess sector from keyword list to pick relevant synonyms."""
    joined = " ".join(keywords).lower()
    if any(w in joined for w in ["hypno", "thérapie", "médecin", "santé", "psy", "kiné"]):
        return "sante"
    if any(w in joined for w in ["boutique", "produit", "achat", "shop"]):
        return "ecommerce"
    if any(w in joined for w in ["logiciel", "saas", "app", "software"]):
        return "saas"
    return "default"


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def cluster_keywords(keyword_items: list) -> list:
    """Group keyword items by intent into clusters."""
    buckets: dict = {}
    for item in keyword_items:
        intent = item["intent"]
        if intent not in buckets:
            buckets[intent] = []
        buckets[intent].append(item["keyword"])

    clusters = []
    for intent, kws in buckets.items():
        cluster_name = f"{intent.capitalize()} keywords"
        clusters.append({
            "cluster_name": cluster_name,
            "intent": intent,
            "keywords": kws,
        })
    return clusters


# ---------------------------------------------------------------------------
# Gap detection (basic heuristic — compare against domain slug)
# ---------------------------------------------------------------------------

def detect_gaps(keyword_items: list, domain: str) -> list:
    """
    Surface keywords whose topic does not appear in the domain name.
    This is a lightweight heuristic; real gap detection requires SERP data.
    """
    domain_tokens = set(re.split(r"[-.]", domain.lower()))
    gaps = []
    for item in keyword_items:
        kw_tokens = set(item["keyword"].lower().split())
        if not kw_tokens.intersection(domain_tokens):
            gaps.append(item["keyword"])
    return gaps


# ---------------------------------------------------------------------------
# SERP enrichment via free_serp_client.py
# ---------------------------------------------------------------------------

def enrich_with_serp(keyword_items: list, serp_key: str) -> list:
    """
    Call free_serp_client.py for each keyword to get search volume.
    Falls back to volume=null on any error.
    """
    enriched = []
    for item in keyword_items:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/free_serp_client.py",
                    "--query", item["keyword"],
                    "--api-key", serp_key,
                    "--mode", "volume",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                item = dict(item)
                item["volume"] = data.get("volume", None)
            else:
                item = dict(item)
                item["volume"] = None
        except Exception:
            item = dict(item)
            item["volume"] = None
        enriched.append(item)
    return enriched


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def keyword_research(keywords: list, domain: str, serp_key: str = None) -> dict:
    """
    Core research function. Returns dict with keys: keywords, clusters, gaps.

    Args:
        keywords: List of seed keyword strings.
        domain:   Target domain (used for gap heuristic).
        serp_key: Optional Serper API key for volume enrichment.

    Returns:
        {
            "keywords": [{"keyword": ..., "intent": ..., "volume": null, "source": ...}],
            "clusters": [{"cluster_name": ..., "intent": ..., "keywords": [...]}],
            "gaps":     [str, ...],
        }
    """
    sector = detect_sector_from_keywords(keywords)

    all_items = []
    seen = set()

    def add_item(kw: str, source: str) -> None:
        kw_clean = kw.strip().lower()
        if not kw_clean or kw_clean in seen:
            return
        seen.add(kw_clean)
        all_items.append({
            "keyword": kw_clean,
            "intent": detect_intent(kw_clean),
            "volume": None,
            "source": source,
        })

    # Seed keywords
    for kw in keywords:
        add_item(kw, "seed")

    # Variations for each seed keyword
    for kw in keywords:
        for variation in generate_variations(kw, sector):
            add_item(variation, "generated")

    # Enrich with SERP volumes if key provided
    if serp_key:
        all_items = enrich_with_serp(all_items, serp_key)

    clusters = cluster_keywords(all_items)
    gaps = detect_gaps(all_items, domain)

    return {
        "keywords": all_items,
        "clusters": clusters,
        "gaps": gaps,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Keyword research and semantic variation generator."
    )
    parser.add_argument(
        "--keywords",
        required=True,
        help="Comma-separated list of seed keywords.",
    )
    parser.add_argument(
        "--domain",
        required=True,
        help="Target domain (e.g. hypnotherapie-hypnose.fr).",
    )
    parser.add_argument(
        "--serp-key",
        default=None,
        help="Serper.dev API key for volume enrichment (optional).",
    )
    args = parser.parse_args()

    seed_keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    result = keyword_research(
        keywords=seed_keywords,
        domain=args.domain,
        serp_key=args.serp_key,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
