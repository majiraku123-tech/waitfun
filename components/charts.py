"""
FestivalFlow AI — components/charts.py
時系列グラフ・KPIメトリクスコンポーネント

Plotly・Altairを使用したインタラクティブなグラフコンポーネント。
管理者ダッシュボードで使用する。
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from core.data_manager import Event
from core.queue_models import STATUS_COLORS


def render_kpi_cards(events: list[Event]) -> None:
    """
    管理者ダッシュボード用KPIカード×4を表示する。

    表示するKPI：
        1. 総来場推定人数（全イベントの行列合計）
        2. 平均混雑度ρ（全イベントの平均利用率）
        3. 最混雑イベント名（利用率ρが最大のイベント）
        4. 異常値検知件数（anomaly_flagが立っているイベント数）

    Args:
        events: 全イベントのリスト
    """
    if not events:
        st.warning("イベントデータがありません。")
        return

    # KPI計算
    total_queue = sum(e.queue_length for e in events)
    metrics_list = [e.get_metrics() for e in events]
    avg_utilization = np.mean([m.utilization for m in metrics_list])
    most_crowded = max(events, key=lambda e: e.get_metrics().utilization)
    anomaly_count = sum(1 for e in events if e.anomaly_flag)

    # KPIカード表示
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#EFF6FF,#DBEAFE);
                    border:2px solid #3B82F6;border-radius:12px;padding:16px;text-align:center;">
            <div style="font-size:12px;color:#3B82F6;font-weight:600;margin-bottom:4px;">👥 総来場推定人数</div>
            <div style="font-size:36px;font-weight:800;color:#1E40AF;">{total_queue:,}</div>
            <div style="font-size:12px;color:#64748B;">人（行列合計）</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        rho_pct = round(avg_utilization * 100, 1)
        rho_color = "#22C55E" if avg_utilization < 0.5 else "#EAB308" if avg_utilization < 0.75 else "#EF4444"
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#F0FDF4,#DCFCE7);
                    border:2px solid {rho_color};border-radius:12px;padding:16px;text-align:center;">
            <div style="font-size:12px;color:{rho_color};font-weight:600;margin-bottom:4px;">📊 平均混雑度ρ</div>
            <div style="font-size:36px;font-weight:800;color:{rho_color};">{rho_pct}%</div>
            <div style="font-size:12px;color:#64748B;">全イベント平均</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        most_metrics = most_crowded.get_metrics()
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#FFF7ED,#FFEDD5);
                    border:2px solid #F97316;border-radius:12px;padding:16px;text-align:center;">
            <div style="font-size:12px;color:#F97316;font-weight:600;margin-bottom:4px;">🔥 最混雑イベント</div>
            <div style="font-size:20px;font-weight:800;color:#9A3412;">{most_crowded.emoji} {most_crowded.name}</div>
            <div style="font-size:12px;color:#64748B;">待ち {most_metrics.wait_minutes}分 / ρ={round(most_metrics.utilization*100)}%</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        alert_color = "#EF4444" if anomaly_count > 0 else "#22C55E"
        alert_icon = "🚨" if anomaly_count > 0 else "✅"
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#FFF1F2,#FFE4E6);
                    border:2px solid {alert_color};border-radius:12px;padding:16px;text-align:center;">
            <div style="font-size:12px;color:{alert_color};font-weight:600;margin-bottom:4px;">{alert_icon} 異常値検知</div>
            <div style="font-size:36px;font-weight:800;color:{alert_color};">{anomaly_count}</div>
            <div style="font-size:12px;color:#64748B;">件（要確認）</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)


def render_time_series_chart(events: list[Event], selected_events: list[str] = None) -> None:
    """
    全イベントの行列人数推移を折れ線グラフで表示する（Plotly）。

    各イベントの更新履歴から時系列データを生成してグラフ化する。

    Args:
        events          : 全イベントのリスト
        selected_events : 表示するイベントIDのリスト（Noneの場合は全件表示）
    """
    if not events:
        st.info("表示するデータがありません。")
        return

    fig = go.Figure()

    # カラーパレット
    colors = px.colors.qualitative.Set2

    for idx, event in enumerate(events):
        if selected_events and event.id not in selected_events:
            continue
        if len(event.history) < 2:
            continue

        timestamps = [h.timestamp for h in event.history]
        queue_lengths = [h.queue_length for h in event.history]

        # ISO形式のタイムスタンプをフォーマット
        time_labels = []
        for ts in timestamps:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_labels.append(dt.strftime("%H:%M"))
            except Exception:
                time_labels.append(ts[-8:-3])  # HH:MM部分を抽出

        fig.add_trace(go.Scatter(
            x=time_labels,
            y=queue_lengths,
            mode="lines+markers",
            name=f"{event.emoji} {event.name}",
            line=dict(width=2, color=colors[idx % len(colors)]),
            marker=dict(size=6),
            hovertemplate=(
                f"<b>{event.name}</b><br>"
                "時刻: %{x}<br>"
                "行列: %{y}人<br>"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        title=dict(text="📈 行列人数タイムライン", font=dict(size=16, color="#0F172A")),
        xaxis_title="時刻",
        yaxis_title="行列人数（人）",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400,
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        margin=dict(l=40, r=20, t=60, b=40),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#E2E8F0")
    fig.update_yaxes(showgrid=True, gridcolor="#E2E8F0", rangemode="tozero")

    st.plotly_chart(fig, use_container_width=True)


def render_ranking_table(events: list[Event]) -> None:
    """
    混雑度ランキング（上位5件）と空き状況ランキング（下位5件）を並列表示する。

    Args:
        events: 全イベントのリスト
    """
    if not events:
        return

    sorted_by_crowd = sorted(events, key=lambda e: e.get_metrics().utilization, reverse=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🔥 混雑ランキング TOP5")
        for i, event in enumerate(sorted_by_crowd[:5], 1):
            metrics = event.get_metrics()
            bar_width = min(100, int(metrics.utilization * 100))
            st.markdown(f"""
            <div style="margin-bottom:8px;padding:10px 12px;background:white;border-radius:8px;
                        border-left:4px solid {metrics.color};box-shadow:0 1px 3px rgba(0,0,0,0.1);">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-weight:600;color:#0F172A;">{i}. {event.emoji} {event.name}</span>
                    <span style="color:{metrics.color};font-weight:700;">{metrics.wait_minutes}分待ち</span>
                </div>
                <div style="background:#E2E8F0;border-radius:999px;height:6px;margin-top:6px;">
                    <div style="background:{metrics.color};width:{bar_width}%;height:6px;border-radius:999px;"></div>
                </div>
                <div style="font-size:11px;color:#64748B;margin-top:2px;">ρ = {round(metrics.utilization*100)}%</div>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown("#### 💨 穴場ランキング TOP5")
        sorted_by_free = sorted(events, key=lambda e: e.get_metrics().utilization)
        for i, event in enumerate(sorted_by_free[:5], 1):
            metrics = event.get_metrics()
            bar_width = min(100, int(metrics.utilization * 100))
            st.markdown(f"""
            <div style="margin-bottom:8px;padding:10px 12px;background:white;border-radius:8px;
                        border-left:4px solid {metrics.color};box-shadow:0 1px 3px rgba(0,0,0,0.1);">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-weight:600;color:#0F172A;">{i}. {event.emoji} {event.name}</span>
                    <span style="color:{metrics.color};font-weight:700;">{metrics.wait_minutes}分待ち</span>
                </div>
                <div style="background:#E2E8F0;border-radius:999px;height:6px;margin-top:6px;">
                    <div style="background:{metrics.color};width:{bar_width}%;height:6px;border-radius:999px;"></div>
                </div>
                <div style="font-size:11px;color:#64748B;margin-top:2px;">ρ = {round(metrics.utilization*100)}%</div>
            </div>
            """, unsafe_allow_html=True)


