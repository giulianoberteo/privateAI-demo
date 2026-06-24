"""
ui/themes.py — VMware Clarity colour palettes and CSS builder.

All visual constants live here. ui-app.py imports from this module and
contains no hardcoded colours or CSS strings.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Colour palettes  (VMware Clarity Design System)
# ─────────────────────────────────────────────────────────────────────────────

# Clarity Design dark — construction scale (hsl 198) + blue[400] accent
DARK = dict(
    bg_app          = "#1B2B32",   # construction[1000]
    bg_sidebar      = "#17252B",   # construction[1100] hsl(200,31%,13%)
    bg_card         = "#21333B",   # construction[900]
    bg_card_hover   = "#2D4048",   # construction[800]
    bg_input        = "#21333B",   # construction[900]
    bg_tag          = "#2D4048",   # construction[800]
    border          = "#6A7A81",   # construction[500]
    border_focus    = "#2EC0FF",   # blue[400] hsl(198,100%,59%)
    text_primary    = "#FFFFFF",
    text_secondary  = "#AEB7BC",   # construction[300]
    text_muted      = "#859399",   # construction[400] hsl(198,9%,56%)
    accent          = "#2EC0FF",   # blue[400]
    tag_text        = "#2EC0FF",
    shadow          = "0 1px 3px rgba(0,0,0,0.4)",
    shadow_hover    = "0 3px 8px rgba(0,0,0,0.5)",
)

# Clarity Design light — construction scale + blue[700] action colour
LIGHT = dict(
    bg_app          = "#F1F7F8",   # construction[50]
    bg_sidebar      = "#FFFFFF",
    bg_card         = "#FCFDFD",   # construction[25]
    bg_card_hover   = "#E3EAED",   # construction[100] hsl(198,20%,91%)
    bg_input        = "#FFFFFF",
    bg_tag          = "#E6F7FF",   # blue[50] hsl(198,100%,95%)
    border          = "#CBD3D8",   # construction[200] hsl(198,14%,82%)
    border_focus    = "#0079AD",   # blue[700] hsl(198,100%,34%)
    text_primary    = "#3A4D55",   # construction[700]
    text_secondary  = "#6A7A81",   # construction[500]
    text_muted      = "#AEB7BC",   # construction[300]
    accent          = "#0079AD",   # blue[700]
    tag_text        = "#0079AD",
    shadow          = "0 1px 3px rgba(0,0,0,0.1)",
    shadow_hover    = "0 3px 8px rgba(0,0,0,0.15)",
)

PALETTES = {"dark": DARK, "light": LIGHT}


# ─────────────────────────────────────────────────────────────────────────────
# CSS builder
# ─────────────────────────────────────────────────────────────────────────────

def build_css(v: dict) -> str:
    """Return a <style> block with all palette values baked in."""
    return f"""
<style>
/* ── Override Streamlit CSS variables ────────────────────── */
:root {{
    --primary-color:              {v['accent']};
    --background-color:           {v['bg_app']};
    --secondary-background-color: {v['bg_input']};
    --text-color:                 {v['text_primary']};
    --font: 'Metropolis', 'Avenir Next', Arial, sans-serif;
}}

/* ── Metropolis (local — ui/static/fonts/) ───────────────── */
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-Thin.woff2') format('woff2');              font-weight:100; font-style:normal;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-ThinItalic.woff2') format('woff2');       font-weight:100; font-style:italic;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-ExtraLight.woff2') format('woff2');       font-weight:200; font-style:normal;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-ExtraLightItalic.woff2') format('woff2'); font-weight:200; font-style:italic;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-Light.woff2') format('woff2');            font-weight:300; font-style:normal;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-LightItalic.woff2') format('woff2');     font-weight:300; font-style:italic;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-Regular.woff2') format('woff2');          font-weight:400; font-style:normal;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-RegularItalic.woff2') format('woff2');   font-weight:400; font-style:italic;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-Medium.woff2') format('woff2');           font-weight:500; font-style:normal;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-MediumItalic.woff2') format('woff2');    font-weight:500; font-style:italic;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-SemiBold.woff2') format('woff2');         font-weight:600; font-style:normal;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-SemiBoldItalic.woff2') format('woff2');  font-weight:600; font-style:italic;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-Bold.woff2') format('woff2');             font-weight:700; font-style:normal;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-BoldItalic.woff2') format('woff2');      font-weight:700; font-style:italic;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-ExtraBold.woff2') format('woff2');        font-weight:800; font-style:normal;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-ExtraBoldItalic.woff2') format('woff2'); font-weight:800; font-style:italic;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-Black.woff2') format('woff2');            font-weight:900; font-style:normal;  font-display:swap; }}
@font-face {{ font-family:'Metropolis'; src:url('app/static/fonts/Metropolis-BlackItalic.woff2') format('woff2');     font-weight:900; font-style:italic;  font-display:swap; }}

