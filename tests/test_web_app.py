"""test_web_app.py — Tests for the FastAPI web application static-serving behaviour.

Skipped automatically when fastapi / httpx are not installed.
"""

import pytest

# Skip the entire module if FastAPI (and its test client) is not available.
fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")


class TestSpaFallback:
    """The SPA 404 fallback must NOT intercept /assets/ requests.

    Serving index.html HTML in response to a missing JS chunk causes
    "Failed to fetch dynamically imported module" in the browser.
    """

    @pytest.fixture()
    def client(self, tmp_path):  # type: ignore[override]
        """Return a TestClient backed by the real app with a temporary static dir."""
        from starlette.testclient import TestClient

        # Point the module-level paths at a temp directory so we control
        # exactly which files exist without touching the real build output.
        import web.app as web_module
        from web.app import _ASSETS_DIR, _STATIC_DIR, app

        fake_static = tmp_path / "static"
        fake_assets = fake_static / "assets"
        fake_assets.mkdir(parents=True)

        # Write a minimal index.html
        (fake_static / "index.html").write_text("<html>spa</html>", encoding="utf-8")

        # Write a single real asset
        (fake_assets / "real-chunk.js").write_bytes(b"console.log('hi')")

        # Patch module-level path constants for this test.
        original_static = web_module._STATIC_DIR
        original_assets = web_module._ASSETS_DIR
        web_module._STATIC_DIR = fake_static
        web_module._ASSETS_DIR = fake_assets

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        # Restore originals after the test.
        web_module._STATIC_DIR = original_static
        web_module._ASSETS_DIR = original_assets

    def test_root_serves_index(self, client) -> None:  # type: ignore[override]
        resp = client.get("/")
        assert resp.status_code == 200
        assert "spa" in resp.text

    def test_existing_asset_served(self, client) -> None:  # type: ignore[override]
        resp = client.get("/assets/real-chunk.js")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/javascript")

    def test_missing_asset_returns_404_not_html(self, client) -> None:
        """A missing /assets/ file must return 404, not index.html.

        This is the regression test for "Failed to fetch dynamically imported
        module": the old SPA fallback returned index.html for every 404 GET,
        including asset paths, so the browser received HTML when it expected JS.
        """
        resp = client.get("/assets/nonexistent-chunk-AbCdEfGh.js")
        assert resp.status_code == 404, (
            "Expected 404 for a missing asset, got index.html (SPA fallback). "
            "This would cause 'Failed to fetch dynamically imported module'."
        )
        # The body must not be the SPA shell HTML.
        assert "<html>spa</html>" not in resp.text

    def test_unknown_spa_route_returns_index(self, client) -> None:
        """Non-asset 404s (SPA client-side routes) should still return index.html."""
        resp = client.get("/projects/some-deep-route")
        assert resp.status_code == 200
        assert "spa" in resp.text

    def test_index_has_no_cache_headers(self, client) -> None:
        """index.html must never be cached to avoid stale chunk references."""
        resp = client.get("/")
        cc = resp.headers.get("cache-control", "")
        assert "no-store" in cc or "no-cache" in cc
