"""
FestivalFlow AI — components/quiz.py
待機時間エンタメクイズコンポーネント

推定待ち時間が15分以上のイベントで自動表示されるクイズ。
大谷翔平 × 3問 + K-POP × 3問（計6問・ランダム出題）。
"""

import random
import streamlit as st


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# クイズデータベース
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OHTANI_QUESTIONS = [
    {
        "question": "大谷翔平選手が2023年のWBCで達成した偉業は？",
        "options": ["MVP獲得", "本塁打王", "最多勝", "奪三振王"],
        "answer": 0,
        "explanation": "大谷翔平選手はWBC2023で日本の優勝に貢献し、トーナメントMVPを獲得しました！",
    },
    {
        "question": "大谷翔平選手の出身都道府県はどこ？",
        "options": ["北海道", "岩手県", "大阪府", "愛知県"],
        "answer": 1,
        "explanation": "大谷翔平選手は岩手県奥州市出身です。花巻東高校でも活躍しました！",
    },
    {
        "question": "大谷翔平選手が2023年シーズンに移籍した球団は？",
        "options": ["ヤンキース", "レッドソックス", "ドジャース", "カブス"],
        "answer": 2,
        "explanation": "2024年から大谷翔平選手はLAドジャースに移籍。10年7億ドルという史上最大契約を結びました！",
    },
    {
        "question": "大谷翔平選手のMLBでのポジションは？",
        "options": ["指名打者のみ", "投手のみ", "投手・指名打者の二刀流", "外野手・投手の二刀流"],
        "answer": 2,
        "explanation": "大谷翔平選手は投手としても打者としても活躍する二刀流プレーヤーです！",
    },
    {
        "question": "大谷翔平選手が初めてMLBでMVPを受賞した年は？",
        "options": ["2018年", "2019年", "2020年", "2021年"],
        "answer": 3,
        "explanation": "大谷翔平選手は2021年にALのMVPを満票で獲得。歴史的な二刀流シーズンでした！",
    },
]

