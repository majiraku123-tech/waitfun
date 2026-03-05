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
from core.data_manager import Event, get_sorted_events
from components.event_card import render_event_card, render_recommended_banner
from components.quiz import render_waiting_quiz

def render_visitor_view() -> None:
    """
    来場者向けのメイン画面を描画する。
    クオリティを維持しつつ、堅牢なエラーハンドリングを実装。
    """
    """高級感のある統計タイルを表示（視認性向上版）"""
    open_events = [e for e in events if e.is_open]
    if not open_events:
        return

    avg_wait = sum(e.get_metrics().wait_minutes for e in open_events) / len(open_events)
    
    c1, c2, c3, c4 = st.columns(4)
    data = [
        (c1, "🎪", "開催中", f"{len(open_events)}", "件", "#0EA5E9"),
        (c2, "⏱️", "平均待ち", f"{int(avg_wait)}", "分", "#F97316"),
        (c3, "🟢", "空き", f"{sum(1 for e in open_events if e.get_metrics().status == 'LOW')}", "件", "#22C55E"),
        (c4, "🚨", "異常値", f"{sum(1 for e in events if e.anomaly_flag)}", "件", "#EF4444"),
    ]
    
    for col, icon, label, val, unit, color in data:
        with col:
            st.markdown(f"""
            <div style="background:white; border-radius:12px; padding:15px; text-align:center; border:1px solid #E2E8F0; box-shadow:0 2px 4px rgba(0,0,0,0.05);">
                <div style="font-size:20px;">{icon}</div>
                <div style="font-size:11px; color:#64748B !important; font-weight:600; margin:4px 0;">{label}</div>
                <div style="font-size:24px; font-weight:800; color:{color} !important; line-height:1;">{val}<span style="font-size:12px; color:#94A3B8 !important;">{unit}</span></div>
            </div>
            """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── 2. AI穴場推薦バナー ──
    render_recommended_banner(events)

    # ── 3. 統計サマリー（リッチデザイン版） ──
    _render_summary_stats(events)

    # ── 4. フィルタリング & ソート ──
    st.markdown("### 📋 全イベント一覧")
    
    col_s1, col_s2 = st.columns([2, 1])
    with col_s1:
        sort_option = st.selectbox(
            "並び替え",
            options=["wait_time", "category", "recommended"],
            format_func=lambda x: {
                "wait_time": "⏱️ 待ち時間が短い順",
                "category": "🏷️ カテゴリ別",
                "recommended": "⭐ おすすめ順",
            }[x],
            label_visibility="collapsed"
        )
    with col_s2:
        all_cats = sorted(list(set(e.category for e in events)))
        selected_cat = st.selectbox("カテゴリ", ["すべて"] + all_cats, label_visibility="collapsed")

    # データ加工
    filtered = events if selected_cat == "すべて" else [e for e in events if e.category == selected_cat]
    sorted_events = get_sorted_events(filtered, sort_by=sort_option)

    # ── 5. イベントカード一覧（グリッドレイアウト） ──
    if not sorted_events:
        st.warning("該当するイベントがありません。")
    else:
        # 2列表示のロジック
        for i in range(0, len(sorted_events), 2):
            col1, col2 = st.columns(2)
            with col1:
                _render_event_unit(sorted_events[i])
            with col2:
                if i + 1 < len(sorted_events):
                    _render_event_unit(sorted_events[i + 1])

    # ── 6. 凡例（フッター） ──
    _render_legend()


def _render_event_unit(event: Event) -> None:
    """カードとクイズをセットで描画するユニット"""
    render_event_card(event)
    metrics = event.get_metrics()
    # 待ち時間が長い場合のみ、クオリティを落とさずクイズを表示
    if metrics.wait_minutes >= 15:
        render_waiting_quiz(event.id, metrics.wait_minutes)


def _render_summary_stats(events: list[Event]) -> None:
    """高級感のある統計タイルを表示"""
    open_events = [e for e in events if e.is_open]
    if not open_events:
        return

    avg_wait = sum(e.get_metrics().wait_minutes for e in open_events) / len(open_events)
    
    # 4つのカラムで統計を表示
    c1, c2, c3, c4 = st.columns(4)
    data = [
        (c1, "🎪", "開催中", f"{len(open_events)}", "件", "#0EA5E9"),
        (c2, "⏱️", "平均待ち", f"{int(avg_wait)}", "分", "#F97316"),
        (c3, "🟢", "空き", f"{sum(1 for e in open_events if e.get_metrics().status == 'LOW')}", "件", "#22C55E"),
        (c4, "🚨", "異常値", f"{sum(1 for e in events if e.anomaly_flag)}", "件", "#EF4444"),
    ]
    
    for col, icon, label, val, unit, color in data:
        with col:
            st.markdown(f"""
            <div style="background:white; border-radius:12px; padding:15px; text-align:center; border:1px solid #E2E8F0; box-shadow:0 2px 4px rgba(0,0,0,0.05);">
                <div style="font-size:20px;">{icon}</div>
                <div style="font-size:11px; color:#64748B; margin:4px 0;">{label}</div>
                <div style="font-size:24px; font-weight:800; color:{color};">{val}<span style="font-size:12px; color:#94A3B8;">{unit}</span></div>
            </div>
            """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)


def _render_legend() -> None:
    """凡例のデザインも維持"""
    st.markdown("---")
    st.markdown("""
    <div style="color:#64748B; font-size:12px; text-align:center; opacity:0.8;">
        理論基盤: M/M/1 待ち行列モデル (Kendall's Notation) <br>
        🟢 空き (<50%) | 🟡 やや混雑 | 🟠 混雑 | 🔴 満員 (>90%)
    </div>
    """, unsafe_allow_html=True)