/* ── Font stack ──────────────────────────────────────────── */
html, body, .stApp, [data-testid="stAppViewContainer"],
button, input, textarea, select,
p, li, label, h1, h2, h3, h4, h5, h6,
[data-baseweb="base-input"], [data-baseweb="select"],
[data-testid="stChatInput"] textarea {{
    font-family: 'Metropolis', 'Avenir Next', Arial, sans-serif !important;
}}
/* Restore Material Icons for Streamlit icon elements */
[class*="material-icons"],
[class*="material-symbols"],
[data-testid="stSidebarCollapseButton"] span,
[data-testid="stSidebarCollapseButton"] *,
[data-testid="collapsedControl"] span,
[data-testid="collapsedControl"] * {{
    font-family: 'Material Symbols Sharp', 'Material Symbols Outlined',
                 'Material Symbols Rounded', 'Material Icons',
                 'Material Icons Outlined', 'Material Icons Round' !important;
}}

/* ── Reset & app shell ───────────────────────────────────── */
.stApp,
[data-testid="stAppViewContainer"] {{
    background-color: {v['bg_app']} !important;
}}
[data-testid="stHeader"] {{
    background-color: {v['bg_app']} !important;
    border-bottom: 1px solid {v['border']};
}}
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div:first-child {{
    background-color: {v['bg_sidebar']} !important;
    border-right: 1px solid {v['border']} !important;
}}
[data-testid="stMainBlockContainer"] {{
    max-width: 1400px;
    padding: 1.75rem 2.5rem 4rem;
}}
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"] {{
    background-color: {v['bg_app']} !important;
}}

/* ── Typography ──────────────────────────────────────────── */
p, li, label {{
    color: {v['text_primary']};
    font-size: 16px;
    line-height: 1.6;
}}
span {{
    color: {v['text_primary']};
    line-height: 1.6;
}}
h1 {{
    color: {v['text_primary']};
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.3;
}}
h2, h3 {{
    color: {v['text_primary']};
    font-weight: 600;
    letter-spacing: -0.02em;
    line-height: 1.3;
}}
h4 {{
    color: {v['text_primary']};
    font-weight: 600;
    letter-spacing: -0.01em;
}}
[data-testid="stCaptionContainer"] p,
small, .stCaption {{
    color: {v['text_secondary']} !important;
    font-size: 14px;
}}

/* ── Sidebar text ────────────────────────────────────────── */
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span {{
    color: {v['text_primary']} !important;
}}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{
    color: {v['text_primary']} !important;
}}
[data-testid="stSidebarCollapseButton"] button {{
    background: transparent !important;
    border: none !important;
    color: {v['text_secondary']} !important;
}}
[data-testid="stSidebarCollapseButton"] svg {{
    fill: {v['text_secondary']} !important;
    color: {v['text_secondary']} !important;
}}
[data-testid="collapsedControl"] button {{
    background: {v['bg_sidebar']} !important;
    border: 1px solid {v['border']} !important;
    color: {v['text_secondary']} !important;
    border-radius: 0 3px 3px 0;
}}
[data-testid="collapsedControl"] svg {{
    fill: {v['text_primary']} !important;
    color: {v['text_primary']} !important;
}}

/* ── Bordered containers (cards) ─────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] > div {{
    background-color: {v['bg_card']} !important;
    border: 1px solid {v['border']} !important;
    border-radius: 3px !important;
    box-shadow: {v['shadow']};
    transition: box-shadow 0.15s ease, background-color 0.15s ease;
}}
[data-testid="stVerticalBlockBorderWrapper"] > div:hover {{
    background-color: {v['bg_card_hover']} !important;
    box-shadow: {v['shadow_hover']};
}}

/* ── Buttons ─────────────────────────────────────────────── */
.stButton > button,
[data-testid="stBaseButton-secondary"] {{
    background: transparent !important;
    border: 1px solid {v['accent']} !important;
    color: {v['accent']} !important;
    border-radius: 3px;
    font-weight: 500;
    font-size: 14px;
    padding: 6px 16px;
    transition: background 0.12s, color 0.12s;
}}
.stButton > button:hover,
[data-testid="stBaseButton-secondary"]:hover {{
    background: {v['accent']} !important;
    color: #ffffff !important;
}}
.stButton > button[kind="primary"],
[data-testid="stBaseButton-primary"] {{
    background: {v['accent']} !important;
    border: none !important;
    color: #ffffff !important;
    font-weight: 600;
}}
.stButton > button[kind="primary"]:hover,
[data-testid="stBaseButton-primary"]:hover {{
    opacity: 0.88;
}}