def render_utilization_bar_chart(events: list[Event]) -> None:
    """
    全イベントの利用率を横棒グラフで表示する（Plotly）。

    Args:
        events: 全イベントのリスト
    """
    if not events:
        return

    sorted_events = sorted(events, key=lambda e: e.get_metrics().utilization)
    names = [f"{e.emoji} {e.name}" for e in sorted_events]
    utilizations = [round(e.get_metrics().utilization * 100, 1) for e in sorted_events]
    colors = [e.get_metrics().color for e in sorted_events]

    fig = go.Figure(go.Bar(
        x=utilizations,
        y=names,
        orientation="h",
        marker_color=colors,
        text=[f"{u}%" for u in utilizations],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>利用率: %{x}%<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text="📊 イベント別サーバー利用率ρ", font=dict(size=16, color="#0F172A")),
        xaxis=dict(title="利用率ρ (%)", range=[0, 120]),
        yaxis=dict(title=""),
        height=max(300, len(events) * 40),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        margin=dict(l=150, r=60, t=60, b=40),
        showlegend=False,
    )
    fig.add_vline(x=90, line_dash="dash", line_color="#EF4444", annotation_text="危険ライン(90%)")
    fig.add_vline(x=75, line_dash="dot", line_color="#F97316", annotation_text="警告ライン(75%)")

    st.plotly_chart(fig, use_container_width=True)
