import requests
import time
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class JiraClient:
    """Jira Data Center REST API クライアント。

    認証、プロキシ設定、およびリトライロジックを管理する。
    """

    def __init__(self, base_url: str, token: str, proxy: Optional[str] = None):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        self.proxies = None
        if proxy:
            self.proxies = {
                "http": proxy,
                "https": proxy
            }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        if self.proxies:
            self.session.proxies.update(self.proxies)

    def _request(self, method: str, path: str, params: Optional[Dict] = None, retries: int = 3, backoff: float = 2.0) -> Dict:
        """共通リクエストハンドラ。指数バックオフを伴う再試行を行う。

        Jiraのレート制限(429)や一時的なサーバーエラー(5xx)に対応する。
        """
        url = f"{self.base_url}{path}"
        for i in range(retries):
            try:
                response = self.session.request(method, url, params=params, timeout=30)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429 or 500 <= response.status_code < 600:
                    logger.warning(f"一時的なサーバーエラーまたはレート制限が発生しました（ステータスコード: {response.status_code}）。再試行します ({i+1}/{retries})...")
                    time.sleep(backoff * (2 ** i))
                    continue
                else:
                    response.raise_for_status()
            except requests.exceptions.RequestException as e:
                if i == retries - 1:
                    raise
                logger.warning(f"リクエストに失敗しました（原因: {e}）。再試行します ({i+1}/{retries})...")
                time.sleep(backoff * (2 ** i))

        raise Exception(f"最大リトライ回数を超えたため、取得に失敗しました ({url})。ネットワーク環境やJiraの状態を確認してください。")

    def get_issue(self, issue_key: str) -> Dict:
        """指定されたチケットの詳細情報を取得する。

        Markdown変換用にHTMLコンテンツを取得するため、expand=renderedFields を使用する。
        """
        path = f"/rest/api/2/issue/{issue_key}"
        params = {"expand": "renderedFields,names,schema"}
        return self._request("GET", path, params=params)

    def search_issues(self, jql: str, limit: int = 50) -> List[Dict]:
        """JQLを使用してチケットを検索する。ページネーションを自動的に処理する。

        検索結果の各チケットには、フィールド名とスキーマのメタデータを付与する。
        """
        path = "/rest/api/2/search"
        issues = []
        start = 0
        while True:
            params = {
                "jql": jql,
                "startAt": start,
                "maxResults": limit,
                "expand": "renderedFields,names,schema"
            }
            data = self._request("GET", path, params=params)
            results = data.get("issues", [])

            # フィールド名とスキーマのメタデータを各チケットに付加し、後の整形処理で利用可能にする。
            names = data.get("names", {})
            schema = data.get("schema", {})
            for issue in results:
                if names:
                    issue["names"] = names
                if schema:
                    issue["schema"] = schema

            issues.extend(results)
            logger.info(f"チケット取得中... ({len(issues)} / {data.get('total', 0)})")

            if start + len(results) >= data.get("total", 0) or not results:
                break
            start += len(results)

        return issues
