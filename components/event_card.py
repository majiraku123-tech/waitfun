"""
FestivalFlow AI — components/event_card.py
イベントカードUIコンポーネント

混雑度・待ち時間・トレンド矢印を表示するカードコンポーネント。
来場者画面・担当者画面で共通使用する。
"""

import streamlit as st
from core.data_manager import Event
from core.queue_models import QueueMetrics, calculate_trend, get_recommendation_reason


def render_event_card(event: Event, show_details: bool = True) -> None:
    """
    1件のイベントカードをStreamlitコンポーネントとして描画する。

    Args:
        event       : 表示対象のEventオブジェクト
        show_details: 詳細情報（利用率・履歴）を表示するかどうか
    """
    metrics = event.get_metrics()

    # 混雑度に応じた背景色グラデーション
    bg_color = _get_card_bg_color(metrics.status)
    border_color = metrics.color

    # トレンド計算
    history_lengths = [h.queue_length for h in event.history]
    trend = calculate_trend(history_lengths)
    trend_color = {"↑": "#EF4444", "↓": "#22C55E", "→": "#6B7280"}[trend]

    # 営業状況バッジ
    open_badge = "🟢 営業中" if event.is_open else "⛔ 営業終了"

    # カードHTMLの生成
    anomaly_badge = ""
    if event.anomaly_flag:
        anomaly_badge = '<span style="background:#7F1D1D;color:white;padding:2px 8px;border-radius:4px;font-size:11px;margin-left:8px;">⚠️ 異常値</span>'

    card_html = f"""
    <div style="
        background: {bg_color};
        border: 2px solid {border_color};
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        position: relative;
    ">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px;">
            <div>
                <span style="font-size:28px;">{event.emoji}</span>
                <span style="font-size:18px; font-weight:700; color:#0F172A; margin-left:8px;">{event.name}</span>
                {anomaly_badge}
                <div style="color:#475569; font-size:13px; margin-top:4px;">
                    📍 {event.classroom}（{event.floor}F）&nbsp;｜&nbsp;
                    <span style="background:#E2E8F0;padding:2px 8px;border-radius:999px;font-size:12px;">{event.category}</span>
                    &nbsp;｜&nbsp;{open_badge}
                </div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:32px; font-weight:800; color:{border_color};">
                    {metrics.wait_minutes}<span style="font-size:14px; font-weight:500;">分待ち</span>
                </div>
                <div style="color:{border_color}; font-weight:600; font-size:14px;">
                    {metrics.emoji} {metrics.label}
                </div>
            </div>
        </div>
        <div style="display:flex; gap:16px; margin-top:12px; flex-wrap:wrap;">
            <div style="background:rgba(255,255,255,0.7);border-radius:8px;padding:8px 12px;min-width:100px;">
                <div style="color:#64748B;font-size:11px;font-weight:600;">🚶 現在の行列</div>
                <div style="font-size:20px;font-weight:700;color:#0F172A;">{event.queue_length}<span style="font-size:12px;">人</span></div>
            </div>
            <div style="background:rgba(255,255,255,0.7);border-radius:8px;padding:8px 12px;min-width:100px;">
                <div style="color:#64748B;font-size:11px;font-weight:600;">📊 利用率ρ</div>
                <div style="font-size:20px;font-weight:700;color:#0F172A;">{round(metrics.utilization * 100)}<span style="font-size:12px;">%</span></div>
            </div>
            <div style="background:rgba(255,255,255,0.7);border-radius:8px;padding:8px 12px;min-width:100px;">
                <div style="color:#64748B;font-size:11px;font-weight:600;">📈 トレンド</div>
                <div style="font-size:24px;font-weight:700;color:{trend_color};">{trend}</div>
            </div>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def render_recommended_banner(events: list[Event]) -> None:
    """
    穴場イベントTOP3をAI推薦バナーとして表示する。

    利用率ρが最も低いイベントを3件選出し、推薦理由とともに表示する。

    Args:
        events: 全イベントのリスト
    """
    open_events = [e for e in events if e.is_open]
    if not open_events:
        return

    # 利用率ρが低い順に上位3件を選出
    sorted_events = sorted(open_events, key=lambda e: e.get_metrics().utilization)
    top3 = sorted_events[:3]

    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #0EA5E9, #F97316);
        border-radius: 16px;
        padding: 20px 24px;
        margin-bottom: 24px;
        color: white;
    ">
        <div style="font-size:20px; font-weight:800; margin-bottom:4px;">
            🤖 AI穴場レコメンド
        </div>
        <div style="font-size:13px; opacity:0.9;">
            M/M/1待ち行列モデルによるリアルタイム混雑解析結果
        </div>
    </div>
    """, unsafe_allow_html=True)

    cols = st.columns(min(len(top3), 3))
    for idx, (col, event) in enumerate(zip(cols, top3)):
        metrics = event.get_metrics()
        reason = get_recommendation_reason(metrics)
        rank_badges = ["🥇", "🥈", "🥉"]

        with col:
            card_html = f"""
            <div style="
                background: white;
                border: 2px solid #0EA5E9;
                border-radius: 12px;
                padding: 16px;
                text-align: center;
                height: 100%;
                min-height: 160px;
            ">
                <div style="font-size:24px;">{rank_badges[idx]} {event.emoji}</div>
                <div style="font-weight:700; font-size:15px; color:#0F172A; margin:8px 0 4px;">{event.name}</div>
                <div style="color:#22C55E; font-size:22px; font-weight:800;">{metrics.wait_minutes}分待ち</div>
                <div style="color:#64748B; font-size:11px; margin-top:6px; line-height:1.4;">{reason}</div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)


def _get_card_bg_color(status: str) -> str:
    """
    混雑ステータスに応じたカード背景色を返す（グラデーション）。

    Args:
        status: 混雑ステータス文字列

    Returns:
        str: CSS background-color 値
    """
    bg_colors = {
        "LOW":       "linear-gradient(135deg, #F0FDF4, #DCFCE7)",
        "MODERATE":  "linear-gradient(135deg, #FEFCE8, #FEF9C3)",
        "HIGH":      "linear-gradient(135deg, #FFF7ED, #FFEDD5)",
        "CRITICAL":  "linear-gradient(135deg, #FFF1F2, #FFE4E6)",
        "SATURATED": "linear-gradient(135deg, #FFF1F2, #FECDD3)",
    }
    return bg_colors.get(status, "white")
