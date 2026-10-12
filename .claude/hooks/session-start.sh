#!/bin/bash
# Instala Wrangler (CLI de Cloudflare) en sesiones remotas de Claude Code.
# La autenticación usa CLOUDFLARE_API_TOKEN, definido en los ajustes del entorno.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

if ! command -v wrangler >/dev/null 2>&1; then
  npm install -g wrangler >/dev/null 2>&1
fi
