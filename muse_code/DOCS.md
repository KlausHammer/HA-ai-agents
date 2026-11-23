# AI Agents

> [!WARNING]
> **The agents act without asking for confirmation (YOLO mode), and this app has full administrator access to Home Assistant.**
> Out of the box, any agent you talk to can edit or delete configuration, install or remove apps, change network settings, create or delete backups, update or restart Home Assistant and run any command in the container. It does so without asking you first.
> The house rules ask the agents to check with you before risky steps. That is a request to the AI, **not a technical barrier**, and an AI can misunderstand or ignore it.
> Only install this app if you accept that. Make a full backup before you start, and read [Turning YOLO off](#turning-yolo-off).

AI Agents adds an **AI Agents** panel to the sidebar. Each agent runs its own, unmodified command line tool in a real terminal. The agents can build dashboards, write automations, troubleshoot integrations and explain your setup.

| Tab | Agent | Made by | Sign-in |
| --- | --- | --- | --- |
| Claude Code | Claude Code CLI | Anthropic | Claude subscription, or an Anthropic API key |
| Codex | Codex CLI | OpenAI | ChatGPT account (device code), or an OpenAI API key |
| Gemini CLI | Gemini CLI | Google | Google account, or a Gemini API key |
| Muse Code | Muse Code CLI | Meta | Meta account, or a Meta API key |
| Shell | bash | | none, a root shell in the app |
| Files | upload and view images, drawings and PDFs | | |

This app is not made by, or affiliated with, Anthropic, OpenAI, Google or Meta. You need your own account or API key with each vendor, and their terms and prices apply.

## Permissions this app has
These are set by the app and cannot be lowered in the options. They are what makes the agents useful, and also what makes them risky.

| Permission | What it allows |
| --- | --- |
| Supervisor role `admin` (`hassio_role: admin`) | Everything the Supervisor can do: install, remove, start, stop and configure every app; create, download, restore and delete backups; update and restart Home Assistant Core, the OS and the Supervisor; change host network settings; reboot or shut down the host. |
| Home Assistant API (`homeassistant_api`) | Read and change every entity, device, area, automation, script, scene, helper, dashboard and integration, and call every action (lights, locks, alarms, heating …), as an administrator. |
| `/homeassistant` read/write | Your whole configuration, including `secrets.yaml` and `.storage` (logins, integration credentials). |
| `/addon_configs` read/write | The configuration folders of all apps. |
| `/share`, `/media`, `/ssl`, `/backup`, `/local_apps` read/write | Shared files, media, TLS certificates and keys, backup files, local app sources. |
| Network | Outgoing internet access (needed to reach the AI vendors). The app opens **no** ports; the panel is only reachable through Home Assistant. |
| Panel | Only Home Assistant **administrators** can open it. |

Inside the container the agents run as `root`. The agents' own OS sandboxes generally cannot start inside an app container and are switched off by the default arguments, so the container is the only boundary. The token the app uses to talk to Home Assistant (`SUPERVISOR_TOKEN`) is available to every agent and the shell.

## What leaves your Home Assistant
- **Everything you type, and everything an agent reads to answer you**, is sent to that agent's vendor. That includes configuration files, logs, entity states and, if an agent opens them, secrets. Each vendor's privacy terms apply. Some plans or modes let the vendor train on your conversations, so check your account settings.
- **Installs and updates.** The **Install** and **Update** buttons download each agent from its vendor (`claude.ai`, `dev.meta.ai`, the npm registry). Claude Code and Muse Code also update themselves.
- **Version check.** Every 6 hours the app asks the npm registry and Meta's update channel for the newest version numbers. No data about you is sent.
- **When the image is built:** Debian packages, Node.js from nodejs.org (checksum-verified), xterm.js from jsDelivr (checksum-verified) and the community skill from GitHub (pinned commit).

## First start
1. **Make a full backup** (Settings → System → Backups).
2. Start the app and open **AI Agents** in the sidebar. Read the notice and press **I understand**.
3. Pick a tab and press **Install**. The agent is downloaded into the app's storage (`/data`), so it survives restarts and app updates.
4. Sign in. The **Sign in** button is shown until the agent is signed in.
   - **Claude Code** and **Gemini CLI** ask you to sign in when they first start. Open the link they print, sign in, and paste the code back with Ctrl+V. On a phone, use the ⌨ bar.
   - **Codex:** press **Sign in**. It uses a device code, because the normal browser login cannot reach the container.
   - **Muse Code:** press **Sign in** and follow the link.
   - You can also use an API key instead (Settings or app options).
5. Ask for something, for example *"Make a nice dashboard for my living room"* or *"Why did my hallway automation not run last night?"*

## Using the panel
- **Conversations keep running** when you close the panel. Opening a tab continues the agent's last conversation, also after a restart of the app. Press **New conversation**, or use the agent's own command (e.g. `/clear`), to start fresh.
- **Typing while it works:** it is the real CLI, so slash commands, model pickers and interrupting (Esc / Ctrl+C) work as usual.
- **Copy:** select text with the mouse and it is copied when you let go. Right-click or Ctrl+C also copies a selection. Without a selection, Ctrl+C interrupts as usual.
  - Most agents take over the mouse. To select in their tabs, hold **Shift** while you drag.
  - **📋 Copy text** shows the whole terminal, scrollback included, as plain text. Select from it as on any web page, also with a long press on a phone, or copy everything or the last 50 lines.
- **Paste:** Ctrl+V. Ctrl+Shift+V and Shift+Insert also work. On a phone, use the ⌨ bar.
- **Update to x.y.z** appears when a newer version of an agent is published.
- **Files tab:** drop images, floor plans or PDFs there. They are stored in `/share/ai_agents_files/`, where every agent can read them, and agents save images they make there for you to view. Tick several files, or **Select all**, to download them as one zip or delete them together.
- **Settings (gear icon):** auto-compaction, start arguments, API keys and an optional Home Assistant token. Values set here are used instead of the app options. An empty field falls back to the app option, which is shown in grey. Changes apply to conversations started afterwards.

## What the agents are told
When the app starts, every agent gets the same house rules and Home Assistant skills.
- **House rules:**
  - Look before changing anything.
  - Back up files to `/share/ai_agents_backups/` before editing.
  - Validate the configuration, and reload instead of restarting.
  - Ask before restarts, deletions, installs and big changes.
  - Never reveal secrets, and do not operate devices just to test.
  - The rules are written to `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md` and `~/.config/muse/AGENTS.md` inside `/data`. Delete the first line of one of those files and the app stops overwriting it.
- **Skills:**
  - `home-assistant-best-practices`, from [homeassistant-ai/skills](https://github.com/homeassistant-ai/skills) (MIT).
  - `ha-dashboard-design`, `ha-api-recipes`, `ha-troubleshooting`, `ha-verify` and `ha-reporting`.
- **Tools:** `ha-api` (REST API of Core and the Supervisor) and `ha-ws` (WebSocket API). They use the app's Supervisor token. If you set your own long-lived token in Settings, they use that one and the agents act as that user.
- **Checking their own work:** the rules and the `ha-verify` skill tell every agent to check its result before it reports back: states, the config check, automation traces and logs.
  - For dashboards they use `ha-screenshot`. It opens the page in a headless browser inside the app and saves a picture, which the agent then looks at. It also reports failed cards, unavailable entities and script errors.
  - Screenshots appear in the **Files** tab, so you see what the agent saw.
  - `ha-screenshot` needs a long-lived access token: create one under your profile → Security → Long-lived access tokens, and paste it in Settings → Full-access token.
  - Claude Code, Gemini CLI and Codex can look at images. Check your Muse Code version for image support.

## Options
| Option | Default | Meaning |
| --- | --- | --- |
| `agents` | all four | Which agent tabs to show. |
| `claude_args` | `--dangerously-skip-permissions --model sonnet` | Command line arguments for Claude Code. |
| `codex_args` | `--dangerously-bypass-approvals-and-sandbox` | Command line arguments for Codex. |
| `gemini_args` | `--yolo` | Command line arguments for Gemini CLI. |
| `muse_args` | `--yolo` | Command line arguments for Muse Code. |
| `autocompact_tokens` | `400000` | Compact a conversation automatically at this many tokens (0 = each agent's own default). It only matters when the model's context window is larger. |
| `idle_compact_minutes` | `55` | Compact a conversation after this many quiet minutes, while the prompt cache is still warm (0 = off). Codex and Muse Code get `/compact` and Gemini CLI gets `/compress`, but only when something was said since the last compaction and nothing is half typed. Claude Code uses its own idle compaction (about an hour). |
| `anthropic_api_key`, `openai_api_key`, `gemini_api_key`, `meta_api_key` | empty | Optional API keys. Leave them empty to sign in with an account instead. |

## Turning YOLO off
Remove the flag from the agent's arguments, in the app options or on the Settings page, and start a new conversation:
- **Claude Code:** remove `--dangerously-skip-permissions`.
- **Codex:** remove `--dangerously-bypass-approvals-and-sandbox`.
- **Gemini CLI** and **Muse Code:** remove `--yolo`.

The agent then asks before it runs commands or edits files. Codex may also try to start its own sandbox, which can fail inside the container. In that case use `--sandbox danger-full-access --ask-for-approval on-request`.

This lowers the risk. It does not change the app's permissions: an approved command still runs with full access.

## Your data
- **`/data`** (included in backups of this app) holds the installed agents, their logins (OAuth tokens), conversations, `settings.json` with API keys you entered on the Settings page, and an optional Home Assistant token.
  - These files are readable only inside the app. Treat a backup of this app as containing secrets.
  - The installed agents make these backups large, often several hundred MB.
- **`/share/ai_agents_files`** holds files from the Files tab, and **`/share/ai_agents_backups`** holds the copies the agents make before editing. Neither folder is removed when you uninstall the app.
- **To sign an agent out:** use its own command (`/logout` or `logout`). To remove everything, uninstall the app.

## Troubleshooting
- **The app stops right after starting:** look at the app's log.
- **An agent does not start:** open its tab. The terminal shows the error and the exit code. **New conversation** starts it without trying to resume.
- **Sign-in link does not work:** copy the full link. Long links can be wrapped in the terminal, so use the selection with Ctrl+C.
- **For developers:** when the app is installed as a *local* app (`/local_apps/muse_code`), its `app/` and `skills/` folders are used instead of the copies in the image, so changes only need a restart. Apps installed from a repository always run the code in their image.
