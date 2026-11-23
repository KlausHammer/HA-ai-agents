# Home Assistant's Debian base image (multi-arch: amd64 and aarch64). Built with Docker BuildKit,
# by the Supervisor for a local install or by the GitHub workflow for the published images.
FROM ghcr.io/home-assistant/base-debian:bookworm
# BUILD_ARCH is set by the Supervisor and the Home Assistant build actions; TARGETARCH by BuildKit
ARG BUILD_ARCH
ARG TARGETARCH

LABEL \
    org.opencontainers.image.title="Home Assistant App: AI Agents" \
    org.opencontainers.image.description="Claude Code, Codex, Gemini CLI and Muse Code in a sidebar terminal with full admin access to Home Assistant" \
    org.opencontainers.image.source="https://github.com/KlausHammer/HA-ai-agents" \
    org.opencontainers.image.licenses="MIT"

ENV LANG=C.UTF-8 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 python3-websockets python3-yaml curl ca-certificates jq git bubblewrap \
      nano less ripgrep procps xz-utils unzip openssh-client \
 && rm -rf /var/lib/apt/lists/*

# Node.js (needed by Gemini CLI and Codex), checked against the official checksums
ARG NODE_VERSION=22.12.0
RUN arch="${BUILD_ARCH:-${TARGETARCH}}" \
 && case "${arch}" in amd64) a=x64 ;; aarch64|arm64) a=arm64 ;; *) echo "unsupported arch ${arch}"; exit 1 ;; esac \
 && f="node-v${NODE_VERSION}-linux-${a}.tar.xz" \
 && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/${f}" -o "/tmp/${f}" \
 && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/SHASUMS256.txt" | grep " ${f}\$" | (cd /tmp && sha256sum -c -) \
 && tar -xJf "/tmp/${f}" -C /usr/local --strip-components=1 --exclude CHANGELOG.md --exclude README.md --exclude LICENSE \
 && rm "/tmp/${f}" && node --version && npm --version

# Terminal library for the web page (pinned versions, checked against known checksums), served
# locally so the panel needs no CDN
RUN mkdir -p /opt/vendor && cd /opt/vendor \
 && for f in @xterm/xterm@5.5.0/css/xterm.css @xterm/xterm@5.5.0/lib/xterm.js \
             @xterm/addon-fit@0.10.0/lib/addon-fit.js @xterm/addon-web-links@0.11.0/lib/addon-web-links.js; do \
      curl -fsSL "https://cdn.jsdelivr.net/npm/${f}" -o "$(basename "${f}")"; \
    done \
 && printf '%s\n' \
      "ba8e6985669488981ccf40c0cefe3aba80722cb6c92de7ad628b0bd717faf2b6  xterm.css" \
      "1f991ac3b4b283ebf96e60ae23a00a52765dd3a2e46fa6fdda9f1aab032f7495  xterm.js" \
      "bdaefa370b1bfc42ee88d46fe6072400902a4d4b2d45cd93438dda9b23c97089  addon-fit.js" \
      "f230a6c8211ce4614dda5441f27b603c7c1ca95151a655bc0efac6377ee643f0  addon-web-links.js" \
    | sha256sum -c -

# Skills: our own plus the community Home Assistant best-practices skill (MIT), pinned to a commit
ARG HA_SKILLS_COMMIT=166defa51c606b3c77d45a9b29a459d1f993f357
COPY skills /opt/skills
RUN git init -q /tmp/has && cd /tmp/has \
 && git fetch -q --depth 1 https://github.com/homeassistant-ai/skills "${HA_SKILLS_COMMIT}" \
 && git checkout -q FETCH_HEAD \
 && cp -r /tmp/has/skills/* /opt/skills/ \
 && cp /tmp/has/LICENSE /opt/skills/home-assistant-best-practices/LICENSE \
 ; rm -rf /tmp/has; ls /opt/skills

COPY run.sh /run.sh
COPY app /app
RUN chmod a+x /run.sh /app/bin/*

CMD [ "/run.sh" ]
