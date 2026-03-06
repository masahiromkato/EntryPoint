import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

def build_chart(
    df: pd.DataFrame,
    ticker: str,
    ticker_name: str,
    iv_label: str,
    ma_label: str,
    dev_thr: float,
    rsi_thr: float,
    row_heights: list,
    cond_mode: str
) -> go.Figure:

    plot     = df.dropna(subset=["Close"])
    sig      = plot[plot["Signal"] == True]
    has_ohlc = all(c in plot.columns for c in ["Open","High","Low"])

    BG     = "#0E1117"
    GRID   = "rgba(148,163,184,0.055)"
    SEP    = "rgba(59,130,246,0.25)"   # 境界線色
    AMBER  = "#F59E0B"
    BLUE   = "#60A5FA"
    PURPLE = "#A855F7"
    GREEN  = "#4ADE80"
    RED    = "#F87171"
    INDIGO = "#818CF8"

    SIGNAL_MA_COLOR  = "#EF4444" # 赤（レッド）
    SIGNAL_RSI_COLOR = "#A855F7" # 紫（パープル）
    SIGNAL_CHG_COLOR = "#00CED1" # ターコイズブルー
    SIGNAL_CMP_COLOR = "#F97316" # オレンジ (複合)

    AX_F  = dict(color="#64748B", size=11, family="Inter")
    TTL_F = dict(color="#7DD3FC", size=11, family="Inter")
    LEG   = dict(
        bgcolor="rgba(11,18,34,0.82)",
        bordercolor="rgba(59,130,246,0.18)",
        borderwidth=1,
        font=dict(size=10, color="#E2E8F0", family="Inter"),
        orientation="v",
        tracegroupgap=2,
    )

    SPACING = 0.025
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=SPACING,
        row_heights=row_heights,
    )

    # ── Row1: 株価チャート ──────────────────────────────
    if has_ohlc:
        fig.add_trace(go.Candlestick(
            x=plot.index, open=plot["Open"], high=plot["High"],
            low=plot["Low"], close=plot["Close"],
            name="ローソク足",
            increasing_line_color=GREEN, decreasing_line_color=RED,
            increasing_fillcolor="rgba(74,222,128,0.27)",
            decreasing_fillcolor="rgba(248,113,113,0.27)",
            legend="legend", whiskerwidth=0,
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=plot.index, y=plot["Close"],
            name="終値", mode="lines",
            line=dict(color=BLUE, width=1.8), legend="legend",
        ), row=1, col=1)

    ma_p = plot.dropna(subset=["MA_VAL"])
    fig.add_trace(go.Scatter(
        x=ma_p.index, y=ma_p["MA_VAL"],
        name=ma_label, mode="lines",
        line=dict(color=AMBER, width=2, dash="dot"), legend="legend",
    ), row=1, col=1)

    # シグナルマーカー
    if not sig.empty:
        cnt = (sig["Sig_MA"].astype(int) + sig["Sig_RSI"].astype(int) + sig["Sig_CHG"].astype(int))
        if cond_mode == "AND":
            groups = [
                (sig[ sig["Sig_MA"] & ~sig["Sig_RSI"] & ~sig["Sig_CHG"]], SIGNAL_MA_COLOR, f"{ma_label}シグナル"),
                (sig[~sig["Sig_MA"] &  sig["Sig_RSI"] & ~sig["Sig_CHG"]], SIGNAL_RSI_COLOR, "RSIシグナル"),
                (sig[~sig["Sig_MA"] & ~sig["Sig_RSI"] &  sig["Sig_CHG"]], SIGNAL_CHG_COLOR, "騰落率シグナル"),
                (sig[cnt >= 2], SIGNAL_CMP_COLOR, "複合シグナル"),
            ]
        else: # OR時は複合シグナルを非表示にして、個別のものをそのまま描画
            groups = [
                (sig[sig["Sig_MA"]],  SIGNAL_MA_COLOR, f"{ma_label}シグナル"),
                (sig[sig["Sig_RSI"]], SIGNAL_RSI_COLOR, "RSIシグナル"),
                (sig[sig["Sig_CHG"]], SIGNAL_CHG_COLOR, "騰落率シグナル"),
            ]

        for sub_df, col, name in groups:
            if sub_df.empty: continue
            y_ref  = sub_df["Low"] if has_ohlc else sub_df["Close"]
            fig.add_trace(go.Scatter(
                x=sub_df.index, y=y_ref * 0.93,
                mode="markers", name=name,
                marker=dict(symbol="triangle-up", size=22, color=col, opacity=1.0,
                            line=dict(color="#FFFFFF", width=2.5)),
                legend="legend", hoverinfo="skip",
            ), row=1, col=1)

    # ── Row2: RSI ────────────────────────────────────────
    rp = plot.dropna(subset=["RSI"])
    fig.add_hrect(y0=0,  y1=rsi_thr, fillcolor="rgba(248,113,113,0.055)", line_width=0, row=2, col=1)
    fig.add_hrect(y0=70, y1=100,     fillcolor="rgba(74,222,128,0.055)",  line_width=0, row=2, col=1)
    fig.add_trace(go.Scatter(
        x=rp.index, y=rp["RSI"],
        name="RSI(14)", mode="lines",
        line=dict(color=INDIGO, width=1.6),
        legend="legend2",
    ), row=2, col=1)
    fig.add_hline(y=rsi_thr, line=dict(color=AMBER, width=1.2, dash="dot"),
                  annotation_text=f"   閾値 {rsi_thr}",
                  annotation_font=dict(color=AMBER, size=10),
                  annotation_position="top right", row=2, col=1)
    fig.add_hline(y=30, line=dict(color=RED,   width=0.8, dash="dash"), row=2, col=1)
    fig.add_hline(y=70, line=dict(color=GREEN, width=0.8, dash="dash"), row=2, col=1)

    # ── Row3: 累積資産推移 ───────────────────────────────
    pv = plot.dropna(subset=["DCA_Val","Sig_Val"])
    if not pv.empty:
        fig.add_trace(go.Scatter(
            x=pv.index, y=pv["DCA_Val"],
            name="DCA 資産額", mode="lines",
            line=dict(color=BLUE,   width=2.2),
            fill="tozeroy", fillcolor="rgba(96,165,250,0.06)",
            legend="legend3",
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=pv.index, y=pv["Sig_Val"],
            name="シグナル戦略 資産額", mode="lines",
            line=dict(color=PURPLE, width=2.2),
            fill="tozeroy", fillcolor="rgba(168,85,247,0.06)",
            legend="legend3",
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=pv.index, y=pv["DCA_Inv"],
            name="DCA 元本", mode="lines",
            line=dict(color=BLUE,   width=1, dash="dot"), opacity=0.4,
            legend="legend3",
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=pv.index, y=pv["Sig_Inv"],
            name="シグナル 元本", mode="lines",
            line=dict(color=PURPLE, width=1, dash="dot"), opacity=0.4,
            legend="legend3",
        ), row=3, col=1)

    # ── レイアウト ──────────────────────────────────────
    domain1 = fig.layout.yaxis.domain
    domain2 = fig.layout.yaxis2.domain
    domain3 = fig.layout.yaxis3.domain

    sep2_y = (domain1[0] + domain2[1]) / 2.0  # row1(上) と row2(中) の境界
    sep1_y = (domain2[0] + domain3[1]) / 2.0  # row2(中) と row3(下) の境界

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(family="Inter", size=12, color="#FFFFFF"), # グラフ内テキストも真っ白に
        xaxis_rangeslider_visible=False,
        height=1080,
        margin=dict(l=70, r=18, t=50, b=28),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="rgba(14,17,23,0.9)", font_size=12, font_color="#FFFFFF",
                        bordercolor="rgba(59,130,246,0.6)", align="left"),

        # 境界線（太く鮮やかな青い実線）
        shapes=[
            dict(type="line", xref="paper", yref="paper",
                 x0=0, x1=1, y0=sep1_y, y1=sep1_y,
                 line=dict(color="#3B82F6", width=2.5)),
            dict(type="line", xref="paper", yref="paper",
                 x0=0, x1=1, y0=sep2_y, y1=sep2_y,
                 line=dict(color="#3B82F6", width=2.5)),
        ],

        # 各パネルの凡例（左上内側）
        legend =dict(**LEG, x=0.01, y=0.99, xanchor="left", yanchor="top"),
        legend2=dict(**LEG, x=0.01, y=domain2[1] - 0.01, xanchor="left", yanchor="top"),
        legend3=dict(**LEG, x=0.01, y=domain3[1] - 0.01, xanchor="left", yanchor="top"),
    )

    # チャートタイトル注釈
    name_str = f" ： {ticker_name}" if ticker_name else ""
    fig.add_annotation(text=f"▌ 株価チャート {iv_label} ({ma_label}) {ticker}{name_str}",
                       xref="paper", yref="paper", x=0.0, y=1.01,
                       xanchor="left", yanchor="bottom",
                       font=dict(size=13, color="#7DD3FC", family="Inter", weight="bold"), showarrow=False)
    fig.add_annotation(text="▌ RSI (14)",
                       xref="paper", yref="paper", x=0.0, y=sep2_y + 0.005,
                       xanchor="left", yanchor="bottom",
                       font=dict(size=11, color="#7DD3FC", family="Inter"), showarrow=False)
    fig.add_annotation(text="▌ 累積資産推移 — DCA vs シグナル戦略",
                       xref="paper", yref="paper", x=0.0, y=sep1_y + 0.005,
                       xanchor="left", yanchor="bottom",
                       font=dict(size=11, color="#7DD3FC", family="Inter"), showarrow=False)

    # 軸設定
    ax = dict(gridcolor=GRID, zerolinecolor=GRID, tickfont=AX_F, title_font=TTL_F, showgrid=True)
    fig.update_yaxes(title_text="価格",  **ax, row=1, col=1)
    fig.update_yaxes(title_text="RSI",  range=[0,100], **ax, row=2, col=1)
    fig.update_yaxes(title_text="資産額",**ax, row=3, col=1)
    xax = dict(gridcolor=GRID, tickfont=AX_F, showgrid=True)
    fig.update_xaxes(**xax, showticklabels=True,  row=1, col=1)
    fig.update_xaxes(**xax, showticklabels=False, row=2, col=1)
    fig.update_xaxes(**xax, showticklabels=True,  row=3, col=1)

    return fig

