## GitHub 每日熱門精選

每天自動搜尋 GitHub 新創建且快速獲得 stars 的熱門專案，透過 LLM（Claude 或 Ollama）生成繁體中文介紹，產出 Markdown、HTML 與 JSON，並發布到 GitHub Pages 靜態網站。

### 功能概覽

- **每日抓取**：GitHub Search API，預設「最近 1 天新建立、依 stars 排序」
- **繁中介紹**：Claude / Ollama，失敗時 fallback 至 description
- **多格式輸出**：Markdown 文章、每日 HTML、首頁、歷史索引、JSON 資料
- **博客版型**：Hero、排名卡片、分類標籤、SEO meta、響應式設計
- **自動排程**：GitHub Actions 每日 09:05（台灣時間）執行

---

## 一、本地測試

### 1. 準備環境

```bash
cp env.sample .env
# 編輯 .env，至少設定 GITHUB_TOKEN
```

### 2. Docker 建置與執行（推薦）

```bash
docker build -t daily-tasks:latest .

# 僅輸出到 output/，不推送 GitHub
docker run --rm \
  --env-file ./.env \
  -e DRY_RUN=1 \
  -e LLM_PROVIDER=ollama \
  -v "$(pwd)/output:/app/output" \
  daily-tasks:latest
```

輸出目錄結構：

```
output/
  index.html
  archive.html
  assets/style.css
  daily/YYYY/MM/YYYY-MM-DD.md
  daily/YYYY/MM/YYYY-MM-DD.html
  data/latest.json
  data/YYYY-MM-DD.json
  data/archive.json
```

### 3. 直接執行 Python（可選）

```bash
pip install -r requirements.txt
export DRY_RUN=1
export OUTPUT_DIR=output
export GITHUB_TOKEN=your_token
python -m app.main
```

---

## 二、GitHub Actions 排程

工作流程：`.github/workflows/daily.yml`

- **排程**：每日 01:05 UTC（台灣時間 09:05）
- **手動觸發**：Actions → Daily Trending Publisher → Run workflow

### 必要 Secrets

| Secret | 說明 |
|--------|------|
| `GITHUB_TOKEN` | Actions 內建 token（通常自動提供） |
| `ANTHROPIC_API_KEY` | 使用 Claude 時必填 |

可選 **Variables**（Cloudflare Pages SEO 用）：

| Variable | 說明 |
|----------|------|
| `CLOUDFLARE_PAGES_URL` | 正式網址，如 `https://daily-githubrank.pages.dev` |

### Workflow 執行內容

1. checkout repo
2. build Docker image
3. run container（抓取 → LLM → 渲染 → commit 回 GitHub）
4. Cloudflare Pages 偵測 push 後**自動部署**（需先完成下方 Pages 設定）

---

## 三、Cloudflare Pages 部署（推薦）

本專案是**純靜態網站**，用 Cloudflare Pages 託管最合適。

```
GitHub Actions（每日）→ 產生 HTML/JSON → commit 到 main
Cloudflare Pages（自動）→ 偵測 push → build → 上線
```

### 方法 A：Cloudflare Pages 連接 GitHub（推薦，免 API Token）

#### 步驟 1：建立 Pages 專案

