"""
FestivalFlow AI — views/admin_view.py
管理者画面（PIN認証: 9999）

【機能一覧】
    1. KPIカード × 4（総来場推定人数・平均混雑度・最混雑イベント・異常値件数）
    2. 時系列グラフ（Plotly折れ線グラフ）
    3. フロアマップヒートマップ（Plotly 3×4グリッド）
    4. ランキングテーブル（混雑上位5 / 空き上位5）
    5. シミュレーションパネル（モンテカルロ法1000試行）
    6. CSVエクスポート・デモ自動変動・異常値フラグ管理
"""

import time
import streamlit as st

from core.data_manager import Event, LocalDataManager
from core.security import verify_pin, create_session, get_current_role, logout
from core.validators import validate_pin_input
from components.charts import (
    render_kpi_cards,
    render_time_series_chart,
    render_ranking_table,
    render_utilization_bar_chart,
)
from components.heatmap import render_floor_heatmap
from simulation.monte_carlo import render_simulation_panel


def render_admin_view() -> None:
    """
    管理者画面のメインビューを描画する。

    未認証の場合はPINログインフォームを表示する。
    認証済みの場合は管理者ダッシュボードを表示する。
    """
    current_role = get_current_role()

    if current_role != "ADMIN":
        _render_admin_login()
        return

    _render_admin_dashboard()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ログインフォーム
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _render_admin_login() -> None:
    """
    管理者PINログインフォームを表示する。

    管理者PINのみを受け付け、担当者PINは拒否する。
    """
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #FAF5FF, #EDE9FE);
        border: 2px solid #7C3AED;
        border-radius: 20px;
        padding: 32px;
        max-width: 400px;
        margin: 40px auto;
        text-align: center;
        box-shadow: 0 8px 32px rgba(124, 58, 237, 0.15);
    ">
        <div style="font-size: 48px; margin-bottom: 12px;">🔐</div>
        <div style="font-size: 22px; font-weight: 800; color: #4C1D95; margin-bottom: 8px;">
            管理者ログイン
        </div>
        <div style="color: #5B21B6; font-size: 14px; margin-bottom: 24px;">
            管理者専用PINを入力してください
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pin_input = st.text_input(
                "管理者PIN（4〜8桁の数字）",
                type="password",
                placeholder="管理者PIN",
                key="admin_pin_input",
                help="管理者用PINを入力してください。デモ環境: 9999",
            )

            if st.button("🔑 管理者ログイン", type="primary", use_container_width=True):
                # バリデーション
                pin_validation = validate_pin_input(pin_input)
                if not pin_validation.is_valid:
                    st.error(f"❌ {pin_validation.error_message}")
                    return

                # 管理者PINの照合（担当者PINは拒否）
                if verify_pin("ADMIN", pin_input):
                    session = create_session("ADMIN")
                    st.session_state["role"] = "ADMIN"
                    st.session_state["authenticated"] = True
                    st.session_state["session_info"] = session
                    st.success("✅ 管理者としてログインしました！")
                    st.rerun()
                else:
                    st.error("❌ 管理者PINが正しくありません。")

            st.markdown(
                '<div style="text-align:center;margin-top:8px;color:#64748B;font-size:12px;">'
                "🔒 管理者専用ページ。不正アクセスは記録されます。"
                "</div>",
                unsafe_allow_html=True,
            )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 管理者ダッシュボード
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _render_admin_dashboard() -> None:
    """
    管理者ダッシュボードを描画する。

    タブ形式で各機能を分割表示する。
    """
    # ヘッダー
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #4C1D95 0%, #7C3AED 50%, #A855F7 100%);
        border-radius: 20px;
        padding: 24px 32px;
        margin-bottom: 24px;
        color: white;
        box-shadow: 0 8px 32px rgba(124, 58, 237, 0.3);
    ">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
            <div>
                <div style="font-size: 26px; font-weight: 900;">
                    👑 管理者ダッシュボード
                </div>
                <div style="font-size: 13px; opacity: 0.9; margin-top: 4px;">
                    FestivalFlow AI — 全権限モード
                </div>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
                <span style="background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 999px; font-size: 12px;">
                    🔐 管理者認証済み
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ログアウト + デモモードボタン
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🚪 ログアウト", key="admin_logout"):
            logout()
            st.rerun()
    with col2:
        demo_mode = st.session_state.get("demo_mode", False)
        demo_label = "⏹ デモ停止" if demo_mode else "▶️ デモ開始"
        if st.button(demo_label, key="demo_toggle"):
            st.session_state["demo_mode"] = not demo_mode
            st.rerun()
    with col3:
        if demo_mode:
            st.markdown(
                '<span style="color:#F97316;font-weight:700;font-size:13px;">'
                "🔄 デモモード実行中（5秒ごとに自動更新）</span>",
                unsafe_allow_html=True,
            )

    events: list[Event] = st.session_state.get("events", [])

    # デモモードの自動更新
    if demo_mode:
        demo_placeholder = st.empty()
        with demo_placeholder.container():
            LocalDataManager.apply_demo_fluctuation()
            events = st.session_state.get("events", [])

        # 5秒後に再実行
        time.sleep(5)
        st.rerun()

    # ━━ タブ分割 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 KPI概要",
        "📈 時系列分析",
        "🗺️ フロアマップ",
        "🔮 シミュレーション",
        "⚙️ 管理操作",
    ])

    with tab1:
        _render_kpi_tab(events)

    with tab2:
        _render_timeseries_tab(events)

    with tab3:
        _render_heatmap_tab(events)

    with tab4:
        render_simulation_panel(events)

    with tab5:
        _render_management_tab(events)


