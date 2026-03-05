"""
FestivalFlow AI — tests/test_validators.py
バリデーションロジックの網羅的テスト
"""

import pytest
from core.validators import (
    validate_queue_input,
    validate_pin_input,
    sanitize_text_input,
    validate_service_time,
    validate_capacity,
    ValidationResult,
    QUEUE_LENGTH_MAX,
    QUEUE_LENGTH_MIN,
    ANOMALY_THRESHOLD_ABSOLUTE,
)


class TestValidateQueueInput:
    """行列人数バリデーションのテスト"""

    # ── 正常系 ───────────────────────────────────────────────────

    def test_valid_zero(self):
        """0人は有効な入力であること"""
        result = validate_queue_input(0, current_value=10)
        assert result.is_valid is True
        assert result.sanitized_value == 0

    def test_valid_typical(self):
        """一般的な値（30人）は有効であること"""
        result = validate_queue_input(30, current_value=25)
        assert result.is_valid is True
        assert result.sanitized_value == 30

    def test_valid_max(self):
        """最大値（500人）は有効であること"""
        result = validate_queue_input(QUEUE_LENGTH_MAX, current_value=0)
        assert result.is_valid is True
        assert result.sanitized_value == QUEUE_LENGTH_MAX

    def test_string_integer_is_accepted(self):
        """文字列として渡された整数は正常に型変換されること"""
        result = validate_queue_input("50", current_value=40)
        assert result.is_valid is True
        assert result.sanitized_value == 50

    def test_float_is_truncated(self):
        """小数は整数に変換されること"""
        result = validate_queue_input(10.9, current_value=5)
        assert result.is_valid is True
        assert result.sanitized_value == 10

    # ── 異常系 ───────────────────────────────────────────────────

    def test_negative_value_is_invalid(self):
        """負の値は無効であること"""
        result = validate_queue_input(-1, current_value=10)
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_over_max_is_invalid(self):
        """最大値超過（501人）は無効であること"""
        result = validate_queue_input(QUEUE_LENGTH_MAX + 1, current_value=10)
        assert result.is_valid is False

    def test_string_non_integer_is_invalid(self):
        """整数以外の文字列は無効であること"""
        result = validate_queue_input("abc", current_value=10)
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_none_is_invalid(self):
        """Noneは無効であること"""
        result = validate_queue_input(None, current_value=10)
        assert result.is_valid is False

    # ── 異常値検知テスト ─────────────────────────────────────────

    def test_anomaly_flag_on_large_increase(self):
        """前回比+100人以上で異常値フラグが立つこと"""
        result = validate_queue_input(
            ANOMALY_THRESHOLD_ABSOLUTE + 1, current_value=0
        )
        assert result.is_valid is True
        assert result.is_anomaly is True
        assert len(result.warnings) > 0

    def test_anomaly_flag_on_large_decrease(self):
        """前回比-100人以上で異常値フラグが立つこと"""
        result = validate_queue_input(
            0, current_value=ANOMALY_THRESHOLD_ABSOLUTE + 1
        )
        assert result.is_valid is True
        assert result.is_anomaly is True

    def test_no_anomaly_on_small_change(self):
        """前回比±10人程度では異常値フラグが立たないこと"""
        result = validate_queue_input(30, current_value=25)
        assert result.is_valid is True
        assert result.is_anomaly is False

    def test_anomaly_exact_threshold(self):
        """±99人は異常値フラグが立たないこと（境界値テスト）"""
        result = validate_queue_input(
            ANOMALY_THRESHOLD_ABSOLUTE - 1, current_value=0
        )
        # 99人増加は閾値以下なのでフラグなし
        assert result.is_anomaly is False

    # ── ValidationResult の検証 ──────────────────────────────────

    def test_return_type_is_validation_result(self):
        """戻り値が ValidationResult 型であること"""
        result = validate_queue_input(10, current_value=5)
        assert isinstance(result, ValidationResult)

    def test_valid_result_has_no_errors(self):
        """有効な入力のとき errors リストが空であること"""
        result = validate_queue_input(10, current_value=5)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_invalid_result_sanitized_value_is_none(self):
        """無効な入力のとき sanitized_value が None であること"""
        result = validate_queue_input("invalid", current_value=5)
        assert result.is_valid is False
        assert result.sanitized_value is None