1. 開啟 [Cloudflare Dashboard → Workers & Pages](https://dash.cloudflare.com/?to=/:account/workers-and-pages)
2. **Create application** → **Pages** 分頁
3. **Connect to Git** → 選擇 GitHub → 授權 → 選此 repo
4. **Set up builds and deployments** 填寫：

| 設定 | 值 |
|------|-----|
| Production branch | `main` |
| Framework preset | `None` |
| Build command | `bash build.sh` |
| Build output directory | `.pages-deploy` |

5. **Save and Deploy**

首次部署會讀取 repo 內已有的 `index.html`、`daily/`、`data/` 等靔態檔。

#### 步驟 2：設定 GitHub Variable（SEO 用）

Repo → **Settings** → **Secrets and variables** → **Actions** → **Variables**

| Variable | 範例 |
|----------|------|
| `CLOUDFLARE_PAGES_URL` | `https://daily-githubrank.pages.dev` |

每日排程產生內容時，`SITE_URL` / `og:url` 會用這個網址。

#### 步驟 3：完成

- 網站：`https://<專案名稱>.pages.dev`
- 之後每次 GitHub Actions commit 新內容，Cloudflare Pages **自動重新部署**
- 可在 Cloudflare Dashboard 查看部署紀錄與 Preview

#### 自訂網域

Dashboard → 你的 Pages 專案 → **Custom domains** → 新增網域，並把 `CLOUDFLARE_PAGES_URL` 改成自訂網域。

---

### 方法 B：Wrangler 指令部署（可選）

若不想連 Git，可用 Wrangler 從本機或 CI 直接上傳：

```bash
npm install
npx wrangler login
npm run pages:deploy
```

此方式需在 GitHub Secrets 設定 `CLOUDFLARE_API_TOKEN` 與 `CLOUDFLARE_ACCOUNT_ID`，並自行加 deploy workflow。

### 本地預覽

```bash
bash build.sh
npx wrangler pages dev .pages-deploy
```

### 部署檔案範圍

`build.sh` 只打包公開靜態檔，**不會**上傳 Python 原始碼：

```
index.html
archive.html
.nojekyll
_headers
assets/
daily/
data/
```

---

## 四、GitHub Pages（替代方案）

若不想用 Cloudflare，仍可使用 GitHub Pages：

1. Repo → **Settings** → **Pages**
2. **Source**：Deploy from a branch
3. **Branch**：`main` / **Folder**：`/ (root)`

網址：`https://<owner>.github.io/<repo>/`  
此時請將 `SITE_URL` 設為 GitHub Pages URL。

---

## 環境變數說明

### LLM

| 變數 | 預設 | 說明 |
|------|------|------|
| `LLM_PROVIDER` | `claude` | `claude` 或 `ollama` |
| `ANTHROPIC_API_KEY` | — | Claude API 金鑰 |
| `CLAUDE_MODEL` | `claude-3-5-sonnet-20240620` | Claude 模型 |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434/v1` | Ollama OpenAI 相容端點 |
| `OLLAMA_MODEL` | `phi4-mini:3.8b` | Ollama 模型 |

### GitHub

| 變數 | 預設 | 說明 |
|------|------|------|
| `GITHUB_TOKEN` | — | GitHub API 與提交用 |
| `TARGET_REPO` | — | 目標 repo（`owner/repo`） |
| `TARGET_BRANCH` | `main` | 提交分支 |

### 抓取條件

| 變數 | 預設 | 說明 |
|------|------|------|
| `MAX_REPOS` | `5` | 每日最多抓取 repo 數（5/10/15） |
| `HOMEPAGE_REPO_COUNT` | 同 `MAX_REPOS` | 首頁顯示數量 |
| `TRENDING_DAYS` | `1` | 搜尋最近 N 天新建立 repo |
| `TRENDING_LANGUAGE` | — | 限定語言，如 `Python` |
| `TRENDING_TOPICS` | — | 逗號分隔 topics，如 `ai,llm` |
| `MIN_STARS` | `0` | 最低 stars 門檻 |
| `EXCLUDE_FORKS` | `1` | 排除 fork |
| `EXCLUDE_NO_DESCRIPTION` | `0` | 排除無 description |
| `EXCLUDE_EMPTY_README` | `0` | 排除無 README |

### 網站與輸出

| 變數 | 預設 | 說明 |
|------|------|------|
| `PATH_PREFIX` | `daily` | Markdown/HTML 文章路徑前綴 |
| `DATA_PREFIX` | `data` | JSON 路徑前綴 |
| `TIMEZONE` | `Asia/Taipei` | 日期時區 |
| `SITE_NAME` | `GitHub 每日熱門精選` | 網站名稱 |
| `SITE_DESCRIPTION` | （見 env.sample） | SEO 描述 |
| `SITE_URL` | Cloudflare Pages URL | 正式網站 URL（SEO og:url） |
| `CLOUDFLARE_PAGES_URL` | — | 同 SITE_URL，優先於預設 pages.dev |
| `CLOUDFLARE_PAGES_PROJECT` | `daily-githubrank` | Pages 專案名稱 |
| `DRY_RUN` | `0` | `1` 時只寫本地 `output/` |

---

## 每日產出檔案結構

```
index.html                          # 博客首頁（今日 Top N）
archive.html                        # 歷史文章索引
.nojekyll
_headers                            # Cloudflare Pages 快取與安全標頭
assets/style.css
daily/YYYY/MM/YYYY-MM-DD.md         # Markdown 文章
daily/YYYY/MM/YYYY-MM-DD.html       # 每日 HTML 文章
data/latest.json                    # 最新一天資料
data/YYYY-MM-DD.json                # 指定日期資料
data/archive.json                   # 歷史文章索引（JSON）
```

### JSON 欄位

```json
{
  "date": "2026-06-29",
  "title": "GitHub 每日熱門精選 - 2026-06-29",
  "repo_count": 5,
  "repos": [
    {
      "name": "...",
      "full_name": "owner/repo",
      "url": "https://github.com/...",
      "description": "...",
      "stars": 42,
      "language": "Python",
      "topics": ["ai"],
      "categories": ["AI / LLM"],
      "homepage": "...",
      "summary": "繁中介紹..."
    }
  ]
}
```

---

## 專案結構

```
app/
  main.py              # 主流程
  config.py            # 環境變數
  categories.py        # 分類邏輯
  render.py            # 模板渲染與 JSON
  github/
    trending.py        # 搜尋與 repo 詳細資料
    content.py         # GitHub Contents API
  llm/
    provider.py        # Claude / Ollama
templates/
  index.html.j2        # 首頁
  daily.html.j2        # 每日文章
  archive.html.j2      # 歷史索引
  daily.md.j2          # Markdown
assets/
  style.css            # 共用樣式
scripts/
  prepare-pages-deploy.sh  # 打包靜態檔
build.sh                     # Cloudflare Pages 建置入口
.github/workflows/
  daily.yml                  # 每日產生內容
wrangler.jsonc               # Wrangler 本地部署設定
package.json                 # 可選：wrangler 手動部署
Dockerfile
```

---

## 錯誤處理

- 單一 repo GitHub API 失敗：記錄錯誤並跳過，不中断流程
- README 不存在：繼續處理，僅缺少 README 摘要依據
- LLM 失敗：使用 GitHub description 作為 fallback
- 無符合條件 repo：產生空狀態頁面
- 執行結束會輸出 `[SUMMARY]` 紀錄抓取數、成功/失敗 repo、寫入檔案

---

## 疑難排解

- **API 速率限制**：確保 `GITHUB_TOKEN` 有效
- **LLM JSON 解析失敗**：自動 fallback 至 description
- **Ollama 連線**：本機 Docker 使用 `host.docker.internal`
- **Cloudflare Pages 沒更新**：確認 Pages 已連接 GitHub，且 Build output 為 `.pages-deploy`
- **Pages 404**：確認 `build.sh` 可執行，且 repo 根目錄有 `index.html`
- **GitHub Pages 404**：確認 Pages 來源為 `main` 根目錄，且 `.nojekyll` 存在
