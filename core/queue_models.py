"""
FestivalFlow AI — core/queue_models.py
M/M/1待ち行列理論エンジン

参考文献：
    Kleinrock, L. (1975). Queueing Systems Vol.1: Theory. Wiley-Interscience.
    Allen, A.O. (1990). Probability, Statistics, and Queueing Theory. Academic Press.

【採用モデルの根拠】
    M/M/1キューを採用した理由：
    - 文化祭来場者の到着間隔はポアソン過程に近似できる（ランダム・独立な到着）
    - アトラクション体験時間は指数分布に近似（短い体験もあれば長い体験もある）
    - 単一サーバー（1窓口）仮定が多くの出し物に合致する
    capacity引数によりM/M/cへの拡張も対応済み（飲食ブース等の複数カウンター）
"""

import math
from dataclasses import dataclass, field
from typing import Literal, Optional


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# データクラス定義
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 混雑ステータスの型エイリアス
CongestionStatus = Literal["LOW", "MODERATE", "HIGH", "CRITICAL", "SATURATED"]

# ステータスに対応するカラーコードマッピング（UIで使用）
STATUS_COLORS: dict[str, str] = {
    "LOW":       "#22C55E",   # Green-500：空いている
    "MODERATE":  "#EAB308",   # Yellow-500：やや混雑
    "HIGH":      "#F97316",   # Orange-500：混雑
    "CRITICAL":  "#EF4444",   # Red-500：危険レベル
    "SATURATED": "#7F1D1D",   # Red-900：飽和（待ち時間∞）
}

# ステータスに対応する日本語ラベル
STATUS_LABELS: dict[str, str] = {
    "LOW":       "空いています",
    "MODERATE":  "やや混雑",
    "HIGH":      "混雑中",
    "CRITICAL":  "かなり混雑",
    "SATURATED": "満員・入場制限中",
}

# ステータスに対応する絵文字
STATUS_EMOJI: dict[str, str] = {
    "LOW":       "🟢",
    "MODERATE":  "🟡",
    "HIGH":      "🟠",
    "CRITICAL":  "🔴",
    "SATURATED": "⛔",
}


