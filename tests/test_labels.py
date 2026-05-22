import pytest
from j2m_export.config import Config
from j2m_export.cli import main
from unittest.mock import MagicMock, patch
from pathlib import Path

def test_config_labels_cli():
    with patch("sys.argv", ["prog", "--base-url", "http://test", "--token", "test", "--label", "label1", "label2"]):
        config = Config()
        config.load()
        assert config.labels == ["label1", "label2"]

def test_config_labels_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("base_url: http://test\ntoken: test\nlabels:\n  - label1\n  - label2", encoding="utf-8")

    with patch("sys.argv", ["prog", "--config", str(config_file)]):
        config = Config()
        config.load()
        assert config.labels == ["label1", "label2"]

def test_label_filtering():
    # Mock issues
    issue1 = {"key": "PROJ-1", "fields": {"summary": "S1", "labels": ["label1"], "project": {"key": "P"}}}
    issue2 = {"key": "PROJ-2", "fields": {"summary": "S2", "labels": ["label2"], "project": {"key": "P"}}}
    issue3 = {"key": "PROJ-3", "fields": {"summary": "S3", "labels": ["label3"], "project": {"key": "P"}}}

    issues = [issue1, issue2, issue3]

    with patch("j2m_export.cli.Config") as MockConfig, \
         patch("j2m_export.cli.JiraClient") as MockClient, \
         patch("j2m_export.cli.format_issue_md", return_value="MD"), \
         patch("pathlib.Path.write_text") as mock_write:

        mock_config = MockConfig.return_value
        mock_config.base_url = "http://test"
        mock_config.token = "test"
        mock_config.output_dir = "output"
        mock_config.labels = ["label1", "label3"]
        mock_config.issue_keys = ["PROJ-1", "PROJ-2", "PROJ-3"]
        mock_config.jql = None
        mock_config.exclude_fields = []
        mock_config.stop_threshold_mb = 100

        mock_client = MockClient.return_value
        mock_client.get_issue.side_effect = issues

        from j2m_export.cli import main
        main()

        # Should only write 2 issues (label1 and label3)
        assert mock_write.call_count == 2

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
        mock_config.labels = ["label1"]
        mock_config.issue_keys = []
        mock_config.jql = None
        mock_config.exclude_fields = []
        mock_config.stop_threshold_mb = 100

        mock_client = MockClient.return_value
        # Mock search_issues to return issue1
        mock_client.search_issues.return_value = [issue1]

        from j2m_export.cli import main
        main()

        # Should call search_issues with label JQL
        mock_client.search_issues.assert_called_with('labels IN ("label1")')
        # Should write 1 issue
        assert mock_write.call_count == 1
