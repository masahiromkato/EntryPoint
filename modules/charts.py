import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import datetime
from modules.config import (
    BG, GRID, AMBER, BLUE, PURPLE, GREEN, RED, INDIGO,
    SIG_MA_COLOR, SIG_RSI_COLOR, SIG_CHG_COLOR, SIG_CMP_COLOR,
    AX_F, TTL_F, LEG_BASE
)


def render_main_chart(
    df: pd.DataFrame,
    ticker: str,
    ticker_name: str,
    iv_label: str,
    ma_label: str,
    dev_thr: float,
    rsi_thr: float,
    row_heights: list,
    cond_mode: str,
    show_annual_grid: bool = False,
) -> go.Figure:

    # 描画対象（呼び出し側でフィルタリング済み）
    plot     = df.copy()
    plot     = plot.dropna(subset=["Close"])
    sig      = plot[plot["Signal"] == True]
    has_ohlc = all(c in plot.columns for c in ["Open", "High", "Low"])

    SPACING = 0.022
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=SPACING,
        row_heights=row_heights,
    )

    # ── Row1: 株価チャート ───────────────────────────────────
    if has_ohlc:
        fig.add_trace(go.Candlestick(
            x=plot.index, open=plot["Open"], high=plot["High"],
            low=plot["Low"], close=plot["Close"],
            name="ローソク足",
            increasing_line_color=GREEN, decreasing_line_color=RED,
            increasing_fillcolor=GREEN,
            decreasing_fillcolor=RED,
            legendgroup="price", legend="legend", whiskerwidth=0.4,
            showlegend=False,
            # ツールチップの完全制御（Date, Open, Close, Changeのみ）
            hovertemplate=(
                "Date: %{x|%Y-%m-%d}<br>"
                "Open: %{open:,.2f}<br>"
                "Close: %{close:,.2f}<br>"
                "Change: %{customdata:+.2f}%<extra></extra>"
            ),
            customdata=plot["PRICE_CHG"].values if "PRICE_CHG" in plot.columns else np.zeros(len(plot)),
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=plot.index, y=plot["Close"],
            name="終値", mode="lines",
            line=dict(color=BLUE, width=1.8),
            legendgroup="price", legend="legend",
        ), row=1, col=1)

    ma_p = plot.dropna(subset=["MA_VAL"])
    fig.add_trace(go.Scatter(
        x=ma_p.index, y=ma_p["MA_VAL"],
        name=ma_label, mode="lines",
        line=dict(color=AMBER, width=2, dash="dot"),
        legendgroup="price", legend="legend",
        hoverinfo="skip",  # MAのホバー表示を物理的に遮断
    ), row=1, col=1)

    # ── シグナルマーカー ─────────────────────────────────────
    if not sig.empty:
        cnt = sig["Sig_MA"].astype(int) + sig["Sig_RSI"].astype(int) + sig["Sig_CHG"].astype(int)

        if cond_mode == "AND":
            groups = [
                (sig[ sig["Sig_MA"] & ~sig["Sig_RSI"] & ~sig["Sig_CHG"]], SIG_MA_COLOR,  f"{ma_label}シグナル"),
                (sig[~sig["Sig_MA"] &  sig["Sig_RSI"] & ~sig["Sig_CHG"]], SIG_RSI_COLOR, "RSIシグナル"),
                (sig[~sig["Sig_MA"] & ~sig["Sig_RSI"] &  sig["Sig_CHG"]], SIG_CHG_COLOR, "騰落率シグナル"),
                (sig[cnt >= 2],                                             SIG_CMP_COLOR, "複合シグナル"),
            ]
        else:  # OR: 複合シグナルは不表示
            groups = [
                (sig[sig["Sig_MA"]],  SIG_MA_COLOR,  f"{ma_label}シグナル"),
                (sig[sig["Sig_RSI"]], SIG_RSI_COLOR, "RSIシグナル"),
                (sig[sig["Sig_CHG"]], SIG_CHG_COLOR, "騰落率シグナル"),
            ]

        for sub_df, col, name in groups:
            if sub_df.empty:
                continue
            y_ref = sub_df["Low"] if has_ohlc else sub_df["Close"]
            fig.add_trace(go.Scatter(
                x=sub_df.index, y=y_ref * 0.93,
                mode="markers", name=name,
                marker=dict(
                    symbol="circle", size=14, color=col, opacity=1.0,
                    line=dict(color="#E0E0E0", width=1.0),
                ),
                legendgroup="price", legend="legend", hoverinfo="skip",
            ), row=1, col=1)

    # ── 年次グリッド ─────────────────────────────────────────
    # ラベルが物理的に重ならないよう、年数に応じてステップとフォントを自動調整
    if show_annual_grid:
        years     = sorted(plot.index.year.unique())
        num_years = len(years)

        # ── 表示間隔の自動計算 ──────────────────────────────
        if num_years <= 15:
            step = 1
        elif num_years <= 30:
            step = 2
        elif num_years <= 50:
            step = 5
        else:
            step = 10

        # ── 表示年リスト確定（集計区間の計算に必要）────────
        display_years = [y for i, y in enumerate(years)
                         if i == 0 or (y % step == 0)]
        num_labels = len(display_years)

        # ── フォントサイズ: 表示ラベル数に応じて動的計算 ───
        # display_years が少ないほど大きく、多いほど小さく
        if num_labels <= 8:
            ann_fontsize = 13
        elif num_labels <= 15:
            ann_fontsize = 11
        elif num_labels <= 25:
            ann_fontsize = 10
        else:
            ann_fontsize = 8

        # ── スマート年号省略ヘルパー ────────────────────────
        def _period_str(y_from: int, y_to: int) -> str:
            """
            同一年          : '2011'
            同一世紀内複数年 : '2020-24' (後半2桁省略)
            世紀跨ぎ複数年   : '1999-2002' (フル)
            """
            if step == 1 or y_from == y_to:
                return f"<b>{y_from}</b>"
            # 世紀が同じかどうか（例: 2000〜2099 は同一世紀）
            if y_from // 100 == y_to // 100:
                return f"<b>{y_from}-{y_to % 100:02d}</b>"  # :02d で "2020-04" 等ゼロ埋め
            return f"<b>{y_from}-{y_to}</b>"

        for idx, y in enumerate(display_years):
            sub_yr = plot[plot.index.year == y]
            if sub_yr.empty:
                continue
            first_day = sub_yr.index[0]

            # ── 区間シグナル累計: 全ラベル合計 = チャート▽総数 ──
            if "Signal" in df.columns:
                y_from = y
                y_to   = display_years[idx + 1] - 1 if idx + 1 < len(display_years) else years[-1]
                mask   = (df.index.year >= y_from) & (df.index.year <= y_to)
                num_signals = int(df.loc[mask, "Signal"].sum())
            else:
                y_to = y
                num_signals = 0

            # 期間文字列（スマート省略）
            period_txt = _period_str(y, y_to)

            # 垂直点線（全Row共通）
            fig.add_vline(
                x=first_day.timestamp() * 1000,
                line=dict(color="rgba(255,255,255,0.15)", width=1, dash="dot"),
                row="all", col=1,
            )
            # ラベル: paper 座標の最上端に固定 → ローソク足と不干渉
            count_color = "#F59E0B" if num_signals > 0 else "rgba(255,255,255,0.45)"
            cnt_fsize   = ann_fontsize + 2
            fig.add_annotation(
                x=first_day,
                y=0.99,
                yref="paper",
                text=(
                    f"{period_txt}<br>"
                    f"<span style='color:{count_color};font-size:{cnt_fsize}px'>"
                    f"<b>{num_signals}回</b></span>"
                ),
                showarrow=False,
                font=dict(color="rgba(255,255,255,0.85)", size=ann_fontsize, family="Inter"),
                xanchor="left",
                yanchor="top",
                bgcolor="rgba(0,0,0,0)",
                align="left",
            )

    # ── Row2: RSI ───────────────────────────────────────────
    rp = plot.dropna(subset=["RSI"])
    fig.add_hrect(y0=0,  y1=rsi_thr, fillcolor="rgba(248,113,113,0.055)", line_width=0, row=2, col=1)
    fig.add_hrect(y0=70, y1=100,     fillcolor="rgba(74,222,128,0.055)",  line_width=0, row=2, col=1)
    fig.add_trace(go.Scatter(
        x=rp.index, y=rp["RSI"],
        name="RSI(14)", mode="lines",
        line=dict(color=INDIGO, width=1.6),
        legendgroup="rsi", legend="legend2",
    ), row=2, col=1)
    # RSI 30/70 固定ライン
    fig.add_hline(y=30, line=dict(color=RED,   width=1.0, dash="dash"), row=2, col=1)
    fig.add_hline(y=70, line=dict(color=GREEN, width=1.0, dash="dash"), row=2, col=1)

    # ── Row3: 累積資産推移 ───────────────────────────────────
    pv = plot.dropna(subset=["DCA_Val", "Sig_Val"])
    if not pv.empty:
        fig.add_trace(go.Scatter(
            x=pv.index, y=pv["DCA_Val"],
            name="DCA 資産額", mode="lines",
            line=dict(color=BLUE, width=1.5),
            fill="tozeroy", fillcolor="rgba(96,165,250,0.06)",
            legendgroup="port", legend="legend3",
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=pv.index, y=pv["Sig_Val"],
            name="シグナル戦略 資産額", mode="lines",
            line=dict(color=PURPLE, width=1.5),
            fill="tozeroy", fillcolor="rgba(168,85,247,0.06)",
            legendgroup="port", legend="legend3",
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=pv.index, y=pv["DCA_Inv"],
            name="DCA 元本", mode="lines",
            line=dict(color=BLUE, width=1, dash="dot"), opacity=0.4,
            legendgroup="port", legend="legend3",
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=pv.index, y=pv["Sig_Inv"],
            name="シグナル 元本", mode="lines",
            line=dict(color=PURPLE, width=1, dash="dot"), opacity=0.4,
            legendgroup="port", legend="legend3",
        ), row=3, col=1)

    # ── レイアウト ──────────────────────────────────────────
    domain1 = fig.layout.yaxis.domain
    domain2 = fig.layout.yaxis2.domain
    domain3 = fig.layout.yaxis3.domain
    sep2_y = (domain1[0] + domain2[1]) / 2.0
    sep1_y = (domain2[0] + domain3[1]) / 2.0

    name_str  = f" ： {ticker_name}" if ticker_name else ""
    title_txt = f"▌ 株価チャート {iv_label} ({ma_label}) {ticker}{name_str}"

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(family="Inter", size=12, color="#FFFFFF"),
        xaxis_rangeslider_visible=False,
        height=1080,
        margin=dict(l=70, r=18, t=50, b=28),
        hovermode="x",  # unifiedを廃止し、最上部の自動ヘッダー（年月など）を根絶
        hoverlabel=dict(
            bgcolor="rgba(14,17,23,0.75)",
            font_size=12, font_color="#FFFFFF",
            bordercolor="rgba(59,130,246,0.6)", align="left",
            namelength=0,  # トレース名を物理的に削除しヘッダーノイズを遮断
        ),
        shapes=[
            dict(type="line", xref="paper", yref="paper",
                 x0=0, x1=1, y0=sep1_y, y1=sep1_y,
                 line=dict(color="#3B82F6", width=2.5)),
            dict(type="line", xref="paper", yref="paper",
                 x0=0, x1=1, y0=sep2_y, y1=sep2_y,
                 line=dict(color="#3B82F6", width=2.5)),
        ],
        legend =dict(**LEG_BASE, x=0.01, y=0.93, xanchor="left", yanchor="top"),
        legend2=dict(**LEG_BASE, x=0.01, y=domain2[1] - 0.01, xanchor="left", yanchor="top"),
        legend3=dict(**LEG_BASE, x=0.01, y=domain3[1] - 0.01, xanchor="left", yanchor="top"),
    )

    # チャートタイトル注釈
    fig.add_annotation(text=title_txt,
                       xref="paper", yref="paper", x=0.0, y=1.01,
                       xanchor="left", yanchor="bottom",
                       font=dict(size=13, color="#7DD3FC", family="Inter", weight="bold"),
                       showarrow=False)
    fig.add_annotation(text="▌ RSI (14)",
                       xref="paper", yref="paper", x=0.0, y=sep2_y + 0.005,
                       xanchor="left", yanchor="bottom",
                       font=dict(size=11, color="#7DD3FC", family="Inter"), showarrow=False)
    fig.add_annotation(text="▌ 累積資産推移 — DCA vs シグナル戦略",
                       xref="paper", yref="paper", x=0.0, y=sep1_y + 0.005,
                       xanchor="left", yanchor="bottom",
                       font=dict(size=11, color="#7DD3FC", family="Inter"), showarrow=False)

    # 軸設定
    ax  = dict(gridcolor=GRID, zerolinecolor=GRID, tickfont=AX_F, title_font=TTL_F, showgrid=True)
    fig.update_yaxes(title_text="価格",   **ax, row=1, col=1)
    fig.update_yaxes(title_text="RSI",    range=[0, 100], zeroline=False, **ax, row=2, col=1)
    fig.update_yaxes(title_text="資産額", **ax, row=3, col=1)
    
    # x軸のホバー形式を統一してヘッダー抑制を助ける
    xax = dict(gridcolor=GRID, tickfont=AX_F, showgrid=True, hoverformat="%Y-%m-%d")
    fig.update_xaxes(**xax, showticklabels=True,  row=1, col=1)
    fig.update_xaxes(**xax, showticklabels=False, row=2, col=1)
    fig.update_xaxes(**xax, showticklabels=True,  row=3, col=1)

    # ── 閾値ラインを最前面に描画 ───────────────────────────
    fig.add_hline(
        y=rsi_thr, 
        line=dict(color=AMBER, width=1.5, dash="dash"),
        annotation_text=f" 閾値 {rsi_thr:.1f} ",
        annotation_font=dict(color=AMBER, size=12, family="Inter"),
        annotation_position="top right", 
        row=2, col=1
    )

    return fig


