# Cowork API — Building HTML Artifacts

When building HTML dashboards or artifact UIs that call CareerPlug MCP tools,
use the `window.cowork` API. This runs inside the artifact sandbox, not in the
MCP server itself.

---

## `window.cowork.callMcpTool(name, args)`

Calls any connected MCP tool and returns the result. This is how an artifact
fetches live data from CareerPlug (or any other connected MCP server).

```js
const result = await window.cowork.callMcpTool(
  "mcp__careerplug__list_applicants",
  { status: "active", per_page: 50 }
);
```

**Required:** every tool name used here must be declared in the artifact's
`mcp_tools` list when the artifact is created or updated. Undeclared tools
will be blocked at runtime.

---

## `window.cowork.askClaude(prompt, data[])`

Runs a fast AI inference call (Haiku) over data you've already fetched. Use
it for summaries, classifications, rankings, or any natural-language
processing you don't want to hard-code.

```js
const summary = await window.cowork.askClaude(
  "Rank these applicants by experience level",
  [applicant1, applicant2, applicant3]
);
```

---

## `window.cowork.runScheduledTask(taskId)`

Triggers one of your scheduled tasks by ID. Must be invoked from a user
gesture (e.g. a button click) — it will not fire automatically on page load.

```js
button.addEventListener("click", () => {
  window.cowork.runScheduledTask("your-task-id");
});
```

---

## CDN Constraints

The artifact sandbox only allows these CDN libraries:

- **Chart.js** — charts and graphs
- **Grid.js** — data tables
- **Mermaid** — diagrams

**Tailwind CDN is blocked.** Use inline `style` attributes or a `<style>` block
for all layout and styling — do not load Tailwind or any other CSS framework
from a CDN.
