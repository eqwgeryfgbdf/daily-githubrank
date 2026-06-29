#!/usr/bin/env bash
set -euo pipefail

deployDir="${1:-.pages-deploy}"
rootDir="$(cd "$(dirname "$0")/.." && pwd)"

rm -rf "${rootDir}/${deployDir}"
mkdir -p "${rootDir}/${deployDir}"

copyIfExists() {
  if [[ -e "${rootDir}/$1" ]]; then
    mkdir -p "${rootDir}/${deployDir}/$(dirname "$1")"
    cp -R "${rootDir}/$1" "${rootDir}/${deployDir}/$1"
  fi
}

for path in index.html archive.html .nojekyll _headers assets daily data; do
  copyIfExists "${path}"
done

file_count="$(find "${rootDir}/${deployDir}" -type f | wc -l | tr -d ' ')"
echo "Prepared Cloudflare Pages deploy directory: ${deployDir} (${file_count} files)"
