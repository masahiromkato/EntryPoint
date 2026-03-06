import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import datetime

# =============================================================================
# モジュールインポート
# =============================================================================
from modules.config import set_global_css, PRESET_TICKERS, INTERVAL_OPTIONS, JPY_TICKERS
from modules.data import fetch_data, fetch_ticker_name
from modules.indicators import calc_indicators, gen_signals, PANDAS_TA_AVAILABLE
from modules.simulation import simulate
from modules.charts import build_chart, build_dev_chart

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
def currency(ticker: str) -> str:
    return "¥" if ticker in JPY_TICKERS else "$"

def fmt(val: float, ticker: str) -> str:
    s  = currency(ticker)
    av = abs(val)
    if av >= 1_000_000_000: return f"{s}{val/1_000_000_000:.2f}B"
    if av >= 1_000_000:     return f"{s}{val/1_000_000:.2f}M"
    if av >= 1_000:         return f"{s}{val/1_000:.1f}K"
    return f"{s}{val:,.2f}"

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

    # ═══ サイドバー ══════════════════════════════════
    with st.sidebar:
        st.markdown("## ⚙️ 設定パネル")
        st.divider()

        # ── ティッカー ──────────────────────────────
        st.markdown("### 📌 ティッカー")
        mode = st.radio("入力方法", ["プリセット","手動入力"],
                        horizontal=True, label_visibility="collapsed")
        if mode == "プリセット":
            label  = st.selectbox("銘柄", list(PRESET_TICKERS.keys()),
                                  label_visibility="collapsed")
            ticker = PRESET_TICKERS[label]
        else:
            ticker = st.text_input("ティッカー", value="VOO",
                                   placeholder="例: VOO / QQQ / 1321",
                                   label_visibility="collapsed").strip().upper()
            if ticker.isdigit():
                ticker += ".T"
                
        ticker_name = fetch_ticker_name(ticker)
        name_disp = f" {ticker_name}" if ticker_name else ""
        st.markdown(
            f'選択中 &nbsp;<span class="ticker-badge">{ticker}{name_disp}</span>',
            unsafe_allow_html=True, )
        st.divider()

        # ── 時間軸・期間 ────────────────────────────
        st.markdown("### 📅 時間軸・取得期間")
        iv_label = st.selectbox("足種", list(INTERVAL_OPTIONS.keys()), index=1,
                                label_visibility="collapsed")
        iv          = INTERVAL_OPTIONS[iv_label]
        interval_yf = iv["yf"]
        unit        = iv["unit"]

        ma_period   = st.number_input("MA（移動平均）期間", min_value=1, max_value=500, value=50, step=1)
        ma_label    = f"{ma_period}{iv['ma_suffix']}MA"
        
        today = datetime.date.today()
        default_start = today - datetime.timedelta(days=365*10)
        
        c_start, c_end = st.columns(2)
        with c_start:
            start_date = st.date_input("開始日", value=default_start, min_value=datetime.date(1970, 1, 1))
        with c_end:
            end_date = st.date_input("終了日", value=today, min_value=datetime.date(1970, 1, 1))

        if start_date and end_date:
            analysis_years = (end_date - start_date).days / 365.25
            st.caption(f"分析期間: {analysis_years:.1f} 年")
        else:
            analysis_years = 0
            
        st.divider()

        # ── シグナル条件（個別トグル付き）──────────
        st.markdown("### 🎯 シグナル条件")
        cond_raw  = st.radio("条件の組み合わせ",
                             ["OR（いずれか一つ）","AND（すべて同時）"],
                             help="OR = 感度高。AND = 確度高。")
        cond_mode = "OR" if "OR" in cond_raw else "AND"

        # 騰落率（最上位）
        st.markdown("---")
        col_toggleA, col_titleA = st.columns([1, 5])
        use_chg = col_toggleA.checkbox("", value=True, key="use_chg")
        col_titleA.markdown("**騰落率（前足比）**")
        chg_thr = st.slider(f"騰落率 閾値 (%)", -20.0, -1.0, -5.0, 0.1,
                            disabled=not use_chg,
                            help=f"前{unit}終値比で何%下落したらシグナルとするか",
                            key="chg_thr")

        # RSI（2番目）
        st.markdown("---")
        col_toggleC, col_titleC = st.columns([1, 5])
        use_rsi = col_toggleC.checkbox("", value=False, key="use_rsi")
        col_titleC.markdown("**RSI(14)**")
        rsi_thr = st.slider("RSI(14) 閾値", 15.0, 85.0, 35.0, 0.1,
                            disabled=not use_rsi,
                            help="RSI がこの値以下でシグナル点灯",
                            key="rsi_thr")

        # MA乖離率（3番目）
        st.markdown("---")
        col_toggleB, col_titleB = st.columns([1, 5])
        use_ma = col_toggleB.checkbox("", value=False, key="use_ma")
        col_titleB.markdown(f"**{ma_label}乖離率**")
        dev_thr = st.slider(f"{ma_label} 乖離率 閾値 (%)", -30.0, -1.0, -10.0, 0.1,
                            disabled=not use_ma,
                            help=f"終値が{ma_label}を何%下回ったらシグナルとするか",
                            key="dev_thr")
        st.divider()

        # ── シミュレーション ─────────────────────────
        sym = "¥" if ticker in JPY_TICKERS else "$"
        st.markdown("### 💰 積立シミュレーション")
        periodic_invest = st.number_input(
            f"毎{unit}の積立額 ({sym})", 100, 10_000_000, 10_000, 1_000,
            help="DCA・シグナル戦略の毎周期の積立額")
        signal_bonus = st.number_input(
            f"シグナル時の追加投資額 ({sym})", 0, 50_000_000, 50_000, 5_000,
            help=f"シグナル点灯した{unit}のみ追加で投資する額")
        st.divider()

        # ── チャート高さ比率 ─────────────────────────
        st.markdown("### 📐 チャート高さ比率")
        h_price = st.slider("株価チャート",  10, 80, 65, 5,
                            help="上段（株価）の高さ比率")
        h_rsi   = st.slider("RSIチャート",   5,  40, 20, 5,
                            help="中段（RSI）の高さ比率")
        h_port  = st.slider("資産推移",      5,  50, 15, 5,
                            help="下段（ポートフォリオ）の高さ比率")
        total_h = h_price + h_rsi + h_port
        row_heights = [h_price/total_h, h_rsi/total_h, h_port/total_h]

        st.divider()
        st.caption(f"RSI計算: {'pandas_ta' if PANDAS_TA_AVAILABLE else '手掌握実装（フォールバック）'}")
        st.caption("データ: Yahoo Finance（最大24時間キャッシュ）")

    # ═══ データ取得・計算 ═════════════════════════
    with st.spinner(f"📡  {ticker} の{iv_label}データを取得中…"):
        # MA計算用に過去データ（バッファ）を追加取得
        buffer_days = ma_period * 31 if interval_yf == "1mo" else (ma_period * 7 + 30 if interval_yf == "1wk" else ma_period * 1.5 + 30)
        fetch_start = start_date - datetime.timedelta(days=int(buffer_days))
        df = fetch_data(ticker, start_date=fetch_start, end_date=end_date, interval=interval_yf)

    if df.empty:
        st.error(
            f"❌  **{ticker}** のデータを取得できませんでした。\n\n"
            "**考えられる原因：**\n"
            "- ティッカーシンボルが間違っている\n"
            "- 指定の期間・足種にデータが存在しない（日足の30年分など）\n"
            "- Yahoo Finance の一時的な障害\n\n"
            "ティッカーや足種・取得年数を変更してお試しください。", icon="🚫")
        st.stop()

    df = calc_indicators(df, ma_period=ma_period)
    df = gen_signals(
        df,
        float(dev_thr), use_ma,
        float(rsi_thr), use_rsi,
        float(chg_thr), use_chg,
        cond_mode,
    )
    df = simulate(df, float(periodic_invest), float(signal_bonus))

    actual_start = df.index.min().date()

    # 取得したデータからユーザー指定の表示期間のみを抽出
    mask = (df.index.date >= start_date) & (df.index.date <= end_date)
    df = df.loc[mask]

    if df.empty:
        st.warning("指定された期間内に取引データがありませんでした。開始日を調整するか他の銘柄をお試しください。", icon="⚠️")
        st.stop()

    latest     = df["Close"].dropna().iloc[-1]
    ma_last    = df["MA_VAL"].dropna().iloc[-1]     if df["MA_VAL"].notna().any()     else None
    dev_last   = df["DEV"].dropna().iloc[-1]        if df["DEV"].notna().any()        else None
    rsi_last   = df["RSI"].dropna().iloc[-1]        if df["RSI"].notna().any()        else None
    chg_last   = df["PRICE_CHG"].dropna().iloc[-1]  if df["PRICE_CHG"].notna().any()  else None
    sig_count  = int(df["Signal"].sum())
    is_signal  = bool(df["Signal"].iloc[-1])        if df["Signal"].notna().any()     else False
    csym       = currency(ticker)

    # ═══ メトリクス ═══════════════════════════════
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    with c1: st.metric("現在値", f"{csym}{latest:,.2f}")
    with c2: st.metric(ma_label, f"{csym}{ma_last:,.2f}" if ma_last else "計算中…")
    with c3:
        if chg_last is not None:
            st.metric(f"前{unit}比騰落率", f"{chg_last:+.2f}%",
                      delta=f"閾値:{chg_thr}%", delta_color="off")
        else: st.metric(f"前{unit}比騰落率", "計算中…")
    with c4:
        if rsi_last is not None:
            st.metric("RSI(14)", f"{rsi_last:.1f}", delta=f"閾値:{rsi_thr}", delta_color="off")
        else: st.metric("RSI(14)", "計算中…")
    with c5:
        if dev_last is not None:
            st.metric(f"{ma_label}乖離率", f"{dev_last:+.1f}%",
                      delta=f"閾値:{dev_thr}%", delta_color="off")
        else: st.metric(f"{ma_label}乖離率", "計算中…")
    with c6: st.metric("累計シグナル数", f"{sig_count} 回")

    # シグナルランプ
    lamp = ('<span class="lamp lamp-on"><span class="dot dot-on"></span>🔴 現在シグナル点灯中！</span>'
            if is_signal else
            '<span class="lamp lamp-off"><span class="dot dot-off"></span>⚪️ 現在シグナルなし</span>')
    st.markdown(lamp, unsafe_allow_html=True)

    # 有効条件表示
    active_conds = []
    if use_chg: active_conds.append(f"騰落率 ≤ {chg_thr}%")
    if use_ma:  active_conds.append(f"{ma_label}乖離率 ≤ {dev_thr}%")
    if use_rsi: active_conds.append(f"RSI(14) ≤ {rsi_thr}")
    if active_conds:
        st.caption(f"有効な判定条件 [{cond_mode}]: " + "  /  ".join(active_conds))
    else:
        st.warning("⚠️ 判定条件が1つも有効になっていません。チェックボックスをONにしてください。", icon="⚠️")

    st.divider()

    # ═══ メインチャート ════════════════════════════
    if (actual_start - start_date).days > 60:
        st.info(f"💡 **{ticker}** の価格データは **{actual_start.strftime('%Y年%m月%d日')}** 以降しか存在しない（設定された開始日よりも後に上場・設定された）ため、取得可能な最長期間からの表示となっています。", icon="ℹ️")

    # 連動ズームのための3段統合チャート
    fig = build_chart(
        df, ticker, ticker_name, iv_label, ma_label,
        float(dev_thr), float(rsi_thr),
        row_heights, cond_mode
    )
    st.plotly_chart(fig, use_container_width=True)

    # ═══ MA乖離率（折りたたみ）═════════════════════
    with st.expander(f"📊  {ma_label}乖離率チャートを開く", expanded=False):
        st.plotly_chart(build_dev_chart(df, float(dev_thr), ma_label), use_container_width=True)

    # ═══ シミュレーション結果サマリー ══════════════
    st.markdown("### 📋 積立シミュレーション 結果サマリー")
    pv = df.dropna(subset=["DCA_Val","Sig_Val"])

    if not pv.empty:
        last = pv.iloc[-1]
        dv,di = float(last["DCA_Val"]), float(last["DCA_Inv"])
        sv,si = float(last["Sig_Val"]), float(last["Sig_Inv"])
        dr,sr = float(last["DCA_ROI"]), float(last["Sig_ROI"])

        # CAGR / MDD 計算
        t_years = (pv.index[-1] - pv.index[0]).days / 365.25 if len(pv) > 1 else 1
        d_cagr = ((dv / di) ** (1 / max(t_years, 0.01)) - 1) * 100 if di > 0 else 0
        s_cagr = ((sv / si) ** (1 / max(t_years, 0.01)) - 1) * 100 if si > 0 else 0
        d_mdd  = (pv["DCA_Val"] / pv["DCA_Val"].cummax() - 1).min() * 100
        s_mdd  = (pv["Sig_Val"] / pv["Sig_Val"].cummax() - 1).min() * 100

        cl,cr = st.columns(2)
        with cl:
            st.markdown("#### 💙 DCA（定額積立）")
            a,b = st.columns(2)
            a.metric("最終資産額",   fmt(dv,ticker))
            b.metric("投資元本合計", fmt(di,ticker))
            c_,d = st.columns(2)
            c_.metric("含み益", fmt(dv-di,ticker))
            d.metric("ROI",    f"{dr:+.1f}%")
            e,f = st.columns(2)
            e.metric("年間平均利回り (CAGR)", f"{d_cagr:+.1f}%")
            f.metric("最大ドローダウン (MDD)", f"{d_mdd:+.1f}%")
            
        with cr:
            st.markdown("#### 💜 シグナル戦略（定額 ＋ シグナル追加）")
            g,h_ = st.columns(2)
            g.metric("最終資産額",   fmt(sv,ticker))
            h_.metric("投資元本合計", fmt(si,ticker))
            i,j = st.columns(2)
            i.metric("含み益", fmt(sv-si,ticker))
            j.metric("ROI",    f"{sr:+.1f}%")
            k,l = st.columns(2)
            k.metric("年間平均利回り (CAGR)", f"{s_cagr:+.1f}%")
            l.metric("最大ドローダウン (MDD)", f"{s_mdd:+.1f}%")

        st.markdown("#### ⚖️ 戦略比較")
        x1,x2,x3 = st.columns(3)
        x1.metric("ROI差（シグナル − DCA）", f"{sr-dr:+.1f} pt",
                  help="シグナル戦略の ROI が DCA より何ポイント上か")
        x2.metric("シグナル追加投資 累計", fmt(si-di,ticker),
                  help="シグナル点灯時の追加投資額の累計")
        x3.metric("追加分による利益差", fmt((sv-si)-(dv-di),ticker),
                  help="シグナル戦略の含み益 − DCA の含み益")
    else:
        st.info("シミュレーションデータが不足しています。取得期間を延ばしてください。")

    # ═══ シグナル発生履歴 ══════════════════════════
    with st.expander("📅  買いシグナル 発生日一覧", expanded=False):
        sig_rows = df[df["Signal"]==True][["Close","MA_VAL","DEV","RSI","PRICE_CHG"]].copy()
        if sig_rows.empty:
            st.info("現在の条件ではシグナルが発生していません。閾値を緩めるかトグルをONにしてください。")
        else:
            sig_rows.index.name = "日付"
            sig_rows = sig_rows.rename(columns={
                "Close":"終値", "MA_VAL":ma_label,
                "DEV":f"{ma_label}乖離率(%)", "RSI":"RSI(14)",
                "PRICE_CHG":f"前{unit}比騰落率(%)",
            })
            for c in sig_rows.columns:
                sig_rows[c] = sig_rows[c].round(2)
            sig_rows.sort_index(ascending=False, inplace=True)
            st.dataframe(sig_rows, use_container_width=True)
            st.caption(f"合計 {len(sig_rows)} 回のシグナル（条件: {cond_mode}）")

    st.divider()
    st.caption(
        "⚠️ 本アプリは教育・研究目的のみです。分析・シミュレーション結果は投資助言ではありません。"
        "投資判断は自己責任で行ってください。  |  データ提供: Yahoo Finance"
    )

if __name__ == "__main__":
    main()
