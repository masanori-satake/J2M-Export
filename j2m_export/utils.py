import re
from pathlib import Path

def sanitize_filename(name: str) -> str:
    """文字列をファイル名として使用可能な形式にサニタイズする。

    OS(Windows/Linux/Mac)の制約に基づき不適切な文字を削除し、長さを制限する。
    """
    # ファイル名に使用できない文字を削除
    name = re.sub(r'[\\/*?:"<>|]', '', name)
    # 前後の空白を削除し、長さを100文字以内に制限する
    return name.strip()[:100]

def get_unique_filename(output_dir: str, project_key: str, summary: str, issue_key: str, suffix: str = "") -> Path:
    """エクスポート用のファイル名を生成する。

    命名規則: 【プロジェクトキー】 サマリー (チケットキー)<suffix>.md
    """
    base_name = f"【{project_key}】 {summary} ({issue_key})"
    sanitized_name = sanitize_filename(base_name)

    return Path(output_dir) / f"{sanitized_name}{suffix}.md"

def bytes_to_mb(bytes_count: int) -> float:
    return bytes_count / (1024 * 1024)

def is_within_size_limit(current_bytes: int, threshold_mb: float) -> bool:
    return bytes_to_mb(current_bytes) <= threshold_mb
