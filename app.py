import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import datetime

# =============================================================================
# モジュールインポート
# =============================================================================
from modules.config import config, set_global_css
from modules.data import fetch_ticker_name, DataFetchError
from modules.logic import run_analysis_pipeline
from modules.indicators import PANDAS_TA_AVAILABLE
from modules.charts import render_main_chart, build_dev_chart, build_rsi_detail_chart, build_chg_chart

# =============================================================================
# ページ設定 & CSS
# =============================================================================
st.set_page_config(
    page_title="Entry Points",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
set_global_css()

# =============================================================================
# ユーティリティ & コールバック
# =============================================================================
def reset_run():
    st.session_state["run_triggered"] = False

def sync_start_year():
    y = st.session_state["start_year"]
    # 開始年が変更された場合は、1月1日にリセット（以前の仕様）
    st.session_state["start_date"] = datetime.date(y, 1, 1)
    reset_run()

def sync_start_date():
    st.session_state["start_year"] = st.session_state["start_date"].year
    reset_run()

def sync_end_year():
    y = st.session_state["end_year"]
    today = datetime.date.today()
    if y == today.year:
        # 今年が選択された場合は今日の日付をセット
        st.session_state["end_date"] = today
    else:
        # 過去年が選択された場合は12月31日にセット
        st.session_state["end_date"] = datetime.date(y, 12, 31)
    reset_run()

def sync_end_date():
    st.session_state["end_year"] = st.session_state["end_date"].year
    reset_run()

def currency_symbol(ticker: str, display_currency: str) -> str:
    # 指数（^GSPC等）の場合は記号なし
    if ticker.startswith("^"):
        return ""
    if ticker in config.JPY_TICKERS or display_currency == "JPY":
        return "¥"
    return "$"

def fmt(val: float, ticker: str, display_currency: str) -> str:
    s  = currency_symbol(ticker, display_currency)
    av = abs(val)
    if av >= 1_000_000_000: return f"{s}{val/1_000_000_000:.2f}B"
    if av >= 1_000_000:     return f"{s}{val/1_000:.1f}K" if ticker.startswith("^") else f"{s}{val/1_000_000:.2f}M"
    if av >= 1_000:         return f"{s}{val:,.0f}" if ticker.startswith("^") else f"{s}{val/1_000:.1f}K"
    return f"{s}{val:,.2f}" if ticker.startswith("^") else f"{s}{val:,.2f}"

def render_custom_metric(label, value, delta=None, color_class="val-sky"):
    """
    Renders a custom HTML metric block that matches the design of st.metric
    but allows for precise color control.
    """
    delta_html = f'<div class="custom-metric-delta">{delta}</div>' if delta else ""
    st.markdown(f"""
        <div class="custom-metric-container">
            <div class="custom-metric-label">{label}</div>
            <div class="custom-metric-value {color_class}">{value}</div>
            {delta_html}
        </div>
    """, unsafe_allow_html=True)

# =============================================================================
# キャッシュ化されたパイプライン
# =============================================================================
@st.cache_data(ttl=86400, show_spinner=False)
def run_analysis_pipeline_v2(**kwargs):
    return run_analysis_pipeline(**kwargs)

@st.cache_data(ttl=86400 * 7, show_spinner=False)
def fetch_ticker_name_cached(ticker: str) -> str:
    return fetch_ticker_name(ticker)

# =============================================================================
# メインアプリ
# =============================================================================
def main():
    # ヘッダー
    st.markdown("""
    <div class="app-header">
        <h1>Historical Entry Points</h1>
    </div>
    """, unsafe_allow_html=True)

    # ═══ 状態の初期化 ══════════════════════════════════════════
    if "run_triggered" not in st.session_state:
        st.session_state["run_triggered"] = False

    # ═══ サイドバー ══════════════════════════════════════════
    with st.sidebar:
        # 📌 スティッキーヘッダー（実行ボタン + 銘柄選択）
        with st.container():
            if st.button("実行", type="primary", use_container_width=True):
                st.session_state["run_triggered"] = True
            
            # ── ティッカー ────────────────────────────────────────
            st.markdown("### 📌 ティッカー")
            mode = st.radio("入力方法", ["プリセット", "手動入力"],
                            horizontal=True, label_visibility="collapsed",
                            on_change=reset_run)
            if mode == "プリセット":
                label  = st.selectbox("銘柄", list(config.PRESET_TICKERS.keys()),
                                       label_visibility="collapsed",
                                       on_change=reset_run)
                ticker = config.PRESET_TICKERS[label]
            else:
                raw_ticker = st.text_input("ティッカー", value="",
                                           placeholder="例: VOO / QQQ / 1321",
                                           label_visibility="collapsed",
                                           on_change=reset_run).strip().upper()
                ticker = raw_ticker + ".T" if raw_ticker.isdigit() else raw_ticker

            ticker_name = fetch_ticker_name_cached(ticker)
            name_disp   = f" {ticker_name}" if ticker_name else ""
            st.markdown(
                f'選択中 &nbsp;<span class="ticker-badge">{name_disp.strip()}</span>',
                unsafe_allow_html=True,
            )
        
        st.divider()
        st.markdown("### 📅 時間軸・取得期間")
        st.write("")
        
        col_iv1, col_iv2 = st.columns(2, vertical_alignment="bottom")
        with col_iv1:
            iv_label = st.selectbox("足種", list(config.INTERVAL_OPTIONS.keys()), index=1, on_change=reset_run)
        with col_iv2:
            ma_period = st.number_input("MA期間", min_value=1, max_value=500, value=50, step=1, on_change=reset_run)
        
        iv          = config.INTERVAL_OPTIONS[iv_label]
        interval_yf = iv["yf"]
        unit        = iv["unit"]
        ma_label    = f"{ma_period}{iv['ma_suffix']}MA"

        # ── 📅 期間指定（西暦・日付連動） ──────────────────────
        today         = datetime.date.today()
        default_start = today - datetime.timedelta(days=365 * 10)

        if "start_date" not in st.session_state: st.session_state["start_date"] = default_start
        if "end_date"   not in st.session_state: st.session_state["end_date"]   = today
        if "start_year" not in st.session_state: st.session_state["start_year"] = default_start.year
        if "end_year"   not in st.session_state: st.session_state["end_year"]   = today.year

        # 1. 西暦入力 (横並び)
        st.markdown("<div style='margin-bottom:2px;'></div>", unsafe_allow_html=True)
        cy_start, cy_end = st.columns(2, vertical_alignment="bottom")
        with cy_start:
            st.number_input("開始年", 1970, today.year, key="start_year", on_change=sync_start_year)
        with cy_end:
            st.number_input("終了年", 1970, today.year, key="end_year", on_change=sync_end_year)

        # 2. 日付入力 (横並び)
        st.markdown("<div style='margin-bottom:2px;'></div>", unsafe_allow_html=True)
        c_start, c_end = st.columns(2, vertical_alignment="bottom")
        with c_start:
            start_date = st.date_input("開始日", key="start_date",
                                        min_value=datetime.date(1970, 1, 1),
                                        on_change=sync_start_date)
        with c_end:
            end_date = st.date_input("終了日", key="end_date",
                                      min_value=datetime.date(1970, 1, 1),
                                      on_change=sync_end_date)

        if start_date and end_date:
            analysis_years = (end_date - start_date).days / 365.25
            st.caption(f"分析期間: {analysis_years:.1f} 年")
        else:
            analysis_years = 0

        # 🎯 シグナル条件 (セパレーターで視認性を確保)
        st.divider()
        st.markdown("### 🎯 シグナル条件")
        st.markdown("<div style='margin-bottom:5px;'></div>", unsafe_allow_html=True)

        # ── session_state 初期化（シンプル化）─────────────────
        init_vals = {
            "chg_thr_num": 5.0,
            "rsi_thr_num": 35.0,
            "dev_thr_num": 10.0,
            "use_chg": True,
            "use_rsi": False,
            "use_ma": False
        }
        for _k, _v in init_vals.items():
            if _k not in st.session_state:
                st.session_state[_k] = _v

        # ── 3カラム構成の集約レイアウト ──────────────────────
        col_spec = [0.7, 2.0, 4.3]
        # 1. 騰落率
        _c1, _c2, _c3 = st.columns(col_spec, vertical_alignment="center")
        use_chg = _c1.checkbox("", key="use_chg", on_change=reset_run)
        _c2.markdown("<p style='margin:0;font-size:0.85rem;font-weight:700;'>騰落率</p>", unsafe_allow_html=True)
        chg_thr_num = _c3.number_input(
            "chg_num", min_value=0.01, max_value=20.0, step=1.0, format="%.2f",
            disabled=not use_chg, key="chg_thr_num",
            label_visibility="collapsed", on_change=reset_run
        )
        chg_thr = -chg_thr_num # 内部的に負の値へ

        # 2. RSI(14)
        _c1, _c2, _c3 = st.columns(col_spec, vertical_alignment="center")
        use_rsi = _c1.checkbox("", key="use_rsi", on_change=reset_run)
        _c2.markdown("<p style='margin:0;font-size:0.85rem;font-weight:700;'>RSI(14)</p>", unsafe_allow_html=True)
        rsi_thr = _c3.number_input(
            "rsi_num", min_value=15.0, max_value=85.0, step=1.0, format="%.2f",
            disabled=not use_rsi, key="rsi_thr_num",
            label_visibility="collapsed", on_change=reset_run
        )

        # 3. MA乖離
        _c1, _c2, _c3 = st.columns(col_spec, vertical_alignment="center")
        use_ma = _c1.checkbox("", key="use_ma", on_change=reset_run)
        _c2.markdown("<p style='margin:0;font-size:0.85rem;font-weight:700;'>MA乖離</p>", unsafe_allow_html=True)
        dev_thr_num = _c3.number_input(
            "dev_num", min_value=0.01, max_value=30.0, step=1.0, format="%.2f",
            disabled=not use_ma, key="dev_thr_num",
            label_visibility="collapsed", on_change=reset_run
        )
        dev_thr = -dev_thr_num # 内部的に負の値へ

        st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)
        cond_raw  = st.radio("条件の組み合わせ",
                             ["OR（いずれか一つ）", "AND（すべて同時）"],
                             index=0 if st.session_state.get("cond_mode_val", "OR") == "OR" else 1,
                             help="OR = 感度高。AND = 確度高。",
                             label_visibility="collapsed", on_change=reset_run)
        cond_mode = "OR" if "OR" in cond_raw else "AND"
        st.session_state["cond_mode_val"] = cond_mode

        # ── 💱 表示設定 ───────────────────────────
        st.divider()
        st.markdown("### 💱 表示設定")
        is_native_jpy   = ticker in config.JPY_TICKERS
        display_currency = st.radio(
            "表示通貨", ["USD", "JPY"],
            horizontal=True, disabled=is_native_jpy,
            help="JPY選択時：USD建て銘柄を当日のドル円レートで円換算します。",
            label_visibility="collapsed", on_change=reset_run
        )
        if is_native_jpy: display_currency = "JPY"
        show_annual_grid = st.checkbox("年次グリッドを表示", value=True, on_change=reset_run)

        # ── 💰 積立シミュレーション ──────────────────────────────
        st.divider()
        sym = "¥" if display_currency == "JPY" or is_native_jpy else "$"
        st.markdown("### 💰 積立シミュレーション")
        periodic_invest = st.number_input(
            f"毎{unit}の積立額 ({sym})", 100, 10_000_000, 10_000, 1_000, on_change=reset_run)
        signal_bonus = st.number_input(
            f"シグナル時の買付額 ({sym})", 0, 50_000_000, 50_000, 5_000, on_change=reset_run)

        # ── 📐 チャート高さ比率 ──────────────────────────────────
        st.divider()
        st.markdown("### 📐 チャート高さ比率")
        h_price = st.slider("株価チャート", 10, 80, 65, 5, on_change=reset_run)
        h_rsi   = st.slider("RSIチャート",  5,  40, 20, 5, on_change=reset_run)
        h_port  = st.slider("資産推移",     5,  50, 15, 5, on_change=reset_run)
        total_h     = h_price + h_rsi + h_port
        row_heights = [h_price/total_h, h_rsi/total_h, h_port/total_h]

        st.divider()
        st.caption(f"RSI計算: {'pandas_ta' if PANDAS_TA_AVAILABLE else '手動実装（フォールバック）'}")
        st.caption("データ: Yahoo Finance（最大24時間キャッシュ）")

    # ═══ メイン解析・表示の実行ガード ════════════════════════
    if not st.session_state["run_triggered"]:
        st.info("👈 設定を調整し、サイドバー上部の「実行」ボタンを押すと解析を開始します。", icon="ℹ️")
        st.stop()

    # ═══ 解析実行（pipeline 呼び出し） ════════════════════════
    try:
        stock_data, metrics = run_analysis_pipeline_v2(
            ticker=ticker,
            interval_yf=interval_yf,
            ma_period=ma_period,
            start_date=start_date,
            end_date=end_date,
            display_currency=display_currency,
            is_native_jpy=is_native_jpy,
            dev_thr=dev_thr, use_ma=use_ma,
            rsi_thr=rsi_thr, use_rsi=use_rsi,
            chg_thr=chg_thr, use_chg=use_chg,
            # (注意) app.py 内部では元の cond_mode 変数を使用
            cond_mode=cond_mode,
            periodic_invest=periodic_invest,
            signal_bonus=signal_bonus
        )
    except DataFetchError as e:
        st.error(f"❌  **データの取得に失敗しました**\n\n{str(e)}", icon="🚫")
        st.stop()

    # パイプライン結果の展開
    latest    = metrics.latest
    ma_last   = metrics.ma_last
    dev_last  = metrics.dev_last
    rsi_last  = metrics.rsi_last
    chg_last  = metrics.chg_last
    sig_count = metrics.sig_count
    is_signal = metrics.is_signal
    actual_start = metrics.actual_start
    csym      = currency_symbol(ticker, display_currency)

    # ═══ メトリクス行 ═════════════════════════════════════════
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    
    # 騰落率と乖離率のカラー判定 (Green if > 0, Red if < 0, Sky if 0)
    chg_color = "val-green" if (chg_last or 0) > 0 else "val-red" if (chg_last or 0) < 0 else "val-sky"
    dev_color = "val-green" if (dev_last or 0) > 0 else "val-red" if (dev_last or 0) < 0 else "val-sky"

    with c1: render_custom_metric("現在値", f"{csym}{latest:,.2f}")
    with c2: render_custom_metric(ma_label, f"{csym}{ma_last:,.2f}" if ma_last else "計算中…")
    with c3:
        if chg_last is not None:
            render_custom_metric(f"前{unit}比騰落率", f"{chg_last:+.2f}%", 
                                 delta=f"閾値:{chg_thr}%", color_class=chg_color)
        else:
            render_custom_metric(f"前{unit}比騰落率", "計算中…")
    with c4:
        if rsi_last is not None:
            render_custom_metric("RSI(14)", f"{rsi_last:.1f}", delta=f"閾値:{rsi_thr}")
        else:
            render_custom_metric("RSI(14)", "計算中…")
    with c5:
        if dev_last is not None:
            render_custom_metric(f"{ma_label}乖離率", f"{dev_last:+.1f}%", 
                                 delta=f"閾値:{dev_thr}%", color_class=dev_color)
        else:
            render_custom_metric(f"{ma_label}乖離率", "計算中…")
    with c6:
        render_custom_metric("累計シグナル数", f"{sig_count} 回", color_class="val-amber")

    # シグナルランプ
    lamp = ('<span class="lamp lamp-on"><span class="dot dot-on"></span>🔴 現在シグナル点灯中！</span>'
            if is_signal else
            '<span class="lamp lamp-off"><span class="dot dot-off"></span>⚪️ 現在シグナルなし</span>')
    st.markdown(lamp, unsafe_allow_html=True)

    # 有効条件キャプション
    active_conds = []
    if use_chg: active_conds.append(f"騰落率 ≤ {chg_thr}%")
    if use_ma:  active_conds.append(f"{ma_label}乖離率 ≤ {dev_thr}%")
    if use_rsi: active_conds.append(f"RSI(14) ≤ {rsi_thr}")
    if active_conds:
        cur_note = f" | 表示通貨: {display_currency}" if display_currency == "JPY" and not is_native_jpy else ""
        st.caption(f"有効な判定条件 [{cond_mode}]: " + "  /  ".join(active_conds) + cur_note)
    else:
        st.warning("⚠️ 判定条件が1つも有効になっていません。チェックボックスをONにしてください。", icon="⚠️")

    st.divider()

    # ═══ メインチャート ════════════════════════════════════════
    # 描画対象期間をここで厳密に切り出す（責務の移動）
    plot_data = stock_data.slice_range(start_date, end_date)

    # データの実態開始日とユーザー指定の開始日が大きく乖離している場合に注意表示
    if (actual_start - start_date).days > 60:
        st.info(
            f"💡 **{ticker}** の価格データは **{actual_start.strftime('%Y年%m月%d日')}** 以降しか存在しない"
            "（設定された開始日よりも後に上場・設定された）ため、取得可能な最長期間からの表示となっています。",
            icon="ℹ️"
        )

    fig = render_main_chart(
        plot_data, ticker_name, iv_label, ma_label,
        float(dev_thr), float(rsi_thr),
        row_heights, cond_mode, show_annual_grid,
    )
    st.plotly_chart(fig, use_container_width=True)

    # 1. 買いシグナル発生日一覧
    with st.expander("📅  買いシグナル 発生日一覧", expanded=False):
        sig_rows = stock_data.df[stock_data.signal == True][["Close", "MA_VAL", "PRICE_CHG", "RSI", "DEV"]].copy()
        if sig_rows.empty:
            st.info("現在の条件ではシグナルが発生していません。閾値を緩めるかトグルをONにしてください。")
        else:
            sig_rows.index.name = "日付"
            sig_rows.index = sig_rows.index.strftime('%Y-%m-%d') # 時刻を消す
            sig_rows = sig_rows.rename(columns={
                "Close":     "終値",
                "MA_VAL":    ma_label,
                "PRICE_CHG": f"前{unit}比騰落率(%)",
                "RSI":       "RSI(14)",
                "DEV":       f"{ma_label}乖離率(%)",
            })
            # Format numeric columns to 2 decimal places, keep index (date) as-is
            for c in sig_rows.columns:
                sig_rows[c] = sig_rows[c].apply(
                    lambda x: f"{x:.2f}" if isinstance(x, (int, float)) and x == x else x
                )
            sig_rows.sort_index(ascending=False, inplace=True)
            # カウントを表の上に白字で目立つ表示
            st.markdown(
                f"<span style='color:#FFFFFF;font-size:14px;font-weight:bold;'>"
                f"📌 合計 {len(sig_rows)} 回のシグナル（条件: {cond_mode}）</span>",
                unsafe_allow_html=True,
            )
            # st.table renders a static HTML table; CSS below styles it dark
            st.markdown("""
                <style>
                div[data-testid="stTable"] table {
                    background:#1E1E2E !important; color:#E2E8F0 !important;
                    border-collapse:collapse; 
                    width: auto !important;
                    margin-left: 0 !important;
                }
                div[data-testid="stTable"] th, div[data-testid="stTable"] td {
                    padding: 6px 12px !important; border-bottom:1px solid #334155 !important;
                    white-space: nowrap !important;
                    text-align: right !important;
                }
                div[data-testid="stTable"] td {
                    padding-right: 12px !important;
                }
                div[data-testid="stTable"] th {
                    background:#0F172A !important; color:#94A3B8 !important;
                    border-bottom:1px solid #475569 !important;
                }
                /* 日付列（1列目）の幅を最適化 */
                div[data-testid="stTable"] th:nth-child(1), 
                div[data-testid="stTable"] td:nth-child(1) {
                    min-width: 90px !important;
                    max-width: 100px !important;
                    text-align: left !important;
                    padding-left: 8px !important;
                }
                /* 4列目（騰落率）と 6列目（乖離率）の幅を 80px に制限 */
                div[data-testid="stTable"] th:nth-child(4), 
                div[data-testid="stTable"] td:nth-child(4),
                div[data-testid="stTable"] th:nth-child(6), 
                div[data-testid="stTable"] td:nth-child(6) {
                    min-width: 80px !important;
                    max-width: 90px !important;
                }
                div[data-testid="stTable"] tr:hover td {
                    background:#1E3A5F !important;
                }
                </style>
            """, unsafe_allow_html=True)
            st.table(sig_rows)

    # 2. 騰落率詳細チャート
    with st.expander(f"📊  前{unit}比 騰落率チャートを開く", expanded=False):
        st.plotly_chart(build_chg_chart(stock_data, float(chg_thr), unit), use_container_width=True)

    # 3. RSIチャート
    with st.expander("📊  RSI(14) チャートを開く", expanded=False):
        st.plotly_chart(build_rsi_detail_chart(stock_data, float(rsi_thr)), use_container_width=True)

    # 4. MA乖離率チャート
    with st.expander(f"📊  {ma_label}乖離率チャートを開く", expanded=False):
        st.plotly_chart(build_dev_chart(stock_data, float(dev_thr), ma_label), use_container_width=True)

    # ═══ シミュレーション結果サマリー ═════════════════════════
    st.markdown("### 📋 積立シミュレーション 結果サマリー")
    pv = stock_data.df.dropna(subset=["DCA_Val", "Sig_Val"])

    if not pv.empty:
        last = pv.iloc[-1]
        dv, di = float(last["DCA_Val"]), float(last["DCA_Inv"])
        sv, si = float(last["Sig_Val"]), float(last["Sig_Inv"])
        dr, sr = float(last["DCA_ROI"]), float(last["Sig_ROI"])

        t_years = (pv.index[-1] - pv.index[0]).days / 365.25 if len(pv) > 1 else 1
        d_cagr  = ((dv / di) ** (1 / max(t_years, 0.01)) - 1) * 100 if di > 0 else 0
        s_cagr  = ((sv / si) ** (1 / max(t_years, 0.01)) - 1) * 100 if si > 0 else 0
        d_mdd   = (stock_data.dca_val / stock_data.dca_val.cummax() - 1).min() * 100
        s_mdd   = (stock_data.sig_val / stock_data.sig_val.cummax() - 1).min() * 100

        cl, cr = st.columns(2)
        with cl:
            st.markdown("##### 💙 DCA (定額積立)")
            a, b = st.columns(2)
            a.metric("最終資産額",   fmt(dv, ticker, display_currency))
            b.metric("投資元本合計", fmt(di, ticker, display_currency))
            c_, d = st.columns(2)
            c_.metric("含み益", fmt(dv - di, ticker, display_currency))
            d.metric("ROI",    f"{dr:+.1f}%")
            e, f = st.columns(2)
            e.metric("年間平均利回り (CAGR)", f"{d_cagr:+.1f}%")
            f.metric("最大ドローダウン (MDD)", f"{d_mdd:+.1f}%")

        with cr:
            st.markdown("##### 💜 シグナル戦略")
            g, h_ = st.columns(2)
            g.metric("最終資産額",   fmt(sv, ticker, display_currency))
            h_.metric("投資元本合計", fmt(si, ticker, display_currency))
            i, j = st.columns(2)
            i.metric("含み益", fmt(sv - si, ticker, display_currency))
            j.metric("ROI",    f"{sr:+.1f}%")
            k, l = st.columns(2)
            k.metric("年間平均利回り (CAGR)", f"{s_cagr:+.1f}%")
            l.metric("最大ドローダウン (MDD)", f"{s_mdd:+.1f}%")

        st.markdown("#### ⚖️ 戦略比較")
        x1, x2, x3 = st.columns(3)
        x1.metric("ROI差（シグナル − DCA）", f"{sr - dr:+.1f} pt",
                  help="シグナル戦略の ROI が DCA より何ポイント上か")
        x2.metric("シグナル戦略 買付額", fmt(si - di, ticker, display_currency),
                  help="シグナル点灯時に投資した金額の累計")
        x3.metric("シグナル分による利益差", fmt((sv - si) - (dv - di), ticker, display_currency),
                  help="シグナル戦略の含み益 − DCA の含み益")
    else:
        st.info("シミュレーションデータが不足しています。取得期間を延ばしてください。")

    st.divider()
    st.caption(
        f"RSI計算: {'pandas_ta' if PANDAS_TA_AVAILABLE else '手動実装（フォールバック）'} | "
        "データ提供: Yahoo Finance"
    )


if __name__ == "__main__":
    main()
