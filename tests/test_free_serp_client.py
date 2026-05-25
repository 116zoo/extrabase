"""Tests for free_serp_client.py"""
import importlib.util
from unittest.mock import patch, MagicMock


def load_module():
    spec = importlib.util.spec_from_file_location("free_serp_client", "scripts/free_serp_client.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ─── DuckDuckGo SERP ──────────────────────────────────────────────────────────

DDG_MOCK_RESULTS = [
    {"href": "https://concurrent1.fr/page", "title": "Concurrent 1", "body": "Description 1"},
    {"href": "https://concurrent2.fr/autre", "title": "Concurrent 2", "body": "Description 2"},
    {"href": "https://wikipedia.org/wiki/hypnose", "title": "Wikipedia", "body": "Hypnose wiki"},
]


def test_serp_ddg_returns_organic():
    mod = load_module()
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = DDG_MOCK_RESULTS
    with patch("duckduckgo_search.DDGS", return_value=mock_ddgs):
        result = mod.get_serp_ddg("hypnose paris", max_results=10)
    assert len(result["organic"]) == 3
    assert result["organic"][0]["rank"] == 1
    assert result["organic"][0]["url"] == "https://concurrent1.fr/page"
    assert result["organic"][0]["domain"] == "concurrent1.fr"
    assert result["source"] == "duckduckgo"


def test_serp_ddg_handles_import_error():
    mod = load_module()
    with patch.dict("sys.modules", {"duckduckgo_search": None}):
        result = mod.get_serp_ddg("test keyword")
    assert result["error"] is not None


# ─── Serper.dev ───────────────────────────────────────────────────────────────

SERPER_MOCK_RESPONSE = {
    "organic": [
        {"link": "https://site1.fr/", "title": "Site 1", "snippet": "Description 1"},
        {"link": "https://site2.fr/page", "title": "Site 2", "snippet": "Description 2"},
    ]
}


def test_serper_returns_results():
    mod = load_module()
    mock_resp = MagicMock()
    mock_resp.json.return_value = SERPER_MOCK_RESPONSE
    with patch("requests.post", return_value=mock_resp):
        result = mod.get_serp_serper("hypnose paris", api_key="fake_key")
    assert len(result["organic"]) == 2
    assert result["organic"][0]["url"] == "https://site1.fr/"
    assert result["source"] == "serper"


def test_serper_returns_error_without_key():
    mod = load_module()
    result = mod.get_serp_serper("test", api_key="")
    assert result["error"] is not None


# ─── Competitor detection ─────────────────────────────────────────────────────

def test_competitors_filters_target_domain():
    mod = load_module()
    ddg_results = [
        {"href": "https://mysite.fr/", "title": "My Site", "body": ""},
        {"href": "https://concurrent.fr/", "title": "Concurrent", "body": ""},
        {"href": "https://wikipedia.org/wiki/test", "title": "Wikipedia", "body": ""},
        {"href": "https://winner.fr/page", "title": "Winner", "body": ""},
    ]
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = ddg_results
    with patch("duckduckgo_search.DDGS", return_value=mock_ddgs):
        result = mod.get_competitors(["hypnose paris"], target_domain="mysite.fr", delay=0)
    domains = [c["domain"] for c in result["competitors"]]
    assert "mysite.fr" not in domains
    assert "wikipedia.org" not in domains
    assert "concurrent.fr" in domains


def test_competitors_returns_sorted_by_relevance():
    mod = load_module()
    # Two keywords — concurrent.fr appears in both → higher score
    def mock_text(keyword, **kwargs):
        if "paris" in keyword:
            return [
                {"href": "https://concurrent.fr/", "title": "C", "body": ""},
                {"href": "https://other.fr/", "title": "O", "body": ""},
            ]
        return [
            {"href": "https://concurrent.fr/", "title": "C", "body": ""},
        ]
    mock_ddgs = MagicMock()
    mock_ddgs.text.side_effect = mock_text
    with patch("duckduckgo_search.DDGS", return_value=mock_ddgs):
        result = mod.get_competitors(["hypnose paris", "hypnothérapie"], delay=0)
    assert result["competitors"][0]["domain"] == "concurrent.fr"


# ─── OpenPageRank ─────────────────────────────────────────────────────────────

def test_authority_returns_placeholder_without_key():
    mod = load_module()
    result = mod.get_domain_authority(["concurrent.fr", "other.fr"], api_key=None)
    assert result["error"] is not None
    assert len(result["domains"]) == 2


def test_authority_parses_opr_response():
    mod = load_module()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "response": [
            {"domain": "concurrent.fr", "page_rank_decimal": 3.5, "rank": 12000, "status_code": 200},
        ]
    }
    with patch("requests.get", return_value=mock_resp):
        result = mod.get_domain_authority(["concurrent.fr"], api_key="fake_key")
    assert result["domains"][0]["page_rank"] == 3.5
    assert result["domains"][0]["domain"] == "concurrent.fr"