KPOP_QUESTIONS = [
    {
        "question": "BTSのリーダーは誰？",
        "options": ["ジン", "シュガ", "RM", "ジョングク"],
        "answer": 2,
        "explanation": "BTSのリーダーはRM（本名：キム・ナムジュン）です。ラップを担当しています！",
    },
    {
        "question": "BLACKPINKのメンバーは何人？",
        "options": ["3人", "4人", "5人", "6人"],
        "answer": 1,
        "explanation": "BLACKPINKはジス、ジェニー、ロゼ、リサの4人組グループです！",
    },
    {
        "question": "TWICE（トワイス）の出身国はどこ？",
        "options": ["韓国のみ", "日本のみ", "韓国・日本・台湾のメンバーが混在", "中国のみ"],
        "answer": 2,
        "explanation": "TWICEは韓国・日本・台湾出身のメンバーで構成された9人組グループです！",
    },
    {
        "question": "K-POPの「K」は何の頭文字？",
        "options": ["カワイイ（Kawaii）", "韓国（Korea）", "キング（King）", "キー（Key）"],
        "answer": 1,
        "explanation": "「K-POP」の「K」はKorea（韓国）の頭文字です。韓国のポップミュージックを指します！",
    },
    {
        "question": "aespaのメンバーが持つユニークな設定は？",
        "options": ["全員が宇宙人", "AIアバター（ae）を持つ", "動物がモチーフ", "超能力を持つ"],
        "answer": 1,
        "explanation": "aespaの各メンバーにはAIアバター（ae）が存在するという世界観を持つグループです！",
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# クイズコンポーネント
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def render_waiting_quiz(event_id: str, wait_minutes: int) -> None:
    """
    待機時間が15分以上の場合にエンタメクイズを表示する。

    セッション状態でクイズの進行を管理する。
    各イベントは独立したクイズセッションを持つ（event_idで区別）。

    Args:
        event_id    : クイズを表示するイベントのID（セッション管理用）
        wait_minutes: 推定待ち時間（分）。15分未満の場合は何も表示しない。
    """
    # 15分未満の場合は何も表示しない
    if wait_minutes < 15:
        return

    # セッションキーをイベントIDで区別
    quiz_key = f"quiz_{event_id}"
    score_key = f"quiz_score_{event_id}"
    current_q_key = f"quiz_current_q_{event_id}"
    questions_key = f"quiz_questions_{event_id}"
    answered_key = f"quiz_answered_{event_id}"

    # クイズの初期化（初回表示時のみ）
    if questions_key not in st.session_state:
        # 大谷問題3問 + K-POP問題3問 をランダムに選出
        selected_ohtani = random.sample(OHTANI_QUESTIONS, min(3, len(OHTANI_QUESTIONS)))
        selected_kpop = random.sample(KPOP_QUESTIONS, min(3, len(KPOP_QUESTIONS)))
        all_questions = selected_ohtani + selected_kpop
        random.shuffle(all_questions)
        st.session_state[questions_key] = all_questions
        st.session_state[score_key] = 0
        st.session_state[current_q_key] = 0
        st.session_state[answered_key] = []

    questions = st.session_state[questions_key]
    current_q_idx = st.session_state[current_q_key]
    score = st.session_state[score_key]
    answered = st.session_state[answered_key]

    # クイズUIの表示
    with st.expander(f"🎮 待ち時間クイズに挑戦！（推定{wait_minutes}分待ち）", expanded=False):
        st.markdown("""
        <div style="background:linear-gradient(135deg,#F0F9FF,#E0F2FE);
                    border-radius:12px;padding:16px;margin-bottom:16px;">
            <div style="font-size:16px;font-weight:700;color:#0EA5E9;">
                ⏳ 待ち時間を楽しく過ごそう！
            </div>
            <div style="color:#475569;font-size:13px;margin-top:4px;">
                大谷翔平 & K-POP クイズに挑戦。全6問に答えよう！
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 全問回答済みの場合はスコア表示
        if current_q_idx >= len(questions):
            _render_quiz_result(score, len(questions), quiz_key, score_key,
                                current_q_key, questions_key, answered_key)
            return

        # 現在の問題を表示
        question_data = questions[current_q_idx]
        progress = (current_q_idx + 1) / len(questions)

        # プログレスバー
        st.progress(progress)
        st.markdown(
            f"<div style='color:#64748B;font-size:12px;text-align:right;'>"
            f"問題 {current_q_idx + 1} / {len(questions)}　｜　スコア: {score}点</div>",
            unsafe_allow_html=True,
        )

        # カテゴリバッジ
        category_html = "⚾ 大谷翔平" if "大谷" in question_data["question"] else "🎵 K-POP"

        st.markdown(f"""
        <div style="background:white;border-radius:12px;padding:16px;
                    border:2px solid #E2E8F0;margin:12px 0;">
            <div style="color:#0EA5E9;font-size:12px;font-weight:600;margin-bottom:8px;">
                {category_html}
            </div>
            <div style="font-size:16px;font-weight:700;color:#0F172A;">
                Q{current_q_idx + 1}. {question_data['question']}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 選択肢ボタン
        # 既に回答済みかどうかをチェック
        already_answered = current_q_idx in answered

        if not already_answered:
            cols = st.columns(2)
            for opt_idx, option in enumerate(question_data["options"]):
                col = cols[opt_idx % 2]
                with col:
                    if st.button(
                        f"{'ABCD'[opt_idx]}. {option}",
                        key=f"quiz_opt_{quiz_key}_{current_q_idx}_{opt_idx}",
                        use_container_width=True,
                    ):
                        # 回答を記録
                        is_correct = opt_idx == question_data["answer"]
                        if is_correct:
                            st.session_state[score_key] += 1

                        st.session_state[answered_key] = answered + [current_q_idx]
                        st.session_state[f"quiz_last_answer_{quiz_key}_{current_q_idx}"] = {
                            "selected": opt_idx,
                            "is_correct": is_correct,
                            "explanation": question_data["explanation"],
                            "correct_answer": question_data["answer"],
                        }
                        st.rerun()
        else:
            # 回答済み：結果を表示
            last_answer = st.session_state.get(f"quiz_last_answer_{quiz_key}_{current_q_idx}")
            if last_answer:
                if last_answer["is_correct"]:
                    st.success(f"✅ 正解！{last_answer['explanation']}")
                else:
                    correct_text = question_data["options"][last_answer["correct_answer"]]
                    st.error(f"❌ 残念！正解は「{correct_text}」です。\n{last_answer['explanation']}")

            if st.button(
                "次の問題へ →" if current_q_idx < len(questions) - 1 else "結果を見る 🏆",
                key=f"quiz_next_{quiz_key}_{current_q_idx}",
                type="primary",
                use_container_width=True,
            ):
                st.session_state[current_q_key] = current_q_idx + 1
                st.rerun()


def _render_quiz_result(
    score: int,
    total: int,
    quiz_key: str,
    score_key: str,
    current_q_key: str,
    questions_key: str,
    answered_key: str,
) -> None:
    """
    クイズ終了時のスコア結果を表示する。

    SNSシェア用テキストも生成する。

    Args:
        score       : 正解数
        total       : 総問題数
        quiz_key    : セッションキーのベース
        score_key   : スコアのセッションキー
        current_q_key: 現在の問題番号のセッションキー
        questions_key: 問題リストのセッションキー
        answered_key : 回答済みリストのセッションキー
    """
    score_rate = score / total if total > 0 else 0
    if score_rate >= 0.85:
        rank_label = "🏆 クイズマスター！"
        rank_color = "#F97316"
        comment = "素晴らしい！大谷翔平とK-POPの両方に詳しいですね！"
    elif score_rate >= 0.6:
        rank_label = "⭐ なかなかの知識！"
        rank_color = "#EAB308"
        comment = "良い結果です！もう少しで満点でした！"
    else:
        rank_label = "📚 これからの人"
        rank_color = "#0EA5E9"
        comment = "まだまだこれから！楽しんでいただけましたか？"

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#F0F9FF,#FFF7ED);
                border-radius:16px;padding:24px;text-align:center;border:2px solid #E2E8F0;">
        <div style="font-size:48px;margin-bottom:8px;">{rank_label.split()[0]}</div>
        <div style="font-size:22px;font-weight:800;color:{rank_color};">{rank_label[2:]}</div>
        <div style="font-size:48px;font-weight:900;color:#0F172A;margin:12px 0;">
            {score} <span style="font-size:20px;color:#64748B;">/ {total}</span>
        </div>
        <div style="color:#475569;font-size:14px;">{comment}</div>
    </div>
    """, unsafe_allow_html=True)

    # SNSシェア用テキスト
    share_text = (
        f"🎉 文化祭待ち時間クイズに挑戦！\n"
        f"結果：{score}/{total}問正解 {rank_label}\n"
        f"#FestivalFlow #文化祭 #大谷翔平 #KPOP"
    )
    st.markdown("**📱 SNSでシェアしよう！**")
    st.code(share_text, language=None)

    # もう一度挑戦ボタン
    if st.button("🔄 もう一度挑戦する", key=f"quiz_retry_{quiz_key}", use_container_width=True):
        for key in [score_key, current_q_key, questions_key, answered_key]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
