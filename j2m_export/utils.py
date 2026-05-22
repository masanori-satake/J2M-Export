import re
from pathlib import Path

def sanitize_filename(name: str) -> str:
    """
    Sanitize string for use as a filename (Windows/Linux/Mac compatible).
    """
    # Remove characters that are not allowed in filenames
    name = re.sub(r'[\\/*?:"<>|]', '', name)
    # Replace spaces with underscores or just keep them? Reference uses spaces.
    # We'll keep spaces but trim and limit length.
    return name.strip()[:100]

def get_unique_filename(output_dir: str, project_key: str, summary: str, issue_key: str) -> Path:
    """
    Generate a unique filename for the export.
    """
    base_name = f"【{project_key}】 {summary}"
    sanitized_name = sanitize_filename(base_name)

    path = Path(output_dir) / f"{sanitized_name}.md"
    if path.exists():
        # Append issue key if file exists
        path = Path(output_dir) / f"{sanitized_name} ({issue_key}).md"

    return path

def bytes_to_mb(bytes_count: int) -> float:
    return bytes_count / (1024 * 1024)

def is_within_size_limit(current_bytes: int, threshold_mb: float) -> bool:
    return bytes_to_mb(current_bytes) <= threshold_mb
