from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import json


@dataclass
class RepoInfo:
    full_name: str
    name: str
    html_url: str
    description: str | None
    stars: int
    language: str | None
    homepage: str | None
    topics: list[str]
    readme_excerpt: str | None


class LLMProvider:
    def generate_repo_summaries(self, repos: List[RepoInfo]) -> List[Dict[str, str]]:
        raise NotImplementedError


def _build_prompt(repos: List[RepoInfo]) -> str:
    repos_payload = [
        {
            "full_name": r.full_name,
            "name": r.name,
            "url": r.html_url,
            "description": r.description or "",
            "stars": r.stars,
            "language": r.language or "",
            "homepage": r.homepage or "",
            "topics": r.topics,
            "readme_excerpt": r.readme_excerpt or "",
        }
        for r in repos
    ]
    instruction = (
        "你是一位繁體中文技術編輯。請閱讀每個 GitHub 專案的描述與 README 內容，"
        "為每個專案撰寫繁體中文介紹。\n"
        "要求：\n"
        "1. intro_md 使用固定 Markdown 結構：\n"
        "   - **一句話說明**：...\n"
        "   - **專案用途**：...\n"
        "   - **適合使用對象**：...\n"
        "   - **技術亮點**：...\n"
        "   - **可能限制或注意事項**：...\n"
        "2. 每段 1~3 句，整體約 150~250 字。\n"
        "3. 必須綜合 README 內容總結，禁止直接翻譯或照抄長篇 README。\n"
        "4. JSON 中的 full_name 必須與輸入完全一致（包含 owner/repo）。\n"
        "5. 只輸出 JSON，格式為 {\"summaries\":[{\"full_name\":string,\"intro_md\":string}...] }。"
    )
    return instruction + "\n\nINPUT:\n" + json.dumps(repos_payload, ensure_ascii=False)


class ClaudeClient(LLMProvider):
    def __init__(self, api_key: str, model: str):
        from anthropic import Anthropic

        self.client = Anthropic(api_key=api_key)
        self.model = model

    def generate_repo_summaries(self, repos: List[RepoInfo]) -> List[Dict[str, str]]:
        prompt = _build_prompt(repos)
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(part.text for part in resp.content if getattr(part, "text", None))
            data = json.loads(text)
            if isinstance(data, dict) and isinstance(data.get("summaries"), list):
                return data["summaries"]
        except Exception:
            pass
        # fallback：產生空白介紹，避免中斷
        return [{"full_name": r.full_name, "intro_md": r.description or ""} for r in repos]


class OllamaClient(LLMProvider):
    def __init__(self, base_url: str, model: str):
        from openai import OpenAI

        # Ollama 的 OpenAI 相容端點需要一個 API Key 字串，但實際不驗證
        self.client = OpenAI(base_url=base_url, api_key="ollama")
        self.model = model

    def generate_repo_summaries(self, repos: List[RepoInfo]) -> List[Dict[str, str]]:
        prompt = _build_prompt(repos)
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4000,
            )
            text = resp.choices[0].message.content or "{}"
            
            # 嘗試清理 Markdown 標記
            clean_text = text.strip()
            if "```json" in clean_text:
                clean_text = clean_text.split("```json")[1].split("```")[0]
            elif "```" in clean_text:
                clean_text = clean_text.split("```")[1].split("```")[0]
            
            data = json.loads(clean_text.strip())
            # print(f"[DEBUG] Parsed data: {json.dumps(data, ensure_ascii=False)[:500]}...")

            if isinstance(data, dict) and isinstance(data.get("summaries"), list):
                return data["summaries"]
            elif isinstance(data, list):
                # Fallback: 如果模型直接回傳 List
                return data
            else:
                print(f"[WARN] Ollama response format invalid. Raw: {text[:200]}...")
        except Exception as e:
            print(f"[WARN] Ollama generation failed: {e}")
            print(f"[DEBUG] Raw response was: {text if 'text' in locals() else 'N/A'}")
        return [{"full_name": r.full_name, "intro_md": r.description or ""} for r in repos]


def create_llm_client(provider: str, *, anthropic_api_key: str | None = None, claude_model: str = "claude-3-5-sonnet-20240620", ollama_base_url: str = "http://localhost:11434/v1", ollama_model: str = "llama3.1:8b-instruct") -> LLMProvider:
    p = (provider or "claude").lower()
    if p == "claude":
        if not anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 未設定。若要使用 Ollama，請將 LLM_PROVIDER 設為 ollama。")
        return ClaudeClient(api_key=anthropic_api_key, model=claude_model)
    if p == "ollama":
        return OllamaClient(base_url=ollama_base_url, model=ollama_model)
    raise RuntimeError(f"未知的 LLM_PROVIDER: {provider}")