/* ── Text inputs & text areas ────────────────────────────── */
[data-baseweb="base-input"] {{
    background-color: {v['bg_input']} !important;
    color: {v['text_primary']} !important;
}}
[data-baseweb="base-input"] > div {{
    background-color: {v['bg_input']} !important;
}}
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input,
.stTextInput input,
.stTextArea textarea,
[data-baseweb="base-input"] input,
[data-baseweb="base-input"] textarea {{
    background-color: {v['bg_input']} !important;
    border: 1px solid {v['border']} !important;
    color: {v['text_primary']} !important;
    border-radius: 3px;
    transition: border-color 0.12s;
}}
.stApp .stTextInput input::placeholder,
.stApp .stTextArea textarea::placeholder,
.stApp [data-baseweb="base-input"] input::placeholder,
.stApp [data-baseweb="base-input"] textarea::placeholder,
.stApp [data-testid="stChatInput"] textarea::placeholder {{
    color: {v['text_muted']} !important;
    opacity: 1;
}}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus,
[data-baseweb="base-input"] input:focus,
[data-baseweb="base-input"] textarea:focus {{
    border-color: {v['border_focus']} !important;
    box-shadow: 0 0 0 2px {v['accent']}33 !important;
    outline: none;
}}

/* ── Select boxes ────────────────────────────────────────── */
.stSelectbox > div > div,
.stMultiSelect > div > div {{
    background-color: {v['bg_input']} !important;
    color: {v['text_primary']} !important;
}}
[data-baseweb="select"] {{
    background-color: {v['bg_input']} !important;
}}
[data-baseweb="select"] > div,
[data-baseweb="select"] > div > div {{
    background-color: {v['bg_input']} !important;
    border-color: {v['border']} !important;
    color: {v['text_primary']} !important;
}}
[data-baseweb="select"] span,
[data-baseweb="select"] input,
[data-baseweb="select"] [data-baseweb="input"] {{
    background-color: transparent !important;
    color: {v['text_primary']} !important;
}}
.stApp .stSelectbox [data-baseweb="select"] div {{
    color: {v['text_primary']} !important;
}}
[data-baseweb="tag"] {{
    background-color: {v['bg_tag']} !important;
    border-color: {v['border']} !important;
}}
[data-baseweb="tag"] span {{
    color: {v['tag_text']} !important;
}}
[data-baseweb="popover"],
[data-baseweb="popover"] > div {{
    background-color: {v['bg_card']} !important;
}}
[data-baseweb="popover"] [data-baseweb="menu"] {{
    background-color: {v['bg_card']} !important;
    border: 1px solid {v['border']} !important;
    border-radius: 3px;
}}
[data-baseweb="popover"] ul,
[data-baseweb="popover"] li {{
    background-color: {v['bg_card']} !important;
}}
[data-baseweb="popover"] [role="option"] {{
    background-color: {v['bg_card']} !important;
    color: {v['text_primary']} !important;
}}
[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="popover"] [aria-selected="true"] {{
    background-color: {v['bg_tag']} !important;
}}

