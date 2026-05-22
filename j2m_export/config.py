import os
import yaml
import argparse
from pathlib import Path
from typing import Optional, List, Union

# Default config file location
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "j2m_config.yaml"

class Config:
    """
    Configuration management for J2M-Export.
    Supports CLI arguments, environment variables, and config files.
    """
    def __init__(self):
        self.base_url: Optional[str] = None
        self.issue_keys: List[str] = []
        self.jql: Optional[str] = None
        self.output_dir: str = "output"
        self.max_mb: float = 100.0
        self.stop_threshold_mb: float = 95.0
        self.proxy: Optional[str] = None
        self.token: Optional[str] = None

    def load(self):
        """
        Load configuration. Priority: CLI > Config File > Default.
        """
        # Parse for config file path first
        pre_parser = argparse.ArgumentParser(add_help=False)
        pre_parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG_PATH))
        pre_args, _ = pre_parser.parse_known_args()

        config_path = Path(pre_args.config)

        # 1. Load from config file (Low priority)
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        self.base_url = file_config.get("base_url", self.base_url)

                        keys = file_config.get("issue_keys")
                        if keys:
                            if isinstance(keys, list):
                                self.issue_keys = [str(k) for k in keys]
                            else:
                                self.issue_keys = [str(keys)]

                        self.jql = file_config.get("jql", self.jql)
                        self.output_dir = file_config.get("output_dir", self.output_dir)
                        self.max_mb = float(file_config.get("max_mb", self.max_mb))
                        self.stop_threshold_mb = float(file_config.get("stop_threshold_mb", self.stop_threshold_mb))
                        self.proxy = file_config.get("proxy", self.proxy)
                        self.token = file_config.get("token", self.token)
            except Exception as e:
                print(f"Warning: Failed to load config file {config_path}: {e}")

        # 2. Load from environment variables
        env_https_proxy = os.environ.get("HTTPS_PROXY")
        env_http_proxy = os.environ.get("HTTP_PROXY")
        if env_https_proxy:
            self.proxy = env_https_proxy
        elif env_http_proxy:
            self.proxy = env_http_proxy

        # 3. Load from CLI (Highest priority)
        parser = argparse.ArgumentParser(description="Jiraチケット情報をMarkdownファイルに変換するツール")
        parser.add_argument("--base-url", type=str, help="JiraのベースURL (例: https://jira.example.com)")
        parser.add_argument("--issue-key", type=str, nargs="+", help="エクスポートするチケットID（複数指定可能）")
        parser.add_argument("--jql", type=str, help="エクスポート対象を特定するJQLクエリ")
        parser.add_argument("--output-dir", type=str, help="Markdownファイルを保存するディレクトリ")
        parser.add_argument("--max-mb", type=float, help="出力ファイルの最大サイズ (MB)")
        parser.add_argument("--stop-threshold-mb", type=float, help="処理を停止する閾値 (MB)")
        parser.add_argument("--proxy", type=str, help="HTTP/HTTPS プロキシURL")
        parser.add_argument("--config", type=str, help=f"設定ファイルのパス (既定: j2m_config.yaml)")
        parser.add_argument("--token", type=str, help="JiraのBearerトークン")

        cli_args = parser.parse_args()

        if cli_args.base_url: self.base_url = cli_args.base_url
        if cli_args.issue_key: self.issue_keys = cli_args.issue_key
        if cli_args.jql: self.jql = cli_args.jql
        if cli_args.output_dir: self.output_dir = cli_args.output_dir
        if cli_args.max_mb is not None: self.max_mb = cli_args.max_mb
        if cli_args.stop_threshold_mb is not None: self.stop_threshold_mb = cli_args.stop_threshold_mb
        if cli_args.proxy: self.proxy = cli_args.proxy
        if cli_args.token: self.token = cli_args.token

    def validate(self):
        """
        Validate required settings.
        """
        if not self.base_url:
            raise ValueError("base_url is required")
        if not self.issue_keys and not self.jql:
            raise ValueError("Either issue_key or jql is required")
        if not self.token:
            raise ValueError("token is required")

        if self.base_url.endswith("/"):
            self.base_url = self.base_url[:-1]
