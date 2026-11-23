---
name: ha-reporting
description: How to present results, plans and findings to the user clearly - short summaries, tables, before/after, rollback steps, and readable terminal output. Use at the end of every task and whenever you propose a plan or explain something about their Home Assistant.
---

# Presenting work clearly

The user reads your answer in a terminal panel, often on a phone. Make it easy to skim.

## Shape of a final answer
1. **One-line result first.** Say what is now true, e.g. "The kitchen dashboard now has a Climate section with all 4 thermostats."
2. **What changed.** A short list with exact names: files, dashboards, automations, entity ids.
3. **How to check it and how to undo it.** Where to click to see the change, and the backup path or the reverse command.
4. **Open points, only if there are any.** What you did not do and why, or a question that needs an answer.

## Style
- Use plain words. Skip filler and repeated summaries, and lead with the answer, not the process.
- Use the user's names for things (friendly names, area names). Show the entity id in `code` the first time you mention it.
- Use tables only for real comparisons or inventories. Keep them to about 4 columns with short cells, so they fit in about 100 characters.
- Give numbers with units and sensible rounding ("21.5 °C", "3.2 kWh"). Give times in the user's local time.
- Never paste secrets, long logs or whole configs. Quote only the 3–10 lines that matter.
- When something failed, say so plainly and give the error. Then say what you tried and what you suggest.

## Plans
- Present a bigger change as a numbered plan that says what will change.
- Mark anything risky: a restart, a deletion, or an action on a device.
- Wait for approval before you carry it out.
