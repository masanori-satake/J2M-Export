import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from .config import Config
from .jira import JiraClient
from .converter import MarkdownConverter
from .utils import get_unique_filename, bytes_to_mb, is_within_size_limit

logger = logging.getLogger(__name__)

# エクスポートから除外できない必須フィールドのリスト。
NON_IGNORABLE_IDS = ['summary', 'project', 'status', 'assignee', 'created', 'key']

def format_field_value(value: Any) -> str:
    """Jiraのフィールド値を型に応じて文字列に整形する。

    辞書型の場合は表示名、リスト型の場合はカンマ区切りの文字列を優先する。
    """
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        # オブジェクトの場合は表示名を優先し、なければ内部名、それもなければJSON文字列を返す。
        return value.get('displayName') or value.get('name') or json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        # リストの場合は各要素を整形し、カンマ区切りで結合する。
        formatted_list = []
        for item in value:
            if isinstance(item, dict):
                val = item.get('displayName') or item.get('name')
                if val:
                    formatted_list.append(str(val))
                else:
                    formatted_list.append(json.dumps(item, ensure_ascii=False))
            else:
                formatted_list.append(str(item))
        return ", ".join(formatted_list)

    return json.dumps(value, ensure_ascii=False)

def format_issue_md(issue: Dict, converter: MarkdownConverter, base_url: str, exclude_fields: Optional[List[str]] = None) -> str:
    """単一のチケットをMarkdown形式の文字列に変換する。
    """
    exclude_fields = exclude_fields or []
    fields = issue.get('fields') or {}
    rendered = issue.get('renderedFields') or {}
    names = issue.get('names') or {}
    schema = issue.get('schema') or {}

    key = issue.get('key')
    summary = fields.get('summary') or 'No Summary'
    url = f"{base_url}/browse/{key}"

    md = f"\n---\n# {summary}\n"
    md += f"- **Key**: {key}\n"

    # 整形時に優先的に表示する標準フィールドの順序。
    standard_order = ['project', 'status', 'priority', 'assignee', 'reporter', 'created', 'updated', 'duedate', 'resolution']
    processed_fields = {'summary', 'description', 'comment', 'worklog', 'attachment'}

    # 1. 必須および主要な標準フィールドの出力
    for fid in standard_order:
        if fid in processed_fields: continue
        if fid in exclude_fields and fid not in NON_IGNORABLE_IDS:
            continue

        val = fields.get(fid)
        if val is not None:
            label = names.get(fid, fid.capitalize())
            md += f"- **{label}**: {format_field_value(val)}\n"
            processed_fields.add(fid)

    # 2. その他の標準フィールドを網羅的に出力
    for fid, val in fields.items():
        if fid in processed_fields: continue
        if fid in exclude_fields and fid not in NON_IGNORABLE_IDS:
            continue

        # カスタムフィールドはAIナレッジとしては不要なことが多いため、現在はスキップする仕様。
        f_schema = schema.get(fid, {})
        if f_schema.get('custom'):
            continue

        if val is not None:
            label = names.get(fid, fid.capitalize())
            md += f"- **{label}**: {format_field_value(val)}\n"
            processed_fields.add(fid)

    md += f"- **URL**: {url}\n\n"

    md += "## Description\n"
    description = rendered.get('description', fields.get('description', ''))
    md += converter.convert(description)

    # コメントの処理
    comments_data = fields.get('comment', {}).get('comments', [])
    if comments_data:
        md += "\n## Comments\n"
        # レンダリング済みコメントは renderedFields の入れ子構造の中に格納されている。
        rendered_comments = rendered.get('comment', {}).get('comments', [])

        for i, comment in enumerate(comments_data):
            author = comment.get('author', {}).get('displayName', 'Anonymous')
            created_at = comment.get('created')

            # Try to get rendered comment body
            body_html = ""
            if i < len(rendered_comments):
                body_html = rendered_comments[i].get('body')

            body = body_html if body_html else comment.get('body', '')

            md += f"\n### Comment by {author} ({created_at})\n"
            md += converter.convert(body)

    return md

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    config = Config()
    try:
        config.load()
        config.validate()
    except Exception as e:
        logger.error(f"設定の読み込みに失敗しました。j2m_config.yamlの内容や引数を確認してください。詳細: {e}")
        sys.exit(1)

    client = JiraClient(config.base_url, config.token, config.proxy)
    converter = MarkdownConverter(config.base_url)

    # 除外フィールド設定の検証
    for eid in config.exclude_fields:
        if eid in NON_IGNORABLE_IDS:
            logger.warning(f"フィールド '{eid}' は必須項目のため、除外設定を無視してエクスポートします。")

    issues_to_process = []

    # 1. 指定されたチケットキーからチケットを収集
    if config.issue_keys:
        for key in config.issue_keys:
            try:
                issue = client.get_issue(key)
                issues_to_process.append(issue)
            except Exception as e:
                logger.error(f"チケット {key} の取得に失敗しました。キーが正しいか、権限があるか確認してください。詳細: {e}")

    # 2. JQLクエリに合致するチケットを収集
    if config.jql:
        try:
            jql_issues = client.search_issues(config.jql)
            # チケットキーで既に取得済みの場合は重複を避ける。
            existing_keys = {i['key'] for i in issues_to_process}
            for issue in jql_issues:
                if issue['key'] not in existing_keys:
                    issues_to_process.append(issue)
        except Exception as e:
            logger.error(f"JQLでのチケット検索に失敗しました。JQLクエリが正しいか確認してください。詳細: {e}")

    # 3. 指定されたキーやJQLで見つからず、ラベルが指定されている場合は、ラベルで直接取得
    if not issues_to_process and config.labels:
        try:
            # ラベル用のJQLを生成（ダブルクォートをエスケープ）
            escaped_labels = [f'"{l.replace("\"", "\\\"")}"' for l in config.labels]
            label_jql = f"labels IN ({', '.join(escaped_labels)})"
            logger.info(f"ラベルによるチケット取得を開始します（JQL: {label_jql}）")
            issues_to_process = client.search_issues(label_jql)
        except Exception as e:
            logger.error(f"ラベルによるチケット取得に失敗しました（現象）。JQLクエリを確認してください（対処方法）。詳細: {e}（原因）")

    if not issues_to_process:
        logger.warning("処理対象のチケットが見つかりませんでした。")
        return

    # 4. ラベルが指定されている場合は、取得したチケットをラベルでフィルタリング（後続フィルタリング）
    if config.labels:
        filtered_issues = []
        label_set = {l.lower() for l in config.labels}
        for issue in issues_to_process:
            issue_labels = [l.lower() for l in issue.get('fields', {}).get('labels', [])]
            # Jiraの挙動（ケースインセンシティブ）に合わせ、大文字小文字を区別せずにラベルをチェック
            if any(label in label_set for label in issue_labels):
                filtered_issues.append(issue)

        issues_to_process = filtered_issues
        logger.info(f"ラベルに合致する {len(issues_to_process)} 件のチケットを抽出しました。対象ラベル: {', '.join(config.labels)}")

    if not issues_to_process:
        logger.warning("ラベルに合致するチケットが見つかりませんでした。")
        return

    # 収集したチケットの処理と保存
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    issue_count = 0

    for issue in issues_to_process:
        key = issue['key']
        summary = issue['fields'].get('summary', 'No Summary')
        project_key = issue['fields'].get('project', {}).get('key', 'UNKNOWN')

        try:
            issue_md = format_issue_md(issue, converter, config.base_url, config.exclude_fields)
            md_bytes = len(issue_md.encode('utf-8'))

            if not is_within_size_limit(total_bytes + md_bytes, config.stop_threshold_mb):
                logger.warning(f"停止閾値 ({config.stop_threshold_mb}MB) に達したため、エクスポートを中断します。")
                break

            output_path = get_unique_filename(config.output_dir, project_key, summary, key)

            output_path.write_text(issue_md, encoding="utf-8")

            total_bytes += md_bytes
            issue_count += 1
            logger.info(f"エクスポート完了: {key} ({summary})")

        except Exception as e:
            logger.exception(f"チケット {key} の処理中にエラーが発生しました。変換処理またはファイル書き込みを確認してください。詳細: {e}")

    logger.info("-" * 50)
    logger.info(f"{issue_count} 件のチケットを正常にエクスポートしました。")
    logger.info(f"合計サイズ: {bytes_to_mb(total_bytes):.2f}MB")

if __name__ == "__main__":
    main()
