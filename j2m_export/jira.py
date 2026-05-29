import requests
import time
import logging
from typing import Dict, List, Optional, Any, Iterator

logger = logging.getLogger(__name__)

class JiraSearchResult:
    """Jira検索結果を保持し、必要に応じてページネーションを行うクラス。

    イテレータとして振る舞い、チケットを順次取得する。
    """
    def __init__(self, client: 'JiraClient', jql: str, limit: int = 50):
        self.client = client
        self.jql = jql
        self.limit = limit
        self._total = None
        self._issues = []
        self._next_start = 0
        self._names = {}
        self._schema = {}

    def _fetch_next_page(self) -> bool:
        """次のページのチケットを取得する。"""
        data = self.client._fetch_page(self.jql, self._next_start, self.limit)
        results = data.get("issues", [])
        self._total = data.get("total", 0)
        self._names = data.get("names", {})
        self._schema = data.get("schema", {})

        for issue in results:
            if self._names:
                issue["names"] = self._names
            if self._schema:
                issue["schema"] = self._schema
            self._issues.append(issue)

        self._next_start += len(results)
        logger.info(f"チケット取得中... ({len(self._issues)} / {self._total})")
        return len(results) > 0

    def __iter__(self) -> Iterator[Dict]:
        """チケットを1件ずつ返すイテレータ。"""
        idx = 0
        while True:
            # キャッシュされているチケットを返す
            if idx < len(self._issues):
                yield self._issues[idx]
                idx += 1
                continue

            # 全件取得済みかチェック
            if self._total is not None and len(self._issues) >= self._total:
                break

            # 次のページを取得
            if not self._fetch_next_page():
                break

            # 取得したページから再開（fetch_next_page内でissuesに追加されている）
            if idx >= len(self._issues):
                break

    def __len__(self) -> int:
        """全チケット件数を取得する。未取得の場合は初回の1ページ目を取得する。"""
        if self._total is None:
            self._fetch_next_page()
        return self._total

    def __bool__(self) -> bool:
        """結果が存在するかどうかを返す。"""
        return len(self) > 0

    def __getitem__(self, index):
        """インデックスによるアクセス。

        注意: 既存のコードやテストとの互換性のために実装。
        全件取得してしまう可能性があるため、可能な限りイテレーションを推奨。
        """
        if isinstance(index, slice):
            stop = index.stop if index.stop is not None else float('inf')
            while len(self._issues) < stop:
                if not self._fetch_next_page():
                    break
                if self._total is not None and len(self._issues) >= self._total:
                    break
            return self._issues[index]
        else:
            while len(self._issues) <= index:
                if not self._fetch_next_page():
                    break
                if self._total is not None and len(self._issues) >= self._total:
                    break
            return self._issues[index]

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

    def _fetch_page(self, jql: str, start: int, limit: int) -> Dict:
        """指定されたページのチケット情報を取得する。"""
        path = "/rest/api/2/search"
        params = {
            "jql": jql,
            "startAt": start,
            "maxResults": limit,
            "expand": "renderedFields,names,schema"
        }
        return self._request("GET", path, params=params)

    def search_issues(self, jql: str, limit: int = 50) -> JiraSearchResult:
        """JQLを使用してチケットを検索する。JiraSearchResult オブジェクトを返し、遅延読み込みをサポートする。
        """
        return JiraSearchResult(self, jql, limit)
