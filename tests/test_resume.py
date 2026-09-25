import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from j2m_export.cli import (
    main,
    get_checkpoint_path,
    load_checkpoint,
    save_checkpoint,
    remove_checkpoint,
    CHECKPOINT_FILENAME
)
from j2m_export.config import Config


def test_checkpoint_helpers(tmp_path):
    """チェックポイントの保存、読み込み、削除のヘルパー関数を検証する。"""
    cp_path = get_checkpoint_path(tmp_path)
    assert cp_path == tmp_path / CHECKPOINT_FILENAME

    # 存在しない場合のロード
    assert load_checkpoint(cp_path, "project = TEST", ["TEST"], []) is None

    # チェックポイントの保存
    save_checkpoint(
        cp_path,
        jql="project = TEST",
        proj_keys=["TEST"],
        labels=[],
        suffix="_260925_120000",
        current_file_index=1,
        total_exported_bytes=1000,
        processed_keys=["TEST-1", "TEST-2"]
    )

    assert cp_path.exists()

    # 条件が一致する場合のロード
    loaded = load_checkpoint(cp_path, "project = TEST", ["TEST"], [])
    assert loaded is not None
    assert loaded["suffix"] == "_260925_120000"
    assert loaded["processed_keys"] == ["TEST-1", "TEST-2"]

    # 条件が不一致の場合のロード（JQL違い）
    assert load_checkpoint(cp_path, "project = OTHER", ["TEST"], []) is None

    # 条件が不一致の場合のロード（プロジェクト違い）
    assert load_checkpoint(cp_path, "project = TEST", ["OTHER"], []) is None

    # チェックポイントの削除
    remove_checkpoint(cp_path)
    assert not cp_path.exists()


def test_main_interruption_and_resume(tmp_path):
    """取得途中で例外が発生した際に途中経過が保存され、次回実行時に再開されることを検証する。"""
    output_dir = tmp_path / "output"

    # モック課題データ
    issue1 = {
        "key": "TEST-1",
        "fields": {"summary": "Summary 1", "description": "Desc 1"},
        "renderedFields": {},
        "names": {},
        "schema": {}
    }
    issue2 = {
        "key": "TEST-2",
        "fields": {"summary": "Summary 2", "description": "Desc 2"},
        "renderedFields": {},
        "names": {},
        "schema": {}
    }
    issue3 = {
        "key": "TEST-3",
        "fields": {"summary": "Summary 3", "description": "Desc 3"},
        "renderedFields": {},
        "names": {},
        "schema": {}
    }

    # 1回目の実行: イテレーション途中で504などの例外をシミュレート
    class FaultyIssuesList:
        def __init__(self):
            """中断までに取得できるチケットを用意する。"""
            self.issues = [issue1, issue2]

        def __len__(self):
            """取得予定のチケット総数を返す。"""
            return 3

        def __iter__(self):
            """2件を返した後に通信障害を再現する。"""
            yield issue1
            yield issue2
            raise Exception("504 Gateway Timeout (Simulated)")

    test_args = [
        "cli.py",
        "--base-url", "https://jira.example.com",
        "--token", "dummy_token",
        "--proj-keys", "TEST",
        "--output-dir", str(output_dir)
    ]

    with patch.object(sys, "argv", test_args):
        with patch("j2m_export.cli.JiraClient") as MockJiraClient:
            mock_client = MagicMock()
            MockJiraClient.return_value = mock_client
            mock_client.search_issues.return_value = FaultyIssuesList()

            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code == 1

    # チェックポイントファイルと出力ファイルが存在することを確認
    cp_path = output_dir / CHECKPOINT_FILENAME
    assert cp_path.exists()

    state = json.loads(cp_path.read_text(encoding="utf-8"))
    assert state["processed_keys"] == ["TEST-1", "TEST-2"]

    # 出力ファイルの内容を確認（TEST-1, TEST-2 が書かれている）
    out_files = list(output_dir.glob("*.md"))
    assert len(out_files) == 1
    content_run1 = out_files[0].read_text(encoding="utf-8")
    assert "TEST-1" in content_run1
    assert "TEST-2" in content_run1
    assert "TEST-3" not in content_run1

    # 2回目の実行: 正常に全件(TEST-1, TEST-2, TEST-3)取得できる環境で再開
    class SuccessfulIssuesList:
        def __init__(self):
            """再開時に取得可能なチケットをすべて用意する。"""
            self.issues = [issue1, issue2, issue3]

        def __len__(self):
            """取得可能なチケット総数を返す。"""
            return 3

        def __iter__(self):
            """再開時に重複分も含む全チケットを返す。"""
            for issue in self.issues:
                yield issue

    with patch.object(sys, "argv", test_args):
        with patch("j2m_export.cli.JiraClient") as MockJiraClient:
            mock_client = MagicMock()
            MockJiraClient.return_value = mock_client
            mock_client.search_issues.return_value = SuccessfulIssuesList()

            # 2回目はエラーにならず正常終了する
            main()

    # チェックポイントファイルが削除されていることを確認
    assert not cp_path.exists()

    # 出力ファイルに TEST-3 が追記されていることを確認
    content_run2 = out_files[0].read_text(encoding="utf-8")
    assert "TEST-1" in content_run2
    assert "TEST-2" in content_run2
    assert "TEST-3" in content_run2


def test_main_no_resume_option(tmp_path):
    """--no-resume オプション指定時に既存のチェックポイントが無視されることを検証する。"""
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    cp_path = output_dir / CHECKPOINT_FILENAME
    save_checkpoint(
        cp_path,
        jql=None,
        proj_keys=["TEST"],
        labels=[],
        suffix="_old_suffix",
        current_file_index=1,
        total_exported_bytes=500,
        processed_keys=["TEST-1"]
    )

    issue1 = {
        "key": "TEST-1",
        "fields": {"summary": "Summary 1"},
        "renderedFields": {},
        "names": {},
        "schema": {}
    }

    test_args = [
        "cli.py",
        "--base-url", "https://jira.example.com",
        "--token", "dummy_token",
        "--proj-keys", "TEST",
        "--output-dir", str(output_dir),
        "--no-resume"
    ]

    class MockIssuesList:
        def __len__(self):
            """新規実行で取得するチケット数を返す。"""
            return 1

        def __iter__(self):
            """再開を無効にした実行でチケットを返す。"""
            yield issue1

    with patch.object(sys, "argv", test_args):
        with patch("j2m_export.cli.JiraClient") as MockJiraClient:
            mock_client = MagicMock()
            MockJiraClient.return_value = mock_client
            mock_client.search_issues.return_value = MockIssuesList()

            main()

    # チェックポイントが削除（または新規で完了）されていること
    assert not cp_path.exists()
