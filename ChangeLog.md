# Claude Code Changes — privateAI-demo

---

## Change Set 51 — Fix alert routing always falling through to docs; add VCF Ops status badge

**Date:** 2026-06-30
**Branch:** `main`

### Problem

Asking "check my lab for alerts" (or any operational prompt) always routed to the VCF documentation path, never calling the Aria Ops API.

### Root cause

`_VCF_OPS_CONFIGURED = bool(os.getenv("VCF_OPS_URL"))` was evaluated **once at module load time**. If `VCF_OPS_URL` was not present in the environment at that exact moment (e.g. the var was set in a different shell, or after the process started), the constant was permanently `False`. The routing guard `and (_VCF_OPS_CONFIGURED or _last == "alert")` then blocked every alert query for the entire lifetime of the process.

### Fix

#### `ui/ui-app.py`

- Removed module-level `_VCF_OPS_CONFIGURED` constant.
- In `_generate_response`, evaluate `_vcf_ops_configured = bool(os.getenv("VCF_OPS_URL"))` at routing time so it always reflects the current process environment.
- Added **🟢 VCF Ops connected / ⚪ VCF Ops not configured** status badge to the top toolbar (fourth column), making it immediately visible whether the env var is being picked up.

---

## Change Set 50 — Fix stale OpsToken causing permanent auth failure on live alerts

**Date:** 2026-06-30
**Branch:** `main`

### Problem

After several hours of running, all live-alert and licence queries silently failed — the app returned a cached 401 error and the LLM responded with an auth failure message instead of live data. Restarting Streamlit was the only workaround.

### Root causes

| # | Bug | Location |
|---|---|---|
| 1 | `_acquire_ops_token_sync` never cleared `_ops_token_ui` when the OpsToken expired. `if _ops_token_ui:` short-circuited every call, returning the stale dead token. | `ui-app.py` |
| 2 | `fetch_lab_alerts` and `fetch_license_info` were decorated with `@st.cache_data`. When a call failed (e.g. 401 from the alerts endpoint), the error tuple `([], "HTTP 401 — ...")` was cached for the full TTL (120 s). Every retry within that window returned the cached failure without hitting the network. | `ui-app.py` |

### Fix

**`_acquire_ops_token_sync`** — added `force: bool = False` parameter. When `force=True`, `_ops_token_ui` is cleared before re-authenticating. Callers pass `force=True` after a 401.

**`fetch_lab_alerts`** — split into two functions:
- `_fetch_alerts_cached(severity)` — decorated with `@st.cache_data`; **raises** exceptions instead of returning error tuples, so `@st.cache_data` never stores failures; includes automatic 401 retry (clear stale token → re-authenticate → retry request).
- `fetch_lab_alerts(severity)` — public wrapper; catches exceptions from `_fetch_alerts_cached` and converts them to the original `(alerts, error)` tuple. Only successful alert lists are cached.

**`fetch_license_info`** — same raise-on-error / wrapper pattern applied:
- `_fetch_license_cached()` raises on error (never cached on failure).
- `fetch_license_info()` wraps and converts exceptions.

---

## Change Set 49 — Fix alert queries returning VCF Architect-style responses

**Date:** 2026-06-30
**Branch:** `main`

### Problem

Asking "check my lab for alerts" (or any operational prompt) returned a response written in a VCF Architect tone — e.g. architecture recommendations — instead of summarising live alert data. The alert data was fetched correctly, but the LLM persona was wrong.

### Root cause

`_generate_response()` in `ui-app.py` always set the same system prompt regardless of routing:
```
"You are a Senior VCF {version} Architect. Answer using only the context provided below..."
```
Even when `is_alert_query = True` and alert data was injected into the context, the architect persona biased the model to respond with architectural content.

### Fix

`ui/ui-app.py` — `_generate_response()` system prompt now branches on query type:

| Query type | Persona |
|---|---|
| `is_alert_query` | VCF Operations monitoring assistant — summarises alerts, groups by severity, suggests remediation |
| `is_license_query` | VCF Operations licensing assistant — reports licence status from live data |
| docs (default) | Senior VCF {version} Architect — unchanged |

---

## Change Set 48 — Live licence status query in UI chat

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `4f3d130`

### What was added

| Component | Change |
|---|---|
| `fetch_license_info()` | New cached sync function in `ui-app.py`; calls `GET /suite-api/api/product/licensing/info` and `GET /suite-api/api/product/licensing/edition`, merges results, converts epoch ms expiry to `YYYY-MM-DD` |
| `_is_license_query()` | New routing helper; triggers on any prompt containing "licens" or "edition" |
| `_generate_response()` | Third routing path added (priority: licence > alert > RAG); sets `last_query_type = "license"` for follow-up continuity |

### User experience

Ask the chatbot any of:
- *"What's our licence status?"*
- *"Which edition are we running?"*
- *"Is VCF Operations licensed?"*
- *"When does the licence expire?"*

The UI surfaces a structured block before the LLM response:

```
VCF Operations licence:
- Status: ✅ Licensed
- Edition: ENTERPRISE
- Licence name: VCF Operations Enterprise
- Expires: 2027-03-15
```

### Endpoints used

| Endpoint | Response field(s) |
|---|---|
| `GET /suite-api/api/product/licensing/info` | `licensed`, `licenseName`, `expirationDate` (epoch ms) |
| `GET /suite-api/api/product/licensing/edition` | `productLicensingEdition` (enum: NOT_LICENSED / CORE / STANDARD / ADVANCED / ENTERPRISE / UNKNOWN) |

---

## Change Set 47 — Enhance MCP get_lab_alerts: all severities, icons, summary header

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `bacc64b`

### Problem

Claude Desktop was defaulting to calling `get_lab_alerts(severity="CRITICAL")` for general health questions, silently filtering out IMMEDIATE, WARNING, and INFORMATION alerts.

### Root causes fixed

| # | Issue | Fix |
|---|---|---|
| 1 | Tool docstring didn't tell the LLM when to omit `severity` | Added an `IMPORTANT` paragraph at the top: call with no arguments for any general health query; only filter if the user explicitly asks for one severity level |
| 2 | Output had no severity per line | Each alert line now starts with icon + `[CRITICALITY]` — the LLM can distinguish and group without re-calling the tool |
| 3 | No total count or severity breakdown | Added a header line: `"Active alerts: N total (X CRITICAL, Y WARNING …)"` |
| 4 | Hardcoded `[:5]` limit | Replaced with `config.MAX_ALERTS` in both the resource-resolution loop and the format loop |

### Output format (before → after)

**Before:**
```
- esxi-01.lab.local: CPU Ready Time Too High
- vcenter.lab.local: Certificate Expiring Soon
```

