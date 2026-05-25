from pathlib import Path
from j2m_export.utils import get_combined_filename

def test_get_combined_filename_basic_mode():
    output_dir = "output"
    proj_keys = ["PROJ1", "PROJ2"]
    labels = ["labelA", "labelB"]

    # 全指定
    path = get_combined_filename(output_dir, proj_keys, labels)
    assert str(path) == "output/【PROJ1 or PROJ2】 and (labelA or labelB).md"

    # プロジェクトのみ
    path = get_combined_filename(output_dir, proj_keys, [])
    assert str(path) == "output/【PROJ1 or PROJ2】 and (all).md"

    # ラベルのみ
    path = get_combined_filename(output_dir, [], labels)
    assert str(path) == "output/【all】 and (labelA or labelB).md"

def test_get_combined_filename_advanced_mode():
    output_dir = "output"
    jql = "project = PROJ AND status = Done"

    path = get_combined_filename(output_dir, [], [], jql=jql)
    assert str(path) == "output/project = PROJ AND status = Done.md"

def test_get_combined_filename_with_suffix_and_index():
    output_dir = "output"
    proj_keys = ["PROJ"]
    suffix = "_250124_120000"

    # インデックスなし（1）
    path = get_combined_filename(output_dir, proj_keys, [], suffix=suffix, index=1)
    assert str(path) == "output/【PROJ】 and (all)_250124_120000.md"

    # インデックスあり（2）
    path = get_combined_filename(output_dir, proj_keys, [], suffix=suffix, index=2)
    assert str(path) == "output/【PROJ】 and (all)_250124_120000_2.md"

def test_get_combined_filename_sanitization():
    output_dir = "output"
    # 禁止文字を含むJQL
    jql = 'project = "PROJ" / status : Done'

    path = get_combined_filename(output_dir, [], [], jql=jql)
    # " / : が削除される
    assert "PROJ" in path.name
    assert "/" not in path.name
    assert ":" not in path.name
