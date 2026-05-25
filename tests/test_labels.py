import pytest
from j2m_export.config import Config
from j2m_export.cli import main
from unittest.mock import MagicMock, patch
from pathlib import Path

def test_config_proj_keys_cli():
    with patch("sys.argv", ["prog", "--base-url", "http://test", "--token", "test", "--proj-keys", "PROJ1", "PROJ2"]):
        config = Config()
        config.load()
        assert config.proj_keys == ["PROJ1", "PROJ2"]

def test_config_proj_keys_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("base_url: http://test\ntoken: test\nproj_keys:\n  - PROJ1\n  - PROJ2", encoding="utf-8")

    with patch("sys.argv", ["prog", "--config", str(config_file)]):
        config = Config()
        config.load()
        assert config.proj_keys == ["PROJ1", "PROJ2"]

def test_basic_mode_fetching():
    issue1 = {"key": "PROJ-1", "fields": {"summary": "S1", "labels": ["label1"], "project": {"key": "PROJ"}}}

    with patch("j2m_export.cli.Config") as MockConfig, \
         patch("j2m_export.cli.JiraClient") as MockClient, \
         patch("j2m_export.cli.format_issue_md", return_value="MD"), \
         patch("pathlib.Path.write_text") as mock_write:

        mock_config = MockConfig.return_value
        mock_config.base_url = "http://test"
        mock_config.token = "test"
        mock_config.output_dir = "output"
        mock_config.proj_keys = ["PROJ"]
        mock_config.labels = ["label1"]
        mock_config.jql = None
        mock_config.exclude_fields = []
        mock_config.stop_threshold_mb = 100
        mock_config.max_mb = 95
        mock_config.overwrite = False

        mock_client = MockClient.return_value
        mock_client.search_issues.return_value = [issue1]

        main()

        # Should call search_issues with combined JQL
        mock_client.search_issues.assert_called_with('project IN ("PROJ") AND labels IN ("label1")')
        # Should write 1 issue (combined)
        assert mock_write.call_count == 1

def test_labels_only_fetching():
    issue1 = {"key": "PROJ-1", "fields": {"summary": "S1", "labels": ["label1"], "project": {"key": "P"}}}

    with patch("j2m_export.cli.Config") as MockConfig, \
         patch("j2m_export.cli.JiraClient") as MockClient, \
         patch("j2m_export.cli.format_issue_md", return_value="MD"), \
         patch("pathlib.Path.write_text") as mock_write:

        mock_config = MockConfig.return_value
        mock_config.base_url = "http://test"
        mock_config.token = "test"
        mock_config.output_dir = "output"
        mock_config.proj_keys = []
        mock_config.labels = ["label1"]
        mock_config.jql = None
        mock_config.exclude_fields = []
        mock_config.stop_threshold_mb = 100
        mock_config.max_mb = 95
        mock_config.overwrite = False

        mock_client = MockClient.return_value
        mock_client.search_issues.return_value = [issue1]

        main()

        # Should call search_issues with label JQL
        mock_client.search_issues.assert_called_with('labels IN ("label1")')
        assert mock_write.call_count == 1

def test_labels_escaping_fetching():
    issue1 = {"key": "PROJ-1", "fields": {"summary": "S1", "labels": ["label\"with\"quotes"], "project": {"key": "P"}}}

    with patch("j2m_export.cli.Config") as MockConfig, \
         patch("j2m_export.cli.JiraClient") as MockClient, \
         patch("j2m_export.cli.format_issue_md", return_value="MD"), \
         patch("pathlib.Path.write_text") as mock_write:

        mock_config = MockConfig.return_value
        mock_config.base_url = "http://test"
        mock_config.token = "test"
        mock_config.output_dir = "output"
        mock_config.proj_keys = []
        mock_config.labels = ["label\"with\"quotes"]
        mock_config.jql = None
        mock_config.exclude_fields = []
        mock_config.stop_threshold_mb = 100
        mock_config.max_mb = 95
        mock_config.overwrite = False

        mock_client = MockClient.return_value
        mock_client.search_issues.return_value = [issue1]

        main()

        # Should call search_issues with escaped double quotes
        mock_client.search_issues.assert_called_with('labels IN ("label\\"with\\"quotes")')
        assert mock_write.call_count == 1
