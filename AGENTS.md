# AGENTS.md

このファイルは、このプロジェクトに関わるエージェント（AI）向けの指示書です。

## コミュニケーション
- ユーザーとのすべてのコミュニケーション、プルリクエスト（PR）のコメントなどは、すべて日本語で行ってください。

## プロジェクト概要
- プロジェクト名: J2M-Export
- 目的: Jira Data Center v10.3.9 のチケット情報を Markdown 形式にエクスポートする。
- 参照プロジェクト: C2M-Export および G2M-Export のアーキテクチャパターンとファイル命名規則に従う。

## 開発ルールと技術仕様

### 1. 依存関係と環境構築
- ランタイム依存関係は `requirements.txt` に記載されています。
- 開発専用の依存関係（pytest など）は `requirements-dev.txt` に記載されています。
- 開発環境のセットアップは `pip install -r requirements.txt` を実行してください。
- テストの実行は `python3 -m pytest tests/` を使用してください。

### 2. 設定管理
- 設定は YAML ファイルで管理します。
- デフォルトの設定パスは `j2m_config.yaml` です。
- Jira のベース URL を読み込む際は、API コールでの一貫性を保つため `rstrip('/')` を使用して正規化してください。

### 3. Jira API と クライアント
- 認証には Bearer トークンを使用します。
- HTTP/HTTPS プロキシ経由のアクセスをサポートしています。
- チケットの説明とコメントを HTML 形式で取得し、正確に Markdown へ変換するため、Jira REST API の `expand=renderedFields` パラメータを使用してください。
- `JiraClient` には、HTTP 5xx サーバーエラーおよび HTTP 429 (Too Many Requests) に対する指数バックオフを伴う自動再試行ロジックを実装してください。

### 4. データ処理と変換
- Jira のフィールドが欠落している場合は、サマリーが空なら 'No Summary'、担当者が空なら 'Unassigned' などのデフォルト値を適切に提供し、エラーを回避してください。
- Markdown への変換には `beautifulsoup4` を使用してください。
- HTML クラスからプログラミング言語識別子（例: `code-python`）を解析し、適切なシンタックスハイライトを適用してください。
- ファイルの書き込みには `Path.write_text` を使用し、明示的に UTF-8 エンコーディングを指定してください。

### 5. コード品質
- `.pre-commit-config.yaml` で設定された pre-commit フックを使用し、`.pre-commit-ci.yml` で自動化されたコード品質管理を行ってください。
- Python, `requests`, `beautifulsoup4`, `PyYAML` を活用した実装を行ってください。
