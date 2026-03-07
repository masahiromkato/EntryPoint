import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import datetime

# =============================================================================
# モジュールインポート
# =============================================================================
from modules.config import set_global_css, PRESET_TICKERS, INTERVAL_OPTIONS, JPY_TICKERS
from modules.data import fetch_data, fetch_ticker_name, fetch_fx_rate, apply_fx_conversion
from modules.indicators import calc_indicators, gen_signals, PANDAS_TA_AVAILABLE
from modules.simulation import simulate
from modules.charts import build_chart, build_dev_chart, build_rsi_detail_chart, build_chg_chart

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
# ユーティリティ
# =============================================================================
def currency_symbol(ticker: str, display_currency: str) -> str:
    # 指数（^GSPC等）の場合は記号なし
    if ticker.startswith("^"):
        return ""
    if ticker in JPY_TICKERS or display_currency == "JPY":
        return "¥"
    return "$"

def fmt(val: float, ticker: str, display_currency: str) -> str:
    s  = currency_symbol(ticker, display_currency)
    av = abs(val)
    if av >= 1_000_000_000: return f"{s}{val/1_000_000_000:.2f}B"
    if av >= 1_000_000:     return f"{s}{val/1_000:.1f}K" if ticker.startswith("^") else f"{s}{val/1_000_000:.2f}M"
    if av >= 1_000:         return f"{s}{val:,.0f}" if ticker.startswith("^") else f"{s}{val/1_000:.1f}K"
    return f"{s}{val:,.2f}" if ticker.startswith("^") else f"{s}{val:,.2f}"

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

    # ═══ サイドバー ══════════════════════════════════════════
    with st.sidebar:
        # ── ティッカー ────────────────────────────────────────
        st.markdown("### 📌 ティッカー")
        mode = st.radio("入力方法", ["プリセット", "手動入力"],
                        horizontal=True, label_visibility="collapsed")
        if mode == "プリセット":
            label  = st.selectbox("銘柄", list(PRESET_TICKERS.keys()),
                                   label_visibility="collapsed")
            ticker = PRESET_TICKERS[label]
        else:
            raw_ticker = st.text_input("ティッカー", value="",
                                       placeholder="例: VOO / QQQ / 1321",
                                       label_visibility="collapsed").strip().upper()
            ticker = raw_ticker + ".T" if raw_ticker.isdigit() else raw_ticker

        ticker_name = fetch_ticker_name(ticker)
        name_disp   = f" {ticker_name}" if ticker_name else ""
        st.markdown(
            f'選択中 &nbsp;<span class="ticker-badge">{ticker}{name_disp}</span>',
            unsafe_allow_html=True,
        )
        st.divider()
        st.markdown("### 📅 時間軸・取得期間")
        iv_label    = st.selectbox("足種", list(INTERVAL_OPTIONS.keys()), index=1,
                                   label_visibility="collapsed")
        iv          = INTERVAL_OPTIONS[iv_label]
        interval_yf = iv["yf"]
        unit        = iv["unit"]

        ma_period = st.number_input("MA（移動平均）期間", min_value=1, max_value=500, value=50, step=1)
        ma_label  = f"{ma_period}{iv['ma_suffix']}MA"

        # ── 📅 期間指定（西暦・日付連動） ──────────────────────

        today         = datetime.date.today()
        default_start = today - datetime.timedelta(days=365 * 10)

        # session_state 初期化
        if "start_date" not in st.session_state: st.session_state["start_date"] = default_start
        if "end_date"   not in st.session_state: st.session_state["end_date"]   = today
        if "start_year" not in st.session_state: st.session_state["start_year"] = default_start.year
        if "end_year"   not in st.session_state: st.session_state["end_year"]   = today.year

        # コールバック: 年入力 -> 日付反映
        def _sync_yr_to_dt():
            st.session_state["start_date"] = datetime.date(st.session_state["start_year"], 1, 1)
            st.session_state["end_date"]   = datetime.date(st.session_state["end_year"], 12, 31)

        # コールバック: 日付変更 -> 年反映
        def _sync_dt_to_yr():
            st.session_state["start_year"] = st.session_state["start_date"].year
            st.session_state["end_year"]   = st.session_state["end_date"].year

        # 1. 西暦入力 (横並び)
        cy_start, cy_end = st.columns(2)
        with cy_start:
            st.number_input("開始年", 1970, today.year, key="start_year", on_change=_sync_yr_to_dt)
        with cy_end:
            st.number_input("終了年", 1970, today.year, key="end_year", on_change=_sync_yr_to_dt)

        # 2. 日付入力 (横並び)
        c_start, c_end = st.columns(2)
        with c_start:
            start_date = st.date_input("開始日", key="start_date", on_change=_sync_dt_to_yr,
                                        min_value=datetime.date(1970, 1, 1))
        with c_end:
            end_date = st.date_input("終了日", key="end_date", on_change=_sync_dt_to_yr,
                                      min_value=datetime.date(1970, 1, 1))

        if start_date and end_date:
            analysis_years = (end_date - start_date).days / 365.25
            st.caption(f"分析期間: {analysis_years:.1f} 年")
        else:
            analysis_years = 0

        # 🎯 シグナル条件 (セパレーターで視認性を確保)
        st.divider()
        st.markdown("### 🎯 シグナル条件")

        # ── session_state 初期化（初回のみ）─────────────────
        for _k, _v in [("chg_thr_val", -5.0), ("rsi_thr_val", 35.0), ("dev_thr_val", -10.0)]:
            if _k not in st.session_state:
                st.session_state[_k] = _v

        # callback: number_input -> slider (force_neg auto-flips positive to negative)
        def _sync_from_num(val_key: str, num_key: str, sld_key: str, force_neg: bool = False):
            v = float(st.session_state[num_key])
            if force_neg and v > 0:
                v = -v
            st.session_state[val_key] = round(v, 2)
            st.session_state[num_key] = round(v, 2) # 反映
            st.session_state[sld_key] = round(v, 2)

        # callback: slider -> number_input
        def _sync_from_sld(val_key: str, num_key: str, sld_key: str, force_neg: bool = False):
            v = float(st.session_state[sld_key])
            st.session_state[val_key] = round(v, 2)
            st.session_state[num_key] = round(v, 2)
            st.session_state[sld_key] = round(v, 2) # 反映

        # CHG (price change vs prev bar)
        _ca, _cb = st.columns([1, 9])
        use_chg = _ca.checkbox("", value=True, key="use_chg")
        _cb.markdown(
            "<p style='margin:0;padding-top:5px;font-size:0.82rem;font-weight:700'>"
            "\u9a30\u843d\u7387 \u95be\u5024 (%)</p>",
            unsafe_allow_html=True,
        )
        st.number_input(
            "chg_num", min_value=0.01, max_value=20.0, step=0.01, format="%.2f",
            disabled=not use_chg, key="chg_thr_num",
            value=abs(st.session_state["chg_thr_val"]),
            on_change=_sync_from_num,
            kwargs=dict(val_key="chg_thr_val", num_key="chg_thr_num",
                        sld_key="chg_thr_sld", force_neg=True),
            label_visibility="collapsed",
        )
        st.slider(
            "chg_sld", -20.0, -0.01, st.session_state["chg_thr_val"], 0.01,
            disabled=not use_chg, key="chg_thr_sld",
            on_change=_sync_from_sld,
            kwargs=dict(val_key="chg_thr_val", num_key="chg_thr_num", sld_key="chg_thr_sld"),
            label_visibility="collapsed",
        )
        chg_thr = float(st.session_state["chg_thr_val"])

        # RSI
        _ra, _rb = st.columns([1, 9])
        use_rsi = _ra.checkbox("", value=False, key="use_rsi")
        _rb.markdown(
            "<p style='margin:0;padding-top:5px;font-size:0.82rem;font-weight:700'>"
            "RSI(14) \u95be\u5024</p>",
            unsafe_allow_html=True,
        )
        st.number_input(
            "rsi_num", min_value=15.0, max_value=85.0, step=0.01, format="%.2f",
            disabled=not use_rsi, key="rsi_thr_num",
            value=st.session_state["rsi_thr_val"],
            on_change=_sync_from_num,
            kwargs=dict(val_key="rsi_thr_val", num_key="rsi_thr_num",
                        sld_key="rsi_thr_sld", force_neg=False),
            label_visibility="collapsed",
        )
        st.slider(
            "rsi_sld", 15.0, 85.0, st.session_state["rsi_thr_val"], 0.01,
            disabled=not use_rsi, key="rsi_thr_sld",
            on_change=_sync_from_sld,
            kwargs=dict(val_key="rsi_thr_val", num_key="rsi_thr_num", sld_key="rsi_thr_sld"),
            label_visibility="collapsed",
        )
        rsi_thr = float(st.session_state["rsi_thr_val"])

        # MA deviation
        _da, _db = st.columns([1, 9])
        use_ma = _da.checkbox("", value=False, key="use_ma")
        _db.markdown(
            f"<p style='margin:0;padding-top:5px;font-size:0.82rem;font-weight:700'>"
            f"{ma_label}\u4e56\u96e2\u7387 \u95be\u5024 (%)</p>",
            unsafe_allow_html=True,
        )
        st.number_input(
            "dev_num", min_value=0.01, max_value=30.0, step=0.01, format="%.2f",
            disabled=not use_ma, key="dev_thr_num",
            value=abs(st.session_state["dev_thr_val"]),
            on_change=_sync_from_num,
            kwargs=dict(val_key="dev_thr_val", num_key="dev_thr_num",
                        sld_key="dev_thr_sld", force_neg=True),
            label_visibility="collapsed",
        )
        st.slider(
            "dev_sld", -30.0, -0.01, st.session_state["dev_thr_val"], 0.01,
            disabled=not use_ma, key="dev_thr_sld",
            on_change=_sync_from_sld,
            kwargs=dict(val_key="dev_thr_val", num_key="dev_thr_num", sld_key="dev_thr_sld"),
            label_visibility="collapsed",
        )
        dev_thr = float(st.session_state["dev_thr_val"])

        # 🧩 条件の組み合わせ（シグナル条件内に統合 ── 余分なラベル・余白を排除）
        cond_raw  = st.radio("条件の組み合わせ",
                             ["OR（いずれか一つ）", "AND（すべて同時）"],
                             index=0 if st.session_state.get("cond_mode_val", "OR") == "OR" else 1,
                             help="OR = 感度高。AND = 確度高。",
                             label_visibility="collapsed")
        cond_mode = "OR" if "OR" in cond_raw else "AND"
        st.session_state["cond_mode_val"] = cond_mode

        # ── 💱 表示設定 ───────────────────────────
        st.divider()
        st.markdown("### 💱 表示設定")
        is_native_jpy   = ticker in JPY_TICKERS
        display_currency = st.radio(
            "表示通貨",
            ["USD", "JPY"],
            horizontal=True,
            disabled=is_native_jpy,
            help="JPY選択時：USD建て銘柄を当日のドル円レートで円換算します。日本株ETFは常にJPY表示です。",
            label_visibility="collapsed",
        )
        if is_native_jpy:
            display_currency = "JPY"
        show_annual_grid = st.checkbox("年次グリッドを表示", value=True)

        # ── 💰 積立シミュレーション ──────────────────────────────
        st.divider()
        sym = "¥" if display_currency == "JPY" or is_native_jpy else "$"
        st.markdown("### 💰 積立シミュレーション")
        periodic_invest = st.number_input(
            f"毎{unit}の積立額 ({sym})", 100, 10_000_000, 10_000, 1_000,
            help="DCA・シグナル戦略の毎周期の積立額")
        signal_bonus = st.number_input(
            f"シグナル時の追加投資額 ({sym})", 0, 50_000_000, 50_000, 5_000,
            help=f"シグナル点灯した{unit}のみ追加で投資する額")

        # ── 📐 チャート高さ比率 ──────────────────────────────────
        st.divider()
        st.markdown("### 📐 チャート高さ比率")
        h_price = st.slider("株価チャート", 10, 80, 65, 5, help="上段（株価）の高さ比率")
        h_rsi   = st.slider("RSIチャート",  5,  40, 20, 5, help="中段（RSI）の高さ比率")
        h_port  = st.slider("資産推移",     5,  50, 15, 5, help="下段（ポートフォリオ）の高さ比率")
        total_h     = h_price + h_rsi + h_port
        row_heights = [h_price/total_h, h_rsi/total_h, h_port/total_h]

        st.divider()
        st.caption(f"RSI計算: {'pandas_ta' if PANDAS_TA_AVAILABLE else '手動実装（フォールバック）'}")
        st.caption("データ: Yahoo Finance（最大24時間キャッシュ）")

    # ═══ データ取得 ════════════════════════════════════════════
    buffer_days = (
        ma_period * 31 if interval_yf == "1mo"
        else ma_period * 7 + 30 if interval_yf == "1wk"
        else int(ma_period * 1.5 + 30)
    )
    fetch_start = start_date - datetime.timedelta(days=buffer_days)

    with st.spinner(f"📡  {ticker} の{iv_label}データを取得中…"):
        df = fetch_data(ticker, start_date=fetch_start, end_date=end_date, interval=interval_yf)

    if df.empty:
        st.error(
            f"❌  **{ticker}** のデータを取得できませんでした。\n\n"
            "**考えられる原因：**\n"
            "- ティッカーシンボルが間違っている\n"
            "- 指定の期間・足種にデータが存在しない\n"
            "- Yahoo Finance の一時的な障害\n\n"
            "ティッカーや足種・取得年数を変更してお試しください。", icon="🚫")
        st.stop()

    # ── 為替変換（USD→JPY, 日本株ETFは対象外）───────────────
    if display_currency == "JPY" and not is_native_jpy:
        with st.spinner("💱 為替レート (USDJPY) を取得して円換算中…"):
            fx_series = fetch_fx_rate(start_date=fetch_start, end_date=end_date, interval=interval_yf)
        if not fx_series.empty:
            df = apply_fx_conversion(df, fx_series)
        else:
            st.warning("⚠️ 為替データ (JPY=X) を取得できなかったため、USD建てのまま表示します。", icon="⚠️")

    # ── 指標・シグナル・シミュレーション ─────────────────────
    df = calc_indicators(df, ma_period=ma_period)
    df = gen_signals(
        df,
        float(dev_thr), use_ma,
        float(rsi_thr), use_rsi,
        float(chg_thr), use_chg,
        cond_mode,
    )
    df = simulate(df, float(periodic_invest), float(signal_bonus))

    # 実際のデータ開始日を取得（ユーザーへのフィードバック用）
    actual_start = df.index.min().date()

    # 表示期間でフィルタリング
    mask = (df.index.date >= start_date) & (df.index.date <= end_date)
    df   = df.loc[mask]

    if df.empty:
        st.warning("指定された期間内に取引データがありませんでした。開始日を調整するか他の銘柄をお試しください。", icon="⚠️")
        st.stop()

    # ── メトリクス計算 ────────────────────────────────────────
    latest    = df["Close"].dropna().iloc[-1]
    ma_last   = df["MA_VAL"].dropna().iloc[-1]    if df["MA_VAL"].notna().any()    else None
    dev_last  = df["DEV"].dropna().iloc[-1]       if df["DEV"].notna().any()       else None
    rsi_last  = df["RSI"].dropna().iloc[-1]       if df["RSI"].notna().any()       else None
    chg_last  = df["PRICE_CHG"].dropna().iloc[-1] if df["PRICE_CHG"].notna().any() else None
    sig_count = int(df["Signal"].sum())
    is_signal = bool(df["Signal"].iloc[-1]) if df["Signal"].notna().any() else False
    csym      = currency_symbol(ticker, display_currency)

    # ═══ メトリクス行 ═════════════════════════════════════════
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: st.metric("現在値", f"{csym}{latest:,.2f}")
    with c2: st.metric(ma_label, f"{csym}{ma_last:,.2f}" if ma_last else "計算中…")
    with c3:
        if chg_last is not None:
            st.metric(f"前{unit}比騰落率", f"{chg_last:+.2f}%",
                      delta=f"閾値:{chg_thr}%", delta_color="off")
        else:
            st.metric(f"前{unit}比騰落率", "計算中…")
    with c4:
        if rsi_last is not None:
            st.metric("RSI(14)", f"{rsi_last:.1f}", delta=f"閾値:{rsi_thr}", delta_color="off")
        else:
            st.metric("RSI(14)", "計算中…")
    with c5:
        if dev_last is not None:
            st.metric(f"{ma_label}乖離率", f"{dev_last:+.1f}%",
                      delta=f"閾値:{dev_thr}%", delta_color="off")
        else:
            st.metric(f"{ma_label}乖離率", "計算中…")
    with c6:
        st.metric("累計シグナル数", f"{sig_count} 回")

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
    # データの実態開始日とユーザー指定の開始日が大きく乖離している場合に注意表示
    if (actual_start - start_date).days > 60:
        st.info(
            f"💡 **{ticker}** の価格データは **{actual_start.strftime('%Y年%m月%d日')}** 以降しか存在しない"
            "（設定された開始日よりも後に上場・設定された）ため、取得可能な最長期間からの表示となっています。",
            icon="ℹ️"
        )

    fig = build_chart(
        df, ticker, ticker_name, iv_label, ma_label,
        float(dev_thr), float(rsi_thr),
        row_heights, cond_mode, show_annual_grid,
    )
    st.plotly_chart(fig, use_container_width=True)

    # 1. 買いシグナル発生日一覧
    with st.expander("📅  買いシグナル 発生日一覧", expanded=False):
        sig_rows = df[df["Signal"] == True][["Close", "MA_VAL", "PRICE_CHG", "RSI", "DEV"]].copy()
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
                    border-collapse:collapse; width:100%; font-size:0.82rem;
                }
                div[data-testid="stTable"] th {
                    background:#0F172A !important; color:#94A3B8 !important;
                    padding:6px 10px; border-bottom:1px solid #334155 !important;
                }
                div[data-testid="stTable"] td {
                    padding:5px 10px; border-bottom:1px solid #1E293B !important;
                    color:#E2E8F0 !important; background:#1E1E2E !important;
                }
                div[data-testid="stTable"] tr:hover td {
                    background:#1E3A5F !important;
                }
                </style>
            """, unsafe_allow_html=True)
            st.table(sig_rows)

    # 2. 騰落率詳細チャート
    with st.expander(f"📊  前{unit}比 騰落率チャートを開く", expanded=False):
        st.plotly_chart(build_chg_chart(df, float(chg_thr), unit), use_container_width=True)

    # 3. RSI詳細チャート
    with st.expander("📊  RSI(14) 詳細チャートを開く", expanded=False):
        st.plotly_chart(build_rsi_detail_chart(df, float(rsi_thr)), use_container_width=True)

    # 4. MA乖離率チャート
    with st.expander(f"📊  {ma_label}乖離率チャートを開く", expanded=False):
        st.plotly_chart(build_dev_chart(df, float(dev_thr), ma_label), use_container_width=True)

    # ═══ シミュレーション結果サマリー ═════════════════════════
    st.markdown("### 📋 積立シミュレーション 結果サマリー")
    pv = df.dropna(subset=["DCA_Val", "Sig_Val"])

    if not pv.empty:
        last = pv.iloc[-1]
        dv, di = float(last["DCA_Val"]), float(last["DCA_Inv"])
        sv, si = float(last["Sig_Val"]), float(last["Sig_Inv"])
        dr, sr = float(last["DCA_ROI"]), float(last["Sig_ROI"])

        t_years = (pv.index[-1] - pv.index[0]).days / 365.25 if len(pv) > 1 else 1
        d_cagr  = ((dv / di) ** (1 / max(t_years, 0.01)) - 1) * 100 if di > 0 else 0
        s_cagr  = ((sv / si) ** (1 / max(t_years, 0.01)) - 1) * 100 if si > 0 else 0
        d_mdd   = (pv["DCA_Val"] / pv["DCA_Val"].cummax() - 1).min() * 100
        s_mdd   = (pv["Sig_Val"] / pv["Sig_Val"].cummax() - 1).min() * 100

        cl, cr = st.columns(2)
        with cl:
            st.markdown("#### 💙 DCA（定額積立）")
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
            st.markdown("#### 💜 シグナル戦略（定額 ＋ シグナル追加）")
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
        x2.metric("シグナル追加投資 累計", fmt(si - di, ticker, display_currency),
                  help="シグナル点灯時の追加投資額の累計")
        x3.metric("追加分による利益差", fmt((sv - si) - (dv - di), ticker, display_currency),
                  help="シグナル戦略の含み益 − DCA の含み益")
    else:
        st.info("シミュレーションデータが不足しています。取得期間を延ばしてください。")

    st.divider()
    st.caption(
        "⚠️ 本アプリは教育・研究目的のみです。分析・シミュレーション結果は投資助言ではありません。"
        "投資判断は自己責任で行ってください。  |  データ提供: Yahoo Finance"
    )


if __name__ == "__main__":
    main()
