import os

import openai
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# 번역 대상 언어 목록
LANGUAGES = ["영어", "일본어", "베트남어", "중국어"]
MAX_CHARS = 5000
DEFAULT_MODEL = "gpt-6.1-sol"

SYSTEM_PROMPT = (
    "You are a professional translator. Translate the user's text into {target}. "
    "Detect the source language automatically. "
    "Output only the translation, with no explanations, quotes, or prefixes. "
    "Preserve line breaks, formatting, proper nouns, and numbers."
)


def get_config(key: str, default: str | None = None) -> str | None:
    """설정값 조회: .env(환경 변수) → st.secrets 순."""
    value = os.getenv(key)
    if value:
        return value
    try:
        return st.secrets.get(key, default)
    except Exception:  # secrets 파일이 없는 경우
        return default


def translate(text: str, target_language: str) -> str:
    """OpenAI API로 텍스트를 target_language로 번역한다."""
    api_key = get_config("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("API 키가 설정되지 않았습니다.")

    client = OpenAI(api_key=api_key, base_url=get_config("OPENAI_BASE_URL"))
    response = client.chat.completions.create(
        model=get_config("OPENAI_MODEL", DEFAULT_MODEL),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(target=target_language)},
            {"role": "user", "content": text},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def error_message(exc: Exception) -> str:
    """예외를 사용자 친화적 메시지로 변환 (키 등 민감 정보는 노출하지 않음)."""
    if isinstance(exc, ValueError):
        return "API 키가 설정되지 않았습니다. `.env` 파일의 `OPENAI_API_KEY`를 확인해주세요."
    if isinstance(exc, openai.AuthenticationError):
        return "API 키 인증에 실패했습니다. 키가 올바른지 확인해주세요."
    if isinstance(exc, openai.RateLimitError):
        return "요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."
    if isinstance(exc, openai.NotFoundError):
        return "설정한 모델을 사용할 수 없습니다. `OPENAI_MODEL` 값을 확인해주세요."
    if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError)):
        return "네트워크 연결에 문제가 있습니다. 인터넷 연결을 확인하고 다시 시도해주세요."
    if isinstance(exc, openai.BadRequestError):
        detail = getattr(exc, "message", "") or ""
        return f"요청이 거부되었습니다. 모델 및 요청 설정을 확인해주세요. ({detail})"
    if isinstance(exc, openai.APIStatusError):
        return f"번역 서버에서 오류가 발생했습니다. (상태 코드 {exc.status_code})"
    return "번역 중 알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해주세요."


st.set_page_config(page_title="AI 번역기", page_icon="🌐", layout="centered")

# 스타일 보정 (라이트/다크 모드 모두에서 테마 변수를 사용)
st.markdown(
    """
    <style>
    .block-container { max-width: 720px; padding-top: 2.5rem; }
    .app-header { text-align: center; margin-bottom: 1.5rem; }
    .app-header h1 { margin-bottom: 0.25rem; }
    .app-header p { opacity: 0.7; margin: 0; }
    .counter { text-align: right; font-size: 0.85rem; opacity: 0.65; margin-top: -0.5rem; }
    .counter.over { color: #e5484d; opacity: 1; font-weight: 600; }
    div.stButton > button { height: 3rem; border-radius: 10px; font-weight: 600; }
    .result-label { font-size: 0.9rem; opacity: 0.7; margin-bottom: 0.25rem; }
    .empty-result { text-align: center; opacity: 0.6; padding: 1.5rem 0; }
    @media (max-width: 480px) {
        .block-container { padding-left: 1rem; padding-right: 1rem; }
        div.stButton > button { font-size: 0.85rem; padding: 0 0.25rem; }
        /* 좁은 화면에서 언어 버튼을 2x2로 배치 */
        div[data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: 0.5rem; }
        div[data-testid="stColumn"], div[data-testid="column"] {
            flex: 1 1 calc(50% - 0.5rem) !important;
            min-width: calc(50% - 0.5rem) !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 헤더
st.markdown(
    '<div class="app-header"><h1>🌐 AI 번역기</h1>'
    "<p>텍스트를 입력하고 원하는 언어 버튼을 눌러보세요</p></div>",
    unsafe_allow_html=True,
)

# 입력 영역
text = st.text_area(
    "번역할 텍스트",
    height=180,
    placeholder="여기에 번역할 내용을 입력하세요...",
    label_visibility="collapsed",
)
length = len(text)
over = " over" if length > MAX_CHARS else ""
st.markdown(
    f'<div class="counter{over}">{length:,} / {MAX_CHARS:,}자</div>',
    unsafe_allow_html=True,
)

# 언어 버튼 4개 (좁은 화면에서는 CSS로 2x2 배치)
columns = st.columns(len(LANGUAGES))
clicked = None
for col, lang in zip(columns, LANGUAGES):
    if col.button(lang, use_container_width=True):
        clicked = lang

# 버튼 클릭 시에만 검증 후 API 호출
if clicked:
    st.session_state.pop("result", None)  # 새 요청 시 이전 결과 제거
    if not text.strip():
        st.warning("번역할 텍스트를 입력해주세요.")
    elif length > MAX_CHARS:
        st.warning(f"입력은 최대 {MAX_CHARS:,}자까지 가능합니다. (현재 {length:,}자)")
    else:
        try:
            with st.spinner(f"{clicked}로 번역 중..."):
                result = translate(text, clicked)
            st.session_state["result"] = {"language": clicked, "text": result}
        except Exception as exc:
            st.error(error_message(exc))

# 결과 카드 (session_state에 유지)
saved = st.session_state.get("result")
with st.container(border=True):
    if saved:
        st.markdown(
            f'<div class="result-label">{saved["language"]} 번역 결과</div>',
            unsafe_allow_html=True,
        )
        st.code(saved["text"], language=None, wrap_lines=True)  # 복사 아이콘 제공
    else:
        st.markdown(
            '<div class="empty-result">번역 결과가 여기에 표시됩니다</div>',
            unsafe_allow_html=True,
        )
