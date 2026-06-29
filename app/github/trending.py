from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List
import pytz
import requests


GITHUB_API = "https://api.github.com"


def _headers(token: str | None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "daily-trending-bot",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@dataclass
class TrendingSearchOptions:
    timezone: str
    max_repos: int
    trending_days: int = 1
    trending_language: str | None = None
    trending_topics: list[str] | None = None
    min_stars: int = 0
    exclude_forks: bool = True
    exclude_no_description: bool = False
    exclude_empty_readme: bool = False


@dataclass
class RepoBrief:
    full_name: str
    name: str
    html_url: str
    description: str | None
    stargazers_count: int
    fork: bool = False


def build_search_query(options: TrendingSearchOptions) -> str:
    """組合 GitHub Search API 查詢字串，保留未來擴充空間。"""
    tz = pytz.timezone(options.timezone or "UTC")
    since_date = (datetime.now(tz) - timedelta(days=max(1, options.trending_days))).date().isoformat()

    parts = [f"created:>{since_date}"]

    if options.min_stars > 0:
        parts.append(f"stars:>={options.min_stars}")

    if options.trending_language:
        parts.append(f"language:{options.trending_language}")

    for topic in options.trending_topics or []:
        parts.append(f"topic:{topic}")

    if options.exclude_forks:
        parts.append("fork:false")

    return " ".join(parts)


def _passes_filters(item: dict, options: TrendingSearchOptions) -> bool:
    if options.exclude_forks and item.get("fork"):
        return False

    description = (item.get("description") or "").strip()
    if options.exclude_no_description and not description:
        return False

    return True


def search_trending_repos(token: str | None, options: TrendingSearchOptions) -> List[RepoBrief]:
    query = build_search_query(options)
    print(f"[INFO] GitHub search query: {query}")

    url = f"{GITHUB_API}/search/repositories"
    fetch_count = max(options.max_repos * 3, options.max_repos + 5)
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": min(fetch_count, 100),
        "page": 1,
    }

    try:
        resp = requests.get(url, headers=_headers(token), params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"[ERROR] GitHub search failed: {exc}")
        raise RuntimeError(f"GitHub 搜尋失敗：{exc}") from exc

    items = resp.json().get("items", [])
    repos: List[RepoBrief] = []

    for item in items:
        if not _passes_filters(item, options):
            continue

        repos.append(
            RepoBrief(
                full_name=item.get("full_name", ""),
                name=item.get("name", ""),
                html_url=item.get("html_url", ""),
                description=item.get("description"),
                stargazers_count=item.get("stargazers_count", 0),
                fork=bool(item.get("fork")),
            )
        )

        if len(repos) >= options.max_repos:
            break

    print(f"[INFO] Found {len(repos)} repos matching filters (requested {options.max_repos})")
    return repos


def fetch_repo_details(token: str | None, full_name: str, *, exclude_empty_readme: bool = False) -> dict:
    url = f"{GITHUB_API}/repos/{full_name}"

    try:
        response = requests.get(url, headers=_headers(token), timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"[ERROR] Failed to fetch repo {full_name}: {exc}")
        raise RuntimeError(f"無法取得 repo 詳細資料 {full_name}：{exc}") from exc

    repo = response.json()

    readme_text = None
    try:
        readme_response = requests.get(
            f"{GITHUB_API}/repos/{full_name}/readme",
            headers={**_headers(token), "Accept": "application/vnd.github.raw"},
            timeout=30,
        )
        if readme_response.status_code == 200:
            readme_text = readme_response.text
            print(f"[INFO] Successfully fetched README for {full_name} ({len(readme_text)} chars)")
        else:
            print(f"[WARN] Failed to fetch README for {full_name}: status {readme_response.status_code}")
    except requests.RequestException as exc:
        print(f"[WARN] Exception fetching README for {full_name}: {exc}")

    if exclude_empty_readme and not (readme_text or "").strip():
        raise RuntimeError(f"README 為空，已依設定排除：{full_name}")

    return {
        "full_name": repo.get("full_name", full_name),
        "name": repo.get("name"),
        "html_url": repo.get("html_url"),
        "description": repo.get("description"),
        "stargazers_count": repo.get("stargazers_count", 0),
        "language": repo.get("language"),
        "homepage": repo.get("homepage"),
        "topics": repo.get("topics", []),
        "readme_excerpt": (readme_text or "")[:12000],
    }
