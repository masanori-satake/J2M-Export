from pathlib import Path
from j2m_export.utils import get_unique_filename

def test_get_unique_filename_new_format():
    # 期待される形式: 【プロジェクトキー】 サマリー (チケットキー)<suffix>.md
    output_dir = "output"
    project_key = "PROJ"
    summary = "テストサマリー"
    issue_key = "PROJ-123"

    # Suffixなし
    path = get_unique_filename(output_dir, project_key, summary, issue_key)
    assert str(path) == "output/【PROJ】 テストサマリー (PROJ-123).md"

    # Suffixあり
    suffix = "_260503_160502"
    path = get_unique_filename(output_dir, project_key, summary, issue_key, suffix=suffix)
    assert str(path) == "output/【PROJ】 テストサマリー (PROJ-123)_260503_160502.md"

def test_get_unique_filename_sanitization():
    output_dir = "output"
    project_key = "PROJ"
    summary = "サマリー / 禁止文字 : * ?"
    issue_key = "PROJ-1"

    path = get_unique_filename(output_dir, project_key, summary, issue_key)
    # / : * ? が削除される
    # "サマリー / 禁止文字 : * ?" -> "サマリー  禁止文字   "
    # base_name = "【PROJ】 サマリー  禁止文字    (PROJ-1)"
    assert str(path) == "output/【PROJ】 サマリー  禁止文字    (PROJ-1).md"

def test_get_unique_filename_collision_due_to_truncation():
    # 非常に長いサマリーにより、チケットキーの部分が削られるケースのシミュレーション
    output_dir = "output"
    project_key = "PROJ"
    # 100文字制限
    # "【PROJ】 " (7文字)
    # 残り93文字。サマリーが100文字あると、(PROJ-1) の部分は削られる
    long_summary = "A" * 100
    issue_key_1 = "PROJ-1"
    issue_key_2 = "PROJ-2"

    path1 = get_unique_filename(output_dir, project_key, long_summary, issue_key_1)
    path2 = get_unique_filename(output_dir, project_key, long_summary, issue_key_2)

    # サマリーが長すぎて (PROJ-1) や (PROJ-2) が削られる場合、同じファイル名になる
    assert path1 == path2
    assert len(path1.stem) == 100
