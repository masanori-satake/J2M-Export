import pytest
from unittest.mock import MagicMock, patch
from j2m_export.jira import JiraClient, JiraSearchResult

@patch("requests.Session.request")
def test_jira_search_result_lazy_loading(mock_request):
    # 1ページ目 (2件)
    page1 = {
        "issues": [{"key": "PROJ-1"}, {"key": "PROJ-2"}],
        "total": 3,
        "names": {"summary": "Summary"},
        "schema": {"summary": {"type": "string"}}
    }
    # 2ページ目 (1件)
    page2 = {
        "issues": [{"key": "PROJ-3"}],
        "total": 3,
        "names": {"summary": "Summary"},
        "schema": {"summary": {"type": "string"}}
    }

    mock_request.side_effect = [
        MagicMock(status_code=200, json=lambda: page1),
        MagicMock(status_code=200, json=lambda: page2)
    ]

    client = JiraClient("https://jira.example.com", "fake_token")
    # limit=2にして、2ページに分かれるようにする
    search_result = client.search_issues("project = PROJ", limit=2)

    # まだリクエストは行われていないはず
    assert mock_request.call_count == 0

    # イテレーション開始
    issues_iter = iter(search_result)

    # 1件目取得 -> 1ページ目のリクエストが発生
    issue1 = next(issues_iter)
    assert issue1["key"] == "PROJ-1"
    assert mock_request.call_count == 1

    # 2件目取得 -> まだ1ページ目のキャッシュがあるはず
    issue2 = next(issues_iter)
    assert issue2["key"] == "PROJ-2"
    assert mock_request.call_count == 1

    # 3件目取得 -> 2ページ目のリクエストが発生
    issue3 = next(issues_iter)
    assert issue3["key"] == "PROJ-3"
    assert mock_request.call_count == 2

    # 終了
    with pytest.raises(StopIteration):
        next(issues_iter)

@patch("requests.Session.request")
def test_jira_search_result_len(mock_request):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "issues": [{"key": "PROJ-1"}],
        "total": 10,
        "names": {},
        "schema": {}
    }
    mock_request.return_value = mock_response

    client = JiraClient("https://jira.example.com", "fake_token")
    search_result = client.search_issues("project = PROJ")

    # len() を呼ぶとリクエストが発生する
    assert len(search_result) == 10
    assert mock_request.call_count == 1

@patch("requests.Session.request")
def test_jira_search_result_getitem(mock_request):
    page1 = {
        "issues": [{"key": "PROJ-1"}, {"key": "PROJ-2"}],
        "total": 3,
        "names": {},
        "schema": {}
    }
    page2 = {
        "issues": [{"key": "PROJ-3"}],
        "total": 3,
        "names": {},
        "schema": {}
    }
    mock_request.side_effect = [
        MagicMock(status_code=200, json=lambda: page1),
        MagicMock(status_code=200, json=lambda: page2)
    ]

    client = JiraClient("https://jira.example.com", "fake_token")
    search_result = client.search_issues("project = PROJ", limit=2)

    # インデックスアクセス
    assert search_result[2]["key"] == "PROJ-3"
    assert mock_request.call_count == 2