def _render_kpi_tab(events: list[Event]) -> None:
    """
    KPI概要タブを描画する。

    Args:
        events: 全イベントのリスト
    """
    st.markdown("#### 📊 リアルタイムKPI")
    render_kpi_cards(events)

    st.markdown("---")

    # 異常値アラート表示
    anomaly_events = [e for e in events if e.anomaly_flag]
    if anomaly_events:
        st.markdown("#### 🚨 異常値アラート")
        for event in anomaly_events:
            metrics = event.get_metrics()
            col1, col2 = st.columns([3, 1])
            with col1:
                st.warning(
                    f"⚠️ **{event.emoji} {event.name}**（{event.classroom}）\n\n"
                    f"現在の行列: {event.queue_length}人 / 待ち時間: {metrics.wait_minutes}分 / ρ={round(metrics.utilization*100)}%"
                )
            with col2:
                if st.button(f"✅ 解除", key=f"clear_flag_{event.id}"):
                    LocalDataManager.set_anomaly_flag(event.id, flag=False)
                    st.success("フラグを解除しました。")
                    st.rerun()
    else:
        st.success("✅ 現在、異常値フラグが立っているイベントはありません。")

    st.markdown("---")

    # 利用率バーチャート
    st.markdown("#### 📊 イベント別利用率ρ")
    render_utilization_bar_chart(events)

    # ランキングテーブル
    st.markdown("---")
    st.markdown("#### 🏆 混雑度ランキング")
    render_ranking_table(events)


def _render_timeseries_tab(events: list[Event]) -> None:
    """
    時系列分析タブを描画する。

    Args:
        events: 全イベントのリスト
    """
    st.markdown("#### 📈 行列人数タイムライン")

    # イベントフィルター
    event_options = {e.id: f"{e.emoji} {e.name}" for e in events}
    selected = st.multiselect(
        "表示するイベントを選択",
        options=list(event_options.keys()),
        default=list(event_options.keys())[:5],  # デフォルト5件
        format_func=lambda x: event_options[x],
    )

    render_time_series_chart(events, selected_events=selected if selected else None)

    # 詳細テーブル
    st.markdown("#### 📋 イベント詳細テーブル")
    import pandas as pd

    table_data = []
    for event in events:
        metrics = event.get_metrics()
        table_data.append({
            "": event.emoji,
            "イベント名": event.name,
            "教室": event.classroom,
            "カテゴリ": event.category,
            "行列人数": event.queue_length,
            "待ち時間(分)": metrics.wait_minutes,
            "利用率ρ(%)": round(metrics.utilization * 100, 1),
            "状態": metrics.label,
            "最終更新": event.last_updated_at[-8:-3] if event.last_updated_at else "-",
        })

    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_heatmap_tab(events: list[Event]) -> None:
    """
    フロアマップヒートマップタブを描画する。

    Args:
        events: 全イベントのリスト
    """
    st.markdown("#### 🗺️ フロアマップ混雑ヒートマップ")
    render_floor_heatmap(events)


