---
name: ha-dashboard-design
description: Design and build good-looking, usable Home Assistant dashboards (Lovelace). Use when creating, redesigning or polishing a dashboard, view, card layout, theme, or a custom card, or when the user asks for something to "look nice".
---

# Dashboard design for Home Assistant

## Workflow
1. **Inventory first.** List the dashboards (`ha-ws '{"type":"lovelace/dashboards/list"}'`) and read the current config (`ha-ws '{"type":"lovelace/config","url_path":"<path or null>"}'`). Check the installed custom cards (`ha-ws '{"type":"lovelace/resources"}'`), plus areas, devices and entities. Use only cards that are installed. You may suggest HACS cards, but do not assume they are there.
2. **Save the old config** to `/share/ai_agents_backups/dashboards/<path>-<timestamp>.json` before you change it.
3. **Sketch the structure** in your reply when the change is big (views, sections, what goes where), and agree it with the user.
4. **Write the new config** and save it with `ha-ws '{"type":"lovelace/config/save","url_path":"<path>","config":{...}}'`. Pipe large JSON through `ha-ws -`. A dashboard in YAML mode is edited in its YAML file instead.
5. **Verify.** Read the config back and check that every entity id exists (`ha-ws '{"type":"config/entity_registry/list"}'` or `ha-api GET /api/states`). Then ask the user to look at it on both a phone and a desktop.

## Layout principles
- **View type.** Use the **sections** view type (`type: sections`, `max_columns: 3` or `4`) for most views. It reflows on phones and keeps a consistent grid. Use `panel` for one big card, such as a map or floor plan. Use `masonry` only for legacy configs.
- **One view per purpose** (Overview, Climate, Energy, Media, Security), or one per floor or area in big homes. Put the most-used controls in the first section of the first view.
- **Hierarchy.** Give each section a `heading` card, then the primary controls, then the details. Group by area or by task, not by device type.
- **Show state, hide noise.**
  - Prefer `tile` cards with `features` (brightness, cover position, climate HVAC modes, fan speed) over many separate buttons.
  - Hide diagnostic and config entities.
  - Use `visibility` conditions (state, screen width, user) so things show only when relevant. For example, show a "washing machine done" tile only while it is done.
- **Badges** go at the top of a view for at-a-glance status (people, alarm, weather, warnings). Don't use them for controls.
- **Consistency.** Use the same card type for the same kind of thing and the same icon family (mdi). Name things the same way ("Kitchen light", not "kitchen_light_2"). Set friendly names in the entity registry instead of overriding names in every card.
- **Colour means something.** Rely on the theme and state colours. Add your own colours only when they carry meaning (red = needs attention). Never colour everything.
- **Mobile first.** Test at about 390 px width. Avoid long text, tiny tap targets, and horizontal stacks of more than 2–3 items. `grid_options` (columns/rows) controls size in sections.
- **Graphs.**
  - Trends: use `history-graph` or `statistics-graph` with a sensible `hours_to_show` or period.
  - Energy: use the energy cards.
  - Long ranges: use `statistics-graph`, because history is purged after the recorder's keep days.

## Which card to use
| Need | Card |
| --- | --- |
| A light, switch, cover, fan, lock or climate | `tile` with `features` |
| Several related entities in a compact list | `entities` (with section rows and `secondary_info`) |
| A single number to watch | `tile`, or `gauge` if there is a meaningful min and max |
| Trend over time | `history-graph`, `statistics-graph` |
| Room overview with a picture | `area` |
| Weather | `weather-forecast` |
| Camera | `picture-entity` / `picture-glance` |
| Notice shown only under some condition | any card with `visibility`, or `conditional` |
| Free text or instructions | `markdown` (supports templates) |

## Themes
- Themes live in `themes/`. configuration.yaml needs `frontend: themes: !include_dir_merge_named themes`, and you reload them with `frontend.reload_themes`.
- Change a few CSS variables (`primary-color`, `accent-color`, `card-background-color`, `ha-card-border-radius`, `ha-card-box-shadow`) rather than everything.
- Offer both light and dark `modes`.
- Do not make a theme the user's default without asking.

## Custom cards
If no built-in card can do the job, read `references/custom-cards.md` and write a small custom card with no dependencies.

## Done means
- Every entity exists, and nothing shows "Entity not available".
- The phone layout works.
- The old config is saved.
- You told the user how to roll back.
