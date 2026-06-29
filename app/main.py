from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import pytz

from .categories import classify_repo
from .config import AppConfig
from .github.trending import TrendingSearchOptions, search_trending_repos, fetch_repo_details
from .github.content import GitHubContentClient
from .llm.provider import create_llm_client, RepoInfo
from .render import (
    build_daily_data,
    build_daily_paths,
    merge_archive_entry,
    render_archive_html,
    render_daily_html,
    render_daily_markdown,
    render_index_html,
    render_json,
)


@dataclass
class RunLog:
    date_str: str
    repos_requested: int
    repos_fetched: int
    repos_processed: int
    repos_summarized: list[str] = field(default_factory=list)
    repos_failed: list[str] = field(default_factory=list)
    files_written: list[str] = field(default_factory=list)


def _date_str(timezone: str) -> str:
    tz = pytz.timezone(timezone or "UTC")
    return datetime.now(tz).strftime("%Y-%m-%d")


def _write_local_file(base_dir: str, path: str, content: str) -> None:
    full_path = os.path.join(base_dir, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as file:
        file.write(content)
    print(f"[DRY_RUN] wrote {full_path}")


def _upload_file(
    client: GitHubContentClient,
    *,
    owner: str,
    repo: str,
    path: str,
    content: str,
    branch: str,
    message: str,
    author_name: str,
    author_email: str,
    run_log: RunLog,
) -> None:
    client.put_file(
        owner=owner,
        repo=repo,
        path=path,
        content_bytes=content.encode("utf-8"),
        branch=branch,
        message=message,
        author_name=author_name,
        author_email=author_email,
    )
    run_log.files_written.append(path)
    print(f"[INFO] Created/updated {path}")


def _persist_file(
    *,
    dry_run: bool,
    output_dir: str,
    client: GitHubContentClient | None,
    owner: str | None,
    repo: str | None,
    path: str,
    content: str,
    branch: str,
    message: str,
    author_name: str,
    author_email: str,
    run_log: RunLog,
) -> None:
    if dry_run:
        _write_local_file(output_dir, path, content)
        run_log.files_written.append(path)
        return

    if not client or not owner or not repo:
        raise RuntimeError("非 DRY_RUN 模式需要 GitHub client 與 target repo。")

    _upload_file(
        client,
        owner=owner,
        repo=repo,
        path=path,
        content=content,
        branch=branch,
        message=message,
        author_name=author_name,
        author_email=author_email,
        run_log=run_log,
    )


def _load_existing_archive(
    *,
    dry_run: bool,
    output_dir: str,
    client: GitHubContentClient | None,
    owner: str | None,
    repo: str | None,
    branch: str,
    archive_path: str,
) -> dict[str, Any] | None:
    if dry_run:
        local_path = os.path.join(output_dir, archive_path)
        if not os.path.exists(local_path):
            return None
        with open(local_path, encoding="utf-8") as file:
            return json.load(file)

    if not client or not owner or not repo:
        return None

    return client.get_json(owner, repo, archive_path, branch)


def _map_summaries(summaries: list[dict[str, str]], repo_infos: list[RepoInfo]) -> dict[str, str]:
    full_name_to_intro: dict[str, str] = {}
    name_to_intro: dict[str, str] = {}

    for summary in summaries:
        full_name = summary.get("full_name", "")
        intro = summary.get("intro_md", "")
        full_name_to_intro[full_name] = intro
        if "/" in full_name:
            name_to_intro[full_name.split("/")[-1]] = intro
        else:
            name_to_intro[full_name] = intro

    result: dict[str, str] = {}
    for info in repo_infos:
        intro = full_name_to_intro.get(info.full_name) or name_to_intro.get(info.name) or info.description or ""
        result[info.full_name] = intro
    return result


def main() -> None:
    cfg = AppConfig.load()
    dry_run = os.environ.get("DRY_RUN", "0") == "1"
    output_dir = os.environ.get("OUTPUT_DIR", "output")

    owner: str | None = None
    repo: str | None = None
    client: GitHubContentClient | None = None

    if not dry_run:
        if not cfg.target_repo:
            raise RuntimeError("TARGET_REPO 未設定。請提供 owner/repo。")
        owner, repo = cfg.target_repo.split("/", 1)
        client = GitHubContentClient(cfg.github_token)

    date_str = _date_str(cfg.timezone)
    run_log = RunLog(
        date_str=date_str,
        repos_requested=cfg.max_repos,
        repos_fetched=0,
        repos_processed=0,
    )

    search_options = TrendingSearchOptions(
        timezone=cfg.timezone,
        max_repos=cfg.max_repos,
        trending_days=cfg.trending_days,
        trending_language=cfg.trending_language,
        trending_topics=cfg.trending_topics,
        min_stars=cfg.min_stars,
        exclude_forks=cfg.exclude_forks,
        exclude_no_description=cfg.exclude_no_description,
        exclude_empty_readme=cfg.exclude_empty_readme,
    )

    briefs = search_trending_repos(cfg.github_token, search_options)
    run_log.repos_fetched = len(briefs)

    repo_infos: list[RepoInfo] = []
    for brief in briefs:
        try:
            details = fetch_repo_details(
                cfg.github_token,
                brief.full_name,
                exclude_empty_readme=cfg.exclude_empty_readme,
            )
            readme_excerpt = details.get("readme_excerpt")
            if readme_excerpt:
                print(f"[INFO] {details['full_name']}: README available ({len(readme_excerpt)} chars)")
            else:
                print(f"[WARN] {details['full_name']}: No README content")

            repo_infos.append(
                RepoInfo(
                    full_name=details["full_name"],
                    name=details.get("name") or details["full_name"].split("/")[-1],
                    html_url=details.get("html_url", ""),
                    description=details.get("description"),
                    stars=int(details.get("stargazers_count", 0)),
                    language=details.get("language"),
                    homepage=details.get("homepage"),
                    topics=details.get("topics", []),
                    readme_excerpt=readme_excerpt,
                )
            )
            run_log.repos_processed += 1
        except Exception as exc:
            print(f"[ERROR] Skip repo {brief.full_name}: {exc}")
            run_log.repos_failed.append(brief.full_name)

    summaries: list[dict[str, str]] = []
    if repo_infos:
        try:
            llm = create_llm_client(
                cfg.llm_provider,
                anthropic_api_key=cfg.anthropic_api_key,
                claude_model=cfg.claude_model,
                ollama_base_url=cfg.ollama_base_url,
                ollama_model=cfg.ollama_model,
            )
            summaries = llm.generate_repo_summaries(repo_infos)
            run_log.repos_summarized = [item.get("full_name", "") for item in summaries if item.get("intro_md")]
        except Exception as exc:
            print(f"[WARN] LLM summarize failed, use description fallback: {exc}")
            summaries = [{"full_name": info.full_name, "intro_md": info.description or ""} for info in repo_infos]

    intro_map = _map_summaries(summaries, repo_infos)

    repos_context: list[dict[str, Any]] = []
    for info in repo_infos:
        categories = classify_repo(info.language, info.topics)
        repos_context.append(
            {
                "full_name": info.full_name,
                "name": info.name,
                "html_url": info.html_url,
                "description": info.description,
                "stars": info.stars,
                "language": info.language,
                "homepage": info.homepage,
                "topics": info.topics,
                "categories": categories,
                "intro_md": intro_map.get(info.full_name, info.description or ""),
            }
        )

    daily_paths = build_daily_paths(cfg.path_prefix, date_str)
    article_title = f"{cfg.site_name} - {date_str}"
    homepage_repos = repos_context[: cfg.homepage_repo_count]

    markdown_content = render_daily_markdown(
        timezone=cfg.timezone,
        trending_days=cfg.trending_days,
        repos=repos_context,
    )
    daily_html_content = render_daily_html(
        timezone=cfg.timezone,
        repos=repos_context,
        github_repo=cfg.target_repo or "owner/repo",
        site_name=cfg.site_name,
        site_description=cfg.site_description,
        site_url=cfg.site_url,
        daily_html_path=daily_paths["html"],
    )
    index_html_content = render_index_html(
        timezone=cfg.timezone,
        repos=homepage_repos,
        github_repo=cfg.target_repo or "owner/repo",
        site_name=cfg.site_name,
        site_description=cfg.site_description,
        site_url=cfg.site_url,
        daily_html_path=daily_paths["html"],
    )

    daily_data = build_daily_data(date_str=date_str, article_title=article_title, repos=repos_context)
    daily_json = render_json(daily_data)
    latest_json = render_json(daily_data)

    archive_path = f"{cfg.data_prefix}/archive.json"
    existing_archive = _load_existing_archive(
        dry_run=dry_run,
        output_dir=output_dir,
        client=client,
        owner=owner,
        repo=repo,
        branch=cfg.target_branch,
        archive_path=archive_path,
    )
    archive_data = merge_archive_entry(
        existing_archive,
        date_str=date_str,
        title=article_title,
        repo_count=len(repos_context),
        html_path=daily_paths["html"],
        markdown_path=daily_paths["markdown"],
    )
    archive_json = render_json(archive_data)
    archive_html_content = render_archive_html(
        archive=archive_data,
        github_repo=cfg.target_repo or "owner/repo",
        site_name=cfg.site_name,
        site_description=cfg.site_description,
        site_url=cfg.site_url,
    )

    css_source = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
    with open(css_source, encoding="utf-8") as css_file:
        css_content = css_file.read()

    headers_source = os.path.join(os.path.dirname(os.path.dirname(__file__)), "_headers")
    headers_content = ""
    if os.path.exists(headers_source):
        with open(headers_source, encoding="utf-8") as headers_file:
            headers_content = headers_file.read()

    files_to_write = [
        (daily_paths["markdown"], markdown_content, f"chore(daily): {daily_paths['markdown']}"),
        (daily_paths["html"], daily_html_content, f"chore(daily): {daily_paths['html']}"),
        ("index.html", index_html_content, "chore(web): update index.html"),
        ("archive.html", archive_html_content, "chore(web): update archive.html"),
        (f"{cfg.data_prefix}/{date_str}.json", daily_json, f"chore(data): {date_str}.json"),
        (f"{cfg.data_prefix}/latest.json", latest_json, "chore(data): latest.json"),
        (archive_path, archive_json, "chore(data): archive.json"),
        ("assets/style.css", css_content, "chore(web): update assets/style.css"),
    ]
    if headers_content:
        files_to_write.append(("_headers", headers_content, "chore(web): update _headers"))

    if not dry_run:
        _persist_file(
            dry_run=False,
            output_dir=output_dir,
            client=client,
            owner=owner,
            repo=repo,
            path=".nojekyll",
            content="",
            branch=cfg.target_branch,
            message="chore(web): ensure .nojekyll for GitHub Pages",
            author_name=cfg.commit_author_name,
            author_email=cfg.commit_author_email,
            run_log=run_log,
        )

    for path, content, message in files_to_write:
        _persist_file(
            dry_run=dry_run,
            output_dir=output_dir,
            client=client,
            owner=owner,
            repo=repo,
            path=path,
            content=content,
            branch=cfg.target_branch,
            message=message,
            author_name=cfg.commit_author_name,
            author_email=cfg.commit_author_email,
            run_log=run_log,
        )

    print("[SUMMARY] Daily run completed")
    print(f"  date: {run_log.date_str}")
    print(f"  repos requested: {run_log.repos_requested}")
    print(f"  repos fetched: {run_log.repos_fetched}")
    print(f"  repos processed: {run_log.repos_processed}")
    print(f"  repos summarized: {len(run_log.repos_summarized)}")
    if run_log.repos_failed:
        print(f"  repos failed: {', '.join(run_log.repos_failed)}")
    print(f"  files written: {len(run_log.files_written)}")
    for file_path in run_log.files_written:
        print(f"    - {file_path}")


if __name__ == "__main__":
    main()
