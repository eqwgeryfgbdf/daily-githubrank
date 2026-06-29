from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any
import os
import pytz
import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape


def _get_jinja_env() -> Environment:
    templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
    return Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(enabled_extensions=(".html", ".xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _now_in_timezone(timezone: str) -> datetime:
    tz = pytz.timezone(timezone or "UTC")
    return datetime.now(tz)


def _prepare_repos_html(repos: list[dict]) -> list[dict]:
    repos_html: list[dict] = []
    for repo in repos:
        repo_copy = repo.copy()
        intro_md = repo.get("intro_md", "") or repo.get("summary", "") or ""
        repo_copy["intro_html"] = markdown.markdown(intro_md) if intro_md else ""
        repos_html.append(repo_copy)
    return repos_html


def _seo_context(
    *,
    site_name: str,
    site_description: str,
    site_url: str | None,
    page_path: str,
    page_title: str,
    page_description: str | None = None,
) -> dict[str, str | None]:
    og_url = f"{site_url.rstrip('/')}/{page_path.lstrip('/')}" if site_url else None
    return {
        "page_title": page_title,
        "page_description": page_description or site_description,
        "og_url": og_url,
    }


def build_daily_paths(path_prefix: str, date_str: str) -> dict[str, str]:
    year, month, _day = date_str.split("-")
    base = f"{path_prefix}/{year}/{month}/{date_str}"
    return {
        "markdown": f"{base}.md",
        "html": f"{base}.html",
    }


def build_daily_data(*, date_str: str, article_title: str, repos: list[dict]) -> dict[str, Any]:
    return {
        "date": date_str,
        "title": article_title,
        "repo_count": len(repos),
        "repos": [
            {
                "name": repo.get("name"),
                "full_name": repo.get("full_name"),
                "url": repo.get("html_url"),
                "description": repo.get("description"),
                "stars": repo.get("stars"),
                "language": repo.get("language"),
                "topics": repo.get("topics", []),
                "categories": repo.get("categories", []),
                "homepage": repo.get("homepage"),
                "summary": repo.get("intro_md") or repo.get("description") or "",
            }
            for repo in repos
        ],
    }


def merge_archive_entry(
    archive: dict[str, Any] | None,
    *,
    date_str: str,
    title: str,
    repo_count: int,
    html_path: str,
    markdown_path: str,
) -> dict[str, Any]:
    entries = list((archive or {}).get("entries", []))
    new_entry = {
        "date": date_str,
        "title": title,
        "repo_count": repo_count,
        "html_path": html_path,
        "markdown_path": markdown_path,
    }

    entries = [entry for entry in entries if entry.get("date") != date_str]
    entries.append(new_entry)
    entries.sort(key=lambda item: item.get("date", ""), reverse=True)
    return {"entries": entries}


def group_archive_entries(entries: list[dict[str, Any]], *, page_prefix: str = "") -> list[tuple[str, list[tuple[str, list[dict[str, Any]]]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))

    for entry in entries:
        date_value = entry.get("date", "")
        if len(date_value) < 7:
            continue
        year = date_value[:4]
        month = date_value[5:7]
        html_path = entry.get("html_path", "")
        grouped[year][month].append(
            {
                "date": date_value,
                "title": entry.get("title", date_value),
                "repo_count": entry.get("repo_count", 0),
                "html_href": f"{page_prefix}{html_path}",
            }
        )

    result: list[tuple[str, list[tuple[str, list[dict[str, Any]]]]]] = []
    for year in sorted(grouped.keys(), reverse=True):
        months = []
        for month in sorted(grouped[year].keys(), reverse=True):
            month_entries = sorted(grouped[year][month], key=lambda item: item["date"], reverse=True)
            months.append((month, month_entries))
        result.append((year, months))
    return result


def render_daily_markdown(*, timezone: str, trending_days: int, repos: list[dict]) -> str:
    now = _now_in_timezone(timezone)
    date_str = now.strftime("%Y-%m-%d")
    env = _get_jinja_env()
    template = env.get_template("daily.md.j2")
    return template.render(
        date_str=date_str,
        timezone=timezone,
        trending_days=trending_days,
        repos=repos,
    )


def render_daily_html(
    *,
    timezone: str,
    repos: list[dict],
    github_repo: str,
    site_name: str,
    site_description: str,
    site_url: str | None,
    daily_html_path: str,
    asset_prefix: str = "../../../",
) -> str:
    now = _now_in_timezone(timezone)
    date_str = now.strftime("%Y-%m-%d")
    article_title = f"{site_name} - {date_str}"
    repos_html = _prepare_repos_html(repos)
    seo = _seo_context(
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        page_path=daily_html_path,
        page_title=article_title,
        page_description=f"{date_str} 的 GitHub 熱門新專案精選，共 {len(repos)} 個項目。",
    )

    env = _get_jinja_env()
    template = env.get_template("daily.html.j2")
    return template.render(
        date_str=date_str,
        timezone=timezone,
        article_title=article_title,
        repos=repos_html,
        github_repo=github_repo,
        css_href=f"{asset_prefix}assets/style.css",
        home_href=f"{asset_prefix}index.html",
        archive_href=f"{asset_prefix}archive.html",
        **seo,
    )


def render_index_html(
    *,
    timezone: str,
    repos: list[dict],
    github_repo: str,
    site_name: str,
    site_description: str,
    site_url: str | None,
    daily_html_path: str,
) -> str:
    now = _now_in_timezone(timezone)
    date_str = now.strftime("%Y-%m-%d")
    repos_html = _prepare_repos_html(repos)

    all_categories: list[str] = []
    seen: set[str] = set()
    for repo in repos:
        for category in repo.get("categories", []):
            if category not in seen:
                seen.add(category)
                all_categories.append(category)

    page_title = f"{site_name} - {date_str}"
    seo = _seo_context(
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        page_path="index.html",
        page_title=page_title,
    )

    env = _get_jinja_env()
    template = env.get_template("index.html.j2")
    return template.render(
        date_str=date_str,
        timezone=timezone,
        site_name=site_name,
        site_description=site_description,
        repos=repos_html,
        all_categories=all_categories,
        github_repo=github_repo,
        css_href="assets/style.css",
        daily_href=daily_html_path,
        archive_href="archive.html",
        **seo,
    )


def render_archive_html(
    *,
    archive: dict[str, Any],
    github_repo: str,
    site_name: str,
    site_description: str,
    site_url: str | None,
) -> str:
    entries = archive.get("entries", [])
    grouped_entries = group_archive_entries(entries, page_prefix="")
    page_title = f"歷史文章 - {site_name}"
    seo = _seo_context(
        site_name=site_name,
        site_description=site_description,
        site_url=site_url,
        page_path="archive.html",
        page_title=page_title,
        page_description="瀏覽過去每日 GitHub 熱門精選文章。",
    )

    env = _get_jinja_env()
    template = env.get_template("archive.html.j2")
    return template.render(
        grouped_entries=grouped_entries,
        github_repo=github_repo,
        css_href="assets/style.css",
        home_href="index.html",
        **seo,
    )


def render_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
