# Changelog

## 0.3.1
- The agents can check their own work:
  - New `ha-screenshot` tool: opens any Home Assistant page in a headless browser (Chromium, now part of the image) and saves a PNG in the Files tab.
  - It reports failed cards, unavailable entities and script errors. Options: phone size, full page, dark or light.
  - It needs a long-lived token in Settings.
  - New `ha-verify` skill, and a house rule that tells every agent to check its result before it reports back: screenshots for dashboards (and to look at the image), and states, the config check, automation traces and logs for everything else.
- The published images are named per architecture (`ghcr.io/klaushammer/{arch}-ha-ai-agents`).

## 0.3.0
- Ready for a public repository: icon and logo, and a description and documentation that list every permission, what is sent to the AI vendors, and that the agents act without confirmation by default.
- A notice about YOLO mode and full access is shown the first time the panel is opened.
- Easier copying from the terminals:
  - Selected text is copied when you release the mouse, and right-click copies too.
  - When an agent has taken over the mouse, a hint says to hold Shift while dragging.
  - New **📋 Copy text** button: the whole terminal as plain text, to select from (also on phones) or copy in full.
- Files tab: select several files, or all of them, and download them as one zip or delete them together.
- Settings page (gear icon, top right): auto-compact, idle compaction, start arguments, API keys and an optional Home Assistant token.
  - Values set there are used instead of the app options. An empty field falls back to the app option, which is shown in grey.
  - With a token set, `ha-api` and `ha-ws` act as that user. The address is detected from Home Assistant, including the port and https.
- Fixed: the app would not start when a folder or a backup copy was left in `app/bin`.
- Agents now back up files to `/share/ai_agents_backups/` instead of next to the original, and Python no longer writes `__pycache__` folders.
- Interrupted uploads in the Files tab no longer leave a half file behind.
- Requests from other web sites are refused.
- The local source folder only overrides the built-in code when the app is installed as a local app.
- The image pins xterm.js (checksum-verified) and the community skill (fixed commit).
- The default Muse Code arguments are now only `--yolo`, with no fixed model.

## 0.2.3
- New option `idle_compact_minutes` (default 55). After that many quiet minutes, the app sends Muse Code and Codex `/compact` and Gemini CLI `/compress`, while the prompt cache is still warm.
  - It only does this when something was said since the last compaction and nothing is half typed.
  - Claude Code uses its own idle compaction (about an hour, before its cache expires), applied from 100k tokens.
- Copy and paste in every terminal: Ctrl+C copies selected text (without a selection it still interrupts), Ctrl+V pastes. Ctrl+Shift+C/V and Ctrl/Shift+Insert also work.

## 0.2.2
- Opening an agent continues its last conversation, also after a restart of the app. If there is nothing to continue, a new conversation starts. Use **New conversation** to start fresh.
- New option `autocompact_tokens` (default 400000), applied to all agents:
  - Claude Code: `CLAUDE_CODE_AUTO_COMPACT_WINDOW`
  - Codex: `model_auto_compact_token_limit`
  - Gemini CLI: `model.compressionThreshold`
  - Muse Code: `context_compaction.soft_threshold`

## 0.2.1
- Full access (Supervisor role admin, all folders) and YOLO mode for every agent by default.
- Fixed: after reloading the page, the terminal answered old queries from the scrollback and that text ended up in the prompt.
- A newly loaded page cannot type into the terminals during its first second.
- Sign in is only shown until an agent is signed in. Update is only shown when a newer version is published (checked every 6 hours). The Stop button is removed; quit an agent with its own exit command.
- Default models: Muse Code muse-spark-1.3-contributor, Claude Code sonnet.

## 0.2.0
- Renamed to **AI Agents**.
- Muse Code, Claude Code, Gemini CLI and Codex each have their own tab with the real interactive CLI. The terminals keep running when the panel is closed, and you can type while an agent works.
- The agents are installed from the panel into `/data`, so they persist across restarts and updates. Each tab has buttons to start, resume, sign in and update.
- Every agent gets the same house rules and Home Assistant skills, including the community best-practices skill.
- Added the `ha-api` and `ha-ws` helper commands.
- The panel is in English, has a light and dark theme, and on phones has an extra key bar and a box for pasting text.

## 0.1.0
- First version: a chat panel for Muse Code.
