from __future__ import annotations

import base64
import json
from typing import Optional
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


class GitHubContentClient:
    def __init__(self, token: Optional[str]):
        if not token:
            raise RuntimeError("缺少 GITHUB_TOKEN。請在環境變數或 GitHub Actions Secrets 設定。")
        self.token = token

    def _get_file(self, owner: str, repo: str, path: str, ref: str) -> dict | None:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
        response = requests.get(url, headers=_headers(self.token), params={"ref": ref}, timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def get_file_text(self, owner: str, repo: str, path: str, branch: str) -> str | None:
        """讀取 repo 內文字檔內容，不存在時回傳 None。"""
        existing = self._get_file(owner, repo, path, branch)
        if not existing:
            return None

        content = existing.get("content")
        if not content:
            return None

        encoding = existing.get("encoding", "base64")
        if encoding != "base64":
            raise RuntimeError(f"不支援的檔案編碼 {encoding}：{path}")

        return base64.b64decode(content).decode("utf-8")

    def get_json(self, owner: str, repo: str, path: str, branch: str) -> dict | None:
        text = self.get_file_text(owner, repo, path, branch)
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            print(f"[WARN] Failed to parse JSON at {path}: {exc}")
            return None

    def put_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content_bytes: bytes,
        *,
        branch: str,
        message: str,
        author_name: str,
        author_email: str,
    ) -> dict:
        existing = self._get_file(owner, repo, path, branch)
        sha = existing.get("sha") if existing else None
        url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
        payload = {
            "message": message,
            "content": base64.b64encode(content_bytes).decode("utf-8"),
            "branch": branch,
            "committer": {"name": author_name, "email": author_email},
        }
        if sha:
            payload["sha"] = sha
        response = requests.put(url, headers=_headers(self.token), json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