**After:**
```
Active alerts: 8 total (2 CRITICAL, 3 IMMEDIATE, 2 WARNING, 1 INFORMATION) — showing first 10

🔴 [CRITICAL] esxi-01.lab.local: CPU Ready Time Too High
🟠 [IMMEDIATE] vcenter.lab.local: Certificate Expiring Soon
🟡 [WARNING] vsan-cluster: Disk Latency High
🟢 [INFORMATION] nsx-manager: Backup Completed
```

---

## Change Set 46 — Update README for toolbar/popover layout and cost shadow

**Date:** 2026-06-27
**Branch:** `main`

### What was changed

#### `README.md`
- Features section rewritten to reflect toolbar-first layout (no sidebar)
- Added **Full-width chat** bullet describing the top toolbar and Settings popover
- Updated Version selector, theme toggle, and cloud cost shadow bullets to reference the new popover/toolbar locations
- Per-message cost estimate (`~$X.XXXX`) mentioned in the cost shadow bullet

---

## Change Set 45 — Fix Settings popover button styling in both themes

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `8923034`

### What was changed

#### `ui/themes.py`
- Merged `[data-testid="stPopoverButton"]` into the existing button selector group (`.stButton > button`, `[data-testid="stBaseButton-secondary"]`) instead of a separate block
- Separate isolated block was losing specificity battles against Streamlit's own primary-button fill in light mode (dark blue background, unreadable text)
- Added `[data-testid="stPopoverButton"] p, span { color: inherit }` to prevent the global `span` rule from overriding button text colour
- Removed the now-redundant standalone `st.popover trigger button` CSS section

---

## Change Set 44 — Replace sidebar with top-toolbar + popover for full-width chat

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `87df02c`

### What was changed

#### `ui-app.py`
- Removed `with st.sidebar:` block entirely
- Added a compact top toolbar using `st.columns([1, 1, 2, 6])`:
  - **🗑️ Clear** — clears chat history and token counters
  - **☀️ / 🌙** — toggles light/dark theme
  - **⚙️ Settings** — `st.popover` containing VCF Version, Brain (LLM), Answer style, cloud cost shadow rates, and session token summary
- All settings widgets use `key=` so values persist in `st.session_state` between reruns (popover widgets only render when open)
- Session state keys `selected_version`, `selected_model`, `temp_label` initialised in the session state init block
- `selected_version`, `selected_model`, and `temp` read from session state after the toolbar block — rest of the code unchanged

---

## Change Set 43 — Show per-message cost estimate in token caption

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `9703daa`

### What was changed

#### `ui-app.py`
`_token_caption` now appends `~$X.XXXX` to each assistant message's token line. The cost is calculated from the message's prompt and completion token counts multiplied by the rates stored in `st.session_state` (`rate_input` / `rate_output`) — the same values set by the sidebar inputs. Session state keys are pre-initialised from `config` defaults so the caption renders correctly on first load before the sidebar has been drawn.

---

## Change Set 42 — Update README for alerts icons, cost shadow, and new config vars

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `c1a2ae9`

### What was changed

#### `README.md`
- Live alerts feature bullet expanded with traffic-light icon legend (🔴🟠🟡🟢) and example natural-language prompts
- Added cloud cost shadow feature bullet
- Configuration table extended with `MAX_ALERTS`, `ALERT_CACHE_TTL`, `UI_PAGE_TITLE`, `UI_PAGE_ICON`, `UI_COST_PER_1M_INPUT`, `UI_COST_PER_1M_OUTPUT`

---

## Change Set 41 — Cloud cost shadow estimate in sidebar

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `77c4b76`

### What was changed

#### `config.py`
- `UI_COST_PER_1M_INPUT` (env override, default `$0.15`) — input token rate
- `UI_COST_PER_1M_OUTPUT` (env override, default `$0.60`) — output token rate
- Defaults approximate GPT-4o mini pricing, a fair cloud equivalent for a 14B-class local model

#### `ui-app.py`
- Two number inputs in the sidebar ("Input $/1M tokens", "Output $/1M tokens") under a "Cloud cost shadow" label — editable live
- Session token counter now appends `~$X.XXXX cloud equivalent` calculated from prompt × input rate + completion × output rate
- Actual Ollama cost is always $0; this is a reference comparison only

---

## Change Set 40 — Externalise page title and icon to config.py

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `c64e656`

### What was changed

#### `config.py`
- `UI_PAGE_TITLE` (env `UI_PAGE_TITLE`, default `"🦅 Hawk - VCF vArchitect Agent"`)
- `UI_PAGE_ICON` (env `UI_PAGE_ICON`, default `"🛡️"`)

#### `ui-app.py`
- `st.set_page_config` and `st.title` now reference `config.UI_PAGE_TITLE` / `config.UI_PAGE_ICON`. No hardcoded branding strings remain in the UI file.

---

## Change Set 39 — Move _SEVERITY_ICON and _TEMP_OPTIONS to config.py

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `097f184`

### What was changed

#### `config.py`
- `UI_SEVERITY_ICON` — severity → emoji mapping for alert display
- `UI_TEMP_OPTIONS` — answer-style label → temperature value presets for the sidebar selector

#### `ui-app.py`
- Both constants removed; all references updated to `config.UI_SEVERITY_ICON` and `config.UI_TEMP_OPTIONS`

---

## Change Set 38 — Externalise configuration; move UI constants to module level

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `82243f2`

### What was changed

#### `config.py`
- `MAX_ALERTS` (env `MAX_ALERTS`, default `10`) — max alerts to fetch and display
- `ALERT_CACHE_TTL` (env `ALERT_CACHE_TTL`, default `120`) — alert result cache duration in seconds
- `UI_DOC_KEYWORDS` — frozenset of keywords that force the RAG path; moving it here means routing behaviour can be tuned without touching UI code

#### `ui-app.py`
- `_SEVERITY_ICON` moved to module level (was a dict literal recreated on every `_generate_response` call)
- `_VCF_OPS_CONFIGURED` evaluated once at startup via `os.getenv` instead of per call
- `fetch_lab_alerts` TTL now reads `config.ALERT_CACHE_TTL`
- Alert fetch/display loops use `config.MAX_ALERTS` instead of hardcoded `10`
- `_DOC_KEYWORDS` removed from the file; `_is_doc_query` now references `config.UI_DOC_KEYWORDS`

---

## Change Set 37 — Differentiate IMMEDIATE from CRITICAL with separate icon

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `5532bd7`

### What was changed

#### `ui/ui-app.py`

IMMEDIATE alerts now use 🟠 (orange) instead of sharing 🔴 (red) with CRITICAL. Full severity scale: 🔴 CRITICAL · 🟠 IMMEDIATE · 🟡 WARNING · 🟢 INFORMATION. Updated both the UI render mapping and the LLM system prompt icon instruction.

---

## Change Set 36 — Show icon + severity word together in alert display

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `34b573d`