class TestValidatePinInput:
    """PINバリデーションのテスト"""

    def test_valid_four_digits(self):
        """4桁の数字PINは有効であること"""
        result = validate_pin_input("1234")
        assert result.is_valid is True
        assert result.sanitized_value == "1234"

    def test_valid_eight_digits(self):
        """8桁の数字PINは有効であること"""
        result = validate_pin_input("12345678")
        assert result.is_valid is True

    def test_empty_pin_is_invalid(self):
        """空文字列のPINは無効であること"""
        result = validate_pin_input("")
        assert result.is_valid is False

    def test_too_short_pin_is_invalid(self):
        """3桁以下のPINは無効であること"""
        result = validate_pin_input("123")
        assert result.is_valid is False

    def test_too_long_pin_is_invalid(self):
        """9桁以上のPINは無効であること"""
        result = validate_pin_input("123456789")
        assert result.is_valid is False

    def test_non_digit_pin_is_invalid(self):
        """数字以外を含むPINは無効であること"""
        result = validate_pin_input("12ab")
        assert result.is_valid is False

    def test_xss_script_is_invalid(self):
        """スクリプトタグを含む入力は無効であること（XSS対策）"""
        result = validate_pin_input("<script>alert('xss')</script>")
        assert result.is_valid is False

    def test_none_pin_is_invalid(self):
        """Noneは無効であること"""
        result = validate_pin_input(None)
        assert result.is_valid is False


class TestSanitizeTextInput:
    """テキストサニタイズのテスト"""

    def test_normal_text_unchanged(self):
        """通常の日本語テキストはそのまま返されること"""
        result = sanitize_text_input("お化け屋敷")
        assert "お化け屋敷" in result

    def test_html_tags_are_escaped(self):
        """HTMLタグがエスケープされること"""
        result = sanitize_text_input("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_ampersand_is_escaped(self):
        """& がエスケープされること"""
        result = sanitize_text_input("A&B")
        assert "&amp;" in result

    def test_max_length_truncation(self):
        """最大長を超えるテキストは切り詰められること"""
        long_text = "あ" * 200
        result = sanitize_text_input(long_text, max_length=50)
        assert len(result) <= 55  # "..." を考慮

    def test_whitespace_stripped(self):
        """前後の空白は除去されること"""
        result = sanitize_text_input("  テスト  ")
        assert result == "テスト"

    def test_non_string_is_converted(self):
        """文字列以外の入力は文字列に変換されること"""
        result = sanitize_text_input(123)
        assert isinstance(result, str)
        assert "123" in result


class TestValidateServiceTime:
    """サービス時間バリデーションのテスト"""

    def test_valid_service_time(self):
        """有効なサービス時間（5.0分）が受け入れられること"""
        result = validate_service_time(5.0)
        assert result.is_valid is True
        assert result.sanitized_value == 5.0

    def test_zero_service_time_is_invalid(self):
        """サービス時間0は無効であること"""
        result = validate_service_time(0)
        assert result.is_valid is False

    def test_negative_service_time_is_invalid(self):
        """負のサービス時間は無効であること"""
        result = validate_service_time(-1.0)
        assert result.is_valid is False

    def test_over_max_service_time_is_invalid(self):
        """120分超のサービス時間は無効であること"""
        result = validate_service_time(121)
        assert result.is_valid is False

    def test_string_float_is_accepted(self):
        """文字列の小数が受け入れられること"""
        result = validate_service_time("3.5")
        assert result.is_valid is True
        assert result.sanitized_value == 3.5


class TestValidateCapacity:
    """窓口数バリデーションのテスト"""

    def test_valid_single_capacity(self):
        """窓口数1は有効であること"""
        result = validate_capacity(1)
        assert result.is_valid is True

    def test_valid_multiple_capacity(self):
        """窓口数5は有効であること"""
        result = validate_capacity(5)
        assert result.is_valid is True
        assert result.sanitized_value == 5

    def test_zero_capacity_is_invalid(self):
        """窓口数0は無効であること"""
        result = validate_capacity(0)
        assert result.is_valid is False

    def test_over_max_capacity_is_invalid(self):
        """窓口数21以上は無効であること"""
        result = validate_capacity(21)
        assert result.is_valid is False
