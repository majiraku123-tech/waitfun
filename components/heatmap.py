"""
FestivalFlow AI — components/heatmap.py
フロアマップヒートマップコンポーネント

Plotlyを使用した3×4グリッドのフロアマップ。
各教室の混雑度をカラーマップ（緑→赤グラデーション）で表示する。
"""

import streamlit as st
import plotly.graph_objects as go
import numpy as np
from core.data_manager import Event


# フロアマップのグリッド定義（行=フロア、列=列番号）
# 各教室の配置をグリッド座標で定義する
FLOOR_MAP_LAYOUT = {
    # floor: [(col_idx, event_id_prefix), ...]
    4: [0, 1, 2],
    3: [0, 1, 2],
    2: [0, 1, 2],
    1: [0, 1, 2],
}


def render_floor_heatmap(events: list[Event]) -> None:
    """
    3×4グリッドのフロアマップヒートマップを描画する（Plotly）。

    各教室の混雑度をカラーマップで表示し、
    マウスオーバーで詳細情報（イベント名・待ち時間・利用率）を表示する。

    Args:
        events: 全イベントのリスト
    """
    if not events:
        st.info("表示するイベントデータがありません。")
        return

    # フロアとカラムに基づいてイベントを配置する
    # グリッド: rows=4（1F〜4F）, cols=3（左・中・右）
    floors = [4, 3, 2, 1]  # 上から下へ（4F→1F）
    cols_per_floor = 3

    # グリッドデータを初期化
    z_values = np.zeros((len(floors), cols_per_floor))
    text_values = [[" " for _ in range(cols_per_floor)] for _ in range(len(floors))]
    hover_texts = [["" for _ in range(cols_per_floor)] for _ in range(len(floors))]

    # イベントをグリッドに配置
    _assign_events_to_grid(events, floors, z_values, text_values, hover_texts)

    # y軸ラベル（フロア名）
    y_labels = [f"{f}F" for f in floors]
    # x軸ラベル（位置）
    x_labels = ["左側", "中央", "右側"]

    # ヒートマップ作成
    fig = go.Figure(data=go.Heatmap(
        z=z_values,
        x=x_labels,
        y=y_labels,
        text=text_values,
        customdata=hover_texts,
        texttemplate="%{text}",
        textfont=dict(size=11, color="white"),
        hovertemplate="%{customdata}<extra></extra>",
        colorscale=[
            [0.0, "#22C55E"],    # LOW: 緑
            [0.5, "#EAB308"],    # MODERATE: 黄
            [0.75, "#F97316"],   # HIGH: オレンジ
            [0.9, "#EF4444"],    # CRITICAL: 赤
            [1.0, "#7F1D1D"],    # SATURATED: 濃赤
        ],
        zmin=0,
        zmax=1,
        showscale=True,
        colorbar=dict(
            title="利用率ρ",
            tickvals=[0, 0.5, 0.75, 0.9, 1.0],
            ticktext=["LOW<br>(0%)", "MODERATE<br>(50%)", "HIGH<br>(75%)", "CRITICAL<br>(90%)", "SATURATED<br>(100%)"],
            len=0.8,
        ),
    ))

    fig.update_layout(
        title=dict(
            text="🗺️ フロアマップ混雑ヒートマップ",
            font=dict(size=16, color="#0F172A"),
        ),
        height=420,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=60, r=100, t=60, b=40),
        xaxis=dict(
            title="フロア区画",
            side="top",
        ),
        yaxis=dict(
            title="フロア",
            autorange="reversed",
        ),
    )

    st.plotly_chart(fig, use_container_width=True)

    # フロア別凡例（テキスト補足）
    _render_floor_legend(events)


def _assign_events_to_grid(
    events: list[Event],
    floors: list[int],
    z_values: np.ndarray,
    text_values: list[list[str]],
    hover_texts: list[list[str]],
) -> None:
    """
    イベントをフロアグリッドに割り当てる内部関数。

    Args:
        events     : 全イベントのリスト
        floors     : フロアのリスト（降順：4→1）
        z_values   : ヒートマップのZ値（利用率0.0〜1.0）
        text_values: カードに表示するテキスト
        hover_texts: ホバー時に表示するテキスト
    """
    # フロア別にイベントを整理
    floor_events: dict[int, list[Event]] = {f: [] for f in floors}
    for event in events:
        if event.floor in floor_events:
            floor_events[event.floor].append(event)

    # グリッドに配置
    for row_idx, floor in enumerate(floors):
        floor_event_list = floor_events[floor]
        for col_idx in range(3):
            if col_idx < len(floor_event_list):
                event = floor_event_list[col_idx]
                metrics = event.get_metrics()

                # Z値（利用率）を設定
                z_values[row_idx][col_idx] = min(metrics.utilization, 1.0)

                # 表示テキスト（短縮名）
                short_name = event.name[:5] + "…" if len(event.name) > 5 else event.name
                text_values[row_idx][col_idx] = (
                    f"{event.emoji}\n{short_name}\n{metrics.wait_minutes}分待"
                )

                # ホバーテキスト（詳細情報）
                hover_texts[row_idx][col_idx] = (
                    f"<b>{event.emoji} {event.name}</b><br>"
                    f"📍 教室: {event.classroom}<br>"
                    f"🚶 行列: {event.queue_length}人<br>"
                    f"⏱️ 待ち時間: {metrics.wait_minutes}分<br>"
                    f"📊 利用率ρ: {round(metrics.utilization * 100)}%<br>"
                    f"💡 状態: {metrics.label}"
                )
            else:
                # イベントが割り当てられていないセル
                z_values[row_idx][col_idx] = -0.1  # 未使用セル（薄灰色）
                text_values[row_idx][col_idx] = "—"
                hover_texts[row_idx][col_idx] = "（イベントなし）"


def _render_floor_legend(events: list[Event]) -> None:
    """
    フロア別イベント一覧を簡易テキストで表示する。

    Args:
        events: 全イベントのリスト
    """
    floor_events: dict[int, list[Event]] = {}
    for event in events:
        floor_events.setdefault(event.floor, []).append(event)

    st.markdown("**フロア別イベント一覧**")
    for floor in sorted(floor_events.keys(), reverse=True):
        event_list = floor_events[floor]
        event_names = "　".join([f"{e.emoji}{e.name}({e.classroom})" for e in event_list])
        metrics_list = [e.get_metrics() for e in event_list]
        avg_rho = sum(m.utilization for m in metrics_list) / len(metrics_list)
        avg_color = "#22C55E" if avg_rho < 0.5 else "#EAB308" if avg_rho < 0.75 else "#EF4444"
        st.markdown(
            f'<span style="color:{avg_color};font-weight:700;">{floor}F</span> {event_names}',
            unsafe_allow_html=True,
        )
