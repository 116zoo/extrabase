"""Tests for dataforseo_client.py"""
import importlib.util
from unittest.mock import patch, MagicMock


def load_module():
    spec = importlib.util.spec_from_file_location("dataforseo_client", "scripts/dataforseo_client.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOCK_SERP_RESPONSE = {
    "tasks": [{
        "result": [{
            "items": [
                {"type": "organic", "rank_group": 1, "url": "https://example.com/page1", "title": "Page One", "description": "Desc"},
                {"type": "organic", "rank_group": 2, "url": "https://competitor.com/page1", "title": "Competitor", "description": "Desc2"},
                {"type": "featured_snippet", "rank_group": 0, "url": "https://other.com", "title": "Snippet"},
            ]
        }]
    }]
}


def test_get_serp_results():
    mod = load_module()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_SERP_RESPONSE
    with patch("requests.post", return_value=mock_resp):
        result = mod.get_serp("hypnose paris", login="user", password="pass", location_code=2250)
    assert len(result["organic"]) == 2
    assert result["organic"][0]["rank"] == 1
    assert result["organic"][0]["url"] == "https://example.com/page1"


def test_returns_error_without_credentials():
    mod = load_module()
    result = mod.get_serp("test keyword", login="", password="", location_code=2250)
    assert result["error"] is not None


def test_get_backlinks_returns_error_without_credentials():
    mod = load_module()
    result = mod.get_backlinks("example.com", login="", password="")
    assert result["error"] is not None


def test_get_keyword_metrics_returns_error_without_credentials():
    mod = load_module()
    result = mod.get_keyword_metrics(["test"], login="", password="")
    assert result["error"] is not None
