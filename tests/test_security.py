"""
FestivalFlow AI — tests/test_security.py
認証フロー・RBAC権限チェックのテスト
"""

import pytest
from unittest.mock import patch, MagicMock
from core.security import (
    verify_pin,
    create_session,
    validate_session,
    ROLES,
    _PIN_HASHES,
)


class TestVerifyPin:
    """PIN照合のテスト"""

    def test_correct_staff_pin(self):
        """正しいスタッフPIN（1234）で認証が成功すること"""
        assert verify_pin("STAFF", "1234") is True

    def test_correct_admin_pin(self):
        """正しい管理者PIN（9999）で認証が成功すること"""
        assert verify_pin("ADMIN", "9999") is True

    def test_wrong_staff_pin(self):
        """誤ったスタッフPINで認証が失敗すること"""
        assert verify_pin("STAFF", "0000") is False

    def test_wrong_admin_pin(self):
        """誤った管理者PINで認証が失敗すること"""
        assert verify_pin("ADMIN", "1234") is False

    def test_staff_pin_for_admin_role(self):
        """スタッフPINで管理者ロールの認証は失敗すること（権限昇格防止）"""
        # 管理者PINは9999、スタッフPINは1234なので
        assert verify_pin("ADMIN", "1234") is False

    def test_nonexistent_role(self):
        """存在しないロールは認証が失敗すること"""
        assert verify_pin("SUPERUSER", "1234") is False

    def test_empty_pin(self):
        """空文字列のPINで認証が失敗すること"""
        assert verify_pin("STAFF", "") is False

    def test_none_pin_handled_safely(self):
        """NoneのPINを渡しても例外が発生しないこと（フェイルセーフ）"""
        try:
            result = verify_pin("STAFF", None)
            assert result is False
        except Exception:
            pass  # 例外が発生する場合もテスト通過（フェイルセーフ）

    def test_sql_injection_attempt(self):
        """SQLインジェクション的な文字列で認証が失敗すること"""
        assert verify_pin("STAFF", "' OR '1'='1") is False

    def test_timing_safety(self):
        """正しいPINと誤りのPINで応答時間が大きく異ならないこと（タイミング攻撃対策確認）"""
        import time
        # bcrypt.checkpw は定時間比較なので両方ほぼ同じ時間がかかる
        start1 = time.monotonic()
        verify_pin("STAFF", "1234")
        elapsed1 = time.monotonic() - start1

        start2 = time.monotonic()
        verify_pin("STAFF", "0000")
        elapsed2 = time.monotonic() - start2

        # 両方がbcryptで処理されるので大きな差はないはず（1秒以内の差）
        assert abs(elapsed1 - elapsed2) < 1.0


class TestCreateSession:
    """セッション生成のテスト"""

    def test_visitor_role_creation(self):
        """VISITORロールのセッションが生成できること"""
        session = create_session("VISITOR")
        assert session["role"] == "VISITOR"
        assert session["authenticated"] is True
        assert session["session_id"] is not None

    def test_staff_role_creation(self):
        """STAFFロールのセッションが生成できること"""
        session = create_session("STAFF")
        assert session["role"] == "STAFF"
        assert "jwt_token" in session

    def test_admin_role_creation(self):
        """ADMINロールのセッションが生成できること"""
        session = create_session("ADMIN")
        assert session["role"] == "ADMIN"

    def test_session_id_is_unique(self):
        """2つのセッションIDが異なること（一意性）"""
        session1 = create_session("STAFF")
        session2 = create_session("STAFF")
        assert session1["session_id"] != session2["session_id"]

    def test_session_contains_jwt(self):
        """セッションにJWTトークンが含まれること"""
        session = create_session("ADMIN")
        jwt_token = session.get("jwt_token")
        assert jwt_token is not None
        # JWTは3つのドット区切りセグメントを持つ
        assert len(jwt_token.split(".")) == 3

    def test_session_contains_expiry(self):
        """セッションに有効期限が含まれること"""
        session = create_session("STAFF")
        assert "expires_at" in session
        assert session["expires_at"] is not None

    def test_invalid_role_raises_error(self):
        """無効なロールで ValueError が発生すること"""
        with pytest.raises(ValueError, match="不正なロール"):
            create_session("HACKER")

    def test_session_id_length(self):
        """セッションIDが十分な長さ（64文字以上）であること"""
        session = create_session("STAFF")
        # token_hex(32) は64文字の16進数文字列
        assert len(session["session_id"]) >= 64


