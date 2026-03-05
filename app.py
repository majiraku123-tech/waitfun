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

def render_sidebar() -> str:
    """
    サイドバーのナビゲーションを描画し、選択されたタブ名を返す。

    Returns:
        str: 選択されたタブ（"visitor" / "staff" / "admin"）
    """
    from core.security import get_current_role, ROLES

    with st.sidebar:
        # ロゴ・タイトル
        st.markdown("""
        <div style="text-align: center; padding: 16px 0 24px;">
            <div style="font-size: 40px;">🎪</div>
            <div style="font-size: 18px; font-weight: 800; color: #F0F9FF; letter-spacing: -0.5px;">
                FestivalFlow AI
            </div>
            <div style="font-size: 11px; color: #94A3B8; margin-top: 4px;">
                文化祭混雑ナビ v1.0
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # 現在のロール表示
        current_role = get_current_role()
        role_info = ROLES[current_role]
        role_colors = {"VISITOR": "#64748B", "STAFF": "#22C55E", "ADMIN": "#A855F7"}
        role_color = role_colors[current_role]
        st.markdown(f"""
        <div style="
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 10px 14px;
            margin-bottom: 16px;
            border: 1px solid rgba(255,255,255,0.15);
        ">
            <div style="font-size: 11px; color: #94A3B8;">現在のロール</div>
            <div style="font-size: 14px; font-weight: 700; color: {role_color}; margin-top: 2px;">
                {role_info['label']}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ナビゲーションメニュー
        nav_options = {
            "🙋 来場者": "visitor",
            "📋 担当者": "staff",
            "🔐 管理者": "admin",
        }

        selected_label = st.radio(
            "ナビゲーション",
            options=list(nav_options.keys()),
            index=0,
            label_visibility="collapsed",
        )
        selected_tab = nav_options[selected_label]

        st.markdown("---")

        # イベント数サマリー
       # --- サイドバー内の統計表示部分（ここから入れ替え） ---
    # 全イベントから開催中のものを抽出（属性がなくてもTrueとする安全設計）
    open_events = [e for e in events if getattr(e, 'is_open', True)]

    if open_events:
        wait_list = []
        for e in open_events:
            try:
                m = e.get_metrics()
                wait_list.append(m.wait_minutes)
            except Exception:
                continue
        avg_wait = sum(wait_list) / len(wait_list) if wait_list else 0
    else:
        avg_wait = 0

    # 統計の表示（デザイン維持）
    st.sidebar.markdown(f"""
        <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.2);">
            <div style="color: rgba(255,255,255,0.7); font-size: 12px;">現在の平均待ち時間</div>
            <div style="color: white; font-size: 28px; font-weight: 800;">{int(avg_wait)}<span style="font-size: 14px; margin-left: 4px;">分</span></div>
        </div>
    """, unsafe_allow_html=True)
    # --- ここまで ---

            st.markdown(f"""
            <div style="font-size: 11px; color: #94A3B8; margin-bottom: 8px;">📊 現在の状況</div>
            <div style="font-size: 12px; color: #CBD5E1;">
                🎪 開催中: {open_count}件<br>
                ⏱️ 平均待ち: {avg_wait}分<br>
                🚨 異常値: {sum(1 for e in events if e.anomaly_flag)}件
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # 技術情報（ポートフォリオ用）
        st.markdown("""
        <div style="font-size: 11px; color: #64748B; line-height: 1.6;">
            <b style="color: #94A3B8;">技術スタック</b><br>
            📐 M/M/1待ち行列理論<br>
            🔐 ゼロトラスト RBAC<br>
            🎲 モンテカルロ法<br>
            📊 Plotly インタラクティブグラフ<br>
            ⚡ Streamlit リアルタイム更新
        </div>
        """, unsafe_allow_html=True)

    return selected_tab


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
