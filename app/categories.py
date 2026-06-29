from __future__ import annotations

from typing import Iterable

# 分類規則：依 topics 與 language 關鍵字匹配，可擴充
CATEGORY_RULES: dict[str, list[str]] = {
    "AI / LLM": [
        "ai",
        "llm",
        "machine-learning",
        "deep-learning",
        "gpt",
        "openai",
        "langchain",
        "nlp",
        "generative-ai",
        "artificial-intelligence",
        "neural-network",
        "transformer",
    ],
    "Developer Tools": [
        "developer-tools",
        "devtools",
        "ide",
        "editor",
        "productivity",
        "vscode",
        "plugin",
        "extension",
        "tooling",
    ],
    "Web": [
        "web",
        "frontend",
        "backend",
        "react",
        "vue",
        "nextjs",
        "html",
        "css",
        "javascript",
        "typescript",
        "fullstack",
    ],
    "Security": [
        "security",
        "cybersecurity",
        "pentest",
        "vulnerability",
        "encryption",
        "authentication",
        "oauth",
    ],
    "Data": [
        "data",
        "database",
        "analytics",
        "sql",
        "big-data",
        "data-science",
        "visualization",
        "pandas",
    ],
    "CLI": [
        "cli",
        "command-line",
        "terminal",
        "shell",
        "tui",
    ],
    "DevOps": [
        "devops",
        "docker",
        "kubernetes",
        "ci-cd",
        "infrastructure",
        "terraform",
        "ansible",
        "cloud",
    ],
    "Mobile": [
        "mobile",
        "android",
        "ios",
        "flutter",
        "react-native",
        "swift",
        "kotlin",
    ],
}

LANGUAGE_CATEGORY_HINTS: dict[str, str] = {
    "Swift": "Mobile",
    "Kotlin": "Mobile",
    "Dart": "Mobile",
    "Go": "CLI",
    "Rust": "Developer Tools",
    "Shell": "CLI",
}


def _normalize(value: str) -> str:
    return value.lower().strip().replace("_", "-")


def classify_repo(language: str | None, topics: Iterable[str]) -> list[str]:
    """依 language 與 topics 回傳匹配的分類標籤（最多 3 個）。"""
    normalizedTopics = {_normalize(t) for t in topics if t}
    matched: list[str] = []

    for category, keywords in CATEGORY_RULES.items():
        for keyword in keywords:
            normalizedKeyword = _normalize(keyword)
            if any(
                normalizedKeyword in topic or topic in normalizedKeyword
                for topic in normalizedTopics
            ):
                if category not in matched:
                    matched.append(category)
                break

    if language:
        hint = LANGUAGE_CATEGORY_HINTS.get(language)
        if hint and hint not in matched:
            matched.append(hint)

    return matched[:3]
