import json
import os
import sys
from datetime import datetime, timezone
import httpx  # pyright: ignore[reportMissingImports]
import streamlit as st
import ollama
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # pyright: ignore[reportMissingImports]
from themes import PALETTES, build_css  # pyright: ignore[reportMissingImports]

# --- PERSISTENT CONNECTION CONFIG ---
# Credentials typed in the Settings popover are saved here so they survive page refreshes.
_OPS_CONFIG_FILE = Path(__file__).resolve().parent / ".vcf_ops_config.json"


def _normalise_ops_url(raw: str) -> str:
    """Prepend https:// if the user typed a bare FQDN (no scheme)."""
    raw = raw.strip().rstrip("/")
    if raw and not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    return raw


def _load_ops_config() -> dict:
    try:
        return json.loads(_OPS_CONFIG_FILE.read_text())
    except Exception:
        return {}


def _save_ops_config(url: str, user: str, password: str) -> None:
    try:
        _OPS_CONFIG_FILE.write_text(
            json.dumps({"url": url, "user": user, "password": password})
        )
    except Exception:
        pass

# --- ARIA OPS TOKEN CACHE ---
# Acquired once per process lifetime; re-acquired when credentials change or a 401 is received.
_ops_token_ui: str = ""
_ops_token_for: str = ""  # "base_url|user" the cached token was issued for


# --- 1. PAGE CONFIG ---
st.set_page_config(page_title=config.UI_PAGE_TITLE, page_icon=config.UI_PAGE_ICON, layout="wide")

# --- 2. SESSION STATE INIT ---
if "theme" not in st.session_state:
    st.session_state.theme = "light"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_tokens" not in st.session_state:
    st.session_state.session_tokens = {"prompt": 0, "completion": 0}
if "last_query_type" not in st.session_state:
    st.session_state.last_query_type = "docs"  # "alert" or "docs"
if "rate_input" not in st.session_state:
    st.session_state.rate_input  = config.UI_COST_PER_1M_INPUT
if "rate_output" not in st.session_state:
    st.session_state.rate_output = config.UI_COST_PER_1M_OUTPUT
if "selected_version" not in st.session_state:
    st.session_state.selected_version = sorted(config.VERSION_MAP.keys(), reverse=True)[0]
if "selected_model" not in st.session_state:
    st.session_state.selected_model = config.LLM_MODEL
if "temp_label" not in st.session_state:
    st.session_state.temp_label = list(config.UI_TEMP_OPTIONS.keys())[0]
if "vcf_ops_url" not in st.session_state:
    _cfg = _load_ops_config()
    st.session_state.vcf_ops_url  = _cfg.get("url",  os.getenv("VCF_OPS_URL",  ""))
    st.session_state.vcf_ops_user = _cfg.get("user", os.getenv("VCF_OPS_USER", ""))
    st.session_state.vcf_ops_pass = _cfg.get("password", os.getenv("VCF_OPS_PASS", ""))

# --- THEME ---
_dark = st.session_state.theme == "dark"


@st.cache_data
def _get_css(theme_name: str) -> str:
    return build_css(PALETTES[theme_name])


st.markdown(_get_css("dark" if _dark else "light"), unsafe_allow_html=True)

st.title(config.UI_PAGE_TITLE)


# --- 3. DATA CONNECTIONS ---
@st.cache_resource
def _init_chroma():
    """Single ChromaDB client + embedding function shared across all version collections."""
    client = chromadb.PersistentClient(path=str(config.DB_PATH))
    emb_fn = embedding_functions.OllamaEmbeddingFunction(
        model_name=config.EMBED_MODEL,
        url=f"{config.OLLAMA_URL}/api/embeddings",
    )
    return client, emb_fn


@st.cache_resource
def get_collection(version: str):
    """Open the ChromaDB collection for the given VCF version (cached per version)."""
    client, emb_fn = _init_chroma()
    col_name = config.VERSION_MAP[version]
    try:
        return client.get_collection(name=col_name, embedding_function=emb_fn)
    except Exception as e:
        st.error(
            f"**VCF {version} collection not found.**  \n"
            f"Run `uv run ingestData.py` with the VCF {version} PDF in `rag/contentData/`.\n\n"
            f"Details: `{e}`"
        )
        st.stop()


