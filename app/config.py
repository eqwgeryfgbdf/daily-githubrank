import os
from dataclasses import dataclass


def _get_env(key: str, default: str | None = None) -> str | None:
    value = os.environ.get(key)
    if value is not None and value != "":
        return value
    return default


def _get_bool(key: str, default: bool = False) -> bool:
    value = _get_env(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(key: str, default: int) -> int:
    value = _get_env(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"環境變數 {key} 必須為整數，目前值：{value}") from exc


def _get_list(key: str) -> list[str]:
    value = _get_env(key)
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass
class AppConfig:
    llm_provider: str
    anthropic_api_key: str | None
    claude_model: str
    ollama_base_url: str
    ollama_model: str
    github_token: str | None
    target_repo: str
    target_branch: str
    max_repos: int
    path_prefix: str
    data_prefix: str
    timezone: str
    commit_author_name: str
    commit_author_email: str
    trending_days: int
    trending_language: str | None
    trending_topics: list[str]
    min_stars: int
    exclude_forks: bool
    exclude_no_description: bool
    exclude_empty_readme: bool
    site_name: str
    site_description: str
    site_url: str | None
    homepage_repo_count: int

    @staticmethod
    def load() -> "AppConfig":
        target_repo = _get_env("TARGET_REPO", _get_env("GITHUB_REPOSITORY", "")) or ""
        site_url = _get_env("SITE_URL") or _get_env("CLOUDFLARE_PAGES_URL")
        if not site_url:
            pages_project = _get_env("CLOUDFLARE_PAGES_PROJECT", "daily-githubrank") or "daily-githubrank"
            site_url = f"https://{pages_project}.pages.dev"

        max_repos = _get_int("MAX_REPOS", 5)

        return AppConfig(
            llm_provider=_get_env("LLM_PROVIDER", "claude") or "claude",
            anthropic_api_key=_get_env("ANTHROPIC_API_KEY"),
            claude_model=_get_env("CLAUDE_MODEL", "claude-3-5-sonnet-20240620") or "claude-3-5-sonnet-20240620",
            ollama_base_url=_get_env("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1")
            or "http://host.docker.internal:11434/v1",
            ollama_model=_get_env("OLLAMA_MODEL", "phi4-mini:3.8b") or "phi4-mini:3.8b",
            github_token=_get_env("GITHUB_TOKEN"),
            target_repo=target_repo,
            target_branch=_get_env("TARGET_BRANCH", "main") or "main",
            max_repos=max_repos,
            path_prefix=_get_env("PATH_PREFIX", "daily") or "daily",
            data_prefix=_get_env("DATA_PREFIX", "data") or "data",
            timezone=_get_env("TIMEZONE", "Asia/Taipei") or "Asia/Taipei",
            commit_author_name=_get_env("COMMIT_AUTHOR_NAME", "DailyTasksBot") or "DailyTasksBot",
            commit_author_email=_get_env("COMMIT_AUTHOR_EMAIL", "bot@example.com") or "bot@example.com",
            trending_days=_get_int("TRENDING_DAYS", 1),
            trending_language=_get_env("TRENDING_LANGUAGE"),
            trending_topics=_get_list("TRENDING_TOPICS"),
            min_stars=_get_int("MIN_STARS", 0),
            exclude_forks=_get_bool("EXCLUDE_FORKS", True),
            exclude_no_description=_get_bool("EXCLUDE_NO_DESCRIPTION", False),
            exclude_empty_readme=_get_bool("EXCLUDE_EMPTY_README", False),
            site_name=_get_env("SITE_NAME", "GitHub 每日熱門精選") or "GitHub 每日熱門精選",
            site_description=_get_env(
                "SITE_DESCRIPTION",
                "每日精選 GitHub 新創建熱門專案，由 AI 生成繁體中文介紹。",
            )
            or "每日精選 GitHub 新創建熱門專案，由 AI 生成繁體中文介紹。",
            site_url=site_url,
            homepage_repo_count=_get_int("HOMEPAGE_REPO_COUNT", max_repos),
        )
