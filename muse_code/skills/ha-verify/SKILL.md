---
name: ha-verify
description: Check your own work in Home Assistant before you report back - see a dashboard as the user sees it with ha-screenshot (then look at the image), confirm states and attributes, run the config check, read automation traces and the logs. Use after every change, and whenever you claim that something works.
---

# Check your own work

You can see and test what you made. Do it before you say "done", and tell the user what you checked.

## Dashboards and anything visual
1. Take a screenshot: `ha-screenshot /<dashboard-url>/<view-path>`
   - Add `--mobile` to check the phone layout, `--full` for the whole view, and `--dark` or `--light` for a theme.
   - Find the URL with `ha-ws '{"type":"lovelace/dashboards/list"}'`. The default dashboard is `/lovelace/<view path or index>`.
2. **Look at the PNG** with your image or file reading tool:
   - Claude Code: read the file.
   - Gemini CLI: `read_file`, or `@/path/file.png`.
   - Codex: its image viewing tool.
   - Check alignment, empty or cut-off cards, unreadable text, wrong icons, and whether it looks good on a phone.
3. Read the report it prints:
   - `CARD ERROR`: a card failed, for example a missing custom card, wrong YAML or a wrong type.
   - `WARNING`: an entity is not available, or the id is wrong.
   - `JS ERROR`: scripts failed.
   - Exit code 1 means there were errors on the page. Fix them and take a new screenshot.
4. The screenshot is saved in `/share/ai_agents_files/`. Tell the user they can see it in the **Files** tab.
5. `ha-screenshot` needs the user's long-lived token, set in the app's Settings. Without one, it says how to get one. Ask the user once, and meanwhile check the dashboard config with `ha-ws` (are all entities there, are all custom cards installed?).

## Entities, helpers, scenes, scripts
- `ha-api GET /api/states/<entity_id> | jq '{state, attributes}'` after the change.
- For new entities, check that they exist and are not `unavailable`: `ha-api GET /api/states | jq -r '.[] | select(.state=="unavailable") | .entity_id'`.

## Configuration (YAML)
- `ha-api POST /api/config/core/check_config` must say `valid`. Then reload the domain and confirm the change is live (state, or the entity in the registry).

## Automations
- After saving: `ha-api POST /api/services/automation/reload`, then `ha-api GET /api/states/automation.<id>` must exist and be `on`.
- To test without operating real devices, run the actions only when the user agrees: `ha-api POST /api/services/automation/trigger '{"entity_id":"automation.<id>","skip_condition":false}'`.
- Read what happened: `ha-ws '{"type":"trace/list","domain":"automation","item_id":"<id from automations.yaml>"}'`, then `ha-ws '{"type":"trace/get","domain":"automation","item_id":"<id>","run_id":"<run_id>"}'`. The trace shows which trigger fired, which condition stopped it, and the error of each step.

## Integrations and apps
- Config entries: `ha-ws '{"type":"config_entries/get"}' | jq '.[] | select(.state!="loaded") | {domain,title,state,reason}'`.
- Logs after the change: `ha-api GET /core/logs | tail -80`, or `/addons/<slug>/logs` for an app. Look for new errors that mention what you changed.

## Report
Say what you checked and what you saw ("Screenshot on phone size: 3 sections, no card errors; the thermostat card shows 21.5 °C"). If you could not check something, say so.
