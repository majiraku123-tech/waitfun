"""
FestivalFlow AI — core/validators.py
入力バリデーション・異常値検知エンジン

【脅威モデル】
    - DoS攻撃：極端な入力値でサーバーリソースを枯渇させる攻撃
    - データ改ざん：不正な値を入力してシステム状態を破壊する攻撃
    - XSS攻撃：スクリプトを含む文字列を入力してブラウザ上で実行させる攻撃

【設計方針】
    すべてのユーザー入力はこのモジュールを経由してバリデーションを受ける。
    バリデーション結果は ValidationResult dataclass で統一的に返す。
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 定数定義
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 行列人数の許容範囲（DoS対策）
QUEUE_LENGTH_MIN: int = 0
QUEUE_LENGTH_MAX: int = 500

# 急激な変化の閾値（前回比この人数以上の変化で警告フラグ）
ANOMALY_THRESHOLD_ABSOLUTE: int = 100
# 急激な変化の閾値（前回比この割合以上の変化で警告フラグ）
ANOMALY_THRESHOLD_RATIO: float = 3.0  # 3倍以上の変化

# 文化祭の開場・閉場時刻
FESTIVAL_OPEN_TIME: time = time(9, 0)   # 9:00
FESTIVAL_CLOSE_TIME: time = time(18, 0)  # 18:00

# イベント名の最大文字数
EVENT_NAME_MAX_LENGTH: int = 50

# PINの長さ要件
PIN_MIN_LENGTH: int = 4
PIN_MAX_LENGTH: int = 8


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# バリデーション結果データクラス
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class ValidationResult:
    """
    バリデーション実行結果を格納するデータクラス。

    Attributes:
        is_valid       : バリデーション通過ならTrue
        is_anomaly     : 異常値フラグ（管理者通知が必要な場合True）
        errors         : エラーメッセージのリスト
        warnings       : 警告メッセージのリスト（is_validはTrueだが注意が必要な場合）
        sanitized_value: サニタイズ済みの入力値（型変換・正規化済み）
    """
    is_valid: bool
    is_anomaly: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sanitized_value: Optional[object] = None

    @property
    def has_warnings(self) -> bool:
        """警告が存在するかどうかを返す。"""
        return len(self.warnings) > 0

    @property
    def error_message(self) -> str:
        """全エラーメッセージを改行で結合して返す。"""
        return "\n".join(self.errors)

    @property
    def warning_message(self) -> str:
        """全警告メッセージを改行で結合して返す。"""
        return "\n".join(self.warnings)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 行列人数バリデーション
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def validate_queue_input(
    value: object,
    current_value: int = 0,
    check_festival_hours: bool = True,
) -> ValidationResult:
    """
    行列人数入力の全バリデーションを実施する。

    【チェック項目】
        1. 型チェック（整数または整数に変換可能な値であること）
        2. 範囲チェック（0〜500：DoS攻撃・データ破壊対策）
        3. 急激な変化検知（前回比±100人以上で管理者警告フラグ）
        4. 営業時間内チェック（開場・閉場時刻との整合性）

    Args:
        value               : バリデーション対象の入力値
        current_value       : 現在の行列人数（前回値との比較に使用）
        check_festival_hours: 営業時間チェックを行うかどうか

    Returns:
        ValidationResult: バリデーション結果

    Examples:
        >>> result = validate_queue_input(30, current_value=25)
        >>> result.is_valid  # True
        >>> result = validate_queue_input(-1, current_value=25)
        >>> result.is_valid  # False
        >>> result.errors    # ["行列人数は0以上500以下の整数を入力してください"]
    """
    errors: list[str] = []
    warnings: list[str] = []
    is_anomaly = False
    sanitized_value = None

    # ── チェック1：型変換 ─────────────────────────────────────────
    try:
        int_value = int(value)
        sanitized_value = int_value
    except (TypeError, ValueError):
        return ValidationResult(
            is_valid=False,
            errors=["行列人数は整数で入力してください。"],
            sanitized_value=None,
        )

    # ── チェック2：範囲チェック ──────────────────────────────────
    # 【脅威】DoS攻撃：500人を超える入力でM/M/1計算を異常動作させる攻撃
    if int_value < QUEUE_LENGTH_MIN:
        errors.append(
            f"行列人数は{QUEUE_LENGTH_MIN}人以上を入力してください。"
            f"（入力値: {int_value}人）"
        )
    elif int_value > QUEUE_LENGTH_MAX:
        errors.append(
            f"行列人数は{QUEUE_LENGTH_MAX}人以下を入力してください。"
            f"（入力値: {int_value}人）\n"
            "DoS攻撃対策のため上限を設けています。"
        )

    if errors:
        return ValidationResult(
            is_valid=False,
            errors=errors,
            sanitized_value=None,
        )

    # ── チェック3：急激な変化検知 ────────────────────────────────
    # 【脅威】データ改ざん：意図的な大幅変化でシステム状態を破壊する攻撃
    absolute_change = abs(int_value - current_value)
    if current_value > 0:
        ratio_change = int_value / current_value if current_value > 0 else float("inf")
    else:
        ratio_change = 0.0

    if absolute_change >= ANOMALY_THRESHOLD_ABSOLUTE:
        is_anomaly = True
        warnings.append(
            f"⚠️ 前回比 ±{absolute_change}人 の大幅な変化です。\n"
            "管理者への確認通知が自動送信されます。"
        )
    elif current_value > 0 and ratio_change >= ANOMALY_THRESHOLD_RATIO:
        is_anomaly = True
        warnings.append(
            f"⚠️ 前回比 {ratio_change:.1f}倍 の急激な増加です。\n"
            "管理者への確認通知が自動送信されます。"
        )

    # ── チェック4：営業時間内チェック ───────────────────────────
    if check_festival_hours:
        current_time = datetime.now().time()
        if not (FESTIVAL_OPEN_TIME <= current_time <= FESTIVAL_CLOSE_TIME):
            warnings.append(
                f"⚠️ 現在は営業時間外（{FESTIVAL_OPEN_TIME.strftime('%H:%M')}〜"
                f"{FESTIVAL_CLOSE_TIME.strftime('%H:%M')}）です。\n"
                "この更新は記録されますが、来場者には表示されない場合があります。"
            )

    # 全チェック通過
    return ValidationResult(
        is_valid=True,
        is_anomaly=is_anomaly,
        errors=[],
        warnings=warnings,
        sanitized_value=int_value,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PIN バリデーション
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def validate_pin_input(pin: str) -> ValidationResult:
    """
    PIN入力のフォーマットバリデーションを実施する。

    【注意】このバリデーションは形式チェックのみ。
    実際の認証チェックは security.verify_pin() で行う。

    【チェック項目】
        1. 空文字列チェック
        2. 長さチェック（4〜8文字）
        3. 数字のみチェック（英字・記号混在を拒否）
        4. XSSチェック（スクリプトタグなどの危険文字列を拒否）

    Args:
        pin: 入力されたPIN文字列

    Returns:
        ValidationResult: バリデーション結果
    """
    errors: list[str] = []

    # ── チェック1：空チェック ────────────────────────────────────
    if not pin or not pin.strip():
        return ValidationResult(
            is_valid=False,
            errors=["PINを入力してください。"],
        )

    # ── チェック2：長さチェック ──────────────────────────────────
    if len(pin) < PIN_MIN_LENGTH or len(pin) > PIN_MAX_LENGTH:
        errors.append(
            f"PINは{PIN_MIN_LENGTH}〜{PIN_MAX_LENGTH}桁で入力してください。"
        )

    # ── チェック3：数字のみチェック ─────────────────────────────
    if not pin.isdigit():
        errors.append("PINは数字のみで入力してください。")

    # ── チェック4：XSSチェック ───────────────────────────────────
    # 【脅威】XSS攻撃：スクリプトタグを含む入力でブラウザ上でコードを実行させる攻撃
    dangerous_patterns = [
        r"<script", r"javascript:", r"on\w+\s*=", r"<iframe", r"<img",
        r"eval\(", r"document\.", r"window\.",
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, pin, re.IGNORECASE):
            return ValidationResult(
                is_valid=False,
                errors=["不正な入力が検出されました。"],
            )

    if errors:
        return ValidationResult(is_valid=False, errors=errors)

    return ValidationResult(
        is_valid=True,
        sanitized_value=pin.strip(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# テキスト入力バリデーション（XSSサニタイズ）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def sanitize_text_input(text: str, max_length: int = 100) -> str:
    """
    テキスト入力をサニタイズしてXSS攻撃を防ぐ。

    unsafe_allow_html=True でレンダリングする前に必ず呼び出すこと。

    【処理内容】
        1. 文字列の型変換
        2. 前後の空白除去
        3. HTMLエスケープ（<, >, &, ", ' を HTML エンティティに変換）
        4. 最大長のトランケート

    Args:
        text      : サニタイズ対象のテキスト
        max_length: 最大文字数（デフォルト100文字）

    Returns:
        str: サニタイズ済みテキスト
    """
    if not isinstance(text, str):
        text = str(text)

    # 前後の空白除去
    text = text.strip()

    # HTMLエスケープ（XSS対策）
    text = (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )

    # 最大長のトランケート
    if len(text) > max_length:
        text = text[:max_length] + "..."

    return text


def validate_service_time(value: object) -> ValidationResult:
    """
    平均サービス時間（分）の入力バリデーション。

    Args:
        value: バリデーション対象の値

    Returns:
        ValidationResult: バリデーション結果
    """
    try:
        float_value = float(value)
    except (TypeError, ValueError):
        return ValidationResult(
            is_valid=False,
            errors=["サービス時間は数値で入力してください。"],
        )

    if float_value <= 0:
        return ValidationResult(
            is_valid=False,
            errors=["サービス時間は0より大きい値を入力してください。"],
        )
    if float_value > 120:
        return ValidationResult(
            is_valid=False,
            errors=["サービス時間は120分以下を入力してください。"],
        )

    return ValidationResult(is_valid=True, sanitized_value=float_value)


def validate_capacity(value: object) -> ValidationResult:
    """
    窓口数（capacity）の入力バリデーション。

    Args:
        value: バリデーション対象の値

    Returns:
        ValidationResult: バリデーション結果
    """
    try:
        int_value = int(value)
    except (TypeError, ValueError):
        return ValidationResult(
            is_valid=False,
            errors=["窓口数は整数で入力してください。"],
        )

    if int_value < 1:
        return ValidationResult(
            is_valid=False,
            errors=["窓口数は1以上を入力してください。"],
        )
    if int_value > 20:
        return ValidationResult(
            is_valid=False,
            errors=["窓口数は20以下を入力してください。"],
        )

    return ValidationResult(is_valid=True, sanitized_value=int_value)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 【設計ドキュメント】validators.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ■ バリデーション設計原則
#   1. 全入力はこのモジュールを必ず経由する（単一責任）
#   2. ValidationResult で統一的な結果を返す（一貫性）
#   3. エラーと警告を分離する（is_valid=Trueでも警告は出せる）
#   4. サニタイズ済みの値を返す（型変換・正規化を呼び出し元が意識しなくてよい）
#
# ■ 異常値検知の閾値設定根拠
#   ±100人閾値：文化祭の平均的な人気イベントの収容人数（100〜200人）に基づく。
#   1分以内に100人変化することは物理的に困難なため、入力ミスまたは不正と判断。
#
# ■ XSS対策の方針
#   unsafe_allow_html=True でのレンダリング前には必ず sanitize_text_input() を通す。
#   ユーザー入力をHTMLとして扱う場合は、この関数でエスケープ処理を行う。
