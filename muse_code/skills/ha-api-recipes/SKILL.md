---
name: ha-api-recipes
description: Exact commands for reading and changing Home Assistant from this app with ha-api and ha-ws - entities, devices, areas, helpers, automations, scripts, scenes, dashboards, integrations, backups and logs. Use whenever you need to inspect or change Home Assistant state or configuration.
---

# Home Assistant API recipes

- `ha-api` is REST: Core under `/api/...`, the Supervisor otherwise.
- `ha-ws` is WebSocket.
- Both use `$SUPERVISOR_TOKEN`, or the user's own token when one is set on the app's settings page.
- Pipe output through `jq` to keep it small, e.g. `ha-api GET /api/states | jq -r '.[].entity_id' | grep '^light\.'`

## Read
| What | Command |
| --- | --- |
| All states / one state | `ha-api GET /api/states`, `ha-api GET /api/states/<entity_id>` |
| Entity registry (names, areas, disabled, platform) | `ha-ws '{"type":"config/entity_registry/list"}'` |
| Devices / areas / floors / labels | `config/device_registry/list`, `config/area_registry/list`, `config/floor_registry/list`, `config/label_registry/list` |
| Integrations (config entries) | `ha-ws '{"type":"config_entries/get"}'` |
| Services and their fields | `ha-api GET /api/services` |
| Template (often the quickest answer) | `ha-ws '{"type":"render_template","template":"{{ area_entities(\"Kitchen\") }}"}'` |
| History | `ha-api GET "/api/history/period/<ISO start>?filter_entity_id=<id>&minimal_response"` |
| Long-term statistics | `ha-ws '{"type":"recorder/statistics_during_period","start_time":"<ISO>","statistic_ids":["<id>"],"period":"day"}'` |
| Logs | `ha-api GET /core/logs`, `ha-ws '{"type":"system_log/list"}'`, `ha-api GET /addons/<slug>/logs` |
| Repairs | `ha-ws '{"type":"repairs/list_issues"}'` |
| Config and version | `ha-api GET /api/config`, `ha-api GET /core/info` |

## Change

### Services, entities, devices and areas
- **Call a service:** `ha-api POST /api/services/<domain>/<service> '{"entity_id":"<id>", ...}'`. Add `?return_response` for services that return data, e.g. `weather.get_forecasts`.
- **Rename or move an entity:** `ha-ws '{"type":"config/entity_registry/update","entity_id":"<id>","name":"New name","area_id":"kitchen"}'`.
  - `new_entity_id` changes the id itself. Ask first, because it breaks references.
  - Devices: `config/device_registry/update` with `device_id`.
- **Areas:** `config/area_registry/create` (`name`), and `config/area_registry/update` (`area_id`, `name`, `icon`, `floor_id`).

### UI automations, scripts and scenes
UI automations are stored in automations.yaml, each with an `id`.
- **Read:** `ha-api GET /api/config/automation/config/<id>`
- **Create or replace:** `ha-api POST /api/config/automation/config/<id> '<json config>'`. Choose a new unique id for a new automation. It reloads by itself.
- **Delete:** `ha-api DELETE /api/config/automation/config/<id>`. Ask first.
- **Trace of the last runs:** `ha-ws '{"type":"trace/list","domain":"automation","item_id":"<id>"}'`
- **Scripts and scenes** use the same pattern: `/api/config/script/config/<key>` and `/api/config/scene/config/<id>`.

### Helpers
- These helpers are managed over WebSocket: input_boolean, input_number, input_select, input_text, input_datetime, input_button, counter, timer and schedule.
  - Commands: `ha-ws '{"type":"<domain>/list"}'`, `<domain>/create`, `<domain>/update` (with `<domain>_id`), and `<domain>/delete`.
- Template, group, utility_meter and derivative helpers are config-entry helpers. Create them in the UI or with `config_entries/flow`, and ask the user if unsure.

### Dashboards
- `lovelace/config` reads a config (`url_path`, where `null` = the default dashboard), and `lovelace/config/save` writes it.
- `lovelace/dashboards/create` creates a dashboard. It takes `url_path` (must contain a hyphen), `title`, `icon`, `show_in_sidebar` and `require_admin`.
- `lovelace/resources` lists the custom card resources.

### Reload instead of restart
- By domain: `automation.reload`, `script.reload`, `scene.reload`, `group.reload`, `input_*.reload`, `template.reload`.
- Whole config: `homeassistant.reload_core_config`, `homeassistant.reload_all`.
- One integration: `ha-api POST /api/services/homeassistant/reload_config_entry '{"entry_id":"<id>"}'`.

### YAML changes
1. Back up the file and make the edit.
2. Run `ha-api POST /api/config/core/check_config`. It must report `valid`.
3. Reload the domain.
4. Restart (`ha-api POST /api/services/homeassistant/restart`) only after the user agrees.

## Backups
- **Quick file backup** (outside the folder, so nothing loads the copy): `f=/homeassistant/automations.yaml; B=/share/ai_agents_backups/$(date +%Y%m%d-%H%M); mkdir -p "$B$(dirname "$f")" && cp -a "$f" "$B$f"`
- **Full Home Assistant backup** takes a while, so ask first. Newer HA: `ha-api POST /api/services/backup/create_automatic`. Otherwise: `ha-api POST /api/services/hassio/backup_partial '{"homeassistant":true,"name":"before changes"}'`.

## Gotchas
- Entity ids can change when devices are renamed. Always list them again instead of reusing old ids.
- `.storage/*` files are owned by Home Assistant. Read them if you must, but never write them while it runs.
- `unavailable` or `unknown` states are normal for a moment after a reload. Check again before you conclude anything.
- With large outputs, filter with `jq` or templates instead of dumping thousands of lines.