/* ── Radio buttons ───────────────────────────────────────── */
[data-testid="stRadio"] label {{
    color: {v['text_primary']} !important;
}}
[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {{
    color: {v['text_primary']} !important;
}}

/* ── Slider ──────────────────────────────────────────────── */
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {{
    background-color: {v['accent']} !important;
    border-color: {v['accent']} !important;
}}
[data-testid="stSlider"] [data-baseweb="slider"] div[data-testid="stSliderThumb"] {{
    background-color: {v['accent']} !important;
}}

/* ── Status widget ───────────────────────────────────────── */
[data-testid="stStatusWidget"] {{
    background-color: {v['bg_card']} !important;
    border: none !important;
    border-radius: 3px !important;
}}
[data-testid="stStatusWidget"] p,
[data-testid="stStatusWidget"] span {{
    color: {v['text_primary']} !important;
}}

/* ── Alert / info boxes ──────────────────────────────────── */
[data-testid="stAlert"] {{
    background-color: {v['bg_card']} !important;
    border: 1px solid {v['border']} !important;
    border-radius: 3px !important;
}}
[data-testid="stAlert"] p {{
    color: {v['text_primary']} !important;
}}

/* ── Chat ────────────────────────────────────────────────── */
[data-testid="stChatInput"] {{
    background-color: {v['bg_app']} !important;
    border-top: 1px solid {v['border']};
}}
[data-testid="stChatInput"] > div {{
    background-color: transparent !important;
    border: none !important;
}}
[data-testid="stChatInput"] [data-baseweb="base-input"] {{
    background-color: {v['bg_input']} !important;
    border: none !important;
    border-radius: 3px !important;
    color: {v['text_primary']} !important;
}}
[data-testid="stChatInput"] [data-baseweb="base-input"] > div {{
    background-color: {v['bg_input']} !important;
    border: none !important;
    color: {v['text_primary']} !important;
}}
[data-testid="stChatInput"] textarea,
[data-testid="stChatInputTextArea"] {{
    background-color: {v['bg_input']} !important;
    color: {v['text_primary']} !important;
    border: none !important;
    min-height: 3rem !important;
    max-height: 8rem !important;
}}
[data-testid="stChatInput"] [data-baseweb="base-input"],
[data-testid="stChatInput"] > div > div {{
    max-width: 100% !important;
    width: 100% !important;
}}
[data-testid="stChatMessage"] {{
    background-color: {v['bg_card']} !important;
    border: 1px solid {v['border']} !important;
    border-radius: 3px;
}}
[data-testid="stChatMessage"] [data-testid="stLayoutWrapper"],
[data-testid="stChatMessage"] [data-testid="stLayoutWrapper"] > div,
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] > div {{
    border: none !important;
    box-shadow: none !important;
    background-color: transparent !important;
}}
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] > div:hover {{
    background-color: transparent !important;
    box-shadow: none !important;
}}
[data-testid="stChatMessageContent"],
[data-testid="stChatMessageContent"] p,
[data-testid="stChatMessageContent"] li,
[data-testid="stChatMessageContent"] span,
[data-testid="stChatMessageContent"] h1,
[data-testid="stChatMessageContent"] h2,
[data-testid="stChatMessageContent"] h3,
[data-testid="stChatMessageContent"] h4,
[data-testid="stChatMessageContent"] strong,
[data-testid="stChatMessageContent"] em,
[data-testid="stChatMessageContent"] a {{
    color: {v['text_primary']} !important;
}}
[data-testid="stChatMessageContent"] code {{
    background-color: {v['bg_input']} !important;
    color: {v['tag_text']} !important;
    border-radius: 4px;
    padding: 1px 5px;
}}
[data-testid="stChatMessageContent"] pre {{
    background-color: {v['bg_input']} !important;
    border: 1px solid {v['border']} !important;
    border-radius: 8px;
    padding: 12px;
}}
[data-testid="stChatMessageContent"] pre code {{
    color: {v['text_primary']} !important;
    background-color: transparent !important;
    padding: 0;
}}

/* ── Expander ────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    background-color: {v['bg_card']} !important;
    border-radius: 3px;
}}
[data-testid="stExpander"] summary {{
    background-color: {v['bg_card']} !important;
    color: {v['text_primary']} !important;
}}
[data-testid="stExpander"] summary:hover {{
    background-color: {v['bg_card_hover']} !important;
}}
[data-testid="stExpander"] summary svg,
[data-testid="stExpanderToggleIcon"],
[data-testid="stExpanderToggleIcon"] svg {{
    fill: {v['text_secondary']} !important;
    color: {v['text_secondary']} !important;
    stroke: {v['text_secondary']} !important;
}}
[data-testid="stExpanderDetails"] {{
    background-color: {v['bg_card']} !important;
    color: {v['text_primary']} !important;
}}
[data-testid="stExpanderDetails"] p,
[data-testid="stExpanderDetails"] li,
[data-testid="stExpanderDetails"] span,
[data-testid="stExpanderDetails"] label {{
    color: {v['text_primary']} !important;
}}

/* ── Divider ─────────────────────────────────────────────── */
hr {{
    border-color: {v['border']} !important;
    margin: 0.75rem 0;
}}

/* ── Scrollbar ───────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {v['bg_app']}; }}
::-webkit-scrollbar-thumb {{
    background: {v['border']};
    border-radius: 3px;
}}
::-webkit-scrollbar-thumb:hover {{ background: {v['accent']}88; }}

/* ── Responsive ──────────────────────────────────────────── */
@media screen and (max-width: 1200px) {{
    [data-testid="stMainBlockContainer"] {{ padding: 1.25rem 1.5rem 3rem; }}
}}
@media screen and (max-width: 900px) {{
    [data-testid="stMainBlockContainer"] {{ padding: 1rem 1rem 2.5rem; }}
}}
@media screen and (max-width: 640px) {{
    [data-testid="stMainBlockContainer"] {{ padding: 0.75rem 0.75rem 2rem; }}
    h1 {{ font-size: 1.5rem !important; }}
}}
</style>
"""