def build_dev_chart(df: pd.DataFrame, dev_thr: float, ma_label: str) -> go.Figure:
    v      = df.dropna(subset=["DEV"])
    # ネオンカラー: プラス = 発光グリーン, マイナス = 発光レッド
    colors = np.where(v["DEV"] < 0, "rgba(255,50,80,0.92)", "rgba(50,255,140,0.92)")
    sig    = v[v["Sig_MA"] == True] if "Sig_MA" in v.columns else v.iloc[:0]
    fig    = go.Figure()
    fig.add_trace(go.Bar(
        x=v.index, y=v["DEV"], 
        marker_color=colors, 
        opacity=1.0, 
        marker_line_width=0,
        name=f"{ma_label}乖離率",
        hovertemplate="%{y:+.2f}%<extra></extra>",
        customdata=v["DEV"].values,
    ))
    fig.add_hline(y=dev_thr, line=dict(color=AMBER, width=2.5, dash="dash"),
                  annotation_text=f" 閾値 {dev_thr:.1f}% ",
                  annotation_font=dict(color=AMBER, size=11),
                  annotation_position="bottom right")
    fig.add_hline(y=0, line=dict(color="rgba(255,255,255,0.07)", width=1))
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(family="Inter", color="#94A3B8"),
        title=dict(text=f"{ma_label}乖離率（閾値: {dev_thr}%）", font=dict(color="#E2E8F0", size=13)),
        height=285, margin=dict(l=65, r=18, t=42, b=18),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="rgba(14,17,23,0.82)", font_color="#FFFFFF", font_size=11),
        xaxis=dict(gridcolor=GRID, tickfont=AX_F),
        yaxis=dict(title="乖離率 (%)", gridcolor=GRID, tickfont=AX_F, zeroline=False),
        showlegend=False,
        legend=dict(**{k: v for k, v in LEG_BASE.items() if k not in ("x", "xanchor")},
                    x=0.01, xanchor="left", y=0.99, yanchor="top"),
    )
    return fig


