import os
import yaml
import argparse
import logging
from pathlib import Path
from typing import Optional, List, Union

logger = logging.getLogger(__name__)

# デフォルトの設定ファイルパス。リポジトリのルートディレクトリに配置される。
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "j2m_config.yaml"

class Config:
    """J2M-Exportの設定管理クラス。

    CLI引数、環境変数、およびYAML設定ファイルからの設定読み込みをサポートする。
    """

    def __init__(self):
        self.base_url: Optional[str] = None
        self.issue_keys: List[str] = []
        self.labels: List[str] = []
        self.jql: Optional[str] = None
        self.output_dir: str = "output"
        self.max_mb: float = 100.0
        self.stop_threshold_mb: float = 95.0
        self.exclude_fields: List[str] = []
        self.proxy: Optional[str] = None
        self.token: Optional[str] = None

    def load(self):
        """設定をロードする。

        優先順位は CLI引数 > 設定ファイル > デフォルト値 の順。
        """
        # 最初に設定ファイルのパスを特定するために引数をパースする。
        pre_parser = argparse.ArgumentParser(add_help=False)
        pre_parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG_PATH))
        pre_args, _ = pre_parser.parse_known_args()

        config_path = Path(pre_args.config)

        # 1. 設定ファイルからの読み込み（低優先度）
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        self.base_url = file_config.get("base_url", self.base_url)

                        keys = file_config.get("issue_keys")
                        if keys:
                            if isinstance(keys, list):
                                self.issue_keys = [str(k).strip() for k in keys]
                            else:
                                logger.warning("issue_keys はリスト形式で指定してください。")

                        lbls = file_config.get("labels")
                        if lbls:
                            if isinstance(lbls, list):
                                self.labels = [str(l).strip() for l in lbls]
                            else:
                                logger.warning("labels はリスト形式で指定してください。")

                        self.jql = file_config.get("jql", self.jql)
                        self.output_dir = file_config.get("output_dir", self.output_dir)
                        self.max_mb = float(file_config.get("max_mb", self.max_mb))
                        self.stop_threshold_mb = float(file_config.get("stop_threshold_mb", self.stop_threshold_mb))

                        exclude = file_config.get("exclude_fields")
                        if exclude:
                            if isinstance(exclude, list):
                                self.exclude_fields = [str(e).strip() for e in exclude]
                            else:
                                logger.warning("exclude_fields はリスト形式で指定してください。")

                        self.proxy = file_config.get("proxy", self.proxy)
                        self.token = file_config.get("token", self.token)
            except Exception as e:
                logger.warning(f"設定ファイル {config_path} の読み込みに失敗しました。ファイル形式が正しいか確認してください。詳細: {e}")

        # 2. 環境変数からの読み込み。標準的なプロキシ環境変数をチェックする。
        env_https_proxy = os.environ.get("HTTPS_PROXY")
        env_http_proxy = os.environ.get("HTTP_PROXY")
        if env_https_proxy:
            self.proxy = env_https_proxy
        elif env_http_proxy:
            self.proxy = env_http_proxy

        # 3. CLI引数からの読み込み（最高優先度）
        parser = argparse.ArgumentParser(description="Jiraチケット情報をMarkdownファイルに変換するツール")
        parser.add_argument("--base-url", type=str, help="JiraのベースURL (例: https://jira.example.com)")
        parser.add_argument("--issue-keys", type=str, nargs="+", help="エクスポートするチケットID（複数指定可能）")
        parser.add_argument("--labels", type=str, nargs="+", help="対象とするラベル（複数指定可能。いずれかに合致するものを抽出）")
        parser.add_argument("--jql", type=str, help="エクスポート対象を特定するJQLクエリ")
        parser.add_argument("--output-dir", type=str, help="Markdownファイルを保存するディレクトリ")
        parser.add_argument("--max-mb", type=float, help="出力ファイルの最大サイズ (MB)")
        parser.add_argument("--stop-threshold-mb", type=float, help="処理を停止する閾値 (MB)")
        parser.add_argument("--exclude-fields", type=str, nargs="+", help="除外するフィールドの内部ID（複数指定可能）")
        parser.add_argument("--proxy", type=str, help="HTTP/HTTPS プロキシURL")
        parser.add_argument("--config", type=str, help=f"設定ファイルのパス (既定: j2m_config.yaml)")
        parser.add_argument("--token", type=str, help="JiraのBearerトークン")

        cli_args = parser.parse_args()

        if cli_args.base_url: self.base_url = cli_args.base_url

        # チケット選択引数（jql, issue_keys, labels）が一つでもCLIで指定されたら、設定ファイルの設定をすべて無視する。
        if cli_args.issue_keys or cli_args.labels or cli_args.jql:
            self.issue_keys = [k.strip() for k in cli_args.issue_keys] if cli_args.issue_keys else []
            self.labels = [l.strip() for l in cli_args.labels] if cli_args.labels else []
            self.jql = cli_args.jql

        if cli_args.output_dir: self.output_dir = cli_args.output_dir
        if cli_args.max_mb is not None: self.max_mb = cli_args.max_mb
        if cli_args.stop_threshold_mb is not None: self.stop_threshold_mb = cli_args.stop_threshold_mb
        if cli_args.exclude_fields:
            self.exclude_fields = [f.strip() for f in cli_args.exclude_fields]
        if cli_args.proxy: self.proxy = cli_args.proxy
        if cli_args.token: self.token = cli_args.token

    def validate(self):
        """必須設定項目のバリデーションを行う。

        Jira APIとの通信に必要な最小限の設定を確認する。
        """
        if not self.base_url:
            raise ValueError("base_url（JiraのベースURL）が設定されていません。")
        if not self.issue_keys and not self.jql and not self.labels:
            raise ValueError("issue_key, jql, label のいずれか一つは必須です。")
        if not self.token:
            raise ValueError("token（Bearerトークン）が設定されていません。")

        self.base_url = self.base_url.rstrip("/")
