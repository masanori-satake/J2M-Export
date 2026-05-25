import re
from pathlib import Path

def sanitize_filename(name: str) -> str:
    """文字列をファイル名として使用可能な形式にサニタイズする。

    OS(Windows/Linux/Mac)の制約に基づき不適切な文字を削除・置換し、長さを制限する。
    """
    # ファイル名に使用できない文字を削除
    name = re.sub(r'[\\/*?:"<>|]', '', name)
    # 改行やタブをスペースに置換
    name = re.sub(r'[\r\n\t]+', ' ', name)
    # 前後の空白を削除し、長さを150文字以内に制限する（結合ファイル名は長くなる可能性があるため少し拡張）
    return name.strip()[:150]

def get_combined_filename(output_dir: str, proj_keys: list, labels: list, jql: str = None, suffix: str = "", index: int = 1) -> Path:
    """結合エクスポート用のファイル名を生成する。

    Basicモード命名規則: 【proj1 or proj2】 and (labelA or labelB)
    Advancedモード命名規則: サニタイズされたJQL
    """
    if jql:
        base_name = jql
    else:
        p_part = " or ".join(proj_keys) if proj_keys else "all"
        l_part = " or ".join(labels) if labels else "all"
        base_name = f"【{p_part}】 and ({l_part})"

    sanitized_name = sanitize_filename(base_name)

    # インデックス（分割番号）の付与
    index_suffix = f"_{index}" if index > 1 else ""

    return Path(output_dir) / f"{sanitized_name}{suffix}{index_suffix}.md"

def bytes_to_mb(bytes_count: int) -> float:
    return bytes_count / (1024 * 1024)

def is_within_size_limit(current_bytes: int, threshold_mb: float) -> bool:
    return bytes_to_mb(current_bytes) <= threshold_mb