def _acquire_ops_token_sync(base_url: str, user: str, password: str, force: bool = False) -> str:
    """Acquire an Aria Ops OpsToken, caching it for the process lifetime.

    The cache is invalidated when credentials change (different base_url/user)
    or when force=True is passed (e.g. after a 401 on the alerts endpoint).
    """
    global _ops_token_ui, _ops_token_for
    cache_key = f"{base_url}|{user}"
    if _ops_token_ui and _ops_token_for == cache_key and not force:
        return _ops_token_ui
    _ops_token_ui  = ""
    _ops_token_for = ""
    # authSource is the display name of the auth source in Aria Ops.
    # Omitting it (default) works for local accounts; set VCF_OPS_AUTH_SOURCE for LDAP.
    auth_source = os.getenv("VCF_OPS_AUTH_SOURCE", "")
    body: dict = {"username": user, "password": password}
    if auth_source:
        body["authSource"] = auth_source
    with httpx.Client(verify=False) as http:  # noqa: S501 — lab uses self-signed cert
        resp = http.post(
            f"{base_url}/suite-api/api/auth/token/acquire",
            json=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        _ops_token_ui  = resp.json()["token"]
        _ops_token_for = cache_key
        return _ops_token_ui


@st.cache_data(ttl=config.ALERT_CACHE_TTL, show_spinner=False)
def _fetch_alerts_cached(base_url: str, user: str, password: str, severity: str = "") -> list[dict]:
    """Fetch live alerts from Aria Ops — raises on any error so failures are never cached.

    Credentials are explicit parameters so @st.cache_data invalidates when they change.
    Performs one automatic retry on 401 (expired token).
    """
    global _ops_token_ui
    token = os.getenv("VCF_OPS_TOKEN", "")  # Basic-auth fallback for advanced users

    if not base_url or (not user and not token):
        return []

    with httpx.Client(verify=False) as http:  # noqa: S501
        # --- Step 1: Authenticate ---
        if user:
            ops_token = _acquire_ops_token_sync(base_url, user, password)
            headers = {"Authorization": f"OpsToken {ops_token}", "Accept": "application/json"}
        else:
            headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}

        # --- Step 2: Fetch alerts; retry once on 401 (expired token) ---
        url = f"{base_url}/suite-api/api/alerts"
        if severity:
            url += f"?alertCriticality={severity.upper()}"
        resp = http.get(url, headers=headers)

        if resp.status_code == 401 and user:
            # Token expired — force re-authentication and retry once.
            ops_token = _acquire_ops_token_sync(base_url, user, password, force=True)
            headers = {"Authorization": f"OpsToken {ops_token}", "Accept": "application/json"}
            resp = http.get(url, headers=headers)

        resp.raise_for_status()
        raw_alerts = resp.json().get("alerts", [])

        # --- Step 3: Resolve resource names ---
        # Aria Ops alert objects contain only a resourceId (UUID). We call
        # GET /resources/{id} for each unique resource to get the display name.
        resource_cache: dict[str, str] = {}
        for a in raw_alerts[:config.MAX_ALERTS]:
            rid = a.get("resourceId", "")
            if rid and rid not in resource_cache:
                r = http.get(f"{base_url}/suite-api/api/resources/{rid}", headers=headers)
                resource_cache[rid] = (
                    r.json().get("resourceKey", {}).get("name", rid)
                    if r.status_code == 200 else rid
                )

        # --- Step 4: Build structured result list ---
        alerts = []
        for a in raw_alerts[:config.MAX_ALERTS]:
            rid = a.get("resourceId", "")
            alerts.append({
                "resource":    resource_cache.get(rid, rid or "unknown"),
                "name":        a.get("alertDefinitionName") or a.get("alertName") or a.get("type", "unknown"),
                "criticality": a.get("criticality", a.get("alertLevel", "")).upper(),
            })
        return alerts


def fetch_lab_alerts(base_url: str, user: str, password: str, severity: str = "") -> tuple[list[dict], str]:
    """Public wrapper around _fetch_alerts_cached.

    Converts exceptions to ([], error_message). Errors are NOT cached.
    """
    try:
        return _fetch_alerts_cached(base_url, user, password, severity), ""
    except httpx.HTTPStatusError as e:
        return [], f"HTTP {e.response.status_code} — {e.response.text[:200]}"
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"


