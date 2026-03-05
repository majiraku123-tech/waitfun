"""
FestivalFlow AI — core/security.py
認証・RBAC・セッション管理モジュール

【セキュリティ設計方針】
    ゼロトラストセキュリティモデルを採用：
    「信頼しない・常に検証する」原則に基づき、
    すべてのアクション前に権限チェックを実施する。

【脅威モデル】
    - 特権昇格攻撃 → RBAC + 最小権限の原則
    - セッション固定攻撃 → ロール昇格時にsession_id再生成
    - 平文パスワード漏洩 → bcryptソルト付きハッシュ
    - ブルートフォース攻撃 → bcryptのコストパラメータ（work factor）で緩和

【本番移行時の注意】
    PIN_HASHESはデモ用設定です。本番環境では：
    1. Supabase Auth に差し替える
    2. PINを st.secrets で管理する
    3. MFA（多要素認証）の追加を検討する
"""

import hashlib
import secrets
import time
from datetime import datetime, timezone
from typing import Optional

import bcrypt
import streamlit as st
from jose import JWTError, jwt

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RBAC ロール定義
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROLES: dict[str, dict] = {
    "VISITOR": {
        "level": 0,
        "label": "来場者",
        "permissions": ["read:events", "read:wait_time"],
        "accessible_views": ["visitor"],
    },
    "STAFF": {
        "level": 1,
        "label": "担当者",
        "permissions": ["read:events", "read:wait_time", "write:queue"],
        "accessible_views": ["visitor", "staff"],
    },
    "ADMIN": {
        "level": 2,
        "label": "管理者",
        "permissions": [
            "read:events",
            "read:wait_time",
            "write:queue",
            "read:analytics",
            "write:config",
            "export:data",
        ],
        "accessible_views": ["visitor", "staff", "admin", "simulation"],
    },
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 認証設定
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# JWT署名シークレット（本番環境では st.secrets["JWT_SECRET"] を使用すること）
# デモ用に固定値を使用（本番では毎起動時にランダム生成推奨）
_JWT_SECRET = "festivalflow-demo-secret-2024-change-in-production"
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_HOURS = 8  # 文化祭1日分の有効期限

# bcrypt ワークファクター（コスト係数）
# 値が高いほどブルートフォース耐性が上がるが計算コストも増加
# 本番推奨値: 12、デモ用: 4（高速化のため低めに設定）
_BCRYPT_ROUNDS = 4

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PINハッシュ（デモ用）
# 【重要】平文PINをここに記載することはセキュリティ上望ましくない。
# 本番環境では Supabase Auth または st.secrets を使用すること。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_PIN_HASHES: dict[str, bytes] = {
    "STAFF": bcrypt.hashpw(b"1234", bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)),
    "ADMIN": bcrypt.hashpw(b"9999", bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)),
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 認証関数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def verify_pin(role: str, pin: str) -> bool:
    """
    入力されたPINをbcryptハッシュと照合する。

    【セキュリティ】
        - 比較はbcrypt.checkpwで実施（タイミング攻撃対策：定時間比較）
        - PIN平文はこの関数内でのみ使用し、session_stateに保存しない
        - ロールが存在しない場合もFalseを返す（情報漏洩防止）

    Args:
        role: 認証を試みるロール（"STAFF" または "ADMIN"）
        pin : 入力されたPIN文字列

    Returns:
        bool: 認証成功ならTrue、失敗ならFalse
    """
    if role not in _PIN_HASHES:
        return False

    try:
        # bytes変換して比較（PINが空文字列の場合も安全に処理）
        pin_bytes = pin.encode("utf-8")
        return bcrypt.checkpw(pin_bytes, _PIN_HASHES[role])
    except Exception:
        # 予期しない例外はFalseとして扱う（フェイルセーフ）
        return False


def create_session(role: str) -> dict:
    """
    認証済みセッションを生成する。

    JWTペイロードにロールと有効期限を含む。
    セッションIDはCSPRNG（secrets.token_hex）で生成する。

    【脅威対策】
        セッション固定攻撃：ロール昇格のたびに新しいsession_idを生成する。
        セッションハイジャック：JWTの有効期限（8時間）で自動失効させる。

    Args:
        role: 認証されたロール文字列（ROLES キーのいずれか）

    Returns:
        dict: セッション情報（role, session_id, jwt_token, created_at, expires_at）

    Raises:
        ValueError: roleが不正な値の場合
    """
    if role not in ROLES:
        raise ValueError(f"不正なロールです: {role}")

    # CSPRNG（暗号論的安全疑似乱数生成器）でセッションIDを生成
    session_id = secrets.token_hex(32)

    # JWT発行時刻・有効期限
    now_ts = int(time.time())
    exp_ts = now_ts + (_JWT_EXPIRE_HOURS * 3600)

    # JWTペイロード
    payload = {
        "sub": session_id,
        "role": role,
        "level": ROLES[role]["level"],
        "iat": now_ts,
        "exp": exp_ts,
    }

    # JWT署名
    jwt_token = jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)

    return {
        "role": role,
        "session_id": session_id,
        "jwt_token": jwt_token,
        "created_at": datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat(),
        "expires_at": datetime.fromtimestamp(exp_ts, tz=timezone.utc).isoformat(),
        "authenticated": True,
    }


