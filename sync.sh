#!/bin/bash
# Copies the app source (../muse_code) into this repository before a commit and adds the lines that
# only the published copy needs: the prebuilt image and the repository link.
set -euo pipefail
cd "$(dirname "$0")"
OWNER="$(sed -n 's#^url: https://github.com/\([^/]*\)/.*#\1#p' repository.yaml)"
REPO="$(sed -n 's#^url: https://github.com/[^/]*/\(.*\)#\1#p' repository.yaml)"
rm -rf muse_code && mkdir muse_code
tar -C ../muse_code --exclude='__pycache__' --exclude='*.bak-*' --exclude='*.part' -cf - . | tar -C muse_code -xf -
lc_owner="$(echo "${OWNER}" | tr '[:upper:]' '[:lower:]')"
sed -i "s#^slug: muse_code#slug: muse_code\nurl: \"https://github.com/${OWNER}/${REPO}/tree/main/muse_code\"\nimage: \"ghcr.io/${lc_owner}/{arch}-ha-ai-agents\"#" muse_code/config.yaml
sed -i "s#github.com/OWNER/HA-ai-agents#github.com/${OWNER}/${REPO}#" muse_code/Dockerfile
grep -n '^url:\|^image:' muse_code/config.yaml