def build_rsi_detail_chart(df: pd.DataFrame, rsi_thr: float) -> go.Figure:
    v   = df.dropna(subset=["RSI"])
    sig = v[v["Sig_RSI"] == True] if "Sig_RSI" in v.columns else v.iloc[:0]
    fig = go.Figure()
    fig.add_hrect(y0=0,    y1=rsi_thr, fillcolor="rgba(248,113,113,0.06)", line_width=0)
    fig.add_hrect(y0=70,   y1=100,     fillcolor="rgba(74,222,128,0.06)",  line_width=0)
    fig.add_trace(go.Scatter(
        x=v.index, y=v["RSI"],
        name="RSI(14)", mode="lines",
        line=dict(color=INDIGO, width=1.8),
    ))
    fig.add_hline(y=rsi_thr, line=dict(color=AMBER, width=1.5, dash="dash"),
                  annotation_text=f" 閾値 {rsi_thr:.1f} ",
                  annotation_font=dict(color=AMBER, size=12, family="Inter"),
                  annotation_position="top right")
    fig.add_hline(y=30, line=dict(color=RED,   width=0.8, dash="dash"),
                  annotation_text="30.0 ", annotation_position="bottom right",
                  annotation_font=dict(color=RED, size=10))
    fig.add_hline(y=70, line=dict(color=GREEN, width=0.8, dash="dash"),
                  annotation_text="70.0 ", annotation_position="top right",
                  annotation_font=dict(color=GREEN, size=10))
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(family="Inter", color="#94A3B8"),
        title=dict(text=f"RSI(14)（閾値: {rsi_thr}）", font=dict(color="#E2E8F0", size=13)),
        height=285, margin=dict(l=65, r=18, t=42, b=18),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="rgba(14,17,23,0.82)", font_color="#FFFFFF", font_size=11),
        xaxis=dict(gridcolor=GRID, tickfont=AX_F),
        yaxis=dict(title="RSI", range=[0, 100], gridcolor=GRID, tickfont=AX_F, zeroline=False),
        showlegend=False,
        legend=dict(**{k: v for k, v in LEG_BASE.items() if k not in ("x", "xanchor")},
                    x=0.01, xanchor="left", y=0.99, yanchor="top"),
    )
    return fig


