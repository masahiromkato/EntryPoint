import streamlit as st

# =============================================================================
# 定数
# =============================================================================
PRESET_TICKERS: dict[str, str] = {
    "S&P 500 ETF　　(VOO)":      "VOO",
    "NASDAQ-100 ETF　(QQQ)":     "QQQ",
    "小型株 ETF　　  (IWM)":       "IWM",
    "新興国 ETF　　  (VWO)":       "VWO",
    "インド株 ETF　  (INDA)":      "INDA",
    "日経225 ETF　　 (1321.T)":   "1321.T",
    "TOPIX ETF　　　 (1306.T)":   "1306.T",
}

INTERVAL_OPTIONS: dict[str, dict] = {
    "日足": {"yf":"1d",  "ma_suffix":"日",   "unit":"日"},
    "週足": {"yf":"1wk", "ma_suffix":"週",   "unit":"週"},
    "月足": {"yf":"1mo", "ma_suffix":"カ月", "unit":"月"},
}

# 元々JPY建てのティッカー（為替変換不要）
JPY_TICKERS: set[str] = {"1321.T","1306.T","1308.T","1320.T","2558.T","2559.T"}


def set_global_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, .stApp, .main .block-container {
    background-color: #0E1117 !important;
    color: #FFFFFF !important;
    font-family: 'Inter', sans-serif !important;
}
/* ── 余白の極限排除 ── */
.main .block-container {
    padding-top: 0rem !important;
    padding-bottom: 0rem !important;
    max-width: 100% !important;
    margin-top: -6rem !important;
}
header[data-testid="stHeader"] { background: transparent !important; height: 0 !important; }