def build_dev_chart(df: pd.DataFrame, dev_thr: float, ma_label: str) -> go.Figure:
    v      = df.dropna(subset=["DEV"])
    colors = np.where(v["DEV"] < 0, "#F87171", "#4ADE80")
    fig    = go.Figure()
    fig.add_trace(go.Bar(x=v.index, y=v["DEV"], marker_color=colors, opacity=0.78, name=f"{ma_label}乖離率"))
    fig.add_hline(y=dev_thr, line=dict(color="#F59E0B", width=1.5, dash="dash"),
                  annotation_text=f"閾値 {dev_thr}%", annotation_font_color="#F59E0B",
                  annotation_position="top right")
    fig.add_hline(y=0, line=dict(color="rgba(255,255,255,0.07)", width=1))
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
        font=dict(family="Inter", color="#94A3B8"),
        title=dict(text=f"{ma_label}乖離率の推移", font=dict(color="#E2E8F0", size=13)),
        height=285, margin=dict(l=65,r=18,t=42,b=18),
        xaxis=dict(gridcolor="rgba(148,163,184,0.055)", tickfont=dict(color="#64748B")),
        yaxis=dict(title="乖離率 (%)", gridcolor="rgba(148,163,184,0.055)", tickfont=dict(color="#64748B")),
        showlegend=False,
    )
    return fig
