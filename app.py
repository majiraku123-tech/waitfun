"""
FestivalFlow AI — app.py
Streamlitエントリーポイント・ルーティング制御

【アーキテクチャ概要】
    - エントリーポイント: このファイルがStreamlitの起動ファイル
    - ルーティング: st.sidebar のタブ選択でビューを切り替え
    - 状態管理: initialize_session_state() で全キーを一元管理
    - セキュリティ: ロール昇格時にセッションを再生成

【デプロイ方法】
    ローカル: streamlit run app.py
    Streamlit Cloud: このファイルをエントリーポイントとして指定
"""

import streamlit as st
from core.data_manager import load_initial_events
from views.visitor_view import render_visitor_view
from views.staff_view import render_staff_view
from views.admin_view import render_admin_view

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ページ設定（st.set_page_config は必ず最初に呼ぶ）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.set_page_config(
    page_title="FestivalFlow AI — 文化祭混雑ナビ",
    page_icon="🎪",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/your-username/festivalflow-ai",
        "Report a bug": "https://github.com/your-username/festivalflow-ai/issues",
        "About": (
            "## 🎪 FestivalFlow AI\n"
            "M/M/1待ち行列理論によるリアルタイム混雑管理システム\n\n"
            "**技術スタック：**\n"
            "- 待ち行列理論（Kleinrock, 1975）\n"
            "- ゼロトラストセキュリティ・RBAC\n"
            "- モンテカルロシミュレーション\n\n"
            "© 2024 FestivalFlow AI Team"
        ),
    },
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# グローバルCSSスタイル
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _inject_global_styles() -> None:
    """
    アプリ全体に適用するCSSスタイルを注入する。

    Streamlitのデフォルトスタイルを上書きし、
    カスタムカラーパレットとフォントを適用する。
    """
    st.markdown("""
    <style>
    /* ━━ カラーパレット定義 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    :root {
        --color-primary:    #0EA5E9;  /* Sky-500 */
        --color-accent:     #F97316;  /* Orange-500 */
        --color-low:        #22C55E;  /* Green-500 */
        --color-mid:        #EAB308;  /* Yellow-500 */
        --color-high:       #EF4444;  /* Red-500 */
        --color-bg:         #F0F9FF;  /* Sky-50 */
        --color-surface:    #FFFFFF;
        --color-text:       #0F172A;  /* Slate-900 */
    }

    /* ━━ 全体背景 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    .stApp {
        background-color: #F0F9FF;
    }

    /* ━━ メインコンテンツエリア ━━━━━━━━━━━━━━━━━━━━━━━━━ */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    /* ━━ サイドバー ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
    }
    [data-testid="stSidebar"] * {
        color: #E2E8F0 !important;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stMarkdown {
        color: #CBD5E1 !important;
    }

    /* ━━ ボタンスタイル ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0EA5E9, #0284C7);
        border: none;
        color: white;
    }

    /* ━━ タブスタイル ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        font-size: 14px;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #0EA5E9;
    }

    /* ━━ 入力フィールド ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    .stNumberInput input,
    .stTextInput input {
        border-radius: 8px;
        border: 1.5px solid #E2E8F0;
    }
    .stNumberInput input:focus,
    .stTextInput input:focus {
        border-color: #0EA5E9;
        box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.1);
    }

    /* ━━ モバイル対応 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    @media (max-width: 640px) {
        .main .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
    }

    /* ━━ フッター非表示 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# セッション状態の初期化
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def initialize_session_state() -> None:
    """
    アプリ起動時に全session_stateキーを初期化する。

    KeyError防止のため、存在しないキーのみ初期化する。
    React の useState() に相当する Streamlit の状態管理パターン。
    """
    defaults = {
        "role": "VISITOR",               # 現在のロール（VISITOR/STAFF/ADMIN）
        "authenticated": False,           # 認証済みフラグ
        "session_info": None,            # セッション情報（JWT等）
        "events": load_initial_events(), # 全イベントデータ
        "last_updated": None,            # 最終更新時刻（表示用）
        "anomaly_alerts": [],            # 異常値アラートのリスト
        "demo_mode": False,              # デモ自動変動モード
        "simulation_scale": 1.0,        # シミュレーションの来場者数スケール
        "simulation_results": None,      # シミュレーション結果キャッシュ
        "staff_class_id": "ALL",         # 担当者のクラスID
        "current_tab": "visitor",        # 現在のタブ
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# サイドバー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def render_sidebar():
    """
    サイドバーの描画と統計計算
    """
    # 1. 最初に session_state からイベントリストを取得する（これが抜けていました）
    events = st.session_state.get("events", [])
    
    st.sidebar.title("🎮 メニュー")

    # 2. 開催中のイベントを安全に計算
    # getattr(e, 'is_open', True) により、属性がなくてもエラーを回避
    open_events = [e for e in events if getattr(e, 'is_open', True)]

    if open_events:
        wait_list = []
        for e in open_events:
            try:
                # get_metrics() が存在するか、実行できるかを確認
                m = e.get_metrics()
                wait_list.append(m.wait_minutes)
            except Exception:
                continue
        avg_wait = sum(wait_list) / len(wait_list) if wait_list else 0
    else:
        avg_wait = 0

    # 3. 統計情報の描画（!important でダークモード対策）
    st.sidebar.markdown(f"""
        <div style="background: rgba(255,255,255,0.1); padding: 16px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.2); margin-bottom: 20px;">
            <div style="color: rgba(255,255,255,0.8) !important; font-size: 12px; font-weight: 600;">現在の平均待ち時間</div>
            <div style="color: white !important; font-size: 32px; font-weight: 800; line-height: 1;">
                {int(avg_wait)}<span style="font-size: 14px; margin-left: 4px; opacity: 0.8;">分</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 4. ナビゲーション
    tabs = {
        "visitor": "🏠 来場者ホーム",
        "map": "🗺️ エリアマップ",
        "admin": "🔐 管理者パネル"
    }
    
    selected = st.sidebar.radio(
        "メニューを選択",
        options=list(tabs.keys()),
        format_func=lambda x: tabs[x],
        label_visibility="collapsed"
    )
    
    return selected


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メインルーティング
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main() -> None:
    """
    アプリのエントリーポイント。

    1. 状態初期化
    2. グローバルCSS適用
    3. サイドバー描画（タブ選択）
    4. 選択されたタブに対応するビューを描画
    """
    # 状態初期化（アプリ起動ごとに実行）
    initialize_session_state()

    # グローバルCSSスタイル適用
    _inject_global_styles()

    # サイドバーナビゲーション
    selected_tab = render_sidebar()

    # ルーティング：タブに応じたビューを描画
    if selected_tab == "visitor":
        render_visitor_view()
    elif selected_tab == "staff":
        render_staff_view()
    elif selected_tab == "admin":
        render_admin_view()
    else:
        render_visitor_view()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# エントリーポイント
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    main()
# else: main() は削除します。Streamlitでは不要です。
