"""
FestivalFlow AI — core/data_manager.py
状態管理・Supabaseアダプター層

【アーキテクチャ設計】
    アダプターパターンを採用し、バックエンドの差し替えを容易にする。
    ローカル開発時はインメモリ（st.session_state）で動作。
    本番環境では SupabaseAdapter クラスに差し替えるだけでリアルタイムDB連携可能。

【スケーラビリティ戦略】
    ローカル開発：st.session_stateでインメモリ管理
    本番移行時：DataAdapter抽象クラスの実装を SupabaseAdapter に変更するのみ
    WebSocket（Supabase Realtime）はsubscribeメソッドで対応予定
"""

import uuid
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

from core.queue_models import calculate_mm1_metrics, QueueMetrics


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# データクラス定義
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class HistoryRecord:
    """
    行列更新履歴の1レコード。

    Attributes:
        timestamp   : 更新時刻（ISO 8601形式）
        queue_length: 記録時の行列人数
        updated_by  : 更新者のロール文字列
        wait_minutes: 記録時の推定待ち時間（分）
    """
    timestamp: str
    queue_length: int
    updated_by: str
    wait_minutes: int


@dataclass
class Event:
    """
    イベントエンティティ（文化祭の各出し物）。

    Attributes:
        id              : UUID形式のイベントID（列挙攻撃対策で連番は使用しない）
        name            : イベント名（日本語）
        classroom       : 教室番号（例：'3-A'）
        floor           : 階数（1〜4）
        category        : カテゴリ（4種類）
        emoji           : カテゴリ絵文字
        queue_length    : 現在の行列人数
        avg_service_time: 平均サービス時間（分）
        capacity        : 並列処理能力（窓口数）
        staff_class_id  : 担当者アクセス制御キー
        is_open         : 営業中フラグ
        history         : 更新履歴（最新20件を保持）
        last_updated_at : 最終更新時刻（ISO 8601）
        anomaly_flag    : 異常値検知フラグ
    """
    id: str
    name: str
    classroom: str
    floor: int
    category: Literal["アトラクション", "飲食", "展示", "パフォーマンス"]
    emoji: str
    queue_length: int
    avg_service_time: float
    capacity: int
    staff_class_id: str
    is_open: bool
    history: list = field(default_factory=list)
    last_updated_at: Optional[str] = None
    anomaly_flag: bool = False
    # core/data_manager.py の Eventクラスの中に追加