@dataclass
class QueueMetrics:
    """
    M/M/1待ち行列モデルの計算結果を格納するデータクラス。

    Attributes:
        wait_minutes    : 推定待ち時間（分、切り上げ）
        utilization     : サーバー利用率ρ（0.0〜1.0以上）
        avg_queue_length: 平均キュー長Lq（行列内で待つ人数の期待値）
        avg_system_length: 平均システム内人数L（サービス中含む）
        status          : 混雑ステータス文字列
        throughput      : 実効スループット（人/分）
        arrival_rate    : 到着率λ（人/分）
        service_rate    : サービス率μ（人/分）
        color           : ステータスに対応するカラーコード
        label           : ステータスの日本語ラベル
        emoji           : ステータスの絵文字
    """
    wait_minutes: int
    utilization: float
    avg_queue_length: float
    avg_system_length: float
    status: CongestionStatus
    throughput: float
    arrival_rate: float
    service_rate: float
    color: str = field(init=False)
    label: str = field(init=False)
    emoji: str = field(init=False)

    def __post_init__(self) -> None:
        """ステータスから派生するフィールドを自動設定する。"""
        self.color = STATUS_COLORS[self.status]
        self.label = STATUS_LABELS[self.status]
        self.emoji = STATUS_EMOJI[self.status]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メイン計算関数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calculate_mm1_metrics(
    queue_length: int,
    avg_service_time: float,
    capacity: int = 1,
    time_window: float = 60.0,
) -> QueueMetrics:
    """
    M/M/1待ち行列モデルによる混雑指標を計算する。

    【数式定義】（Kleinrock, 1975 より）
        λ（到着率）    = queue_length / time_window       [人/分]
        μ（サービス率） = capacity / avg_service_time       [人/分]
        ρ（利用率）    = λ / μ                            [無次元、0≦ρ＜1 が安定条件]

        安定条件（ρ ＜ 1）が満たされる場合：
            Lq（平均キュー長）    = ρ² / (1 - ρ)          [人]
            L（平均システム内人数）= ρ / (1 - ρ)           [人]
            Wq（平均待ち時間）    = ρ / (μ × (1 - ρ))     [分]
            W（平均滞在時間）     = Wq + 1/μ              [分]

    【境界条件の処理】
        ρ ≧ 1.0  → SATURATED（待ち時間理論上∞。上限60分で打ち切り）
        ρ ≧ 0.9  → CRITICAL
        ρ ≧ 0.75 → HIGH
        ρ ≧ 0.5  → MODERATE
        ρ ＜ 0.5  → LOW

    Args:
        queue_length     : 現在の行列人数（人）
        avg_service_time : 平均サービス時間（分）
        capacity         : 並列サービス数（窓口数）。M/M/cへの拡張に使用。
        time_window      : 観測時間ウィンドウ（分）。デフォルト60分。

    Returns:
        QueueMetrics: 計算結果を格納したデータクラスインスタンス

    Raises:
        ValueError: avg_service_time または time_window が 0以下の場合
        ValueError: queue_length が負の場合
        ValueError: capacity が 1未満の場合

    Examples:
        >>> metrics = calculate_mm1_metrics(queue_length=30, avg_service_time=5.0)
        >>> print(metrics.wait_minutes)  # 推定待ち時間（分）
        >>> print(metrics.status)        # "MODERATE" など
    """
    # ── 入力値の検証 ───────────────────────────────────────────
    if avg_service_time <= 0:
        raise ValueError(f"avg_service_time は正の値が必要です。入力値: {avg_service_time}")
    if time_window <= 0:
        raise ValueError(f"time_window は正の値が必要です。入力値: {time_window}")
    if queue_length < 0:
        raise ValueError(f"queue_length は0以上が必要です。入力値: {queue_length}")
    if capacity < 1:
        raise ValueError(f"capacity は1以上が必要です。入力値: {capacity}")

    # ── 行列がない場合の早期返却 ────────────────────────────────
    if queue_length == 0:
        return QueueMetrics(
            wait_minutes=0,
            utilization=0.0,
            avg_queue_length=0.0,
            avg_system_length=0.0,
            status="LOW",
            throughput=0.0,
            arrival_rate=0.0,
            service_rate=float(capacity) / avg_service_time,
        )

    # ── 基本パラメータ計算 ──────────────────────────────────────
    # λ：到着率（人/分）
    # 観測時間ウィンドウ内に queue_length 人が到着したと仮定
    lambda_rate: float = queue_length / time_window

    # μ：サービス率（人/分）
    # capacity 個の窓口が各々 avg_service_time 分でサービスを完了
    mu_rate: float = float(capacity) / avg_service_time

    # ρ：サーバー利用率（トラフィック強度）
    # M/M/1では ρ = λ/μ、M/M/cでは ρ = λ/(c×μ) = λ/(μ_total)
    rho: float = lambda_rate / mu_rate

    # ── 飽和状態の処理（ρ ≧ 1.0）──────────────────────────────
    if rho >= 1.0:
        # 待ち行列が理論上∞に発散する状態
        # 実用上の上限として60分を設定（来場者への表示用）
        return QueueMetrics(
            wait_minutes=60,
            utilization=min(rho, 1.0),
            avg_queue_length=999.0,  # 実質的に∞
            avg_system_length=999.0,
            status="SATURATED",
            throughput=mu_rate,      # スループットはサービス率に制限される
            arrival_rate=lambda_rate,
            service_rate=mu_rate,
        )

    # ── M/M/1公式による待ち時間計算 ────────────────────────────
    # Lq = ρ² / (1 - ρ)  [平均キュー長（サービス中を除く行列内人数）]
    lq: float = (rho ** 2) / (1.0 - rho)

    # L = ρ / (1 - ρ)  [平均システム内人数（サービス中含む）]
    l_system: float = rho / (1.0 - rho)

    # Wq = Lq / λ = ρ / (μ(1-ρ))  [平均待ち時間（分）]
    # Little's Law: L = λW より導出
    wq: float = lq / lambda_rate  # = ρ / (mu_rate * (1 - rho))

    # 待ち時間を分単位の整数に切り上げ（来場者への表示用）
    wait_minutes: int = math.ceil(wq)

    # ── スループット計算 ────────────────────────────────────────
    # 安定状態では到着率 = 処理率（Little's Lawの前提）
    throughput: float = lambda_rate

    # ── ステータス判定 ──────────────────────────────────────────
    status: CongestionStatus = _determine_status(rho)

    return QueueMetrics(
        wait_minutes=wait_minutes,
        utilization=round(rho, 4),
        avg_queue_length=round(lq, 2),
        avg_system_length=round(l_system, 2),
        status=status,
        throughput=round(throughput, 4),
        arrival_rate=round(lambda_rate, 4),
        service_rate=round(mu_rate, 4),
    )


