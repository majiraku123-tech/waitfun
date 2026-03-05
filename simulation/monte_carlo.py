"""
FestivalFlow AI — simulation/monte_carlo.py
モンテカルロ法 × 感度分析 × シナリオ比較

M/M/1モデルのパラメータ不確実性をモンテカルロシミュレーションで評価する。
来場者数の変動シナリオに対する待ち時間・利用率の信頼区間を計算する。
"""

import numpy as np
import streamlit as st
import plotly.graph_objects as go
from dataclasses import dataclass
from core.data_manager import Event
from core.queue_models import calculate_mm1_metrics, QueueMetrics


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# シミュレーション結果データクラス
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SimulationResult:
    """
    モンテカルロシミュレーションの結果を格納するデータクラス。

    Attributes:
        event_id         : シミュレーション対象イベントのID
        event_name       : イベント名
        scale_factor     : 来場者数スケール係数
        n_trials         : シミュレーション試行回数
        mean_wait_minutes: 平均待ち時間（分）
        ci_lower_95      : 95%信頼区間の下限（分）
        ci_upper_95      : 95%信頼区間の上限（分）
        mean_utilization : 平均利用率ρ
        prob_critical    : CRITICAL状態になる確率（%）
        prob_saturated   : SATURATED状態になる確率（%）
        wait_distribution: 待ち時間の分布（全試行結果）
    """
    event_id: str
    event_name: str
    scale_factor: float
    n_trials: int
    mean_wait_minutes: float
    ci_lower_95: float
    ci_upper_95: float
    mean_utilization: float
    prob_critical: float
    prob_saturated: float
    wait_distribution: np.ndarray


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# モンテカルロシミュレーション
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_monte_carlo_simulation(
    events: list[Event],
    scale_factor: float = 1.0,
    n_trials: int = 1000,
    noise_std: float = 0.15,
) -> list[SimulationResult]:
    """
    全イベントに対してモンテカルロシミュレーションを実行する。

    【シミュレーション手法】
        1. 各試行で来場者数に正規分布のノイズを加える
        2. M/M/1モデルで待ち時間・利用率を計算
        3. n_trials回の繰り返しから統計量（平均・信頼区間・確率）を算出

    【確率的モデル】
        scaled_queue ~ Normal(μ = base_queue × scale_factor, σ = μ × noise_std)
        ノイズは実際の来場者数の予測誤差を模擬する（±15%の標準偏差）。

    Args:
        events      : シミュレーション対象のイベントリスト
        scale_factor: 来場者数のスケール係数（1.0 = 現状維持）
        n_trials    : モンテカルロ試行回数（デフォルト1000回）
        noise_std   : 来場者数のノイズ標準偏差（デフォルト15%）

    Returns:
        list[SimulationResult]: 各イベントのシミュレーション結果リスト
    """
    np.random.seed(42)  # 再現性確保のためシードを固定
    results = []

    for event in events:
        if not event.is_open:
            continue

        # ベースとなる来場者数（スケール適用後）
        base_queue = max(1, event.queue_length * scale_factor)

        # モンテカルロ試行
        wait_times = np.zeros(n_trials)
        utilizations = np.zeros(n_trials)
        statuses = []

        for i in range(n_trials):
            # 正規分布のノイズを加えた来場者数
            noisy_queue = max(0, np.random.normal(base_queue, base_queue * noise_std))
            noisy_queue = min(500, int(round(noisy_queue)))  # 上限クリップ

            metrics = calculate_mm1_metrics(
                queue_length=noisy_queue,
                avg_service_time=event.avg_service_time,
                capacity=event.capacity,
            )
            wait_times[i] = metrics.wait_minutes
            utilizations[i] = metrics.utilization
            statuses.append(metrics.status)

        # 統計量の計算
        mean_wait = float(np.mean(wait_times))
        ci_lower = float(np.percentile(wait_times, 2.5))   # 95%信頼区間の下限
        ci_upper = float(np.percentile(wait_times, 97.5))  # 95%信頼区間の上限
        mean_util = float(np.mean(utilizations))

        # 危険状態の確率
        prob_critical = sum(1 for s in statuses if s in ["CRITICAL", "SATURATED"]) / n_trials * 100
        prob_saturated = sum(1 for s in statuses if s == "SATURATED") / n_trials * 100

        results.append(SimulationResult(
            event_id=event.id,
            event_name=event.name,
            scale_factor=scale_factor,
            n_trials=n_trials,
            mean_wait_minutes=round(mean_wait, 1),
            ci_lower_95=round(ci_lower, 1),
            ci_upper_95=round(ci_upper, 1),
            mean_utilization=round(mean_util, 4),
            prob_critical=round(prob_critical, 1),
            prob_saturated=round(prob_saturated, 1),
            wait_distribution=wait_times,
        ))

    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# シミュレーション UI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def render_simulation_panel(events: list[Event]) -> None:
    """
    管理者画面のシミュレーションパネルを描画する。

    スライダーで来場者数スケールを設定し、
    モンテカルロ法による予測結果をリアルタイムで表示する。

    Args:
        events: シミュレーション対象のイベントリスト
    """
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1E3A5F,#0EA5E9);
                border-radius:16px;padding:20px 24px;margin-bottom:24px;color:white;">
        <div style="font-size:20px;font-weight:800;">🔮 シナリオシミュレーター</div>
        <div style="font-size:13px;opacity:0.9;margin-top:4px;">
            モンテカルロ法（1000試行）× M/M/1待ち行列理論による将来予測
        </div>
    </div>
    """, unsafe_allow_html=True)

    # シミュレーション設定
    col1, col2 = st.columns([2, 1])

    with col1:
        scale_pct = st.slider(
            "📈 来場者数の変動率",
            min_value=-50,
            max_value=200,
            value=int((st.session_state.get("simulation_scale", 1.0) - 1.0) * 100),
            step=10,
            format="%d%%",
            help="現在の来場者数からの増減率を設定します。0%=現状維持、100%=2倍。",
        )

    with col2:
        n_trials = st.selectbox(
            "試行回数",
            options=[100, 500, 1000, 5000],
            index=2,
            help="試行回数が多いほど精度が上がりますが計算時間が増加します。",
        )

    scale_factor = 1.0 + scale_pct / 100.0
    st.session_state["simulation_scale"] = scale_factor

    # スケール表示
    if scale_factor > 1.0:
        st.info(f"📊 来場者数 **{scale_pct:+d}%** のシナリオで計算中（現在の{scale_factor:.1f}倍）")
    elif scale_factor < 1.0:
        st.success(f"📊 来場者数 **{scale_pct:+d}%** のシナリオで計算中（現在の{scale_factor:.1f}倍）")
    else:
        st.info("📊 現状維持シナリオで計算中")

    # シミュレーション実行ボタン
    if st.button("🚀 シミュレーション実行", type="primary", use_container_width=True):
        with st.spinner(f"モンテカルロシミュレーション実行中（{n_trials}試行）..."):
            results = run_monte_carlo_simulation(
                events=events,
                scale_factor=scale_factor,
                n_trials=n_trials,
            )
        st.session_state["simulation_results"] = results
        st.success(f"✅ シミュレーション完了！{len(results)}件のイベントを{n_trials}回試行しました。")

    # 結果の表示
    results = st.session_state.get("simulation_results")
    if results:
        _render_simulation_results(results, events)


def _render_simulation_results(results: list[SimulationResult], events: list[Event]) -> None:
    """
    シミュレーション結果を表形式とグラフで表示する。

    Args:
        results: SimulationResult のリスト
        events : 元のイベントリスト（現在値との比較用）
    """
    import pandas as pd

    # イベントIDから現在の待ち時間を取得するマップ
    current_metrics = {e.id: e.get_metrics() for e in events}

    # 結果テーブル
    st.markdown("#### 📋 シミュレーション結果サマリー")
    table_data = []
    for result in results:
        current = current_metrics.get(result.event_id)
        current_wait = current.wait_minutes if current else 0
        delta_wait = result.mean_wait_minutes - current_wait
        delta_str = f"+{delta_wait:.1f}" if delta_wait > 0 else f"{delta_wait:.1f}"

        table_data.append({
            "イベント": f"{[e for e in events if e.id == result.event_id][0].emoji} {result.event_name}",
            "現在の待ち時間": f"{current_wait}分",
            "予測待ち時間（平均）": f"{result.mean_wait_minutes:.1f}分",
            "変化": f"{delta_str}分",
            "95%信頼区間": f"{result.ci_lower_95:.1f}〜{result.ci_upper_95:.1f}分",
            "危険状態確率": f"{result.prob_critical:.1f}%",
        })

    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # 待ち時間分布グラフ（上位3件）
    st.markdown("#### 📊 待ち時間の確率分布（上位3件）")
    top_results = sorted(results, key=lambda r: r.mean_wait_minutes, reverse=True)[:3]

    fig = go.Figure()
    colors = ["#0EA5E9", "#F97316", "#22C55E"]
    for idx, result in enumerate(top_results):
        event_obj = next((e for e in events if e.id == result.event_id), None)
        emoji = event_obj.emoji if event_obj else ""
        fig.add_trace(go.Histogram(
            x=result.wait_distribution,
            name=f"{emoji} {result.event_name}",
            opacity=0.7,
            marker_color=colors[idx],
            nbinsx=30,
            hovertemplate="待ち時間: %{x}分<br>頻度: %{y}回<extra></extra>",
        ))

    fig.update_layout(
        title=dict(text="待ち時間の確率分布（モンテカルロ1000試行）", font=dict(size=14)),
        xaxis_title="待ち時間（分）",
        yaxis_title="試行回数",
        barmode="overlay",
        height=350,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)

    # 危険度マトリクス
    st.markdown("#### ⚠️ 危険度マトリクス")
    high_risk = [r for r in results if r.prob_critical > 50]
    if high_risk:
        for r in high_risk:
            event_obj = next((e for e in events if e.id == r.event_id), None)
            emoji = event_obj.emoji if event_obj else "⚠️"
            st.warning(
                f"{emoji} **{r.event_name}**：このシナリオでは "
                f"**{r.prob_critical:.1f}%の確率でCRITICAL状態**になります。"
                f"スタッフ増員または入場制限を検討してください。"
            )
    else:
        st.success("✅ このシナリオでは全イベントのリスクは許容範囲内です。")