def _render_management_tab(events: list[Event]) -> None:
    """
    管理操作タブを描画する（CSVエクスポート・フラグ管理等）。

    Args:
        events: 全イベントのリスト
    """
    st.markdown("#### ⚙️ 管理操作")

    # ── CSVエクスポート ─────────────────────────────────────────
    st.markdown("##### 📥 データエクスポート")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("📊 全履歴データをCSVでエクスポート", use_container_width=True):
            df = LocalDataManager.export_to_dataframe()
            if df.empty:
                st.warning("エクスポートするデータがありません。")
            else:
                csv_data = df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    label="⬇️ CSVをダウンロード",
                    data=csv_data,
                    file_name="festivalflow_history.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
                st.success(f"✅ {len(df)}件のレコードを準備しました。")

    with col2:
        if st.button("📋 現在のイベントデータをCSVでエクスポート", use_container_width=True):
            import pandas as pd
            event_data = [e.to_dict() for e in events]
            df = pd.DataFrame(event_data)
            csv_data = df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="⬇️ CSVをダウンロード",
                data=csv_data,
                file_name="festivalflow_current.csv",
                mime="text/csv",
                use_container_width=True,
            )

    st.markdown("---")

    # ── 異常値フラグ一括管理 ─────────────────────────────────────
    st.markdown("##### 🚨 異常値フラグ管理")
    anomaly_events = [e for e in events if e.anomaly_flag]

    if anomaly_events:
        st.warning(f"⚠️ {len(anomaly_events)}件のイベントに異常値フラグが立っています。")
        if st.button("✅ 全フラグを一括解除", type="primary", use_container_width=True):
            for event in anomaly_events:
                LocalDataManager.set_anomaly_flag(event.id, flag=False)
            st.session_state["anomaly_alerts"] = []
            st.success("✅ 全フラグを解除しました。")
            st.rerun()

        for event in anomaly_events:
            metrics = event.get_metrics()
            st.markdown(
                f"- {event.emoji} **{event.name}**（{event.classroom}）："
                f"{event.queue_length}人 / {metrics.label}",
            )
    else:
        st.success("✅ 現在、異常値フラグはありません。")

    st.markdown("---")

    # ── セッション情報 ───────────────────────────────────────────
    st.markdown("##### 🔐 セッション情報")
    session_info = st.session_state.get("session_info", {})
    if session_info:
        st.markdown(f"""
        - **ロール:** {session_info.get('role', '-')}
        - **セッションID:** `{session_info.get('session_id', '-')[:16]}...`（短縮表示）
        - **ログイン時刻:** {session_info.get('created_at', '-')}
        - **有効期限:** {session_info.get('expires_at', '-')}
        """)
    else:
        st.info("セッション情報がありません。")

    st.markdown("---")

    # ── デバッグ：行列人数手動設定 ──────────────────────────────
    st.markdown("##### 🔧 行列人数の手動一括設定（デバッグ用）")
    debug_mode = st.checkbox("デバッグモードを有効にする", value=False)
    if debug_mode:
        st.warning("⚠️ この機能はデバッグ専用です。全イベントの行列人数を一括変更します。")
        preset = st.selectbox(
            "プリセットを選択",
            options=["空（全0人）", "普通（ランダム20-60人）", "混雑（ランダム80-150人）"],
        )
        if st.button("🔧 プリセットを適用", use_container_width=True):
            import random
            for event in events:
                if "空" in preset:
                    new_q = 0
                elif "普通" in preset:
                    new_q = random.randint(20, 60)
                else:
                    new_q = random.randint(80, 150)

                LocalDataManager.update_queue_length(
                    event_id=event.id,
                    new_queue_length=new_q,
                    updated_by="ADMIN_DEBUG",
                )
            st.success("✅ プリセットを適用しました。")
            st.rerun()