/* ── サイドバー ── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div:first-child {
    background-color: #111827 !important;
    border-right: 1px solid rgba(255,255,255,0.07) !important;
    color: #FFFFFF !important;
}
section[data-testid="stSidebar"] * { color: #FFFFFF !important; }

/* ── Selectbox 白飛び根絶 ── */
div[data-baseweb="select"],
div[data-baseweb="select"] > div,
div[data-baseweb="select"] > div > div {
    background-color: #1E293B !important;
    border: 1.5px solid #3B82F6 !important;
    border-radius: 6px !important;
}
div[data-baseweb="select"] *:not(svg):not(path) {
    color: #FFFFFF !important;
    background-color: transparent !important;
}
div[data-baseweb="popover"],
div[data-baseweb="popover"] *:not(svg):not(path),
ul[data-baseweb="menu"] *:not(svg):not(path),
li[data-baseweb="menu-item"],
li[data-baseweb="menu-item"] *:not(svg):not(path) {
    background-color: #1E293B !important;
    color: #F8FAFC !important;
}
li[data-baseweb="menu-item"]:hover,
li[data-baseweb="menu-item"]:hover *:not(svg):not(path),
li[data-baseweb="menu-item"][aria-selected="true"],
li[data-baseweb="menu-item"][aria-selected="true"] *:not(svg):not(path) {
    background-color: #3B82F6 !important;
    color: #FFFFFF !important;
}
div[data-baseweb="select"] svg { color: #94A3B8 !important; }

/* ── Text / Number / Date Input 白文字 ── */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stDateInput"] input {
    background-color: #1E293B !important;
    color: #FFFFFF !important;
    border: 1.5px solid #3B82F6 !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    caret-color: #FFFFFF !important;
}
div[data-testid="stTextInput"] input::placeholder,
div[data-testid="stNumberInput"] input::placeholder,
div[data-testid="stDateInput"] input::placeholder { color: #94A3B8 !important; }
div[data-testid="stNumberInput"] button { background:#1E3A5F !important; color:#E2E8F0 !important; }

/* ── サイドバーラベル ── */
section[data-testid="stSidebar"] label {
    font-size: 0.75rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}
div[data-testid="stCheckbox"] label { text-transform: none !important; letter-spacing: 0 !important; font-size: 0.85rem !important; }

/* ── メトリクスカード ── */
div[data-testid="metric-container"] {
    background-color: #1B2537 !important;
    border: 1px solid rgba(59,130,246,0.3) !important;
    border-radius: 10px !important;
    padding: 0.65rem 0.9rem !important;
}
div[data-testid="metric-container"] * { color: #FFFFFF !important; }
div[data-testid="stMetricValue"] > div { font-size:1.35rem !important; font-weight:800 !important; }
div[data-testid="stMetricDelta"] svg  { display: none !important; }
div[data-testid="stMetricDelta"] > div { font-size: 0.8rem !important; }

/* ── アプリヘッダー ── */
.app-header { padding: 0 !important; margin: 0 !important; margin-bottom: -1.5rem !important; margin-top: -4.5rem !important; }
.app-header h1 { margin:0 !important; font-size:1.4rem !important; font-weight:800 !important; color:#FFFFFF !important; line-height: 1 !important; }

/* ── Tooltip ── */
div[data-baseweb="tooltip"], div[data-baseweb="tooltip"] * {
    background-color: #111827 !important; color: #FFFFFF !important;
}

/* ── ティッカーバッジ ── */
.ticker-badge {
    display:inline-block;
    background:#00CED1; color:#050E1A !important;
    font-weight:800; font-size:0.82rem;
    padding:0.16rem 0.65rem; border-radius:999px; letter-spacing:0.04em;
}

/* ── シグナルランプ ── */
.lamp { display:inline-flex; align-items:center; gap:0.4rem; padding:0.24rem 0.8rem; border-radius:999px; font-size:0.78rem; font-weight:700; color: #FFFFFF !important; }
.lamp-on  { border:1.5px solid #4ADE80; background:rgba(74,222,128,0.1); }
.lamp-off { border:1.5px solid #475569; background:rgba(71,85,105,0.1);  }
.dot { width:7px; height:7px; border-radius:50%; display:inline-block; }
.dot-on  { background:#4ADE80; box-shadow:0 0 6px #4ADE80; }
.dot-off { background:#475569; }

/* ── ウィジェット余白圧縮 ── */
div[data-testid="stSlider"]       { margin-bottom: -1.2rem !important; }
div[data-testid="stCheckbox"]     { margin-bottom: -0.8rem !important; }
div[data-testid="stVerticalBlock"] > div { padding-bottom: 0 !important; padding-top: 0 !important; }
div[data-testid="stSelectbox"]    { margin-bottom: -0.5rem !important; }
div[data-testid="stDateInput"]    { margin-bottom: -0.5rem !important; }
div[data-testid="stNumberInput"]  { margin-bottom: -0.5rem !important; }

/* ── Plotly モードバー ── */
.js-plotly-plot .plotly .modebar { background-color: rgba(30,41,59,0.8) !important; border-radius: 6px !important; }
.js-plotly-plot .plotly .modebar-btn path,
.js-plotly-plot .plotly .modebar-btn svg { fill: #FFFFFF !important; color: #FFFFFF !important; }
.js-plotly-plot .plotly .modebar-btn:hover path { fill: #7DD3FC !important; }

/* ── その他 ── */
hr { border-color: rgba(59,130,246,0.08) !important; }
.stCaption, .stCaption *, small { color:#FFFFFF !important; }
h1,h2,h3,h4, p { color:#FFFFFF !important; }
summary, .streamlit-expanderHeader { background:#1B2537 !important; color:#FFFFFF !important; border-radius:8px !important; }

/* ── DataFrame ダークモード強制 ── */
div[data-testid="stDataFrame"] { background:#161B27 !important; border-radius:8px !important; overflow:hidden !important; }
div[data-testid="stDataFrame"] iframe { color-scheme: dark !important; background:#161B27 !important; }
/* Glide Data Grid inner elements */
div[data-testid="stDataFrame"] canvas { filter: none !important; }
div[data-testid="stDataFrame"] > div > div { background:#161B27 !important; }
/* Fallback: force all text children white */
div[data-testid="stDataFrame"] * { color:#E2E8F0 !important; }
</style>
    """, unsafe_allow_html=True)
