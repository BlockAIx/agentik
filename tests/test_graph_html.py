"""Tests for runner.graph_html — interactive HTML dependency graph."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestGenerateGraphHtml:
    def test_creates_html_file(self, tmp_project: Path) -> None:
        from runner.graph_html import generate_graph_html

        with patch("runner.graph_html.webbrowser") as mock_wb:
            path = generate_graph_html(tmp_project, open_browser=False)
            assert path.exists()
            assert path.suffix == ".html"
            mock_wb.open.assert_not_called()

    def test_html_contains_mermaid(self, tmp_project: Path) -> None:
        from runner.graph_html import generate_graph_html

        path = generate_graph_html(tmp_project, open_browser=False)
        content = path.read_text(encoding="utf-8")
        assert "mermaid" in content.lower()
        assert "graph TD" in content or "graph LR" in content

    def test_html_contains_task_nodes(self, tmp_project: Path) -> None:
        from runner.graph_html import generate_graph_html

        path = generate_graph_html(tmp_project, open_browser=False)
        content = path.read_text(encoding="utf-8")
        assert "First Task" in content
        assert "Second Task" in content

    def test_opens_browser_when_requested(self, tmp_project: Path) -> None:
        from runner.graph_html import generate_graph_html

        with patch("runner.graph_html.webbrowser") as mock_wb:
            generate_graph_html(tmp_project, open_browser=True)
            mock_wb.open.assert_called_once()
