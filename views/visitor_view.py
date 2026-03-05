"""
FestivalFlow AI — views/visitor_view.py
来場者画面（認証不要・デフォルト表示）

【機能一覧】
    1. 混雑度カード（緑/黄/赤）+ ソート機能
    2. AI穴場推薦バナー（ρ値TOP3・理由テキスト）
    3. 混雑トレンド表示（履歴5件から傾向算出）
    4. 待機エンタメクイズ（15分以上で自動表示）
"""

import streamlit as st
from core.data_manager import Event, get_sorted_events, get_top_recommended_events
from core.queue_models import calculate_trend
from components.event_card import render_event_card, render_recommended_banner
from components.quiz import render_waiting_quiz


def render_visitor_view() -> None:
    """
    来場者向けのメイン画面を描画する。

    認証不要でアクセス可能。全イベントの混雑状況をリアルタイムで表示する。
    """
    events: list[Event] = st.session_state.get("events", [])

    if not events:
        st.info("🎪 イベント情報を読み込み中です...")
        return

    # ── ヘッダー ────────────────────────────────────────────────
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #0EA5E9 0%, #0284C7 50%, #075985 100%);
        border-radius: 20px;
        padding: 28px 32px;
        margin-bottom: 24px;
        color: white;
        box-shadow: 0 8px 32px rgba(14, 165, 233, 0.3);
    ">
        <div style="font-size: 32px; font-weight: 900; letter-spacing: -0.5px;">
            🎪 FestivalFlow AI
        </div>
        <div style="font-size: 16px; opacity: 0.9; margin-top: 4px;">
            M/M/1待ち行列理論によるリアルタイム混雑ナビ
        </div>
        <div style="margin-top: 16px; display: flex; gap: 16px; flex-wrap: wrap;">
            <span style="background: rgba(255,255,255,0.2); padding: 6px 14px; border-radius: 999px; font-size: 13px;">
                📊 10イベント対応
            </span>
            <span style="background: rgba(255,255,255,0.2); padding: 6px 14px; border-radius: 999px; font-size: 13px;">
                ⚡ リアルタイム更新
            </span>
            <span style="background: rgba(255,255,255,0.2); padding: 6px 14px; border-radius: 999px; font-size: 13px;">
                🤖 AI穴場推薦
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 最終更新時刻 ─────────────────────────────────────────────
    last_updated = st.session_state.get("last_updated")
    if last_updated:
        st.caption(f"🕐 最終更新：{last_updated}")

    # ── AI穴場推薦バナー ──────────────────────────────────────────
    render_recommended_banner(events)

    # ── 統計サマリー ─────────────────────────────────────────────
    _render_summary_stats(events)

    # ── ソートコントロール ────────────────────────────────────────
    st.markdown("### 📋 全イベント一覧")
    col1, col2 = st.columns([3, 1])
    with col1:
        sort_option = st.selectbox(
            "並び替え",
            options=["wait_time", "category", "recommended"],
            format_func=lambda x: {
                "wait_time": "⏱️ 待ち時間が短い順",
                "category": "🏷️ カテゴリ別",
                "recommended": "⭐ おすすめ順",
            }[x],
            label_visibility="collapsed",
        )
    with col2:
        # カテゴリフィルター
        all_categories = list(set(e.category for e in events))
        selected_category = st.selectbox(
            "カテゴリ",
            options=["すべて"] + sorted(all_categories),
            label_visibility="collapsed",
        )

    # ソート＆フィルター適用
    filtered_events = events
    if selected_category != "すべて":
        filtered_events = [e for e in events if e.category == selected_category]

    sorted_events = get_sorted_events(filtered_events, sort_by=sort_option)

    # ── イベントカード一覧 ────────────────────────────────────────
    if not sorted_events:
        st.info(f"「{selected_category}」カテゴリのイベントが見つかりません。")
    else:
        # 2列グリッドでカードを表示
        for i in range(0, len(sorted_events), 2):
            col1, col2 = st.columns(2)
            with col1:
                _render_event_with_quiz(sorted_events[i])
            with col2:
                if i + 1 < len(sorted_events):
                    _render_event_with_quiz(sorted_events[i + 1])

    # ── 凡例 ─────────────────────────────────────────────────────
    _render_legend()


def _render_event_with_quiz(event: Event) -> None:
    """
    イベントカードとクイズを一体で表示する。

    Args:
        event: 表示対象のイベント
    """
    render_event_card(event)

    # 推定待ち時間が15分以上の場合はクイズを表示
    metrics = event.get_metrics()
    if metrics.wait_minutes >= 15:
        render_waiting_quiz(event_id=event.id, wait_minutes=metrics.wait_minutes)


def _render_summary_stats(events: list[Event]) -> None:
    """
    画面上部のサマリー統計（開催中・混雑中・空き・待ち時間平均）を表示する。

    Args:
        events: 全イベントのリスト
    """
    open_count = sum(1 for e in events if e.is_open)
    crowded_count = sum(
        1 for e in events
        if e.is_open and e.get_metrics().status in ["HIGH", "CRITICAL", "SATURATED"]
    )
    free_count = sum(
        1 for e in events
        if e.is_open and e.get_metrics().status in ["LOW", "MODERATE"]
    )
    open_events = [e for e in events if e.is_open]
    avg_wait = (
        sum(e.get_metrics().wait_minutes for e in open_events) / len(open_events)
        if open_events else 0
    )

    col1, col2, col3, col4 = st.columns(4)
    stats = [
        (col1, "🎪", "開催中", str(open_count), "件", "#0EA5E9"),
        (col2, "🔴", "混雑中", str(crowded_count), "件", "#EF4444"),
        (col3, "🟢", "空き", str(free_count), "件", "#22C55E"),
        (col4, "⏱️", "平均待ち", str(int(avg_wait)), "分", "#F97316"),
    ]

    for col, icon, label, value, unit, color in stats:
        with col:
            st.markdown(f"""
            <div style="
                background: white;
                border-radius: 12px;
                padding: 14px 12px;
                text-align: center;
                border: 1px solid #E2E8F0;
                box-shadow: 0 1px 4px rgba(0,0,0,0.06);
            ">
                <div style="font-size: 24px;">{icon}</div>
                <div style="font-size: 12px; color: #64748B; margin: 2px 0;">{label}</div>
                <div style="font-size: 28px; font-weight: 800; color: {color}; line-height: 1.1;">
                    {value}<span style="font-size: 14px; color: #94A3B8;">{unit}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)


def _render_legend() -> None:
    """
    混雑度カラーコードの凡例を画面下部に表示する。
    """
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("""
    <div style="color: #64748B; font-size: 13px; text-align: center;">
        <b>混雑度カラー凡例：</b>
        🟢 空いています（ρ＜50%） ／
        🟡 やや混雑（50%≦ρ＜75%） ／
        🟠 混雑中（75%≦ρ＜90%） ／
        🔴 かなり混雑（90%≦ρ＜100%） ／
        ⛔ 満員（ρ≧100%）
    </div>
    <div style="color: #94A3B8; font-size: 11px; text-align: center; margin-top: 4px;">
        ρ（ロー）= M/M/1待ち行列理論のサーバー利用率。
        Kleinrock (1975) の理論に基づくリアルタイム計算。
    </div>
    """, unsafe_allow_html=True)
