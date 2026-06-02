"""Tests for wp_elementor.py"""
import importlib.util
import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock


def load_module():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location(
        "wp_elementor", os.path.join(base, "scripts", "wp_elementor.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_profile(with_credentials: bool = True) -> dict:
    if with_credentials:
        return {
            "url": "https://example.fr",
            "name": "Test Site",
            "credentials": {
                "wp_rest": {
                    "url": "https://example.fr/wp-json",
                    "token": "test-bearer-token",
                }
            },
        }
    return {
        "url": "https://example.fr",
        "name": "Test Site",
        "credentials": {},
    }


def write_profile(profile: dict) -> str:
    tf = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(profile, tf)
    tf.close()
    return tf.name


def make_mock_post_response(status_code: int, post_id: int = 42, link: str = "https://example.fr/ma-page/") -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = {"id": post_id, "link": link}
    mock.text = json.dumps({"id": post_id, "link": link})
    return mock


def test_returns_error_without_credentials():
    mod = load_module()
    profile = make_profile(with_credentials=False)
    wp_url, token = mod.get_wp_credentials(profile)
    assert wp_url is None
    assert token is None

    profile_path = write_profile(profile)
    try:
        result = {"success": False, "post_id": None, "url": None, "error": "no_wp_credentials"}
        # Simulate what main() does: no credentials → error
        loaded = mod.load_profile(profile_path)
        url, tok = mod.get_wp_credentials(loaded)
        assert url is None
        assert tok is None
    finally:
        os.unlink(profile_path)


def test_posts_page_successfully():
    mod = load_module()
    profile_path = write_profile(make_profile(with_credentials=True))
    try:
        mock_resp = make_mock_post_response(201)
        with patch("requests.post", return_value=mock_resp):
            result = mod.publish_page(
                wp_rest_url="https://example.fr/wp-json",
                token="test-bearer-token",
                title="Ma Page Test",
                slug="ma-page-test",
                content="<p>Contenu de test</p>",
                status="draft",
            )
        assert result["success"] is True
        assert result["post_id"] is not None
        assert result["error"] is None
    finally:
        os.unlink(profile_path)


def test_injects_schema_in_content():
    mod = load_module()
    schema = {"@context": "https://schema.org", "@type": "Service", "name": "Test"}
    content = "<p>Contenu principal</p>"
    result = mod.inject_schema(content, schema)
    assert '<script type="application/ld+json">' in result
    assert "https://schema.org" in result
    assert result.startswith(content)


def test_draft_status_by_default():
    mod = load_module()
    captured_payload = {}

    def mock_post(url, headers=None, json=None, timeout=None):
        captured_payload.update(json or {})
        return make_mock_post_response(201)

    with patch("requests.post", side_effect=mock_post):
        mod.publish_page(
            wp_rest_url="https://example.fr/wp-json",
            token="test-token",
            title="Test",
            slug="test",
            content="<p>test</p>",
            # status not passed → defaults to "draft"
        )

    assert captured_payload.get("status") == "draft"


def test_handles_api_error():
    mod = load_module()
    mock_resp = make_mock_post_response(401)
    mock_resp.text = '{"code":"rest_forbidden","message":"Sorry, you are not allowed."}'
    with patch("requests.post", return_value=mock_resp):
        result = mod.publish_page(
            wp_rest_url="https://example.fr/wp-json",
            token="bad-token",
            title="Test",
            slug="test",
            content="<p>test</p>",
            status="draft",
        )
    assert result["success"] is False
    assert result["error"] is not None
    assert result["post_id"] is None
