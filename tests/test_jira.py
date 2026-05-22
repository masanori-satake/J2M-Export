import pytest
from unittest.mock import MagicMock, patch
from j2m_export.jira import JiraClient

def test_jira_client_init():
    client = JiraClient("https://jira.example.com", "fake_token", "http://proxy:8080")
    assert client.base_url == "https://jira.example.com"
    assert client.headers["Authorization"] == "Bearer fake_token"
    assert client.proxies["http"] == "http://proxy:8080"
    assert client.proxies["https"] == "http://proxy:8080"

@patch("requests.Session.request")
def test_get_issue(mock_request):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"key": "PROJ-1", "fields": {"summary": "Test Issue"}}
    mock_request.return_value = mock_response

    client = JiraClient("https://jira.example.com", "fake_token")
    issue = client.get_issue("PROJ-1")

    assert issue["key"] == "PROJ-1"
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert args[0] == "GET"
    assert "PROJ-1" in args[1]
    assert kwargs["params"]["expand"] == "renderedFields,names,schema"

@patch("requests.Session.request")
def test_search_issues(mock_request):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "issues": [{"key": "PROJ-1"}, {"key": "PROJ-2"}],
        "total": 2,
        "names": {"summary": "Summary"},
        "schema": {"summary": {"type": "string"}}
    }
    mock_request.return_value = mock_response

    client = JiraClient("https://jira.example.com", "fake_token")
    issues = client.search_issues("project = PROJ")

    assert len(issues) == 2
    assert issues[0]["key"] == "PROJ-1"
    assert issues[1]["key"] == "PROJ-2"
    assert issues[0]["names"]["summary"] == "Summary"
    assert issues[0]["schema"]["summary"]["type"] == "string"