@property
def is_open(self) -> bool:
    """イベントが現在開催中かどうかを判定（例：24時間営業フラグなど）"""
    # もし単純なフラグ管理なら self.status == "OPEN" など、
    # あなたの設計に合わせて調整してください。
    # とりあえずエラーを防ぐために True を返すようにしておきます。
    return getattr(self, "_is_open", True)

    def get_metrics(self) -> QueueMetrics:
        """このイベントのM/M/1メトリクスを計算して返す。"""
        return calculate_mm1_metrics(
            queue_length=self.queue_length,
            avg_service_time=self.avg_service_time,
            capacity=self.capacity,
        )

    def to_dict(self) -> dict:
        """辞書形式に変換する（JSON/CSV出力用）。"""
        metrics = self.get_metrics()
        return {
            "id": self.id,
            "name": self.name,
            "classroom": self.classroom,
            "floor": self.floor,
            "category": self.category,
            "emoji": self.emoji,
            "queue_length": self.queue_length,
            "avg_service_time": self.avg_service_time,
            "capacity": self.capacity,
            "is_open": self.is_open,
            "last_updated_at": self.last_updated_at,
            "anomaly_flag": self.anomaly_flag,
            "wait_minutes": metrics.wait_minutes,
            "utilization": metrics.utilization,
            "status": metrics.status,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 初期データ（10件・カテゴリ4種類を均等に含む）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_initial_events() -> list[Event]:
    """
    文化祭の初期イベントデータを生成して返す。

    10件のリアルな文化祭イベント（カテゴリ4種類・均等配置）を返す。
    各イベントの行列人数はデモ用にランダムに初期化される。

    Returns:
        list[Event]: 初期化済みイベントのリスト
    """
    now = _now_iso()
    events_data = [
        # ━━ アトラクション（4件）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # M/M/1安定条件: ρ = (queue/60) / (capacity/service) < 1
        # 各イベントの最大安定行列人数 = capacity/service × 60 × target_ρ
        # お化け屋敷: μ=3/8=0.375/分 → ρ=0.85時の最大=19人
        {
            "id": "evt_a001",
            "name": "お化け屋敷",
            "classroom": "3-A",
            "floor": 3,
            "category": "アトラクション",
            "emoji": "👻",
            "queue_length": random.randint(8, 18),   # ρ≈0.36-0.80 LOW〜HIGH
            "avg_service_time": 8.0,    # 8分/グループ
            "capacity": 3,              # 3グループ同時体験
            "staff_class_id": "3-A",
            "is_open": True,
        },
        # 脱出ゲーム: μ=2/15=0.133/分 → ρ=0.85時の最大=6人
        {
            "id": "evt_a002",
            "name": "脱出ゲーム",
            "classroom": "2-B",
            "floor": 2,
            "category": "アトラクション",
            "emoji": "🎪",
            "queue_length": random.randint(2, 6),    # ρ≈0.25-0.75 LOW〜HIGH
            "avg_service_time": 15.0,   # 15分/ゲーム
            "capacity": 2,              # 2部屋同時進行
            "staff_class_id": "2-B",
            "is_open": True,
        },
        # 謎解き宝探し: μ=5/20=0.25/分 → ρ=0.85時の最大=12人
        {
            "id": "evt_a003",
            "name": "謎解き宝探し",
            "classroom": "屋外",
            "floor": 1,
            "category": "アトラクション",
            "emoji": "🎡",
            "queue_length": random.randint(3, 11),   # ρ≈0.2-0.73
            "avg_service_time": 20.0,   # 20分/チーム
            "capacity": 5,              # 5チーム同時進行
            "staff_class_id": "outdoor",
            "is_open": True,
        },
        # VR体験: μ=4/5=0.8/分 → ρ=0.85時の最大=40人
        {
            "id": "evt_a004",
            "name": "VR体験",
            "classroom": "1-C",
            "floor": 1,
            "category": "アトラクション",
            "emoji": "🎠",
            "queue_length": random.randint(5, 30),   # ρ≈0.1-0.625
            "avg_service_time": 5.0,    # 5分/人
            "capacity": 4,              # 4台同時使用可
            "staff_class_id": "1-C",
            "is_open": True,
        },
        # ━━ 飲食（2件）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ラーメン: μ=8/3=2.667/分 → ρ=0.85時の最大=136人
        {
            "id": "evt_f001",
            "name": "クラスラーメン",
            "classroom": "2-A",
            "floor": 2,
            "category": "飲食",
            "emoji": "🍜",
            "queue_length": random.randint(20, 90),  # ρ≈0.125-0.56
            "avg_service_time": 3.0,    # 3分/人（調理提供）
            "capacity": 8,              # 8口同時調理
            "staff_class_id": "2-A",
            "is_open": True,
        },
        # タピオカ: μ=6/2=3.0/分 → ρ=0.85時の最大=153人
        {
            "id": "evt_f002",
            "name": "タピオカカフェ",
            "classroom": "1-B",
            "floor": 1,
            "category": "飲食",
            "emoji": "🧋",
            "queue_length": random.randint(15, 80),  # ρ≈0.08-0.44
            "avg_service_time": 2.0,    # 2分/杯
            "capacity": 6,              # 6レーン
            "staff_class_id": "1-B",
            "is_open": True,
        },
        # ━━ 展示（2件）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 美術展: μ=30/10=3.0/分 → ρ=0.85時の最大=153人
        {
            "id": "evt_e001",
            "name": "美術部作品展",
            "classroom": "4-A",
            "floor": 4,
            "category": "展示",
            "emoji": "🎨",
            "queue_length": random.randint(0, 15),   # ρ≈0〜0.083
            "avg_service_time": 10.0,   # 10分/人（滞在時間）
            "capacity": 30,             # 同時30人入場可能
            "staff_class_id": "4-A",
            "is_open": True,
        },
        # 科学実験: μ=3/20=0.15/分 → ρ=0.85時の最大=7人
        {
            "id": "evt_e002",
            "name": "科学実験ショー",
            "classroom": "理科室",
            "floor": 2,
            "category": "展示",
            "emoji": "🔬",
            "queue_length": random.randint(2, 6),    # ρ≈0.22-0.67
            "avg_service_time": 20.0,   # 20分/ショー
            "capacity": 3,              # 3ショー同時進行
            "staff_class_id": "science",
            "is_open": True,
        },
        # ━━ パフォーマンス（2件）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 演劇部: μ=3/30=0.1/分 → ρ=0.85時の最大=5人
        {
            "id": "evt_p001",
            "name": "演劇部公演",
            "classroom": "体育館",
            "floor": 1,
            "category": "パフォーマンス",
            "emoji": "🎭",
            "queue_length": random.randint(1, 5),    # ρ≈0.17-0.83
            "avg_service_time": 30.0,   # 30分/公演
            "capacity": 3,              # 3公演/時間帯
            "staff_class_id": "drama",
            "is_open": True,
        },
        # ダンス部: μ=4/15=0.267/分 → ρ=0.85時の最大=13人
        {
            "id": "evt_p002",
            "name": "ダンス部発表",
            "classroom": "ステージ",
            "floor": 1,
            "category": "パフォーマンス",
            "emoji": "💃",
            "queue_length": random.randint(3, 12),   # ρ≈0.19-0.75
            "avg_service_time": 15.0,   # 15分/ステージ
            "capacity": 4,              # 4公演/時間帯
            "staff_class_id": "dance",
            "is_open": True,
        },
    ]

    events = []
    for data in events_data:
        # 初期の履歴レコードを生成（デモ用に過去3件の仮データを作成）
        metrics = calculate_mm1_metrics(
            queue_length=data["queue_length"],
            avg_service_time=data["avg_service_time"],
            capacity=data["capacity"],
        )
        initial_history = [
            HistoryRecord(
                timestamp=now,
                queue_length=data["queue_length"],
                updated_by="SYSTEM",
                wait_minutes=metrics.wait_minutes,
            )
        ]
        events.append(
            Event(
                **data,
                history=initial_history,
                last_updated_at=now,
                anomaly_flag=False,
            )
        )

    return events


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# インメモリ データマネージャー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class LocalDataManager:
    """
    インメモリ（st.session_state）を使用したデータマネージャー。

    本番環境では SupabaseDataManager に差し替えること。
    インターフェースは同一なので、呼び出し元のコードは変更不要。
    """

    @staticmethod
    def get_events() -> list[Event]:
        """
        現在の全イベントリストを返す。

        Returns:
            list[Event]: セッション状態内のイベントリスト
        """
        import streamlit as st
        return st.session_state.get("events", [])

    @staticmethod
    def update_queue_length(
        event_id: str,
        new_queue_length: int,
        updated_by: str = "STAFF",
    ) -> Optional[Event]:
        """
        指定イベントの行列人数を更新し、履歴に記録する。

        イミュータブルな状態更新パターンを使用（副作用防止）。

        Args:
            event_id         : 更新対象イベントのID
            new_queue_length : 新しい行列人数
            updated_by       : 更新者のロール文字列

        Returns:
            Optional[Event]: 更新後のイベント。IDが存在しない場合はNone。
        """
        import streamlit as st

        events: list[Event] = st.session_state.get("events", [])
        updated_event = None

        # 【イミュータブル更新】リストを新しいオブジェクトとして生成
        new_events = []
        for event in events:
            if event.id == event_id:
                # メトリクスを計算して履歴に記録
                metrics = calculate_mm1_metrics(
                    queue_length=new_queue_length,
                    avg_service_time=event.avg_service_time,
                    capacity=event.capacity,
                )

                # 履歴を最新20件に保持（メモリ効率）
                new_history = list(event.history)
                new_history.append(
                    HistoryRecord(
                        timestamp=_now_iso(),
                        queue_length=new_queue_length,
                        updated_by=updated_by,
                        wait_minutes=metrics.wait_minutes,
                    )
                )
                if len(new_history) > 20:
                    new_history = new_history[-20:]

                # 新しいイベントオブジェクトを生成（元のオブジェクトを変更しない）
                updated_event = Event(
                    id=event.id,
                    name=event.name,
                    classroom=event.classroom,
                    floor=event.floor,
                    category=event.category,
                    emoji=event.emoji,
                    queue_length=new_queue_length,
                    avg_service_time=event.avg_service_time,
                    capacity=event.capacity,
                    staff_class_id=event.staff_class_id,
                    is_open=event.is_open,
                    history=new_history,
                    last_updated_at=_now_iso(),
                    anomaly_flag=event.anomaly_flag,
                )
                new_events.append(updated_event)
            else:
                new_events.append(event)

        st.session_state["events"] = new_events
        return updated_event

    @staticmethod
    def set_anomaly_flag(event_id: str, flag: bool) -> None:
        """
        指定イベントの異常値フラグを設定する。

        Args:
            event_id: 対象イベントのID
            flag    : 設定するフラグ値（True=異常あり / False=解除）
        """
        import streamlit as st

        events: list[Event] = st.session_state.get("events", [])
        new_events = [
            Event(
                id=e.id, name=e.name, classroom=e.classroom, floor=e.floor,
                category=e.category, emoji=e.emoji, queue_length=e.queue_length,
                avg_service_time=e.avg_service_time, capacity=e.capacity,
                staff_class_id=e.staff_class_id, is_open=e.is_open,
                history=e.history, last_updated_at=e.last_updated_at,
                anomaly_flag=flag if e.id == event_id else e.anomaly_flag,
            )
            for e in events
        ]
        st.session_state["events"] = new_events

    @staticmethod
    def apply_demo_fluctuation() -> None:
        """
        デモモード用：全イベントの行列人数にランダム変動を適用する。

        文化祭の自然な人数変動をシミュレートするため、
        各イベントの行列人数を±1〜5人の範囲でランダム変動させる。
        """
        import streamlit as st

        events: list[Event] = st.session_state.get("events", [])
        new_events = []

        for event in events:
            if not event.is_open:
                new_events.append(event)
                continue

            # ランダム変動量（-5〜+5人）
            delta = random.randint(-5, 8)
            new_queue = max(0, min(500, event.queue_length + delta))

            metrics = calculate_mm1_metrics(
                queue_length=new_queue,
                avg_service_time=event.avg_service_time,
                capacity=event.capacity,
            )

            new_history = list(event.history)
            new_history.append(
                HistoryRecord(
                    timestamp=_now_iso(),
                    queue_length=new_queue,
                    updated_by="DEMO",
                    wait_minutes=metrics.wait_minutes,
                )
            )
            if len(new_history) > 20:
                new_history = new_history[-20:]

            new_events.append(
                Event(
                    id=event.id, name=event.name, classroom=event.classroom,
                    floor=event.floor, category=event.category, emoji=event.emoji,
                    queue_length=new_queue, avg_service_time=event.avg_service_time,
                    capacity=event.capacity, staff_class_id=event.staff_class_id,
                    is_open=event.is_open, history=new_history,
                    last_updated_at=_now_iso(), anomaly_flag=event.anomaly_flag,
                )
            )

        st.session_state["events"] = new_events

    @staticmethod
    def export_to_dataframe():
        """
        全イベントと全履歴データをpandas DataFrameとして返す。

        管理者のCSVエクスポート機能で使用する。

        Returns:
            pandas.DataFrame: 全履歴データを含むDataFrame
        """
        import pandas as pd
        import streamlit as st

        events: list[Event] = st.session_state.get("events", [])
        rows = []
        for event in events:
            for record in event.history:
                rows.append({
                    "イベントID":    event.id,
                    "イベント名":    event.name,
                    "教室":          event.classroom,
                    "カテゴリ":      event.category,
                    "更新時刻":      record.timestamp,
                    "行列人数":      record.queue_length,
                    "推定待ち時間(分)": record.wait_minutes,
                    "更新者":        record.updated_by,
                })
        return pd.DataFrame(rows)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ユーティリティ関数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _now_iso() -> str:
    """現在時刻をISO 8601形式で返す（UTCタイムゾーン付き）。"""
    return datetime.now(tz=timezone.utc).isoformat()


def get_top_recommended_events(events: list[Event], n: int = 3) -> list[Event]:
    """
    利用率ρが低い順にトップN件のイベントを返す（穴場推薦用）。

    Args:
        events: 全イベントのリスト
        n     : 返すイベント数（デフォルト3件）

    Returns:
        list[Event]: 利用率が低い順に並べたイベントリスト
    """
    open_events = [e for e in events if e.is_open]
    sorted_events = sorted(
        open_events,
        key=lambda e: e.get_metrics().utilization
    )
    return sorted_events[:n]


def get_sorted_events(
    events: list[Event],
    sort_by: Literal["wait_time", "category", "recommended"] = "wait_time",
) -> list[Event]:
    """
    指定された基準でイベントをソートして返す。

    Args:
        events : ソート対象のイベントリスト
        sort_by: ソート基準
                 "wait_time"   : 待ち時間が短い順
                 "category"    : カテゴリ名順（五十音）
                 "recommended" : 穴場スコア順（利用率 × サービス時間の総合評価）

    Returns:
        list[Event]: ソート済みイベントリスト
    """
    if sort_by == "wait_time":
        return sorted(events, key=lambda e: e.get_metrics().wait_minutes)
    elif sort_by == "category":
        return sorted(events, key=lambda e: e.category)
    elif sort_by == "recommended":
        # 穴場スコア：利用率が低く、サービス時間が短いイベントを優先
        return sorted(
            events,
            key=lambda e: e.get_metrics().utilization + (e.avg_service_time / 100)
        )
    else:
        return events


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 【設計ドキュメント】data_manager.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ■ アダプターパターンの採用理由
#   LocalDataManager / SupabaseDataManager を同一インターフェースで実装することで、
#   テスト時・本番移行時にコードの変更なく差し替えが可能。
#
# ■ イミュータブル更新の採用理由
#   Streamlit の st.session_state は辞書/リストへの参照を保持するため、
#   直接変更すると再レンダーが発生しない（Reactと異なる）。
#   新しいリストオブジェクトを代入することで確実に再レンダーをトリガーする。
#
# ■ 履歴20件上限の根拠
#   Streamlit のセッションメモリは1ユーザーあたり数MB程度。
#   10イベント × 20件 = 200レコードで十分な分析データを確保しつつ
#   メモリ使用量を制限する。
