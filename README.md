# Jira to Markdown Exporter (J2M-Export)

Jira Data Center のチケット情報を REST API で取得し、AIナレッジ向けに Markdown へエクスポートするローカルCLIツールです。

## 特徴

- Jira Data Center v10.3.9 対応 (REST API)
- チケットの「説明」や「コメント」を Markdown に変換
- JQL による一括エクスポート対応
- 特定のチケットキー指定によるエクスポート対応
- HTTP/HTTPS Proxy (CONNECTトンネル) 対応
- 出力ファイルサイズ制限機能

## セットアップ

Python 3.8以上が必要です。

```bash
pip install -r requirements.txt
```

## 実行方法

### 1. 設定ファイルの準備

リポジトリ直下の `j2m_config_sample.yaml` を `j2m_config.yaml` にコピーし、環境に合わせて内容を編集してください。

```bash
cp j2m_config_sample.yaml j2m_config.yaml
```

`j2m_config.yaml` の例:

```yaml
base_url: "https://your-jira.com"
token: "your_bearer_token_here"
issue_keys:
  - "PROJ-1"
  - "PROJ-2"
# または JQL を使用
# jql: "project = PROJ AND status = Done"
output_dir: "output"
```

### 2. 実行

最も簡単な実行方法:

```bash
python -m j2m_export.cli
```

引数で上書きして実行:

```bash
python -m j2m_export.cli --base-url https://other-jira.com --token other_token --issue-key PROJ-123
```

## パラメータ

- `--base-url`: JiraのベースURL
- `--issue-key`: エクスポートするチケットID（複数指定可能）
- `--jql`: 対象を特定するJQLクエリ
- `--output-dir`: 出力先ディレクトリ
- `--max-mb`: 出力ファイルの最大サイズ(MB)
- `--stop-threshold-mb`: 処理を停止する閾値(MB)
- `--proxy`: プロキシURL
- `--config`: 設定ファイルパス
- `--token`: Bearerトークン

---

# Jira to Markdown Exporter (J2M-Export)

A local CLI tool to export Jira Data Center ticket information to Markdown for AI knowledge bases using the REST API.

## Features

- Supports Jira Data Center v10.3.9 (REST API)
- Converts ticket "Description" and "Comments" to Markdown
- Supports bulk export via JQL
- Supports export by specific issue keys
- HTTP/HTTPS Proxy support
- Output file size limit functionality

## Setup

Requires Python 3.8+.

```bash
pip install -r requirements.txt
```

## Usage

### 1. Prepare Configuration

Copy `j2m_config_sample.yaml` to `j2m_config.yaml` and edit it.

```bash
cp j2m_config_sample.yaml j2m_config.yaml
```

### 2. Run

```bash
python -m j2m_export.cli
```