def validate_session(session_info: Optional[dict]) -> bool:
    """
    セッション情報が有効かどうかを検証する。

    JWTの署名・有効期限を検証し、不正なセッションを拒否する。

    Args:
        session_info: create_session() で生成したセッション辞書

    Returns:
        bool: セッションが有効ならTrue
    """
    if not session_info:
        return False
    if not session_info.get("authenticated", False):
        return False

    jwt_token = session_info.get("jwt_token")
    if not jwt_token:
        return False

    try:
        # JWT署名・有効期限を検証
        jwt.decode(jwt_token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        return True
    except JWTError:
        return False


def validate_permission(required_permission: str) -> bool:
    """
    現在のStreamlitセッションが指定パーミッションを持つか検証する。

    すべての権限チェックはこの関数を経由すること。
    セッション情報は st.session_state から取得する。

    【最小権限の原則】
        必要最小限のパーミッションのみを付与し、
        操作ごとに都度チェックする。

    Args:
        required_permission: チェックするパーミッション文字列
                             （例："write:queue", "export:data"）

    Returns:
        bool: パーミッションを持つ場合True
    """
    # セッション状態から現在のロールを取得
    current_role = st.session_state.get("role", "VISITOR")

    # セッション有効性チェック（VISITORは常に有効）
    if current_role != "VISITOR":
        session_info = st.session_state.get("session_info")
        if not validate_session(session_info):
            # 無効なセッション → VISITORに降格
            st.session_state["role"] = "VISITOR"
            current_role = "VISITOR"

    # ロールのパーミッションリストを確認
    role_permissions = ROLES.get(current_role, ROLES["VISITOR"])["permissions"]
    return required_permission in role_permissions


def require_permission(required_permission: str) -> None:
    """
    パーミッションを要求し、不足している場合はStreamlitでエラー表示 + 停止する。

    ビュー関数の先頭で使用する権限ガード関数。

    Args:
        required_permission: 必要なパーミッション文字列

    Raises:
        st.stop(): パーミッション不足の場合にStreamlitの実行を停止する
    """
    if not validate_permission(required_permission):
        current_role = st.session_state.get("role", "VISITOR")
        role_label = ROLES.get(current_role, {}).get("label", "不明")
        st.error(
            f"🚫 アクセス権限がありません。\n\n"
            f"現在のロール：**{role_label}**\n"
            f"必要な権限：`{required_permission}`\n\n"
            "担当者または管理者としてログインしてください。"
        )
        st.stop()


def get_current_role() -> str:
    """
    現在のStreamlitセッションのロールを返す。

    Returns:
        str: ロール文字列（"VISITOR" / "STAFF" / "ADMIN"）
    """
    return st.session_state.get("role", "VISITOR")


def get_role_info(role: Optional[str] = None) -> dict:
    """
    ロール情報辞書を返す。

    Args:
        role: ロール文字列。Noneの場合は現在のセッションロールを使用。

    Returns:
        dict: ROLES[role] の辞書
    """
    if role is None:
        role = get_current_role()
    return ROLES.get(role, ROLES["VISITOR"])


def logout() -> None:
    """
    セッションをリセットしてVISITORロールに戻る。

    session_stateから認証関連の情報を安全に削除する。
    """
    keys_to_reset = ["role", "session_info", "authenticated"]
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]

    st.session_state["role"] = "VISITOR"
    st.session_state["authenticated"] = False
    st.session_state["session_info"] = None


def get_staff_accessible_events(events: list, staff_class_id: str) -> list:
    """
    担当者がアクセスできるイベントのみをフィルタリングして返す。

    staff_class_id による行レベルアクセス制御（Row-Level Security）を実装する。
    管理者（ADMIN）は全イベントにアクセス可能。

    Args:
        events        : 全イベントのリスト（dataclass または dict）
        staff_class_id: 担当者のクラスID（例："3-A"）

    Returns:
        list: アクセス可能なイベントのリスト
    """
    current_role = get_current_role()

    if current_role == "ADMIN":
        return events  # 管理者は全イベントにアクセス可能

    if current_role == "STAFF":
        # 担当者は自分のクラスIDに対応するイベントのみアクセス可能
        accessible = []
        for event in events:
            # dataclass と dict の両方に対応
            event_class_id = (
                event.staff_class_id
                if hasattr(event, "staff_class_id")
                else event.get("staff_class_id", "")
            )
            if event_class_id == staff_class_id:
                accessible.append(event)
        return accessible

    return []  # VISITOR はアクセス不可


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 【設計ドキュメント】security.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ■ bcrypt採用理由
#   SHA-256は高速すぎるため、GPUによる総当たり攻撃が容易。
#   bcryptはコスト関数（ラウンド数）により計算時間を意図的に増加させ、
#   ブルートフォース攻撃のコストを指数関数的に増加させる。
#   rounds=4（デモ）→ rounds=12（本番推奨）に変更するだけで強度向上。
#
# ■ JWT採用理由
#   Streamlitはリクエストごとにサーバーサイドで再実行されるステートレス設計。
#   サーバー側にセッションDBを持つより、署名付きJWTで状態を検証する方が
#   スケーラブルかつシンプル。
#
# ■ セッション管理の制約
#   st.session_stateはサーバーメモリ上にのみ存在し、
#   ブラウザストレージ（localStorage/cookie）への書き込みは行わない。
#   これによりXSS攻撃でのセッション情報漏洩リスクを低減する。
#
# ■ 本番移行時の推奨手順
#   1. Supabase Auth SDKに差し替える（verify_pin関数を置換）
#   2. JWT_SECRET を st.secrets["JWT_SECRET"] で管理する
#   3. bcrypt rounds を 12 以上に設定する
#   4. MFA（TOTP）の追加を検討する
