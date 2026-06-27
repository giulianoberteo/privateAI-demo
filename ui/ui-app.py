import os
import sys
import httpx  # pyright: ignore[reportMissingImports]
import streamlit as st
import ollama
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # pyright: ignore[reportMissingImports]
from themes import PALETTES, build_css  # pyright: ignore[reportMissingImports]

# --- ARIA OPS TOKEN CACHE ---
# Acquired once per server process lifetime; shared across all Streamlit sessions.
_ops_token_ui: str = ""


# --- CONSTANTS ---
_TEMP_OPTIONS = {
    "Precise":      0.1,
    "Balanced":     0.4,
    "Creative":     0.7,
    "Experimental": 1.0,
}

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="VCF vArchitect Agent", page_icon="🛡️", layout="wide")

# --- 2. SESSION STATE INIT ---
if "theme" not in st.session_state:
    st.session_state.theme = "light"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_tokens" not in st.session_state:
    st.session_state.session_tokens = {"prompt": 0, "completion": 0}
if "last_query_type" not in st.session_state:
    st.session_state.last_query_type = "docs"  # "alert" or "docs"

# --- THEME ---
_dark = st.session_state.theme == "dark"


@st.cache_data
def _get_css(theme_name: str) -> str:
    return build_css(PALETTES[theme_name])


st.markdown(_get_css("dark" if _dark else "light"), unsafe_allow_html=True)

st.title("🦅 Hawk - VCF vArchitect Agent")


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


def _acquire_ops_token_sync(base_url: str, user: str, password: str) -> str:
    """Exchange username + password for a short-lived Aria Ops OpsToken (cached module-level)."""
    global _ops_token_ui
    if _ops_token_ui:
        return _ops_token_ui
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
        _ops_token_ui = resp.json()["token"]
        return _ops_token_ui


@st.cache_data(ttl=120, show_spinner=False)
def fetch_lab_alerts(severity: str = "") -> tuple[list[dict], str]:
    """Fetch active alerts from Aria Ops and return (alerts, error_message).

    Results are cached for 120 seconds. Call fetch_lab_alerts.clear() to force
    an immediate refresh (e.g. from a Refresh button).

    Steps:
      1. Read connection details from env vars (set in shell or .env before starting Streamlit).
      2. Acquire an OpsToken via POST /suite-api/api/auth/token/acquire (cached module-level).
      3. Fetch alerts from GET /suite-api/api/alerts with an optional severity filter.
      4. Resolve each alert's resourceId to a human-readable name via GET /suite-api/api/resources/{id}.
    """
    base_url = os.getenv("VCF_OPS_URL", "")
    user     = os.getenv("VCF_OPS_USER", "")
    password = os.getenv("VCF_OPS_PASS", "")
    token    = os.getenv("VCF_OPS_TOKEN", "")

    # Return empty gracefully if Aria Ops is not configured.
    if not base_url or (not user and not token):
        return [], ""

    with httpx.Client(verify=False) as http:  # noqa: S501
        try:
            # --- Step 1: Authenticate ---
            # Preferred: exchange username + password for a short-lived OpsToken.
            # Fallback: use a pre-encoded Basic token set in VCF_OPS_TOKEN.
            if user:
                try:
                    ops_token = _acquire_ops_token_sync(base_url, user, password)
                except httpx.HTTPStatusError as e:
                    return [], f"Token acquisition failed — HTTP {e.response.status_code}: {e.response.text[:200]}"
                headers = {"Authorization": f"OpsToken {ops_token}", "Accept": "application/json"}
            else:
                headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}

            # --- Step 2: Fetch alerts ---
            # Without a severity filter the API returns all active alerts.
            # With a filter it returns only alerts matching that criticality level.
            url = f"{base_url}/suite-api/api/alerts"
            if severity:
                url += f"?alertCriticality={severity.upper()}"
            resp = http.get(url, headers=headers)
            resp.raise_for_status()
            raw_alerts = resp.json().get("alerts", [])

            # --- Step 3: Resolve resource names ---
            # Aria Ops alert objects contain only a resourceId (UUID), not a
            # human-readable name. We call GET /resources/{id} for each unique
            # resource in the top-10 alerts to get the display name.
            resource_cache: dict[str, str] = {}
            for a in raw_alerts[:10]:
                rid = a.get("resourceId", "")
                if rid and rid not in resource_cache:
                    r = http.get(f"{base_url}/suite-api/api/resources/{rid}", headers=headers)
                    resource_cache[rid] = (
                        r.json().get("resourceKey", {}).get("name", rid)
                        if r.status_code == 200 else rid
                    )

            # --- Step 4: Build structured result list ---
            alerts = []
            for a in raw_alerts[:10]:
                rid = a.get("resourceId", "")
                alerts.append({
                    "resource":    resource_cache.get(rid, rid or "unknown"),
                    "name":        a.get("alertDefinitionName") or a.get("alertName") or a.get("type", "unknown"),
                    "criticality": a.get("criticality", a.get("alertLevel", "")).upper(),
                })
            return alerts, ""

        except httpx.HTTPStatusError as e:
            return [], f"HTTP {e.response.status_code} — {e.response.text[:200]}"
        except Exception as e:
            return [], f"{type(e).__name__}: {e}"


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
    """Render a compact token-usage line under an assistant message."""
    prompt     = tokens.get("prompt", 0)
    completion = tokens.get("completion", 0)
    tps        = tokens.get("tok_per_sec", 0)

    parts = []
    if prompt:
        parts.append(f"↑ {prompt:,} prompt")
    if completion:
        parts.append(f"↓ {completion:,} completion")
    if tps:
        parts.append(f"{tps:,} tok/s")

    if parts:
        st.caption("  ·  ".join(parts))


# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("Settings")

    available_versions = sorted(config.VERSION_MAP.keys(), reverse=True)
    selected_version   = st.selectbox("VCF Version", available_versions, index=0)

    available_models = get_available_models()
    default_idx      = (
        available_models.index(config.LLM_MODEL)
        if config.LLM_MODEL in available_models else 0
    )
    selected_model = st.selectbox("Brain (LLM)", available_models, index=default_idx)

    _temp_label = st.selectbox("Answer style", list(_TEMP_OPTIONS.keys()), index=0)
    temp = _TEMP_OPTIONS[_temp_label]

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages        = []
        st.session_state.session_tokens  = {"prompt": 0, "completion": 0}
        st.session_state.last_query_type = "docs"
        st.rerun()

    _toggle_label = "☀️ Light mode" if _dark else "🌙 Dark mode"
    if st.button(_toggle_label, use_container_width=True):
        st.session_state.theme = "light" if _dark else "dark"
        st.rerun()

    session_t     = st.session_state.session_tokens
    session_total = session_t["prompt"] + session_t["completion"]
    if session_total > 0:
        st.divider()
        st.caption(
            f"**Session tokens**  \n"
            f"↑ {session_t['prompt']:,} prompt  \n"
            f"↓ {session_t['completion']:,} completion  \n"
            f"**{session_total:,} total**"
        )


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
# Doc keywords trigger the RAG path regardless of anything else.
# Everything that isn't a doc query goes to Aria Ops when VCF_OPS_URL is configured.
_DOC_KEYWORDS = frozenset({
    "vcf", "nsx", "vsan", "vsphere", "esxi", "vcenter", "vcentre",
    "configure", "install", "deploy", "setup", "architecture",
    "storage", "network", "cluster", "sddc", "documentation", "manual",
})

def _is_doc_query(prompt: str) -> bool:
    """Return True when the prompt explicitly references VCF documentation topics."""
    words = set(prompt.lower().split())
    return bool(words & _DOC_KEYWORDS)



# --- 9. RESPONSE GENERATOR ---
def _generate_response(user_prompt: str, version: str, model: str, temperature: float) -> None:
    """Stream an assistant response and append it to session messages."""
    # If the prompt contains VCF/doc keywords → RAG.
    # Otherwise, if Aria Ops is configured → live alerts (catches any natural
    # language like "how's my lab", "any issues?", "give me a summary", etc.).
    # Follow-up after an alert turn also stays on the alert path.
    _vcf_ops_configured = bool(os.getenv("VCF_OPS_URL"))
    is_alert_query = not _is_doc_query(user_prompt) and (
        _vcf_ops_configured
        or st.session_state.get("last_query_type") == "alert"
    )

    with st.chat_message("assistant"):
        with st.status("Fetching live lab alerts..." if is_alert_query else f"Consulting VCF {version} library...") as status:

            _ICON = {"CRITICAL": "🔴", "IMMEDIATE": "🔴", "WARNING": "🟡", "INFORMATION": "🟢"}

            if is_alert_query:
                # Pure alert query — skip RAG entirely, fetch live data only.
                raw_alerts, alert_err = fetch_lab_alerts()
                context     = ""
                source_list = []

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
                        icon = _ICON.get(a["criticality"], "⚪")
                        st.write(f"{icon} {a['criticality']} — **{a['resource']}**: {a['name']}")
                    alert_lines = [
                        f"{_ICON.get(a['criticality'], '⚪')} [{a['criticality']}] {a['resource']}: {a['name']}"
                        for a in raw_alerts
                    ]
                    alert_context = "LIVE LAB ALERTS:\n" + "\n".join(alert_lines)
            else:
                # Documentation query — run RAG, no alert fetch needed.
                context, source_list = get_vcf_context(user_prompt, version)
                st.write("**References found:**")
                for s in source_list:
                    st.write(f"- {s}")
                alert_context = ""

            status.update(label="Analysing data...", state="complete")

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
                "with its severity icon: 🔴 for CRITICAL/IMMEDIATE, 🟡 for WARNING, 🟢 for INFORMATION."
            )

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
    st.session_state.last_query_type = "alert" if is_alert_query else "docs"


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
