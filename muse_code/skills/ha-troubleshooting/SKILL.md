---
name: ha-troubleshooting
description: Systematic troubleshooting of Home Assistant problems - unavailable entities, failing automations, integration errors, Zigbee/Z-Wave/Matter/Wi-Fi devices, slow or broken dashboards, high CPU or database growth. Use when something "does not work" or the user reports an error.
---

# Troubleshooting Home Assistant

Work from evidence:
1. Reproduce the symptom, or find where it shows.
2. Read the logs.
3. Form one hypothesis and test it.
4. Change one thing at a time.

## 1. Collect facts
- **Ask:** what exactly fails, since when, and after which change (an update, a new device, edited YAML)?
- **The entity:** `ha-api GET /api/states/<entity_id>` shows its state, `last_changed`, `last_updated` and attributes.
- **Repairs and errors:** `ha-ws '{"type":"repairs/list_issues"}'` and `ha-ws '{"type":"system_log/list"}'` (errors deduplicated, with counts).
- **The log:** `ha-api GET /core/logs | tail -n 300`, filtered for the integration with `grep -i <domain>`.
- **Versions:** `ha-api GET /core/info`, `ha-api GET /supervisor/info`, `ha-api GET /os/info`.

## 2. By symptom

### An automation did not run, or did the wrong thing
- List its runs with `ha-ws '{"type":"trace/list","domain":"automation","item_id":"<id>"}'`.
- Open one run with `ha-ws '{"type":"trace/get","domain":"automation","item_id":"<id>","run_id":"<run_id>"}'`. It shows which trigger fired, which condition stopped it, and which action failed.
- Check the `mode` (`single` drops new runs while one is running), whether the automation is disabled, and whether entity ids have changed.

### An entity is unavailable
- Is its entry in the device registry disabled?
- Is the config entry loaded? Look at the `state` field in `config_entries/get`.
- Reload the integration (`homeassistant.reload_config_entry`) before trying anything bigger.
- For radio devices:
  - Check the coordinator or controller app logs (`ha-api GET /addons/<slug>/logs`).
  - Check when the device was last seen, its link quality and its battery.
  - Most Zigbee range problems are fixed by a mains-powered router near the device.
  - Channel conflicts with Wi-Fi are common. Zigbee channels 15, 20 and 25 avoid most Wi-Fi channels.

### An integration fails to set up
- Read the log lines from `homeassistant.config_entries` and from the integration's domain.
- Check the credentials.
- Check that the device or service is reachable: run `curl -sv http://<ip>:<port>` from the Shell tab.
- Consider rate limits, and API changes after an update (check the release notes).

### YAML or config errors
- Run `ha-api POST /api/config/core/check_config`, fix the file and line it reports, then reload.

### Performance or disk
- **Database size:** `du -h /homeassistant/home-assistant_v2.db`.
  1. Exclude chatty entities in `recorder:`.
  2. Lower `purge_keep_days`.
  3. Run `recorder.purge` with `repack: true` (ask first).
- **CPU:**
  - Check `ha-api GET /core/stats` and `ha-api GET /addons/<slug>/stats`.
  - Look for template sensors that use `now()` or iterate over huge `states` lists.
  - Look for integrations that poll too often.

### A dashboard is broken, or says "Custom element doesn't exist"
The resource is missing or failed to load.
- Check `ha-ws '{"type":"lovelace/resources"}'`.
- Check the file under `/homeassistant/www` or the HACS install.
- Ask the user to hard-refresh and look at the browser console.

## 3. Fix and confirm
1. Back up, make one change, and reload.
2. Check the original symptom and the logs again.
3. Tell the user the cause, the fix, and what to watch for.

If you could not find the cause, say what you ruled out and what evidence would help next. One option is debug logging: `ha-api POST /api/services/logger/set_level '{"custom_components.x":"debug"}'`.
