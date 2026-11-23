#!/usr/bin/with-contenv bashio
# Starts the terminal server. Everything the agents install or store (binaries, logins,
# sessions, settings) lives under /data, so it survives restarts and app updates.
export HOME=/data LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1
export NPM_CONFIG_PREFIX=/data/npm
export PATH="/data/.local/bin:/data/npm/bin:/usr/local/bin:${PATH}"
mkdir -p /data/.local/bin /data/npm
export SUPERVISOR_TOKEN

export AGENTS="$(bashio::config 'agents' | tr '\n' ' ')"
export AUTOCOMPACT_TOKENS="$(bashio::config 'autocompact_tokens')"
export IDLE_COMPACT_MINUTES="$(bashio::config 'idle_compact_minutes')"
for a in muse claude gemini codex; do
  export "ARGS_${a^^}=$(bashio::config "${a}_args")"
done

# optional API keys; leave them empty to sign in with a subscription instead
for pair in anthropic_api_key:ANTHROPIC_API_KEY gemini_api_key:GEMINI_API_KEY openai_api_key:OPENAI_API_KEY meta_api_key:META_API_KEY; do
  v="$(bashio::config "${pair%%:*}")"
  if bashio::var.has_value "${v}"; then export "${pair##*:}=${v}"; fi
done

# Development only: when this app is installed as a *local* app, its source folder wins over the
# built-in copy, so fixes to app/ and skills/ only need a restart. An app installed from a
# repository always runs the code in its image.
APP=/app
export SKILLS=/opt/skills
if [[ "$(bashio::addon.slug)" == local_* ]]; then
  for d in /local_apps/muse_code /addons/muse_code; do
    if [ -f "${d}/app/server.py" ]; then
      APP="${d}/app"
      if [ -d "${d}/skills" ]; then
        mkdir -p /tmp/skills && cp -r /opt/skills/. /tmp/skills/ 2>/dev/null || true
        cp -r "${d}/skills/." /tmp/skills/ && export SKILLS=/tmp/skills
      fi
      break
    fi
  done
fi

# Small helpers for the agents: ha-api and ha-ws. Only plain files without a dot in the name,
# so backups (ha-api.bak-...) or a __pycache__ folder next to them cannot stop the start.
for f in "${APP}"/bin/*; do
  n="$(basename "${f}")"
  if [ -f "${f}" ] && [[ "${n}" != *.* ]]; then
    install -m 0755 "${f}" "/usr/local/bin/${n}" || bashio::log.warning "could not install ${n}"
  fi
done

bashio::log.info "AI Agents starting (app from ${APP}, skills from ${SKILLS}, agents: ${AGENTS})"
cd /homeassistant
exec python3 "${APP}/server.py" "${APP}"