### What was changed

#### `ui/ui-app.py`

Alert display format updated from `🔴 **resource** — name [CRITICALITY]` to `🔴 CRITICAL — **resource**: name` so the traffic-light icon and its severity label always appear as a pair.

---

## Change Set 35 — Render alert icons directly in the UI widget

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `7b51776`

### What was changed

#### `ui/ui-app.py`

Traffic-light icons were injected into the LLM system prompt but the LLM didn't reliably reproduce them. Fixed with two changes:

1. **Direct UI rendering** — when an alert query is detected, the alert list is now rendered inside the `st.status` widget using `st.write` with icons (`🔴 / 🟡 / 🟢`) and bold resource names. Icons always appear regardless of how the LLM formats its response.
2. **Explicit LLM instruction** — the system prompt now includes a line instructing the LLM to start each alert reference with its severity icon, so the LLM's commentary also uses them consistently.

Removed `_format_alert_context` (dead code — logic inlined into `_generate_response`).

---

## Change Set 34 — Replace alert keyword whitelist with doc-keyword gate

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `5bfc2d7`

### What was changed

#### `ui/ui-app.py`

The `_wants_alerts` keyword whitelist was too brittle — natural phrases like *"how's my lab"*, *"any issues?"*, or *"give me a summary"* never matched and fell through to a pointless RAG search.

New routing logic: if the prompt does **not** contain VCF/documentation keywords (`_is_doc_query` returns False) **and** `VCF_OPS_URL` is configured, the query goes to Aria Ops. Only explicit VCF/doc keywords (`vcf`, `nsx`, `vsan`, `esxi`, `configure`, `cluster`, etc.) force the RAG path. The `_wants_alerts` function and `_ALERT_KEYWORDS` set are removed entirely.

Result: any conversational or operational prompt routes to live alerts when Aria Ops is configured; documentation queries are the explicit opt-out.

---

## Change Set 33 — Traffic-light icons for alert severity

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `e2c110f`

### What was changed

#### `ui/ui-app.py`

Updated alert severity icon mapping in `_format_alert_context` to a standard traffic-light (RAG) pattern: CRITICAL → 🔴, IMMEDIATE → 🔴, WARNING → 🟡, INFORMATION → 🟢.

---

## Change Set 32 — Update README with live alert feature documentation

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `be2c514`

### What was changed

#### `README.md`

- **System architecture**: documented the live alerts path alongside the existing RAG path — intent detection, Aria Ops REST call, no RAG lookup, follow-up awareness.
- **Part 4 — Tools**: rewrote `get_lab_alerts` entry; removed WIP tag; documented all severity levels, OpsToken auth flow, and resource name resolution.
- **Part 5 — Claude Desktop**: added `env` block with `VCF_OPS_*` vars to the config example, with explanation of why credentials go there and not in the chat.
- **Part 7 — Streamlit UI features**: added live lab alerts bullet point.
- **Configuration table**: replaced `VCF_OPS_TOKEN` with `VCF_OPS_USER`, `VCF_OPS_PASS`, and `VCF_OPS_AUTH_SOURCE`.
- **Quick Start**: added env var exports before the Streamlit run command.

---

## Change Set 31 — Persist query type in session state to handle alert follow-ups

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `12eeb7e`

### What was changed

#### `ui/ui-app.py`

Follow-up prompts like "create a table summary" contain no alert keywords, so `_wants_alerts` returned False and the agent fell back to a RAG lookup. Fixed by persisting `last_query_type` (`"alert"` or `"docs"`) in session state after each response. The next prompt inherits the alert path unless it contains explicit VCF/documentation keywords (detected by new `_is_doc_query`), which forces a switch back to RAG. Session state key is reset when the user clears the chat.

---

## Change Set 30 — Skip RAG for alert queries; branch on query type before fetching

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `6ed2807`

### What was changed

#### `ui/ui-app.py`

`_generate_response` now detects query intent before doing any data fetching. `_wants_alerts` is checked first:
- **Alert query** → fetch live Aria Ops data only, skip RAG entirely. Status shows "Fetching live lab alerts..."
- **Documentation query** → run RAG only, skip alert fetch. Status shows "Consulting VCF {version} library..."

Previously `get_vcf_context` always ran first even for pure alert prompts like "show me any lab alert", wasting time on a documentation search that returns nothing useful for live operational data.

---

## Change Set 29 — Move lab alerts from sidebar into chat via system prompt injection

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `313d374`

### What was changed

#### `ui/ui-app.py`

Removed the sidebar Lab Alerts panel. Live alert data is now surfaced through the chat interface: when the user types a prompt containing alert-related keywords (`alert`, `critical`, `warning`, `ops`, `operations`, `alarm`, `issue`, etc.), the app fetches live alerts from Aria Ops and injects them as a `LIVE LAB ALERTS` block into the LLM system prompt before streaming the response. The LLM answers naturally, combining the live alert data with any relevant VCF documentation context.

Two new helpers:
- **`_wants_alerts(prompt)`** — keyword detection to decide whether to fetch alerts for a given prompt.
- **`_format_alert_context(severity)`** — fetches alerts via `fetch_lab_alerts` and returns a formatted string ready for system prompt injection.

The status widget now shows "Fetching live lab alerts..." as an intermediate step when an alert query is detected.

---

## Change Set 28 — Add Lab Alerts panel to Streamlit UI sidebar

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `df9eee2`

### What was changed

#### `ui/ui-app.py`

Ported the `get_lab_alerts` logic from the MCP server into the Streamlit UI as two synchronous functions (Streamlit does not support `async`):

- **`_acquire_ops_token_sync`** — exchanges `VCF_OPS_USER` + `VCF_OPS_PASS` for an Aria Ops OpsToken via `POST /suite-api/api/auth/token/acquire`. Result cached at module level; `VCF_OPS_AUTH_SOURCE` env var supported for LDAP auth sources.
- **`fetch_lab_alerts(severity)`** — fetches active alerts from `GET /suite-api/api/alerts`, resolves each `resourceId` to a human-readable name via `GET /suite-api/api/resources/{id}`, returns a structured `(alerts, error)` tuple. Cached for 120 seconds via `@st.cache_data`.

New sidebar panel ("Lab Alerts") includes:
- Severity filter dropdown (All / Critical / Immediate / Warning / Information)
- 🔄 Refresh button that clears the cache and reruns
- Up to 10 alerts rendered with criticality icons (🔴🟠🟡🔵)
- Graceful "not configured" message when `VCF_OPS_URL` is unset

---

## Change Set 27 — Add inline comments to get_lab_alerts

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `c6230b2`

### What was changed

#### `mcp/server.py`

Added step-by-step inline comments to `get_lab_alerts` explaining the four logical phases: credential loading, authentication (OpsToken vs Basic fallback), alert fetching with optional severity filter, resource name resolution via secondary API call, and output formatting.

