import os
import sys
import json
import logging
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from .config import Config
from .jira import JiraClient
from .converter import MarkdownConverter
from .utils import get_combined_filename, bytes_to_mb, is_within_size_limit

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

            # レンダリング済みのコメント本文の取得を試みる
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
        logger.error(f"設定の読み込みに失敗しました（現象）。j2m_config.yamlの内容や引数を確認してください（対処方法）。詳細: {e}（原因）")
        sys.exit(1)

    client = JiraClient(config.base_url, config.token, config.proxy)
    converter = MarkdownConverter(config.base_url)

    # 除外フィールド設定の検証
    for eid in config.exclude_fields:
        if eid in NON_IGNORABLE_IDS:
            logger.warning(f"フィールド '{eid}' は必須項目のため、除外設定を無視してエクスポートします。")

    issues_to_process = []

    # 1. Advancedモード（JQL指定あり）: JQLを最優先し、他の指定は無視する
    if config.jql:
        logger.info(f"Advancedモード: JQLクエリによるチケット取得を開始します（JQL: {config.jql}）")
        try:
            issues_to_process = client.search_issues(config.jql)
        except Exception as e:
            logger.error(f"JQLでのチケット検索に失敗しました（現象）。JQLクエリが正しいか確認してください（対処方法）。詳細: {e}（原因）")

    # 2. Basicモード（JQL指定なし）: プロジェクトキーまたはラベルによる簡易指定
    else:
        basic_jql_parts = []
        if config.proj_keys:
            escaped_projs = [f'"{p.replace("\"", "\\\"")}"' for p in config.proj_keys]
            basic_jql_parts.append(f"project IN ({', '.join(escaped_projs)})")

        if config.labels:
            escaped_labels = [f'"{l.replace("\"", "\\\"")}"' for l in config.labels]
            basic_jql_parts.append(f"labels IN ({', '.join(escaped_labels)})")

        if basic_jql_parts:
            basic_jql = " AND ".join(basic_jql_parts)
            logger.info(f"Basicモード: チケット取得を開始します（JQL: {basic_jql}）")
            try:
                issues_to_process = client.search_issues(basic_jql)
            except Exception as e:
                logger.error(f"チケットの取得に失敗しました（現象）。指定したプロジェクトやラベルが正しいか確認してください（対処方法）。詳細: {e}（原因）")

    if not issues_to_process:
        logger.warning("処理対象のチケットが見つかりませんでした。")
        return

    # Suffixの生成（非上書き時のみ使用）
    suffix = ""
    if not config.overwrite:
        now = datetime.datetime.now()
        suffix = now.strftime("_%y%m%d_%H%M%S")

    # 書き込み可否の事前チェック
    output_dir = Path(config.output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"出力ディレクトリの作成に失敗しました（現象）。ディレクトリの権限を確認してください（対処方法）。詳細: {e}（原因）")
        sys.exit(1)

    # ディレクトリ自体の書き込み権限チェック
    if not os.access(output_dir, os.W_OK):
        logger.error(f"出力ディレクトリへの書き込み権限がありません（現象）。ディレクトリの権限を確認してください（対処方法）。詳細: {output_dir}（原因）")
        sys.exit(1)

    logger.info(f"合計 {len(issues_to_process)} 件のチケットを処理対象として決定しました。エクスポートを開始します。")

    current_file_index = 1
    current_file_content = ""
    current_file_size = 0
    total_exported_bytes = 0
    issue_count = 0
    total_to_process = len(issues_to_process)

    def write_current_buffer():
        nonlocal current_file_content, current_file_size, current_file_index
        if not current_file_content:
            return

        output_path = get_combined_filename(
            config.output_dir,
            config.proj_keys,
            config.labels,
            config.jql,
            suffix,
            current_file_index
        )

        # 上書き禁止時に既にファイルが存在する場合
        if not config.overwrite and output_path.exists():
            logger.error(f"出力ファイルが既に存在します（現象）。上書きを許可するか、既存のファイルを移動してください（対処方法）。詳細: {output_path}（原因）")
            sys.exit(1)

        # 既存ファイルがある場合の上書き権限チェック
        if output_path.exists() and not os.access(output_path, os.W_OK):
            logger.error(f"既存ファイルへの書き込み権限がありません（現象）。ファイルがロックされていないか確認してください（対処方法）。詳細: {output_path}（原因）")
            sys.exit(1)

        try:
            output_path.write_text(current_file_content, encoding="utf-8")
            logger.info(f"ファイルを保存しました: {output_path} ({bytes_to_mb(current_file_size):.2f}MB)")
            current_file_content = ""
            current_file_size = 0
            current_file_index += 1
        except Exception as e:
            logger.error(f"ファイル {output_path} の出力中にエラーが発生しました（現象）。ディスク容量や権限を確認してください（対処方法）。詳細: {e}（原因）")
            sys.exit(1)

    for i, issue in enumerate(issues_to_process, 1):
        key = issue['key']

        # チケット情報の変換
        try:
            issue_md = format_issue_md(issue, converter, config.base_url, config.exclude_fields)
        except Exception as e:
            logger.error(f"チケット {key} の変換処理中にエラーが発生しました（現象）。Jiraからの取得データを確認してください（対処方法）。詳細: {e}（原因）")
            continue

        md_bytes = len(issue_md.encode('utf-8'))

        # 全体サイズ制限（stop_threshold_mb）のチェック
        if not is_within_size_limit(total_exported_bytes + md_bytes, config.stop_threshold_mb):
            logger.warning(f"実行全体の停止閾値 ({config.stop_threshold_mb}MB) に達する見込みのため、エクスポートを中断します。")
            break

        # 1ファイルあたりのサイズ制限（max_mb）のチェック
        # チケットがファイルを跨がないよう、追加前にサイズを確認する
        if current_file_content and not is_within_size_limit(current_file_size + md_bytes, config.max_mb):
            write_current_buffer()

        current_file_content += issue_md
        current_file_size += md_bytes
        total_exported_bytes += md_bytes
        issue_count += 1
        logger.info(f"[{i}/{total_to_process}] 処理中: {key}")

    # 残りのバッファを書き出す
    write_current_buffer()

    logger.info("-" * 50)
    logger.info(f"{issue_count} 件のチケットを正常にエクスポートしました。")
    logger.info(f"合計サイズ: {bytes_to_mb(total_exported_bytes):.2f}MB")

if __name__ == "__main__":
    main()
