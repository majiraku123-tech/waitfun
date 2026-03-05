"""
FestivalFlow AI — views/staff_view.py
担当者画面（PIN認証: 1234）

【機能一覧】
    1. 行列人数入力UI（+1/-1ボタン + 直接入力）
    2. staff_class_idによるアクセス制御（担当イベントのみ編集可）
    3. リアルタイムバリデーション表示
    4. 更新成功・異常値検知フィードバック
"""

import streamlit as st
from datetime import datetime, timezone

from core.data_manager import Event, LocalDataManager
from core.security import (
    verify_pin, create_session, validate_permission,
    require_permission, get_current_role
)
from core.validators import validate_queue_input, validate_pin_input
from components.event_card import render_event_card


def render_staff_view() -> None:
    """
    担当者画面のメインビューを描画する。

    未認証の場合はPINログインフォームを表示する。
    認証済みの場合は行列人数入力UIを表示する。
    """
    current_role = get_current_role()

    # ── 担当者またはそれ以上のロールが必要 ──────────────────────
    if current_role not in ["STAFF", "ADMIN"]:
        _render_staff_login()
        return

    # ── 担当者画面 ────────────────────────────────────────────────
    _render_staff_dashboard()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ログインフォーム
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _render_staff_login() -> None:
    """
    担当者PINログインフォームを表示する。

    bcryptによりPINをハッシュと照合する。
    平文PINはこの関数スコープ内でのみ使用し、session_stateには保存しない。
    """
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #F0FDF4, #DCFCE7);
        border: 2px solid #22C55E;
        border-radius: 20px;
        padding: 32px;
        max-width: 400px;
        margin: 40px auto;
        text-align: center;
        box-shadow: 0 8px 32px rgba(34, 197, 94, 0.15);
    ">
        <div style="font-size: 48px; margin-bottom: 12px;">👷</div>
        <div style="font-size: 22px; font-weight: 800; color: #14532D; margin-bottom: 8px;">
            担当者ログイン
        </div>
        <div style="color: #166534; font-size: 14px; margin-bottom: 24px;">
            担当者PINを入力してください
        </div>
    </div>
    """, unsafe_allow_html=True)

    # PINフォーム（コンテナで中央揃え）
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pin_input = st.text_input(
                "担当者PIN（4〜8桁の数字）",
                type="password",
                placeholder="例：1234",
                key="staff_pin_input",
                help="担当者用PINを入力してください。デモ環境: 1234",
            )

            if st.button("🔑 ログイン", type="primary", use_container_width=True):
                # ── バリデーション ────────────────────────────────
                pin_validation = validate_pin_input(pin_input)
                if not pin_validation.is_valid:
                    st.error(f"❌ {pin_validation.error_message}")
                    return

                # ── PIN照合（bcrypt）─────────────────────────────
                # 担当者PINの照合
                if verify_pin("STAFF", pin_input):
                    session = create_session("STAFF")
                    st.session_state["role"] = "STAFF"
                    st.session_state["authenticated"] = True
                    st.session_state["session_info"] = session
                    # 担当者は全クラスにアクセス可（デモ用）
                    st.session_state["staff_class_id"] = "ALL"
                    st.success("✅ 担当者としてログインしました！")
                    st.rerun()
                # 管理者PINも受け付ける
                elif verify_pin("ADMIN", pin_input):
                    session = create_session("ADMIN")
                    st.session_state["role"] = "ADMIN"
                    st.session_state["authenticated"] = True
                    st.session_state["session_info"] = session
                    st.session_state["staff_class_id"] = "ALL"
                    st.success("✅ 管理者としてログインしました！")
                    st.rerun()
                else:
                    st.error("❌ PINが正しくありません。もう一度試してください。")

            # 管理者ログインへのリンク
            st.markdown(
                '<div style="text-align:center;margin-top:8px;color:#64748B;font-size:13px;">'
                "管理者の方は「管理者」タブからログインしてください"
                "</div>",
                unsafe_allow_html=True,
            )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 担当者ダッシュボード
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _render_staff_dashboard() -> None:
    """
    担当者向けの行列人数入力ダッシュボードを表示する。
    """
    current_role = get_current_role()
    role_label = "管理者" if current_role == "ADMIN" else "担当者"
    role_color = "#7C3AED" if current_role == "ADMIN" else "#059669"
    role_icon = "👑" if current_role == "ADMIN" else "👷"

    # ヘッダー
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #F0FDF4, #DCFCE7);
        border: 2px solid {role_color};
        border-radius: 16px;
        padding: 20px 24px;
        margin-bottom: 24px;
    ">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <div style="font-size:20px; font-weight:800; color:{role_color};">
                    {role_icon} {role_label}ダッシュボード
                </div>
                <div style="color:#64748B; font-size:13px; margin-top:4px;">
                    行列人数を更新してください。変更は即時反映されます。
                </div>
            </div>
            <div style="text-align:right;">
                <div style="background:{role_color};color:white;padding:4px 12px;
                            border-radius:999px;font-size:12px;font-weight:600;">
                    {role_label}モード
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ログアウトボタン
    if st.button("🚪 ログアウト", key="staff_logout"):
        from core.security import logout
        logout()
        st.rerun()

    events: list[Event] = st.session_state.get("events", [])
    if not events:
        st.info("イベントデータがありません。")
        return

    # 担当者の場合は全イベントを編集可能（デモ用）
    # 本番環境では staff_class_id でフィルタリングする
    editable_events = events

    st.markdown("### 📋 行列人数を更新する")
    st.info("💡 **使い方：** ＋/－ボタンで1人ずつ、または数値を直接入力してEnterを押してください。")

    # イベントごとに入力UIを表示
    for event in editable_events:
        _render_queue_input_card(event)


def _render_queue_input_card(event: Event) -> None:
    """
    1件のイベントに対する行列人数入力カードを表示する。

    Args:
        event: 入力対象のイベント
    """
    metrics = event.get_metrics()

    with st.container():
        st.markdown(f"""
        <div style="
            background: white;
            border: 1px solid #E2E8F0;
            border-left: 4px solid {metrics.color};
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        ">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <div>
                    <span style="font-size:22px;">{event.emoji}</span>
                    <span style="font-weight:700; font-size:16px; color:#0F172A; margin-left:6px;">{event.name}</span>
                    <span style="background:#F1F5F9;color:#475569;padding:2px 8px;
                                 border-radius:999px;font-size:11px;margin-left:6px;">{event.classroom}</span>
                </div>
                <div style="color:{metrics.color}; font-weight:700; font-size:14px;">
                    {metrics.emoji} {metrics.label} | ρ={round(metrics.utilization*100)}%
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 2, 1])

        with col1:
            # ─1ボタン
            if st.button(
                "➖",
                key=f"minus_{event.id}",
                help="1人減らす",
                use_container_width=True,
            ):
                new_val = max(0, event.queue_length - 1)
                _process_queue_update(event, new_val)

        with col2:
            # +1ボタン
            if st.button(
                "➕",
                key=f"plus_{event.id}",
                help="1人増やす",
                use_container_width=True,
            ):
                new_val = min(500, event.queue_length + 1)
                _process_queue_update(event, new_val)

        with col3:
            # 現在値を表示
            st.markdown(
                f'<div style="text-align:center;padding:8px;background:#F8FAFC;'
                f'border-radius:8px;font-size:14px;color:#0F172A;">'
                f'現在: <b>{event.queue_length}人</b></div>',
                unsafe_allow_html=True,
            )

        with col4:
            # 直接入力フォーム
            new_value = st.number_input(
                "人数を直接入力",
                min_value=0,
                max_value=500,
                value=event.queue_length,
                step=1,
                key=f"input_{event.id}",
                label_visibility="collapsed",
            )
            if new_value != event.queue_length:
                _process_queue_update(event, int(new_value))

        with col5:
            # 推定待ち時間表示
            wait_color = metrics.color
            st.markdown(
                f'<div style="text-align:center;padding:8px;background:#F8FAFC;'
                f'border-radius:8px;font-size:13px;color:{wait_color};font-weight:700;">'
                f'~{metrics.wait_minutes}分待</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)


def _process_queue_update(event: Event, new_value: int) -> None:
    """
    行列人数の更新処理を実行する。

    バリデーション → 更新 → フィードバック表示 の流れを実装。

    Args:
        event    : 更新対象のイベント
        new_value: 新しい行列人数
    """
    # バリデーション実行
    validation = validate_queue_input(
        value=new_value,
        current_value=event.queue_length,
        check_festival_hours=False,  # スタッフ画面では時間外でも更新可能
    )

    if not validation.is_valid:
        st.error(f"❌ {validation.error_message}")
        return

    # データ更新
    current_role = get_current_role()
    LocalDataManager.update_queue_length(
        event_id=event.id,
        new_queue_length=validation.sanitized_value,
        updated_by=current_role,
    )

    # 異常値フラグの設定
    if validation.is_anomaly:
        LocalDataManager.set_anomaly_flag(event.id, flag=True)
        # 管理者アラートリストに追加
        alerts = st.session_state.get("anomaly_alerts", [])
        alerts.append({
            "event_name": event.name,
            "old_value": event.queue_length,
            "new_value": validation.sanitized_value,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        })
        st.session_state["anomaly_alerts"] = alerts[-20:]  # 最新20件を保持

    # 最終更新時刻を記録
    now_str = datetime.now().strftime("%H:%M")
    st.session_state["last_updated"] = now_str

    # フィードバック表示
    if validation.is_anomaly:
        st.warning(f"⚠️ 更新しました（{now_str}）\n{validation.warning_message}")
    elif validation.has_warnings:
        st.warning(f"✅ 更新しました（{now_str}）\n{validation.warning_message}")
    else:
        st.success(f"✅ {event.name} の行列を {validation.sanitized_value}人 に更新しました（{now_str}）")

    st.rerun()