---

## Change Set 26 — Make severity filter optional; default returns all active alerts

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `2bbec7c`

### What was changed

#### `mcp/server.py`

Changed `get_lab_alerts` default from `severity="CRITICAL"` to `severity=""`. When empty, the `alertCriticality` query param is omitted entirely and Aria Ops returns all active alerts regardless of severity. Passing a severity value (CRITICAL, IMMEDIATE, WARNING, INFORMATION) still filters as before. Input is uppercased automatically so case doesn't matter.

---

## Change Set 25 — Resolve human-readable resource names in get_lab_alerts

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `89f22d5`

### What was changed

#### `mcp/server.py`

Aria Ops alert objects carry only a `resourceId` UUID — the human-readable name is not embedded in the alert payload. Fixed `get_lab_alerts` to fetch `GET /suite-api/api/resources/{id}` for each unique resource in the top-5 alerts and use `resourceKey.name` as the display label. Results are cached within the call to avoid duplicate requests. Also removed the debug key-list footer added in Change Set 24.

---

## Change Set 24 — Fix alert response parsing; expose schema keys for discovery

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `632e6ac`

### What was changed

#### `mcp/server.py`

Authentication against Aria Ops was succeeding but `get_lab_alerts` was crashing with `KeyError: 'resourceName'` because the actual API response schema differs from what was assumed. Fixed by replacing direct key access with a `.get()` fallback chain that tries multiple candidate field names (`resourceName` → `resource.name` → `resourceIdentifier`; `alertDefinitionName` → `alertName` → `type`). Also appends the first alert's key list to the tool output so the real schema can be confirmed and the fallback chain updated if needed.

---

## Change Set 23 — Better error reporting in get_lab_alerts

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `623147b`

### What was changed

#### `mcp/server.py`

Improved error handling in `get_lab_alerts` to surface the exact HTTP status code, request URL, and response body for each failure point separately (token acquisition vs. alerts endpoint). Previously all failures returned a generic message that made debugging impossible.

---

## Change Set 22 — Fix Aria Ops token acquisition: drop hardcoded authSource

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `68ede26`

### What was changed

#### `mcp/server.py`

Fixed `_acquire_ops_token` to stop sending `"authSource": "LOCAL"` unconditionally.

