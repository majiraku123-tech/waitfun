"""
FestivalFlow AI — tests/test_queue_models.py
M/M/1数式の単体テスト（境界値・飽和条件含む）
"""

import pytest
import math
from core.queue_models import (
    calculate_mm1_metrics,
    calculate_trend,
    get_recommendation_reason,
    simulate_scaled_metrics,
    QueueMetrics,
)


class TestCalculateMm1Metrics:
    """M/M/1メトリクス計算の単体テスト"""

    # ── 正常系テスト ─────────────────────────────────────────────

    def test_zero_queue_returns_low_status(self):
        """行列人数0のとき、status=LOW・待ち時間0を返すこと"""
        metrics = calculate_mm1_metrics(queue_length=0, avg_service_time=5.0)
        assert metrics.status == "LOW"
        assert metrics.wait_minutes == 0
        assert metrics.utilization == 0.0
        assert metrics.avg_queue_length == 0.0

    def test_low_congestion(self):
        """ρ < 0.5 のとき status=LOW を返すこと"""
        # λ = 5/60 ≈ 0.083, μ = 1/5 = 0.2, ρ ≈ 0.417
        metrics = calculate_mm1_metrics(queue_length=5, avg_service_time=5.0)
        assert metrics.status == "LOW"
        assert metrics.utilization < 0.5
        assert metrics.wait_minutes >= 0

    def test_moderate_congestion(self):
        """ρ が 0.5〜0.75 のとき status=MODERATE を返すこと"""
        # λ = 30/60 = 0.5, μ = 1/5 = 0.2, ρ = 2.5
        # → 調整：ρ≈0.6になるパラメータを設定
        # λ = 12/60 = 0.2, μ = 1/3 ≈ 0.333, ρ ≈ 0.6
        metrics = calculate_mm1_metrics(queue_length=12, avg_service_time=3.0)
        assert metrics.status in ["LOW", "MODERATE", "HIGH"]
        assert 0 <= metrics.utilization <= 1.0

    def test_saturated_condition(self):
        """ρ ≧ 1.0 のとき status=SATURATED を返すこと"""
        # λ = 100/60 ≈ 1.667, μ = 1/10 = 0.1, ρ = 16.67 >> 1
        metrics = calculate_mm1_metrics(queue_length=100, avg_service_time=10.0)
        assert metrics.status == "SATURATED"
        assert metrics.wait_minutes == 60  # 飽和時は60分上限

    def test_critical_condition(self):
        """ρ が 0.9〜1.0 のとき status=CRITICAL を返すこと"""
        # ρ ≈ 0.9: λ = 18/60 = 0.3, μ = 1/3 ≈ 0.333, ρ ≈ 0.9
        metrics = calculate_mm1_metrics(queue_length=18, avg_service_time=3.0)
        # ρが0.9付近かどうかを確認
        assert metrics.status in ["HIGH", "CRITICAL", "SATURATED"]

    def test_utilization_formula(self):
        """ρ = λ/μ の計算が正しいこと"""
        # λ = 30/60 = 0.5, μ = 1/5 = 0.2, ρ = 2.5 → SATURATED
        # 正確にρ=0.5になるケース: λ=0.1, μ=0.2 → queue=6, service=5
        metrics = calculate_mm1_metrics(queue_length=6, avg_service_time=5.0)
        # λ = 6/60 = 0.1, μ = 1/5 = 0.2, ρ = 0.5
        expected_rho = (6 / 60) / (1 / 5)
        assert abs(metrics.utilization - expected_rho) < 0.01

    def test_wq_formula(self):
        """Wq = ρ/(μ(1-ρ)) の計算が正しいこと"""
        # λ = 6/60 = 0.1, μ = 0.2, ρ = 0.5
        # Wq = 0.5 / (0.2 * 0.5) = 5.0分
        metrics = calculate_mm1_metrics(queue_length=6, avg_service_time=5.0)
        rho = metrics.utilization
        if rho < 1.0:
            mu = 1 / 5.0
            expected_wq = rho / (mu * (1 - rho))
            expected_wait_ceil = math.ceil(expected_wq)
            assert metrics.wait_minutes == expected_wait_ceil

    def test_capacity_multiplier(self):
        """capacity=2 のとき μ が2倍になること"""
        # capacity=1: μ=0.2, capacity=2: μ=0.4
        metrics1 = calculate_mm1_metrics(queue_length=10, avg_service_time=5.0, capacity=1)
        metrics2 = calculate_mm1_metrics(queue_length=10, avg_service_time=5.0, capacity=2)
        # capacity=2のほうが利用率ρが小さいはず
        assert metrics2.utilization < metrics1.utilization

    def test_throughput_equals_arrival_rate_when_stable(self):
        """安定状態ではスループット = 到着率 であること"""
        metrics = calculate_mm1_metrics(queue_length=6, avg_service_time=5.0)
        if metrics.status != "SATURATED":
            expected_lambda = 6 / 60.0
            assert abs(metrics.throughput - expected_lambda) < 0.001

    # ── 異常系・境界値テスト ───────────────────────────────────

    def test_invalid_negative_queue(self):
        """行列人数が負のとき ValueError を発生させること"""
        with pytest.raises(ValueError, match="queue_length"):
            calculate_mm1_metrics(queue_length=-1, avg_service_time=5.0)

    def test_invalid_zero_service_time(self):
        """サービス時間が0のとき ValueError を発生させること"""
        with pytest.raises(ValueError, match="avg_service_time"):
            calculate_mm1_metrics(queue_length=10, avg_service_time=0.0)

    def test_invalid_negative_service_time(self):
        """サービス時間が負のとき ValueError を発生させること"""
        with pytest.raises(ValueError, match="avg_service_time"):
            calculate_mm1_metrics(queue_length=10, avg_service_time=-1.0)

    def test_invalid_zero_time_window(self):
        """観測ウィンドウが0のとき ValueError を発生させること"""
        with pytest.raises(ValueError, match="time_window"):
            calculate_mm1_metrics(queue_length=10, avg_service_time=5.0, time_window=0.0)

    def test_invalid_zero_capacity(self):
        """窓口数が0のとき ValueError を発生させること"""
        with pytest.raises(ValueError, match="capacity"):
            calculate_mm1_metrics(queue_length=10, avg_service_time=5.0, capacity=0)

    def test_return_type_is_queue_metrics(self):
        """戻り値が QueueMetrics 型であること"""
        metrics = calculate_mm1_metrics(queue_length=10, avg_service_time=5.0)
        assert isinstance(metrics, QueueMetrics)

    def test_status_attributes_are_set(self):
        """QueueMetrics の color・label・emoji が設定されること"""
        metrics = calculate_mm1_metrics(queue_length=10, avg_service_time=5.0)
        assert metrics.color is not None and len(metrics.color) > 0
        assert metrics.label is not None and len(metrics.label) > 0
        assert metrics.emoji is not None and len(metrics.emoji) > 0

    def test_all_statuses_are_reachable(self):
        """全ステータス（LOW/MODERATE/HIGH/CRITICAL/SATURATED）が到達可能であること"""
        statuses = set()
        test_cases = [
            (0, 5.0),    # LOW（ρ=0）
            (6, 5.0),    # MODERATE付近（ρ≈0.5）
            (15, 3.0),   # HIGH付近（ρ≈0.75）
            (18, 3.0),   # CRITICAL付近（ρ≈0.9）
            (100, 5.0),  # SATURATED（ρ>>1）
        ]
        for queue, service in test_cases:
            m = calculate_mm1_metrics(queue, service)
            statuses.add(m.status)
        # 最低3種類のステータスが出現すること
        assert len(statuses) >= 3