def build_chg_chart(df: pd.DataFrame, chg_thr: float, unit: str) -> go.Figure:
    v      = df.dropna(subset=["PRICE_CHG"])
    # ネオンカラー: プラス = 発光グリーン, マイナス = 発光レッド
    colors = np.where(v["PRICE_CHG"] < 0, "rgba(255,50,80,0.92)", "rgba(50,255,140,0.92)")
    sig    = v[v["Sig_CHG"] == True] if "Sig_CHG" in v.columns else v.iloc[:0]
    fig    = go.Figure()
    fig.add_trace(go.Bar(
        x=v.index, y=v["PRICE_CHG"],
        marker_color=colors, 
        opacity=1.0, 
        marker_line_width=0,
        name=f"前{unit}比騰落率",
        hovertemplate="%{y:+.2f}%<extra></extra>",
        customdata=v["PRICE_CHG"].values,
    ))
    fig.add_hline(y=chg_thr, line=dict(color=AMBER, width=2.5, dash="dash"),
                  annotation_text=f" 閾値 {chg_thr:.1f}% ",
                  annotation_font=dict(color=AMBER, size=11),
                  annotation_position="bottom right")
    fig.add_hline(y=0, line=dict(color="rgba(255,255,255,0.07)", width=1))
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(family="Inter", color="#94A3B8"),
        title=dict(text=f"前{unit}比 騰落率（閾値: {chg_thr}%）", font=dict(color="#E2E8F0", size=13)),
        height=285, margin=dict(l=65, r=18, t=42, b=18),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="rgba(14,17,23,0.82)", font_color="#FFFFFF", font_size=11),
        xaxis=dict(gridcolor=GRID, tickfont=AX_F),
        yaxis=dict(title=f"騰落率 (%)", gridcolor=GRID, tickfont=AX_F, zeroline=False),
        showlegend=False,
        legend=dict(**{k: v for k, v in LEG_BASE.items() if k not in ("x", "xanchor")},
                    x=0.01, xanchor="left", y=0.99, yanchor="top"),
    )
    return fig