@st.cache_data(ttl=config.ALERT_CACHE_TTL, show_spinner=False)
def _fetch_license_cached(base_url: str, user: str, password: str) -> dict:
    """Fetch licence info from Aria Ops — raises on error so failures are never cached.

    Credentials are explicit parameters so @st.cache_data invalidates when they change.
    """
    if not base_url or not user:
        raise ValueError("VCF Ops URL and username are required.")

    ops_token = _acquire_ops_token_sync(base_url, user, password)
    headers = {"Authorization": f"OpsToken {ops_token}", "Accept": "application/json"}

    with httpx.Client(verify=False) as http:  # noqa: S501
        info_resp    = http.get(f"{base_url}/suite-api/api/product/licensing/info",    headers=headers)
        edition_resp = http.get(f"{base_url}/suite-api/api/product/licensing/edition", headers=headers)
        info_resp.raise_for_status()
        edition_resp.raise_for_status()
        info    = info_resp.json()
        edition = edition_resp.json()

    exp_ts   = info.get("expirationDate")
    exp_date = (
        datetime.fromtimestamp(exp_ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if exp_ts else "N/A"
    )
    return {
        "licensed":       info.get("licensed", False),
        "licenseName":    info.get("licenseName", "Unknown"),
        "expirationDate": exp_date,
        "edition":        edition.get("productLicensingEdition", "UNKNOWN"),
    }


def fetch_license_info(base_url: str, user: str, password: str) -> tuple[dict, str]:
    """Public wrapper around _fetch_license_cached.

    Converts exceptions to ({}, error_message). Errors are NOT cached.
    """
    try:
        return _fetch_license_cached(base_url, user, password), ""
    except httpx.HTTPStatusError as e:
        return {}, f"HTTP {e.response.status_code} — {e.response.text[:200]}"
    except Exception as e:
        return {}, f"{type(e).__name__}: {e}"


@st.cache_data(ttl=30)
def get_available_models():
    try:
        result = ollama.list()
        names  = [m.model for m in result.models if m.model]
        return names if names else [config.LLM_MODEL, "qwen2.5:32b"]
    except Exception:
        return [config.LLM_MODEL, "qwen2.5:32b"]


# --- 4. TOKEN HELPERS ---
def _chunk_stat(chunk, key: str) -> int:
    """Safely read an integer stat from an Ollama streaming chunk (dict or object)."""
    try:
        val = chunk[key] if isinstance(chunk, dict) else getattr(chunk, key, None)
        return int(val) if val else 0
    except Exception:
        return 0


def _token_caption(tokens: dict) -> None:
    """Render a compact token-usage + cost line under an assistant message."""
    prompt     = tokens.get("prompt", 0)
    completion = tokens.get("completion", 0)
    tps        = tokens.get("tok_per_sec", 0)

    rate_in  = st.session_state.get("rate_input",  config.UI_COST_PER_1M_INPUT)
    rate_out = st.session_state.get("rate_output", config.UI_COST_PER_1M_OUTPUT)
    cost     = prompt / 1_000_000 * rate_in + completion / 1_000_000 * rate_out

    parts = []
    if prompt:
        parts.append(f"↑ {prompt:,} prompt")
    if completion:
        parts.append(f"↓ {completion:,} completion")
    if tps:
        parts.append(f"{tps:,} tok/s")
    if cost:
        parts.append(f"~${cost:.4f}")

    if parts:
        st.caption("  ·  ".join(parts))


# --- 5. TOP TOOLBAR ---
# Narrow action buttons + a settings popover keep the full page width free for chat.
# Widget keys write their values to st.session_state so settings survive while the popover is closed.
_ops_status = ("🟢 VCF Ops connected" if _normalise_ops_url(st.session_state.vcf_ops_url) else "⚪ VCF Ops not configured")
_col_clear, _col_theme, _col_settings, _col_ops_status = st.columns([1, 1, 2, 6])

with _col_clear:
    if st.button("🗑️ Clear", use_container_width=True, help="Clear chat history"):
        st.session_state.messages        = []
        st.session_state.session_tokens  = {"prompt": 0, "completion": 0}
        st.session_state.last_query_type = "docs"
        st.rerun()

with _col_theme:
    if st.button("☀️ Light" if _dark else "🌙 Dark", use_container_width=True, help="Toggle light / dark mode"):
        st.session_state.theme = "light" if _dark else "dark"
        st.rerun()

with _col_ops_status:
    st.caption(_ops_status)

with _col_settings:
    with st.popover("⚙️ Settings", use_container_width=True):
        available_versions = sorted(config.VERSION_MAP.keys(), reverse=True)
        st.selectbox("VCF Version", available_versions, key="selected_version")

        available_models = get_available_models()
        if st.session_state.selected_model not in available_models:
            st.session_state.selected_model = available_models[0] if available_models else config.LLM_MODEL
        st.selectbox("Brain (LLM)", available_models, key="selected_model")

        st.selectbox("Answer style", list(config.UI_TEMP_OPTIONS.keys()), key="temp_label")

        st.divider()
        st.caption("**VCF Operations connection**")
        st.text_input("URL", placeholder="vcf-ops.lab.local", key="vcf_ops_url")
        st.text_input("Username", placeholder="admin@local", key="vcf_ops_user")
        st.text_input("Password", type="password", key="vcf_ops_pass")
        if st.button("💾 Save connection", use_container_width=True):
            _save_ops_config(
                st.session_state.vcf_ops_url,
                st.session_state.vcf_ops_user,
                st.session_state.vcf_ops_pass,
            )
            st.success("Connection saved.")

        st.divider()
        st.caption("**Cloud cost shadow** *(local inference is free)*")
        st.number_input("Input $/1M tokens",  min_value=0.0, step=0.01, format="%.2f", key="rate_input")
        st.number_input("Output $/1M tokens", min_value=0.0, step=0.01, format="%.2f", key="rate_output")

        session_t     = st.session_state.session_tokens
        session_total = session_t["prompt"] + session_t["completion"]
        if session_total > 0:
            st.divider()
            _cost = (
                session_t["prompt"]     / 1_000_000 * st.session_state.rate_input +
                session_t["completion"] / 1_000_000 * st.session_state.rate_output
            )
            st.caption(
                f"**Session tokens**  \n"
                f"↑ {session_t['prompt']:,} prompt  \n"
                f"↓ {session_t['completion']:,} completion  \n"
                f"**{session_total:,} total**  \n"
                f"~**${_cost:.4f}** cloud equivalent"
            )

# Read current settings from session state — the popover widgets may not be rendered
# on every rerun (only when open), so session state is the source of truth.
selected_version = st.session_state.selected_version
selected_model   = st.session_state.selected_model
temp             = config.UI_TEMP_OPTIONS[st.session_state.temp_label]

# --- 6. AUTO-CLEAR ON VERSION SWITCH ---
if st.session_state.get("active_version") != selected_version:
    st.session_state.messages       = []
    st.session_state.session_tokens = {"prompt": 0, "completion": 0}
    st.session_state.active_version = selected_version


# --- 7. RAG ENGINE ---
def get_vcf_context(query: str, version: str):
    collection          = get_collection(version)
    instructional_query = f"{config.QUERY_PREFIX}{query}"
    results             = collection.query(
        query_texts=[instructional_query],
        n_results=config.DEFAULT_N,
    )

    docs  = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]

    context_parts, sources = [], []
    for text, meta, dist in zip(docs, metas, dists):
        if dist > config.MAX_DISTANCE:
            continue
        page      = meta.get("page", "?")
        file_name = meta.get("source", "Manual")
        ver       = meta.get("version", version)
        context_parts.append(f"[VCF {ver} | {file_name} | Page {page}]\n{text}")
        sources.append(f"VCF {ver} — {file_name} (Pg. {page})")

    # If the distance threshold filtered everything, fall back to the closest match
    if not context_parts and docs:
        meta = metas[0]
        ver  = meta.get("version", version)
        context_parts.append(
            f"[VCF {ver} | {meta.get('source', 'Manual')} | Page {meta.get('page', '?')}]\n{docs[0]}"
        )
        sources.append(f"VCF {ver} — {meta.get('source', 'Manual')} (Pg. {meta.get('page', '?')})")

    return "\n---\n".join(context_parts), list(dict.fromkeys(sources))


