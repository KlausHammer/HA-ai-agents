# Writing a small custom card

Write a custom card only when the built-in cards cannot do the job, even with visibility, features and markdown templates.

## Files and registration
1. Put the file in `/homeassistant/www/<name>.js`. It is served at `/local/<name>.js`.
2. Register it as a dashboard resource. This only works when dashboards are in storage mode:
   `ha-ws '{"type":"lovelace/resources/create","res_type":"module","url":"/local/<name>.js?v=1"}'`
   When you update the card, bump `?v=` with `lovelace/resources/update` (`resource_id`, `res_type`, `url`) so browsers load the new version.
3. Use it in a dashboard as `type: custom:<name>`.

## Skeleton (no build step, no external libraries)
```js
class MyCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) throw new Error('entity is required');
    this._config = config;
  }
  set hass(hass) {               // called on every state change: keep it cheap
    this._hass = hass;
    const st = hass.states[this._config.entity];
    if (!this._root) {
      this._root = this.attachShadow({ mode: 'open' });
      this._root.innerHTML = `<style>
        ha-card { padding: 16px; cursor: pointer; }
        .v { font-size: 2em; color: var(--primary-text-color); }
        .n { color: var(--secondary-text-color); }
      </style><ha-card><div class="n"></div><div class="v"></div></ha-card>`;
      this._root.querySelector('ha-card').addEventListener('click', () => {
        this.dispatchEvent(new CustomEvent('hass-more-info', { bubbles: true, composed: true,
          detail: { entityId: this._config.entity } }));
      });
    }
    this._root.querySelector('.n').textContent = st?.attributes.friendly_name ?? this._config.entity;
    this._root.querySelector('.v').textContent = st ? `${st.state} ${st.attributes.unit_of_measurement ?? ''}` : 'unavailable';
  }
  getCardSize() { return 2; }
  getGridOptions() { return { columns: 6, rows: 2, min_columns: 3 }; }  // size in sections views
  static getStubConfig(hass) { return { entity: Object.keys(hass.states)[0] }; }
}
customElements.define('my-card', MyCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: 'my-card', name: 'My card', description: 'Shows one entity' });
```

## Rules
- Use HA CSS variables so the card follows light and dark themes: `--primary-text-color`, `--secondary-text-color`, `--card-background-color`, `--primary-color`, `--divider-color`, `--state-icon-color`.
- In `set hass`, render only what changed. Never rebuild the whole DOM each time, and never call APIs from it in a loop.
- Call services with `this._hass.callService(domain, service, data)`.
- Fetch history with `this._hass.callWS({type: 'history/history_during_period', ...})`, but sparingly, and cache the result.
- Escape any text you put into `innerHTML`, or set `textContent` instead.
- After a change, tell the user to hard-refresh (or bump `?v=`) and to check the browser console for errors.
