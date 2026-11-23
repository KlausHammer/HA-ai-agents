# AI Agents

![Supports amd64](https://img.shields.io/badge/amd64-yes-green.svg) ![Supports aarch64](https://img.shields.io/badge/aarch64-yes-green.svg)

Claude Code, Codex, Gemini CLI and Muse Code in a Home Assistant sidebar panel. Each agent runs its real command line tool in a terminal that keeps running when you close the panel. The agents can build dashboards, write automations, troubleshoot integrations and explain your setup.

> [!WARNING]
> **By default the agents act without asking for confirmation (YOLO mode), and the app has full administrator access.**
> That covers the Supervisor role `admin`, the Home Assistant API, and read/write access to `/homeassistant`, `/addon_configs`, `/share`, `/media`, `/ssl`, `/backup` and `/local_apps`.
> An agent can therefore change or delete any configuration, apps, backups and network settings, update or restart Home Assistant and the host, and operate your devices. It does so without asking you first.
> The house rules ask the agents to check with you before risky steps, but that is not a technical barrier. Make a backup first. See the documentation for how to turn YOLO off.

## Features
- One tab per agent with the unmodified CLI: slash commands, model picker, typing while it works.
- Conversations survive closing the panel and restarting the app.
- Install, sign in and update each agent from the panel. Agents are stored in the app's own storage.
- Shared house rules and Home Assistant skills for every agent, plus the `ha-api` and `ha-ws` tools.
- Files tab for images, drawings and PDFs that you and the agents share.
- Automatic compaction at a token limit and after a quiet period, so long conversations stay cheap.
- Admin-only panel, no open ports.

You need your own account or API key with each vendor you use. This app is not affiliated with Anthropic, OpenAI, Google or Meta.

## Installation
1. Settings → Apps → App store → ⋮ → **Repositories**, and add `https://github.com/KlausHammer/HA-ai-agents`.
2. Install **AI Agents**, start it and open **AI Agents** in the sidebar.

Read the **Documentation** tab before you start. It lists every permission, what is sent to the AI vendors and how to turn YOLO off.

## Layout
```
config.yaml, Dockerfile, run.sh   app definition and image
app/server.py      terminal server (Python standard library, one WebSocket per tab)
app/index.html     the panel (xterm.js)
app/rules.md       house rules given to every agent
app/bin/           ha-api and ha-ws helpers
skills/            Home Assistant skills (SKILL.md format)
```