# --- 8. ALERT HELPERS ---
def _is_doc_query(prompt: str) -> bool:
    """Return True when the prompt contains doc-intent keywords AND no alert-intent keywords.

    Alert-intent words (alert, health, issue…) always win over doc-keyword matches so
    that prompts like "any nsx alerts?" or "sddc health?" route to Aria Ops, not the RAG.
    """
    words = set(prompt.lower().split())
    return bool(words & config.UI_DOC_KEYWORDS) and not bool(words & config.UI_ALERT_KEYWORDS)


def _is_license_query(prompt: str) -> bool:
    """Return True when the prompt is asking about licensing or product edition."""
    lp = prompt.lower()
    return any(kw in lp for kw in ("licens", "edition"))


# --- 9. RESPONSE GENERATOR ---
def _generate_response(user_prompt: str, version: str, model: str, temperature: float) -> None:
    """Stream an assistant response and append it to session messages."""
    # Routing priority:
    #   1. Licence query  → live licence data (if Aria Ops is configured)
    #   2. Alert query    → live alerts      (if Aria Ops is configured or last turn was an alert)
    #   3. Anything else  → RAG over VCF docs
    _last      = st.session_state.get("last_query_type", "docs")
    _ops_url   = _normalise_ops_url(st.session_state.get("vcf_ops_url",  ""))
    _ops_user  = st.session_state.get("vcf_ops_user", "")
    _ops_pass  = st.session_state.get("vcf_ops_pass", "")
    _ops_ready = bool(_ops_url)
    is_license_query = (
        (_is_license_query(user_prompt) and _ops_ready)
        or (_last == "license" and not _is_doc_query(user_prompt) and _ops_ready)
    )
    is_alert_query = (
        not is_license_query
        and not _is_doc_query(user_prompt)
        and (_ops_ready or _last == "alert")
    )

    with st.chat_message("assistant"):
        _spinner = (
            "Checking licence status..." if is_license_query
            else "Fetching live lab alerts..." if is_alert_query
            else f"Consulting VCF {version} library..."
        )
        with st.status(_spinner) as status:
            context         = ""
            source_list     = []
            alert_context   = ""
            license_context = ""

            if is_license_query:
                # Licence query — call both licensing endpoints and surface the result.
                info, lic_err = fetch_license_info(_ops_url, _ops_user, _ops_pass)
                if lic_err:
                    st.error(lic_err)
                    license_context = f"[Licence fetch error: {lic_err}]"
                else:
                    licensed = "✅ Licensed" if info.get("licensed") else "❌ Not licensed"
                    edition  = info.get("edition", "UNKNOWN")
                    lic_name = info.get("licenseName", "Unknown")
                    exp_date = info.get("expirationDate", "N/A")
                    st.write("**VCF Operations licence:**")
                    st.write(f"- **Status:** {licensed}")
                    st.write(f"- **Edition:** {edition}")
                    st.write(f"- **Licence name:** {lic_name}")
                    st.write(f"- **Expires:** {exp_date}")
                    license_context = (
                        f"VCF OPERATIONS LICENCE:\n"
                        f"Status: {'Licensed' if info.get('licensed') else 'Not Licensed'}\n"
                        f"Edition: {edition}\n"
                        f"Licence name: {lic_name}\n"
                        f"Expiration date: {exp_date}"
                    )

            elif is_alert_query:
                # Pure alert query — skip RAG entirely, fetch live data only.
                raw_alerts, alert_err = fetch_lab_alerts(_ops_url, _ops_user, _ops_pass)

                # Render alerts directly in the UI so icons are always visible,
                # regardless of how the LLM chooses to format its response.
                if alert_err:
                    st.error(alert_err)
                    alert_context = f"[Lab alert fetch error: {alert_err}]"
                elif not raw_alerts:
                    st.write("No active alerts found.")
                    alert_context = "[No active lab alerts found at this time.]"
                else:
                    st.write("**Live lab alerts:**")
                    for a in raw_alerts:
                        icon = config.UI_SEVERITY_ICON.get(a["criticality"], "⚪")
                        st.write(f"{icon} {a['criticality']} — **{a['resource']}**: {a['name']}")
                    alert_lines = [
                        f"{config.UI_SEVERITY_ICON.get(a['criticality'], '⚪')} [{a['criticality']}] {a['resource']}: {a['name']}"
                        for a in raw_alerts
                    ]
                    alert_context = "LIVE LAB ALERTS:\n" + "\n".join(alert_lines)
            else:
                # Documentation query — run RAG, no alert fetch needed.
                context, source_list = get_vcf_context(user_prompt, version)
                st.write("**References found:**")
                for s in source_list:
                    st.write(f"- {s}")

            status.update(label="Analysing data...", state="complete")

        if is_alert_query:
            system_prompt = (
                "You are a VCF Operations monitoring assistant. "
                "Check the live alerts of my SDDC."
                "Check the alerts in my lab."
                "Summarize the live lab alerts provided below. "
                "Group by severity, highlight the most critical issues first, "
                "and suggest remediation steps where applicable. "
                "Do not invent alerts not listed in the context. "
            )
        elif is_license_query:
            system_prompt = (
                "You are a VCF Operations licensing assistant. "
                "Report the licence status from the data provided below. "
                "Do not invent information not present in the context. "
            )
        else:
            system_prompt = (
                f"You are a Senior VCF {version} Architect. "
                "Answer using only the context provided below. "
                "Quote specific hardware specs or CLI commands exactly as they appear. "
                "If the answer is not in the context, say so clearly. "
            )

        if context:
            system_prompt += f"\n\nCONTEXT FROM VCF {version} MANUALS:\n{context}"
        if alert_context:
            system_prompt += (
                f"\n\n{alert_context}"
                "\n\nWhen referencing alerts in your response, always start each alert line "
                "with its severity icon: 🔴 for CRITICAL, 🟠 for IMMEDIATE, 🟡 for WARNING, 🟢 for INFORMATION."
            )
        if license_context:
            system_prompt += f"\n\n{license_context}"

        ollama_messages = [{"role": "system", "content": system_prompt}]
        ollama_messages.extend(st.session_state.messages)

        try:
            response = ollama.chat(
                model=model,
                messages=ollama_messages,
                options={"temperature": temperature, "num_ctx": config.NUM_CTX},
                stream=True,
            )

            full_response = ""
            last_chunk    = None
            placeholder   = st.empty()
            for chunk in response:
                token = chunk.message.content
                if token:
                    full_response += token
                    placeholder.markdown(full_response + "▌")
                last_chunk = chunk
            placeholder.markdown(full_response)

        except Exception as e:
            st.error(
                f"**Ollama error:** {e}  \n"
                f"Is Ollama running with `{model}` pulled?"
            )
            return

        prompt_tokens     = _chunk_stat(last_chunk, "prompt_eval_count")
        completion_tokens = _chunk_stat(last_chunk, "eval_count")
        eval_duration_ns  = _chunk_stat(last_chunk, "eval_duration")
        tok_per_sec = (
            round(completion_tokens / (eval_duration_ns / 1e9))
            if eval_duration_ns > 0 else 0
        )

        tokens = {
            "prompt":      prompt_tokens,
            "completion":  completion_tokens,
            "tok_per_sec": tok_per_sec,
        }
        _token_caption(tokens)

        st.session_state.session_tokens["prompt"]     += prompt_tokens
        st.session_state.session_tokens["completion"] += completion_tokens

    st.session_state.messages.append({
        "role":    "assistant",
        "content": full_response,
        "tokens":  tokens,
    })
    st.session_state.last_query_type = (
        "license" if is_license_query else "alert" if is_alert_query else "docs"
    )


# --- 10. CHAT UI ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and "tokens" in message:
            _token_caption(message["tokens"])

# Retry button — shown only after the last assistant message.
if (
    st.session_state.messages
    and st.session_state.messages[-1]["role"] == "assistant"
):
    if st.button("↺  Regenerate", key="retry_btn"):
        st.session_state.messages.pop()
        st.session_state.pending_retry = True
        st.rerun()

# Execute a pending retry: session messages now end with the user question.
if (
    st.session_state.get("pending_retry")
    and st.session_state.messages
    and st.session_state.messages[-1]["role"] == "user"
):
    st.session_state.pending_retry = False
    _generate_response(
        st.session_state.messages[-1]["content"],
        selected_version,
        selected_model,
        temp,
    )

if prompt := st.chat_input(f"Ask about VCF {selected_version} deployment, networking, or storage..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    _generate_response(prompt, selected_version, selected_model, temp)
