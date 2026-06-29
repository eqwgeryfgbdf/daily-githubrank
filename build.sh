#!/usr/bin/env bash
# Cloudflare Pages 建置入口（Git 連線部署時使用）
set -euo pipefail
bash "$(dirname "$0")/scripts/prepare-pages-deploy.sh"