The Aria Ops API (`POST /suite-api/api/auth/token/acquire`) expects `authSource` to be the **display name** of the authentication source as configured in Aria Ops Administration > Authentication Sources — not the internal type ID `"LOCAL"`. Sending the wrong value (or any value that doesn't match an existing auth source name) causes a 401 even with correct credentials.

For local user accounts (`admin`, `admin@local`) the field should be **omitted entirely** — the API uses the default local auth source automatically.

Changes:
- Removed hardcoded `"authSource": "LOCAL"` from the POST body.
- Added optional `VCF_OPS_AUTH_SOURCE` env var. If set, its value is included as `authSource` in the token request — required for LDAP/Active Directory sources. Leave unset for local accounts.
- Added explicit `Content-Type: application/json` header to the token POST (belt-and-suspenders for strict server configurations).

---

## Change Set 21 — Revert credential params; use env vars in claude_desktop_config.json

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `26b17f4`

### What was changed

#### `mcp/server.py`

Reverted the `username` / `password` tool parameters added in Change Set 20. Claude Desktop correctly refuses to accept credentials through chat (security policy). The right approach is to set `VCF_OPS_URL`, `VCF_OPS_USER`, and `VCF_OPS_PASS` in the `"env"` block of `claude_desktop_config.json` — Claude Desktop injects them as environment variables into the MCP server process at startup, so they never pass through the chat or the LLM.

---

## Change Set 20 — Interactive credential prompting in get_lab_alerts

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `429919a`

### What was changed

#### `mcp/server.py`

Added `username` and `password` as explicit optional parameters to `get_lab_alerts`. The tool docstring instructs Claude to ask the user for these values if they are not already known. When provided, they override the `VCF_OPS_USER` / `VCF_OPS_PASS` env vars. This means Claude Desktop will prompt for credentials interactively in the chat when they are not set in the environment, without requiring any manual env var configuration.

---

## Change Set 19 — Auto token acquisition for get_lab_alerts

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `ccaf946`

### What was changed

#### `mcp/server.py`

**`_acquire_ops_token(base_url, user, password)`** (new internal helper)
POSTs to `/suite-api/api/auth/token/acquire` with username and password, returns an `OpsToken`, and caches it in a module-level variable for the server's lifetime. Subsequent calls return the cached token without hitting the network again.

**`get_lab_alerts` updated**
Now accepts two authentication modes:
- **Recommended:** set `VCF_OPS_USER` + `VCF_OPS_PASS` — the server acquires and caches an `OpsToken` automatically. No manual base64 encoding required.
- **Fallback:** set `VCF_OPS_TOKEN` — used as a `Basic` auth header (previous behaviour, kept for backward compat).

`VCF_OPS_URL` is now the Aria Ops **base URL** (e.g. `https://vcf-ops.lab.local`) so both the token endpoint and the alerts endpoint are derived from it. The alerts URL becomes `{base_url}/suite-api/api/alerts`.

---

## Change Set 18 — Fix two bugs in get_lab_alerts

**Date:** 2026-06-27
**Branch:** `main`
**Commit:** `0bc4be4`

### What was changed

#### `mcp/server.py`

**Wrong query parameter** (`severity` → `alertCriticality`)
The Aria Ops REST API uses `alertCriticality` to filter alerts by severity level. The previous `?severity=CRITICAL` parameter was silently ignored by the endpoint, returning all alerts unfiltered.

**Wrong field name** (`alertName` → `alertDefinitionName`)
The Aria Ops alert object has `alertDefinitionName` for the alert description. The previous `a['alertName']` raised a `KeyError` on every alert, causing every call to fall into the `except` block and return an error string instead of the alert list.

---

## Change Set 17 — Fix status widget border by targeting HTML details element

**Date:** 2026-06-24
**Branch:** `main`
**Commit:** `cfa422e`

### What was changed

#### `ui/themes.py`

Previous attempts used `data-testid` selectors that may not have matched what Streamlit actually renders at runtime. `st.status()` always emits a native HTML `<details>`/`<summary>` pair regardless of Streamlit version. Added direct selectors for `details`, `details > div`, and `summary` inside `[data-testid="stChatMessage"]`, stripping `border`, `outline`, and `box-shadow`. Also added `stVerticalBlockBorderWrapper` itself (not just its `> div` child) to the suppression list. Removed the now-redundant earlier attempts that targeted testids which were never matching.

---

## Change Set 16 — Remove all borders from status widget inner elements

**Date:** 2026-06-24
**Branch:** `main`
**Commit:** `79c3a35`

### What was changed

#### `ui/themes.py`

Streamlit's native stylesheet applies a border to the `<details>` and `<summary>` elements that `st.status()` renders internally, not just the outer `[data-testid="stStatusWidget"]` div. Previous fixes targeted the outer container but left the inner elements unstyled. Extended the suppression rule to cover `stStatusWidget details`, `stStatusWidget summary`, `stExpander` inside `stChatMessage`, and their inner `details`/`summary` elements — resetting `border`, `outline`, and `box-shadow` to `none` on all of them.

---

## Change Set 15 — Suppress all card borders inside chat message bubbles

**Date:** 2026-06-24
**Branch:** `main`
**Commit:** `053a94e`

### What was changed

#### `ui/themes.py`

The previous fix only silenced `stLayoutWrapper`. The global `stVerticalBlockBorderWrapper > div` card rule (background, `1px solid border`, `box-shadow`) was still firing inside `stChatMessage`, producing a visible edge around the collapsed status widget content. Extended the scoped override to also cover `stVerticalBlockBorderWrapper > div` and its hover state when nested inside a chat message, resetting `border`, `box-shadow`, and `background-color` to transparent so no card edges appear within the response bubble.

---

## Change Set 14 — Remove border from "Analysing data..." status widget

**Date:** 2026-06-24
**Branch:** `main`
**Commit:** `2d8b5af`

### What was changed

#### `ui/themes.py`

Changed `border: 1px solid {v['border']}` to `border: none` on the `[data-testid="stStatusWidget"]` rule. The `st.status()` widget that shows "Consulting VCF library…" / "Analysing data…" was rendering with a visible outline that clashed visually inside the chat message bubble.

---

## Change Set 13 — Remove border from chat message layout wrapper

**Date:** 2026-06-24
**Branch:** `main`
**Commit:** `f326d62`

### What was changed

#### `ui/themes.py`

Added a scoped CSS rule that strips `border` and `box-shadow` from `[data-testid="stLayoutWrapper"]` and its immediate child `div` when they appear inside a `[data-testid="stChatMessage"]`. The global `stVerticalBlockBorderWrapper > div` card rule was bleeding into the assistant response bubble's internal layout wrapper, producing a visible edge around the answer content. The new rule is scoped to the chat message context so bordered cards elsewhere in the UI are unaffected.

---

## Change Set 12 — RAG pipeline optimisations, UI resilience, and config consistency

**Date:** 2026-06-24
**Branch:** `main`
**Commit:** `fb15b2d`

### What was changed

#### `config.py`

**`QUERY_PREFIX` now env-var overridable**
Changed from a hardcoded string to `os.getenv("QUERY_PREFIX", "...")`. If you swap `EMBED_MODEL` to a model that doesn't need an instructional prefix (e.g. `bge-m3`, `nomic-embed-text`), set `QUERY_PREFIX=""` to avoid degraded retrieval quality. Comment updated to document this.

**New `MAX_DISTANCE` constant**
Added `MAX_DISTANCE = float(os.getenv("MAX_DISTANCE", "1.0"))`. ChromaDB results whose L2 distance exceeds this threshold are excluded from LLM context, reducing noise from low-relevance chunks. Configurable via env var; a closest-match fallback ensures the LLM always receives at least one result.

---

#### `rag/ingestData.py`

**Removed local `DB_PATH` shadow**
The script was defining its own `DB_PATH = Path(__file__).resolve().parent / "chroma_db"` instead of using `config.DB_PATH`. While both resolved to the same path today, any future change to `config.py` would have silently diverged. Removed the local definition; the ChromaDB client now uses `config.DB_PATH` directly.

---

#### `mcp/server.py`

**Collection handle caching**
`_get_collection()` previously called `_chroma.get_collection()` on every MCP tool invocation. Added `_collection_cache: dict = {}` to cache collection handles by version after the first open, eliminating repeated handle creation on each tool call.

**`n_results` lower bound**
`n_results = min(n_results, 50)` had no lower bound — `n_results=0` would cause a ChromaDB error. Changed to `max(1, min(n_results, 50))`.

**Distance filtering**
`search_vcf_documentation` now unpacks `results["distances"][0]` and skips chunks whose distance exceeds `config.MAX_DISTANCE`. A fallback to the closest match is applied if all results are filtered out, so the LLM always receives at least one chunk.

**Dynamic docstring**
Removed the hardcoded `"Available: 9.0, 9.1"` from the `version` arg description — this would have become stale when adding VCF 9.2 or later. Replaced with a reference to `config.VERSION_MAP`.

**`verify=False` annotation**
Added `# noqa: S501 — lab uses self-signed cert` to the `httpx.AsyncClient` call to document why SSL verification is intentionally disabled.

---

#### `ui/ui-app.py`

**Session state init moved to top**
`messages` and `session_tokens` were initialised after the sidebar block that reads them, making the init effectively dead code on every version-switch rerun. All three session state keys (`theme`, `messages`, `session_tokens`) are now initialised at the very top, before `st.set_page_config`, ensuring they exist for every subsequent reference.

**CSS generation cached**
`build_css(PALETTES[...])` was called on every Streamlit rerun, regenerating ~500 lines of CSS on every user interaction. Wrapped in a `@st.cache_data` function `_get_css(theme_name: str)` keyed on the theme string — the CSS is now built once per theme per session.

**`_TEMP_OPTIONS` promoted to module-level constant**
The temperature options dict was re-created on every rerun inside the sidebar block. Moved to a module-level constant so it is evaluated once at import time.

**Streaming chunk access fixed**
`chunk["message"]["content"]` used dict-style access on `ChatResponse`, a Pydantic object returned by `ollama>=0.4`. This raises `TypeError` at runtime. Changed to the correct attribute access: `chunk.message.content`. (Note: `_chunk_stat` already handled both styles; this aligns the content access to match.)

**Error handling around `ollama.chat()`**
The entire streaming block is now wrapped in `try/except`. If Ollama is unreachable or the model is not pulled, the app renders `st.error()` with an actionable message and returns cleanly rather than showing a raw Python traceback.

**Distance filtering in `get_vcf_context`**
Aligned with the MCP server: unpacks `results["distances"][0]` and excludes chunks above `config.MAX_DISTANCE`. A closest-match fallback ensures the context string is never empty.

**`DEFAULT_N + 5` magic number removed**
The query was fetching `DEFAULT_N + 5` results with no subsequent trimming — the extra 5 were always passed to the LLM. Changed to `config.DEFAULT_N`.

**Dead commented-out code removed**
Removed the `##`-prefixed commented-out lines (`st.divider()`, `st.info()`) that had accumulated in the sidebar block.

---

## Change Set 11 — PDF download links in "Prepare your documents" table

**Date:** 2026-06-24
**Branch:** `main`

### What was changed

#### `README.md`

Linked the two filenames in the "Prepare your documents" table to their direct Broadcom TechDocs PDF download URLs, so readers can grab the files straight from the README.

---

## Change Set 10 — Collapsible code blocks in README

**Date:** 2026-06-24
**Branch:** `main`

### What was changed

#### `README.md`

Wrapped every code block in `<details>`/`<summary>` HTML tags so readers can expand or collapse them on demand. Works natively on GitHub and most Markdown renderers that support inline HTML. No change to the actual commands or content.

---

## Change Set 9 — Wider and taller chat input textarea

**Date:** 2026-06-24
**Branch:** `main`

### What was changed

#### `ui/themes.py`

Set `min-height: 3rem` (≈ 2 visible lines) and `max-height: 8rem` on the chat textarea so it starts taller and auto-grows up to ~4 lines before scrolling. Also forced `width: 100%` on the input wrapper to ensure the field uses the full available width.

---

## Change Set 8 — Remove chat input border

**Date:** 2026-06-24
**Branch:** `main`

### What was changed

#### `ui/themes.py`

Removed the `1px solid` border from `[data-testid="stChatInput"] [data-baseweb="base-input"]`. The textarea now blends cleanly into the bottom bar without a visible box outline.

---

## Change Set 7 — Default light theme & button visibility fix

**Date:** 2026-06-24
**Branch:** `main`

### What was changed

#### `ui/ui-app.py`

**Default theme changed to light**
`st.session_state.theme` now initialises to `"light"` instead of `"dark"`. First-time visitors land in the light palette without needing to toggle.

#### `ui/themes.py`

**Button border added for visibility**
All `.stButton > button` elements now carry `border: 1px solid {accent} !important` instead of `border: none`. In dark mode the bright blue outline (`#2EC0FF`) ensures the theme toggle and other sidebar buttons are always discoverable, even when the button background is transparent.

#### `README.md`

Updated the VMware Clarity theme bullet under Streamlit UI features to reflect the new default (light) and the outlined button behaviour.

---

## Change Set 6 — Regenerate button

**Date:** 2026-06-17
**Branch:** `main`

### What was changed

#### `ui/ui-app.py`

**`_generate_response(user_prompt, version, model, temperature)`** (new function)  
Extracted the streaming + token-stats logic that was previously inlined inside the chat input handler into a standalone function. Both the normal chat input path and the new retry path call this function, eliminating code duplication.

**Regenerate button**  
A `↺ Regenerate` button is rendered immediately after the last assistant message whenever it is the most recent item in `st.session_state.messages`. It is never shown for historical messages mid-conversation.

Clicking it:
1. Pops the last assistant message from `st.session_state.messages`.
2. Sets `st.session_state.pending_retry = True` and calls `st.rerun()`.
3. On the next render the `pending_retry` guard detects that the last message is now the user question, clears the flag, and calls `_generate_response()` with the **current** temperature from the sidebar slider — so adjusting the slider before clicking retry produces a differently-sampled answer.

---

## Change Set 5 — VMware Clarity CSS/colour theme

**Date:** 2026-06-17
**Branch:** `main`

### What was added

#### `ui/themes.py` (new file)

Centralises all visual constants and CSS generation, matching the approach used in `personalHRAssistant/ui/themes.py`.

- **`DARK` palette** — built on the Clarity Design System construction scale (hsl 198). Key values: `bg_app=#1B2B32` (construction[1000]), `bg_sidebar=#17252B` (construction[1100]), `accent=#2EC0FF` (blue[400]).
- **`LIGHT` palette** — Clarity light surface with `bg_app=#F1F7F8` (construction[50]) and `accent=#0079AD` (blue[700]).
- **`PALETTES`** dict — keyed by `"dark"` / `"light"` for easy lookup.
- **`build_css(v)`** — accepts a palette dict and returns a `<style>` block covering: Streamlit CSS variable overrides, Metropolis `@font-face` declarations, app shell, typography, sidebar, buttons, text inputs, select boxes, radio buttons, slider, status widget, alerts, chat (input + message bubbles + code blocks), expanders, divider, scrollbar, and responsive breakpoints.

#### `ui/static/fonts/` (new directory)

18 Metropolis `.woff2` font files (weight 100–900, normal + italic), copied from `personalHRAssistant/ui/static/fonts/`. Streamlit serves these via `app/static/fonts/` at runtime.

#### `ui/ui-app.py`

- Imports `PALETTES, build_css` from `themes`.
- Initialises `st.session_state.theme = "dark"` on first load.
- Calls `st.markdown(build_css(PALETTES[...]), unsafe_allow_html=True)` immediately after `set_page_config` so the palette applies before any content renders.
- Adds a **theme toggle button** at the bottom of the sidebar ("☀️ Light mode" / "🌙 Dark mode") that flips `session_state.theme` and calls `st.rerun()`.

#### `README.md`

Added **VMware Clarity theme** bullet to the Streamlit UI features list.

---

## Change Set 4 — Token usage display in Streamlit UI

**Date:** 2026-06-10  
**Commit:** `(see below)`  
**Branch:** `main`

### What was added

#### `ui/ui-app.py`

**`_chunk_stat(chunk, key)`** helper  
Safely reads an integer stat from an Ollama streaming chunk, handling both dict-style (older library) and attribute-style (0.6.x typed objects) access. Returns 0 on missing/None values.

**`_token_caption(tokens)`** helper  
Renders a compact `st.caption` line under an assistant message:  
`↑ 8,432 prompt  ·  ↓ 312 completion  ·  97 tok/s`  
Only includes segments where the value is non-zero.

**Per-response token stats**  
After the streaming loop, the final Ollama chunk (`done=True`) is captured as `last_chunk`. Three fields are extracted:
- `prompt_eval_count` → prompt tokens (system prompt + RAG context + conversation history)
- `eval_count` → completion tokens generated
- `eval_duration` → nanoseconds spent generating; used to compute `tok/s`

The stats dict is passed to `_token_caption()` for immediate display, then stored inside the message dict (`message["tokens"]`) so the caption re-renders correctly when the chat history is replayed on subsequent Streamlit reruns.

**Session token total in sidebar**  
`st.session_state.session_tokens` accumulates prompt and completion tokens across all turns. The sidebar shows a `**Session tokens**` block once at least one response has been generated:
```
↑ 12,450 prompt
↓ 890 completion
13,340 total
```
Resets to zero when the user clicks **Clear Chat** or switches VCF version.

---

## Change Set 3 — README rewrite

**Date:** 2026-06-10  
**Commit:** `(see below)`  
**Branch:** `main`

Full rewrite of `README.md` to reflect all code changes made in Change Sets 1 and 2.

Key updates:
- **Quick Start** section added at the top — four commands to go from zero to running.
- **Part 1 (models)**: removed the `llama3` / `nomic-embed-text` history; shows only the current recommended models (`mxbai-embed-large` + `qwen3.5:35b-a3b`).
- **Part 2 (setup)**: corrected folder name (`privateAI-demo`, not `rag`); replaced individual `uv add` commands with `uv sync`.
- **Part 3 (ingestion)**: added multi-version ingestion table, `testSearch.py` usage, and note that re-runs are idempotent.
- **Part 4 (MCP server)**: documented `version` parameter and the two-call pattern for cross-version comparison queries.
- **Part 5 (Claude Desktop)**: replaced hardcoded `/Users/giuliano/` with `/Users/YOUR_USERNAME/`; corrected `--directory` to point to `privateAI-demo/` (project root, where `pyproject.toml` lives).
- **Part 7 (Streamlit UI)**: added `uv run streamlit run ui/ui-app.py` command; documented version selector, dynamic model list, clear chat, and conversation memory features.
- **Configuration table** (new section): documents all environment variables from `config.py` — `EMBED_MODEL`, `LLM_MODEL`, `OLLAMA_URL`, `DEFAULT_VERSION`, `NUM_CTX`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `BATCH_LIMIT`, `DEFAULT_N`, `VCF_OPS_URL`, `VCF_OPS_TOKEN`.
- **BGE-M3 switch**: updated from "edit model_name in the code" to `EMBED_MODEL=bge-m3 uv run rag/ingestData.py`; updated collection deletion command to use `uv run python -c` (no bare `python` / no hardcoded paths).
- **Multi-version section**: added instructions for adding VCF 9.2 (or any future version) — one line in `VERSION_MAP`, then re-ingest.

---

## Change Set 2 — Versioned Collections (VCF 9.0 / 9.1)

**Date:** 2026-06-10  
**Commit:** `(see below)`  
**Branch:** `main`

### Context

VCF 9.1 was released. Ingesting it into the existing single `docs` collection
would produce conflicting search results: the same topic described differently
across versions could appear in the same retrieval window, confusing the LLM.

**Decision:** Option A — separate ChromaDB collection per version.  
Each query hits exactly one version's data, guaranteeing zero cross-version conflicts.
Comparison questions ("what changed in 9.1?") work by calling the search tool
twice — once per version — which the LLM orchestrates automatically via MCP tool-calling.

### Migration steps (Option A)

1. Place `vmware-cloud-foundation-9.0.pdf` in `rag/contentData/` and run `uv run ingestData.py`
   → creates `docs_vcf90` collection.
2. Place `vmware-cloud-foundation-9-1.pdf` in `rag/contentData/` and run again
   → creates `docs_vcf91` collection.
3. Delete the legacy `docs` collection once verified:
   ```bash
   uv run python -c "import chromadb; chromadb.PersistentClient('rag/chroma_db').delete_collection('docs')"
   ```

### Files changed

#### `config.py`
- Removed `COLLECTION = "docs"` (single hardcoded name).
- Added `VERSION_MAP: dict[str, str]` — maps `"9.0"` → `"docs_vcf90"`, `"9.1"` → `"docs_vcf91"`.
- Added `DEFAULT_VERSION = "9.1"` (overridable via env var).
- Adding a new VCF version in future only requires adding one entry to `VERSION_MAP`.

#### `rag/ingestData.py`
- Added `version_from_filename()`: extracts `"9.0"` / `"9.1"` from a filename using
  a regex anchored to known product keywords (`foundation`, `vcf`, `cloud`), with a
  generic major.minor fallback.
- Files are grouped by detected version; each group is upserted into its own collection
  (`docs_vcf90`, `docs_vcf91`) via `config.VERSION_MAP`.
- Each chunk's metadata now includes `"version"` alongside `"source"` and `"page"`.
- Files whose version cannot be detected, or whose version is not in `VERSION_MAP`,
  are skipped with a clear hint message.
- Startup migration guard: warns if the legacy `docs` collection still exists.

#### `mcp/server.py`
- Added `_get_collection(version)` helper that opens the correct ChromaDB collection
  and raises a clear error (with fix instructions) if it does not exist.
- `search_vcf_documentation` now has a `version: str = config.DEFAULT_VERSION` parameter.
- Tool docstring explicitly instructs the LLM to call the tool twice for comparison questions.
- Result header updated to `[VCF {ver} | {source} | Page {page}]`.

#### `ui/ui-app.py`
- Replaced `init_db()` with two functions: `_init_chroma()` (shared client) and
  `get_collection(version)` (cached per version string).
- Added a version radio selector to the sidebar (sorted descending, defaults to latest).
- Auto-clears chat history when the user switches version, preventing answers from
  one version being mixed with questions about another.
- Chat input placeholder and system prompt are now version-aware.

#### `rag/testSearch.py`
- Added `--version` CLI argument (default: `config.DEFAULT_VERSION`).
- Help text lists all available versions from `config.VERSION_MAP` dynamically.

---

## Change Set 1 — Refactor & Critical Fixes

**Date:** 2026-06-10  
**Commit:** `1e9945b`  
**Branch:** `main`

---

## Overview

Full review of the codebase: README, all Python scripts, and `pyproject.toml`.  
Six files changed across four concerns: shared configuration, ingestion robustness, MCP server improvements, and UI correctness.

---

## 1. New File — `config.py`

**What:** Centralised configuration module at the project root.

**Why:** The embedding model name `"mxbai-embed-large"` was hard-coded in three separate files (`ingestData.py`, `server.py`, `ui-app.py`). Changing the model (e.g. upgrading to `bge-m3`) required editing every file individually and risked drift. The Ollama URL, ChromaDB path, chunk sizes, and number of retrieval results suffered the same problem.

**What it does:**
- Exposes `EMBED_MODEL`, `LLM_MODEL`, `OLLAMA_URL`, `DB_PATH`, `COLLECTION`, `QUERY_PREFIX`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `BATCH_LIMIT`, `DEFAULT_N`, and `NUM_CTX` as module-level constants.
- Every constant is overridable via a matching environment variable (e.g. `EMBED_MODEL=bge-m3 uv run ingestData.py`).
- All other scripts now import this module via `sys.path` insertion.

---

## 2. `rag/ingestData.py`

### Fix: `collection.add()` → `collection.upsert()`

**What:** Replaced all calls to `collection.add()` with `collection.upsert()`.

**Why (bug):** ChromaDB raises an error if you call `add()` with a document ID that already exists in the collection. Since the IDs are deterministic (`{stem}_p{page}_c{chunk}`), running the ingestion script a second time on the same PDFs would always crash. `upsert()` inserts new documents and silently overwrites existing ones, making re-runs idempotent.

---

### Fix: Path resolved via `Path(__file__)`

**What:** Replaced `path="./chroma_db"` with `Path(__file__).resolve().parent / "chroma_db"`.

**Why:** A relative path is resolved against the current working directory at runtime. The script only worked correctly when invoked from inside the `rag/` folder. Using `__file__` makes the path absolute and correct regardless of where the script is run from.

---

### Enhancement: TXT file support

**What:** Added `data_dir.glob("*.txt")` alongside `*.pdf`; TXT files are read as a single page via `Path.read_text()`.

**Why:** The README listed TXT as a supported document type but the code only handled PDF. This brings the implementation in line with the documented capability without adding any new dependency.

---

### Fix: Final batch flush now inside a try/except

**What:** Extracted the flush logic into a `flush_batch()` helper that handles both mid-loop and end-of-file flushes uniformly.

**Why:** The original code wrapped mid-loop batches in `try/except` but the final flush (after the `for` loop) was unguarded. An Ollama error on the last batch would produce an unhandled exception with no hint about the cause.

---

### Enhancement: Ingestion summary at exit

**What:** Counts total chunks upserted and prints them at completion.

**Why:** The original success message gave no indication of how many chunks were indexed, making it hard to spot issues (e.g. a document producing zero chunks due to encoding problems).

---

## 3. `mcp/server.py`

### Enhancement: `n_results` parameter on `search_vcf_documentation`

**What:** Added `n_results: int = config.DEFAULT_N` as an explicit tool parameter (hard-capped at 50).

**Why:** The result count was hard-coded to 20. MCP callers (Claude Desktop, Cherry Studio, etc.) had no way to request a broader or narrower search. Exposing it as a parameter gives the calling LLM control over recall depth.

---

### Enhancement: Source filename included in each result

**What:** Each result entry now reads `[{source} | Page {page}]` instead of `[Page {page}]`.

**Why:** When the vector store contains multiple documents, the page number alone is ambiguous. The source filename tells the LLM (and the end user) which document the snippet came from.

---

### Fix: Lab credentials moved to environment variables

**What:** `VCF_OPS_URL` and `VCF_OPS_TOKEN` are now read from `os.getenv()` instead of being hard-coded strings. The tool returns a clear message if `VCF_OPS_TOKEN` is unset.

**Why:** Hard-coded placeholder credentials in source code are a security smell and would be committed to version history. Env vars are the standard pattern for secrets.

---

### Fix: Startup DB init wrapped in `try/except`

**What:** The `chromadb.PersistentClient` and `get_collection()` calls are now inside a `try/except` block that raises a `RuntimeError` with a clear "run ingestData.py first" message.

**Why:** If the ChromaDB collection does not exist (e.g. on a fresh clone before ingestion), the server crashed with a low-level ChromaDB traceback. The new error message directly tells the user what to do.

---

### Fix: Removed unused loop index variable

**What:** Changed `for i, (text, meta) in enumerate(zip(...))` to `for text, meta in zip(...)`.

**Why:** The index `i` was never used. IDE flagged it as a hint; removing it keeps the code clean.

---

## 4. `ui/ui-app.py`

### Critical Fix: Conversation history now passed to `ollama.chat()`

**What:** `ollama.chat()` now receives the full `st.session_state.messages` history prepended by the system prompt, instead of only the current user message.

**Why (critical bug):** The original code constructed the Ollama message list as:
```python
messages=[
    {'role': 'system', 'content': system_prompt},
    {'role': 'user',   'content': prompt}
]
```
This means the model had **no memory of any previous turn**. Every question was answered as if it were the first message in the conversation. Multi-turn follow-up questions ("expand on that", "what about X?") would fail to reference earlier answers. The fix appends the entire session state so the model sees the complete dialogue.

---

### Performance Fix: `num_ctx=32768` added to Ollama options

**What:** Added `"num_ctx": config.NUM_CTX` (default 32 768 tokens) to `ollama.chat()` options.

**Why:** With 25 retrieved chunks of ~800 characters each (~20 000 characters of context) plus conversation history, the default Ollama context window for some models can be too small, causing silent truncation. Setting `num_ctx` explicitly ensures the full RAG context fits.

---

### Enhancement: Dynamic model list from `ollama.list()`

**What:** Replaced the hardcoded `["qwen3.5:35b-a3b", "qwen2.5:32b"]` selectbox with a `get_available_models()` function that calls `ollama.list()` at startup (cached for 30 seconds). Falls back to the defaults if Ollama is unreachable.

**Why:** The hardcoded list would not reflect models the user had actually pulled. If the default model was not installed, the UI would silently send requests to a non-existent model.

---

### Enhancement: Clear Chat button

**What:** Added a "Clear Chat" button to the sidebar that resets `st.session_state.messages` and calls `st.rerun()`.

**Why:** There was no way to start a fresh conversation without restarting the Streamlit server.

---

### Fix: Friendly error when ChromaDB is missing

**What:** `init_db()` is now wrapped in `try/except`; on failure it calls `st.error()` with a user-readable message and `st.stop()`.

**Why:** A missing or corrupt ChromaDB collection previously caused an unhandled exception that crashed the entire Streamlit page with a Python traceback visible to the user.

---

### Fix: Source deduplication preserves retrieval order

**What:** Changed `for s in set(source_list)` to `for s in dict.fromkeys(source_list)`.

**Why:** `set()` returns elements in an arbitrary (hash-based) order, losing the relevance ranking from ChromaDB. `dict.fromkeys()` deduplicates while preserving the original insertion order (guaranteed in Python 3.7+).

---

## 5. `rag/testSearch.py`

### Fix: Path resolved via `Path(__file__)`

**What:** Replaced `"../rag/chroma_db"` with `Path(__file__).resolve().parent / "chroma_db"`.

**Why:** The old relative path was resolved against the process CWD. Running the script from outside the `rag/` directory produced a "collection not found" error. The `__file__`-based path is always correct.

---

### Enhancement: Shared config constants

**What:** Imports `config` for `EMBED_MODEL`, `OLLAMA_URL`, `COLLECTION`, and `QUERY_PREFIX`.

**Why:** Consistency — if you change the embedding model via the env var, `testSearch.py` now picks up the same model automatically.

---

### Enhancement: Improved output formatting

**What:** Each result now shows `[{i}] {source} (Page {page})` on its own line before the snippet, and the search header reports the model in use.

**Why:** The original output only showed the source and page inline with the text, making it harder to scan multiple results quickly.

---

## 6. `pyproject.toml`

### Fix: Added `httpx` as an explicit dependency

**What:** Added `"httpx>=0.27.0"` to the dependencies list.

**Why:** `mcp/server.py` imports `httpx` directly for the `get_lab_alerts` tool. It was not listed as a dependency — it worked only because `fastmcp` happens to pull it in transitively. Relying on transitive dependencies is fragile; a future `fastmcp` update that drops `httpx` would break the server silently.
