"""
FestivalFlow AI — components/event_card.py
イベントカードUIコンポーネント

混雑度・待ち時間・トレンド矢印を表示するカードコンポーネント。
来場者画面・担当者画面で共通使用する。
"""

import streamlit as st
from core.data_manager import Event 
from core.queue_models import calculate_trend, get_recommendation_reason

def render_event_card(event: Event, show_details: bool = True) -> None:
    metrics = event.get_metrics()
    history_lengths = [h.queue_length for h in event.history]
    trend = calculate_trend(history_lengths)
    trend_color = {"↑": "#EF4444", "↓": "#22C55E", "→": "#64748B"}.get(trend, "#64748B")
    
    # 背景色の定義
    bg_colors = {
        "LOW": "#F0FDF4",      # 薄い緑
        "MODERATE": "#FEFCE8", # 薄い黄
        "HIGH": "#FFF7ED",     # 薄いオレンジ
        "CRITICAL": "#FFF1F2",  # 薄い赤
        "SATURATED": "#FFF1F2",
    }
    bg_color = bg_colors.get(metrics.status, "#FFFFFF")

    # HTML構築：colorに !important をつけて、ダークモードの強制白文字を回避します
    card_html = f"""
    <div style="background: {bg_color}; border: 2px solid {metrics.color}; border-radius: 12px; padding: 16px 20px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div>
                <span style="font-size:28px;">{event.emoji}</span>
                <span style="font-size:18px; font-weight:700; color:#0F172A !important; margin-left:8px;">{event.name}</span>
                <div style="color:#475569 !important; font-size:13px; margin-top:4px; font-weight:500;">📍 {event.classroom}（{event.floor}F）</div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:32px; font-weight:800; color:{metrics.color} !important; line-height:1;">{metrics.wait_minutes}<span style="font-size:14px;">分待ち</span></div>
                <div style="color:{metrics.color} !important; font-weight:700; font-size:14px; margin-top:4px;">{metrics.emoji} {metrics.label}</div>
            </div>
        </div>
        
        <div style="display:flex; gap:12px; margin-top:16px;">
            <div style="background:rgba(255,255,255,0.8); border-radius:8px; padding:8px; flex:1; text-align:center; border:1px solid rgba(0,0,0,0.05);">
                <div style="color:#64748B !important; font-size:11px; font-weight:600; margin-bottom:2px;">🚶 行列</div>
                <div style="font-size:18px; font-weight:800; color:#1E293B !important;">{event.queue_length}<span style="font-size:11px; font-weight:600;">人</span></div>
            </div>
            <div style="background:rgba(255,255,255,0.8); border-radius:8px; padding:8px; flex:1; text-align:center; border:1px solid rgba(0,0,0,0.05);">
                <div style="color:#64748B !important; font-size:11px; font-weight:600; margin-bottom:2px;">📊 利用率</div>
                <div style="font-size:18px; font-weight:800; color:#1E293B !important;">{round(metrics.utilization * 100)}<span style="font-size:11px; font-weight:600;">%</span></div>
            </div>
            <div style="background:rgba(255,255,255,0.8); border-radius:8px; padding:8px; flex:1; text-align:center; border:1px solid rgba(0,0,0,0.05);">
                <div style="color:#64748B !important; font-size:11px; font-weight:600; margin-bottom:2px;">📈 傾向</div>
                <div style="font-size:22px; font-weight:900; color:{trend_color} !important; line-height:1;">{trend}</div>
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
