import requests
import time
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class JiraClient:
    """
    Jira Data Center REST API client.
    Handles authentication, proxy, and retries.
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
        """
        Common request handler with retry logic.
        """
        url = f"{self.base_url}{path}"
        for i in range(retries):
            try:
                response = self.session.request(method, url, params=params, timeout=30)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429 or 500 <= response.status_code < 600:
                    logger.warning(f"Request error {response.status_code} for {url}. Retrying ({i+1}/{retries})...")
                    time.sleep(backoff * (2 ** i))
                    continue
                else:
                    response.raise_for_status()
            except requests.exceptions.RequestException as e:
                if i == retries - 1:
                    raise
                logger.warning(f"Request failed: {e}. Retrying ({i+1}/{retries})...")
                time.sleep(backoff * (2 ** i))

        raise Exception(f"Failed to fetch {url} after {retries} retries")

    def get_issue(self, issue_key: str) -> Dict:
        """
        Fetch issue details. Use expand=renderedFields to get HTML content.
        """
        path = f"/rest/api/2/issue/{issue_key}"
        params = {"expand": "renderedFields,names,schema"}
        return self._request("GET", path, params=params)

    def search_issues(self, jql: str, limit: int = 50) -> List[Dict]:
        """
        Search issues using JQL. Handles pagination.
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

            # Attach names and schema metadata to each issue
            names = data.get("names", {})
            schema = data.get("schema", {})
            for issue in results:
                if names:
                    issue["names"] = names
                if schema:
                    issue["schema"] = schema

            issues.extend(results)

            if start + len(results) >= data.get("total", 0) or not results:
                break
            start += len(results)

        return issues