def _determine_status(rho: float) -> CongestionStatus:
    """
    利用率ρからステータスを判定する内部関数。

    Args:
        rho: サーバー利用率（0.0〜1.0+）

    Returns:
        CongestionStatus: 混雑ステータス文字列
    """
    if rho >= 1.0:
        return "SATURATED"
    elif rho >= 0.9:
        return "CRITICAL"
    elif rho >= 0.75:
        return "HIGH"
    elif rho >= 0.5:
        return "MODERATE"
    else:
        return "LOW"


def get_recommendation_reason(metrics: QueueMetrics) -> str:
    """
    M/M/1指標に基づいて「なぜ空いているか」の理由テキストを生成する。

    AI穴場推薦バナーで使用する説明文を自動生成する。

    Args:
        metrics: QueueMetrics インスタンス

    Returns:
        str: 理由を説明する日本語テキスト
    """
    rho = metrics.utilization

    if rho < 0.2:
        throughput_pct = round(rho * 100)
        return (
            f"サーバー稼働率がわずか{throughput_pct}%！"
            "今がチャンス。ほぼ待たずに楽しめます。"
        )
    elif rho < 0.35:
        return (
            f"利用率{round(rho * 100)}%で非常にスムーズ。"
            f"平均待ち時間は{metrics.wait_minutes}分以下です。"
        )
    else:
        return (
            f"比較的空いています（利用率{round(rho * 100)}%）。"
            f"推定待ち時間は約{metrics.wait_minutes}分です。"
        )


def calculate_trend(history_queue_lengths: list[int]) -> str:
    """
    直近5件の行列人数履歴から混雑トレンドを算出する。

    単純な移動平均差分でトレンド方向を判定する。

    Args:
        history_queue_lengths: 直近の行列人数リスト（時系列順、最大5件）

    Returns:
        str: "↑" (増加中) / "↓" (減少中) / "→" (安定)
    """
    if len(history_queue_lengths) < 2:
        return "→"

    # 直近2〜5件のデータを使用
    recent = history_queue_lengths[-5:]

    # 前半と後半の平均を比較してトレンドを判定
    mid = len(recent) // 2
    if mid == 0:
        # 2件の場合は単純比較
        diff = recent[-1] - recent[0]
    else:
        avg_early = sum(recent[:mid]) / mid
        avg_late = sum(recent[mid:]) / len(recent[mid:])
        diff = avg_late - avg_early

    # 変化率で判定（±10%以上を有意な変化とみなす）
    baseline = max(recent[0], 1)  # ゼロ除算防止
    change_rate = diff / baseline

    if change_rate > 0.1:
        return "↑"
    elif change_rate < -0.1:
        return "↓"
    else:
        return "→"


def simulate_scaled_metrics(
    queue_length: int,
    avg_service_time: float,
    scale_factor: float,
    capacity: int = 1,
) -> QueueMetrics:
    """
    来場者数スケールを変化させた場合のメトリクスをシミュレートする。

    管理者画面のシミュレーションパネルで使用する。
    来場者数が scale_factor 倍になった場合の待ち時間・利用率を予測する。

    Args:
        queue_length    : 現在の行列人数（人）
        avg_service_time: 平均サービス時間（分）
        scale_factor    : 来場者数のスケール係数（例：1.2 = 20%増）
        capacity        : 窓口数（デフォルト1）

    Returns:
        QueueMetrics: スケール後の予測メトリクス
    """
    scaled_queue = max(0, int(queue_length * scale_factor))
    return calculate_mm1_metrics(
        queue_length=scaled_queue,
        avg_service_time=avg_service_time,
        capacity=capacity,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 【設計ドキュメント】queue_models.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ■ 採用した数理モデルと根拠
#   M/M/1キューを採用した理由：
#   - 文化祭来場者の到着間隔はポアソン過程に近似できる（ランダム独立到着）
#   - サービス時間（アトラクション体験時間）は指数分布に近似
#   - 単一サーバー（1窓口）仮定が多くの出し物に合致
#   M/M/cへの拡張が必要なケース（飲食ブースの複数カウンター）は
#   capacity引数で対応できるよう設計済み
#
# ■ スケーラビリティ戦略
#   Phase 1（現在）：M/M/1モデルでリアルタイム推定
#   Phase 2：M/G/1モデルへ拡張（一般分布サービス時間対応）
#   Phase 3：LSTMによる時系列予測（過去データから30分後の混雑を予測）
#
# ■ 今後の改善ロードマップ
#   - Erlang-C公式（scipy.special.erlanc）による M/M/c 精密計算
#   - ピーク時間帯の非定常ポアソン過程（NHPP）への対応
#   - 強化学習による動的スタッフ配置最適化