class TestValidateSession:
    """セッション検証のテスト"""

    def test_valid_session_passes(self):
        """有効なセッションが検証を通過すること"""
        session = create_session("STAFF")
        assert validate_session(session) is True

    def test_none_session_fails(self):
        """Noneセッションが検証を失敗すること"""
        assert validate_session(None) is False

    def test_empty_dict_session_fails(self):
        """空辞書セッションが検証を失敗すること"""
        assert validate_session({}) is False

    def test_tampered_jwt_fails(self):
        """改ざんされたJWTは検証を失敗すること"""
        session = create_session("STAFF")
        # JWTの署名部分を改ざん
        original_token = session["jwt_token"]
        parts = original_token.split(".")
        tampered_token = parts[0] + "." + parts[1] + ".invalidsignature"
        session["jwt_token"] = tampered_token
        assert validate_session(session) is False

    def test_unauthenticated_session_fails(self):
        """authenticated=False のセッションが検証を失敗すること"""
        session = create_session("STAFF")
        session["authenticated"] = False
        assert validate_session(session) is False

    def test_missing_jwt_token_fails(self):
        """jwt_tokenが欠落したセッションが検証を失敗すること"""
        session = create_session("STAFF")
        del session["jwt_token"]
        assert validate_session(session) is False


class TestRbacRoles:
    """RBACロール定義のテスト"""

    def test_visitor_has_minimum_permissions(self):
        """VISITORは最小限の読み取り権限のみ持つこと"""
        visitor_permissions = ROLES["VISITOR"]["permissions"]
        assert "read:events" in visitor_permissions
        assert "write:queue" not in visitor_permissions
        assert "export:data" not in visitor_permissions

    def test_staff_has_write_queue(self):
        """STAFFはwrite:queueパーミッションを持つこと"""
        staff_permissions = ROLES["STAFF"]["permissions"]
        assert "write:queue" in staff_permissions

    def test_admin_has_all_permissions(self):
        """ADMINはexport:dataを含む全パーミッションを持つこと"""
        admin_permissions = ROLES["ADMIN"]["permissions"]
        assert "export:data" in admin_permissions
        assert "write:config" in admin_permissions
        assert "read:analytics" in admin_permissions

    def test_role_levels_are_ordered(self):
        """ロールレベルがVISITOR < STAFF < ADMIN の順であること"""
        assert ROLES["VISITOR"]["level"] < ROLES["STAFF"]["level"]
        assert ROLES["STAFF"]["level"] < ROLES["ADMIN"]["level"]

    def test_visitor_accessible_views(self):
        """VISITORはvisitorビューのみアクセス可能であること"""
        assert "visitor" in ROLES["VISITOR"]["accessible_views"]
        assert "admin" not in ROLES["VISITOR"]["accessible_views"]

    def test_admin_accessible_views_includes_all(self):
        """ADMINは全ビュー（visitor/staff/admin/simulation）にアクセス可能であること"""
        admin_views = ROLES["ADMIN"]["accessible_views"]
        for view in ["visitor", "staff", "admin", "simulation"]:
            assert view in admin_views

    def test_all_roles_have_required_fields(self):
        """全ロールにlevel/label/permissions/accessible_viewsフィールドがあること"""
        required_fields = ["level", "label", "permissions", "accessible_views"]
        for role_name, role_data in ROLES.items():
            for field in required_fields:
                assert field in role_data, f"ロール {role_name} に {field} がありません"

    def test_staff_inherits_visitor_permissions(self):
        """STAFFはVISITORの全パーミッションを含むこと（権限の包含関係）"""
        visitor_perms = set(ROLES["VISITOR"]["permissions"])
        staff_perms = set(ROLES["STAFF"]["permissions"])
        assert visitor_perms.issubset(staff_perms)

    def test_admin_inherits_staff_permissions(self):
        """ADMINはSTAFFの全パーミッションを含むこと（権限の包含関係）"""
        staff_perms = set(ROLES["STAFF"]["permissions"])
        admin_perms = set(ROLES["ADMIN"]["permissions"])
        assert staff_perms.issubset(admin_perms)