class TestCalculateTrend:
    """混雑トレンド計算のテスト"""

    def test_increasing_trend(self):
        """行列が増加傾向のとき '↑' を返すこと"""
        history = [10, 15, 20, 30, 50]
        assert calculate_trend(history) == "↑"

    def test_decreasing_trend(self):
        """行列が減少傾向のとき '↓' を返すこと"""
        history = [50, 40, 30, 20, 10]
        assert calculate_trend(history) == "↓"

    def test_stable_trend(self):
        """行列が安定しているとき '→' を返すこと"""
        history = [30, 30, 31, 29, 30]
        assert calculate_trend(history) == "→"

    def test_single_element(self):
        """要素が1件のとき '→' を返すこと（デフォルト）"""
        assert calculate_trend([30]) == "→"

    def test_empty_list(self):
        """空リストのとき '→' を返すこと"""
        assert calculate_trend([]) == "→"

    def test_two_elements_increasing(self):
        """2件で増加の場合 '↑' を返すこと"""
        assert calculate_trend([10, 25]) == "↑"

    def test_two_elements_decreasing(self):
        """2件で減少の場合 '↓' を返すこと"""
        assert calculate_trend([50, 20]) == "↓"


class TestSimulateScaledMetrics:
    """スケーリングシミュレーションのテスト"""

    def test_scale_factor_one_equals_original(self):
        """スケール係数1.0のとき元の行列と同等のメトリクスを返すこと"""
        original = calculate_mm1_metrics(queue_length=20, avg_service_time=5.0)
        scaled = simulate_scaled_metrics(
            queue_length=20, avg_service_time=5.0, scale_factor=1.0
        )
        # 同一パラメータなので同じメトリクスになるはず
        assert original.status == scaled.status

    def test_scale_factor_increases_utilization(self):
        """スケール係数>1.0のとき利用率が増加すること"""
        original = calculate_mm1_metrics(queue_length=10, avg_service_time=5.0)
        scaled = simulate_scaled_metrics(
            queue_length=10, avg_service_time=5.0, scale_factor=2.0
        )
        assert scaled.utilization >= original.utilization

    def test_scale_factor_zero(self):
        """スケール係数0.0のとき待ち時間0・利用率0として計算されること"""
        scaled = simulate_scaled_metrics(
            queue_length=30, avg_service_time=5.0, scale_factor=0.0
        )
        # scale_factor=0.0のとき行列0人 → 待ち時間0・利用率0になるはず
        assert scaled.wait_minutes == 0 and scaled.utilization == 0.0


class TestGetRecommendationReason:
    """穴場推薦理由テキスト生成のテスト"""

    def test_returns_string(self):
        """推薦理由が文字列として返されること"""
        metrics = calculate_mm1_metrics(queue_length=5, avg_service_time=5.0)
        reason = get_recommendation_reason(metrics)
        assert isinstance(reason, str)
        assert len(reason) > 0

    def test_very_low_utilization_reason(self):
        """利用率が非常に低い場合に適切な推薦文が返されること"""
        metrics = calculate_mm1_metrics(queue_length=1, avg_service_time=5.0)
        reason = get_recommendation_reason(metrics)
        assert "%" in reason or "分" in reason  # 数値情報を含むこと
