import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import google.generativeai as genai
import re

# --- Streamlit 페이지 설정 ---
st.set_page_config(
    page_title="고래미 주식회사 월간 AI 전략 대시보드",
    page_icon="🐳",
    layout="wide"
)

# --- 사용자 정의 영역 ---
# 1. 특정 이름으로 된 제외 항목 리스트
EXCLUDED_ITEMS = [
    "경영지원부 기타코드",
    "추가할인",
    "픽업할인",
    "KPP 파렛트(빨간색) (N11)",
    "KPP 파렛트(파란색) (N12)",
    "KPP 파렛트 (빨간색)",
    "KPP 파렛트 (파란색)",
    "[부재료]NO.320_80g전용_트레이_홈플러스전용_KCP",
    # --- 요청에 따라 추가된 항목 ---
    "미니락교 20g 이엔 (세트상품)",
    "초대리 50g 주비 (세트상품)"
]

# 2. 특정 키워드가 포함된 항목을 제외하기 위한 패턴
EXCLUDED_KEYWORDS_PATTERN = r'택배비|운송비|수수료|쿠폰할인|추가할인|픽업할인'


# --- 데이터 클리닝 함수 ---
def clean_product_name(name):
    if not isinstance(name, str): return name
    brands_and_prefixes = r'\[완제품\]|고래미|설래담'
    name = re.sub(brands_and_prefixes, '', name, flags=re.I).strip()
    spec_full = ''
    match = re.search(r'\[(.*?)\]|\((.*?)\)', name)
    if match:
        spec_full = (match.group(1) or match.group(2) or '').strip()
        name = re.sub(r'\[.*?\]|\(.*?\)', '', name).strip()
    storage = '냉동' if '냉동' in spec_full else '냉장' if '냉장' in spec_full else ''
    spec = re.sub(r'냉동|냉장|\*|1ea|=|1kg', '', spec_full, flags=re.I).strip()
    name = re.sub(r'[_]', ' ', name).strip()
    spec = re.sub(r'[_]', ' ', spec).strip()
    name = re.sub(r'\s+', ' ', name).strip()
    spec = re.sub(r'\s+', ' ', spec).strip()
    if spec and storage: return f"{name} ({spec}) {storage}"
    elif spec: return f"{name} ({spec})"
    elif storage: return f"{name} {storage}"
    else: return name

# --- AI 및 앱 로직 (이하 전체 코드) ---
def configure_google_ai(api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
    except Exception as e:
        st.error(f"Google AI 모델 설정에 실패했습니다: {e}")
        st.stop()

def get_monthly_strategy_report(model, df):
    if model is None: return "AI 모델이 설정되지 않았습니다."
    prompt = f"""
    당신은 '고래미 주식회사'의 수석 비즈니스 전략가입니다.
    아래는 방금 마감된 **지난달의 판매 실적 데이터**입니다. 이 데이터를 기반으로, **다음 달의 비즈니스 성공을 위한 실행 전략 보고서**를 작성해주세요.

    **지난달 판매 데이터 샘플:**
    ```
    {df[['일자', '거래처명', '제품명', '박스', '합계']].head().to_string()}
    ```
    **지난달 주요 성과 지표:**
    - 총 매출: {df['합계'].sum():,.0f} 원
    - 고유 거래처 수: {df['거래처명'].nunique()} 곳
    - 판매 기간: {df['일자'].min().strftime('%Y-%m-%d')} ~ {df['일자'].max().strftime('%Y-%m-%d')}

    **전략 보고서 작성 가이드라인 (다음 달을 위한 제안):**
    1.  **지난달 성과 요약 (Executive Summary):** 지난달 실적의 핵심 성공 요인과 아쉬웠던 점을 요약해주세요.
    2.  **다음 달 핵심 추진 전략:**
        - **주력 제품 강화:** 지난달의 효자 상품(매출 상위 3개)의 판매를 다음 달에 더욱 극대화할 수 있는 구체적인 방안을 제시해주세요. (예: 프로모션, 연관 상품 추천)
        - **핵심 고객 관리:** VIP 고객(매출 상위 3개 거래처) 대상의 다음 달 관계 강화 활동(예: 선공개, 특별 할인)을 제안해주세요.
    3.  **시간대별 판매 동향 기반 전략:** 지난달의 판매 추이(예: 월말에 매출 집중)를 바탕으로 다음 달의 재고 및 마케팅 활동 타이밍을 어떻게 조절해야 할지 조언해주세요.
    4.  **기회 및 위험 요인 관리:**
        - **다음 달의 기회:** 데이터를 통해 포착한 새로운 기회(예: 특정 제품군의 성장세)를 어떻게 활용할지 구체적인 아이디어를 제시해주세요.
        - **잠재적 위험:** 다음 달에 주의해야 할 위험(예: 특정 고객 이탈 가능성, 재고 부족 위험)을 예측하고 대비책을 마련해주세요.
    5.  **[중요] 다음 달 실행 계획 (Action Items for Next Month):**
        - 위 분석을 종합하여, 다음 달에 즉시 시작해야 할 가장 중요한 액션 아이템 3가지를 우선순위와 함께 명확하게 제시해주세요.

    결과는 경영진이 쉽게 이해할 수 있도록 마크다운 형식의 전문적인 보고서로 작성해주세요.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 리포트 생성 중 오류가 발생했습니다: {e}"

def get_low_performer_strategy(model, low_df):
    if model is None: return "AI 모델이 설정되지 않았습니다."
    prompt = f"""
    당신은 창의적인 마케팅 전략가입니다.
    아래는 '고래미 주식회사'의 지난달 판매 실적이 저조했던 상품 리스트입니다.

    **판매 부진 상품 목록:**
    ```
    {low_df.to_string(index=False)}
    ```
    **요청:**
    위 상품들의 재고를 소진하고 판매를 활성화하기 위한 **다음 달 마케팅 전략**을 구체적이고 창의적으로 제안해주세요. 아래 구조에 따라 답변해주세요.

    1.  **문제 진단:** 이 상품들의 판매가 부진한 잠재적인 원인을 2-3가지 추측해주세요. (예: 낮은 인지도, 잘못된 가격 정책, 계절성 등)
    2.  **타겟 고객 재설정:** 이 상품들을 구매할 만한 새로운 타겟 고객층을 정의하고, 그 이유를 설명해주세요.
    3.  **핵심 마케팅 전략 제안 (3가지):**
        - **(전략 1) 묶음 판매 및 할인 프로모션:** 어떤 상품과 묶어서 팔면 좋을지, 어떤 할인율이 매력적일지 구체적인 아이디어를 제시해주세요.
        - **(전략 2) 콘텐츠 마케팅:** 이 상품들을 활용한 레시피, 영상 콘텐츠 등 고객의 구매 욕구를 자극할 콘텐츠 아이디어를 제안해주세요.
        - **(전략 3) 온라인 광고 및 SNS 활용:** 타겟 고객에게 도달하기 위한 광고 문구나 SNS 이벤트 아이디어를 구체적으로 제시해주세요.

    결과는 바로 실행에 옮길 수 있도록 명확하고 설득력 있게 작성해주세요.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 전략 생성 중 오류가 발생했습니다: {e}"

def get_ai_answer(model, df, question):
    if model is None: return "AI 모델이 설정되지 않았습니다. 관리자에게 문의하세요."
    prompt = f"""
    당신은 '고래미 주식회사'의 판매 데이터를 조회하는 친절한 AI 어시스턴트입니다.
    아래 제공된 전체 판매 데이터를 참고하여 사용자의 질문에 답변해주세요.
    **데이터:**
    ```
    {df.to_string()}
    ```
    **사용자 질문:** {question}
    **답변 가이드라인:**
    - 반드시 제공된 데이터에 근거하여 답변해야 합니다.
    - 데이터에 없는 내용은 '데이터에 정보가 없습니다'라고 명확히 밝혀주세요.
    - 가능한 한 질문의 요지에 맞게 간결하고 정확하게 답변해주세요.
    - 계산이 필요한 경우, 직접 계산하여 답변할 수 있습니다.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 답변 생성 중 오류가 발생했습니다: {e}"


# --- Streamlit 앱 메인 로직 ---
st.title("🐳 고래미 주식회사 월간 AI 전략 대시보드")

model = None
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    model = configure_google_ai(api_key)
    st.sidebar.success("✅ AI 모델이 성공적으로 연결되었습니다.")
except KeyError:
    st.sidebar.error("⚠️ GOOGLE_API_KEY가 없습니다. Streamlit Cloud Secrets에 추가해주세요.")
except Exception:
    st.sidebar.error("🚨 AI 모델 연결에 실패했습니다.")

uploaded_file = st.file_uploader("📂 지난달 판매현황 엑셀 파일을 업로드하세요.", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file, sheet_name="판매현황", header=1)
        
        expected_columns = ["일자-No.", "배송상태", "창고명", "거래처코드", "거래처명", "품목코드", "품목명(규격)", "박스", "낱개수량", "단가", "공급가액", "부가세", "외화금액", "합계", "적요", "쇼핑몰고객명", "시리얼/로트No.", "외포장_여부", "전표상태", "전표상태.1", "추가문자형식2", "포장박스", "추가숫자형식1", "사용자지정숫자1", "사용자지정숫자2"]
        df.columns = expected_columns[:len(df.columns)]

        numeric_cols = ["박스", "낱개수량", "단가", "공급가액", "부가세", "합계"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df['일자'] = df['일자-No.'].apply(lambda x: str(x).split('-')[0].strip() if pd.notnull(x) else None)
        df['일자'] = pd.to_datetime(df['일자'], errors='coerce', format='%Y/%m/%d')
        
        df = df.dropna(subset=['품목코드', '일자'])

        mask_static = df['품목명(규격)'].isin(EXCLUDED_ITEMS)
        mask_pattern = df['품목명(규격)'].str.contains(EXCLUDED_KEYWORDS_PATTERN, na=False)
        combined_mask = mask_static | mask_pattern
        
        analysis_df = df[~combined_mask].copy()
        
        analysis_df['제품명'] = analysis_df['품목명(규격)'].apply(clean_product_name)
        
        # --- 'undefined' 항목 제거 로직 ---
        # 거래처명이나 제품명이 비어 있는 경우 분석에서 최종 제외
        analysis_df.dropna(subset=['거래처명'], inplace=True)
        analysis_df = analysis_df[analysis_df['거래처명'].str.strip() != '']
        analysis_df = analysis_df[analysis_df['제품명'].str.strip() != '']
        
        st.success("데이터 로딩 및 전처리가 완료되었습니다.")
        st.info(f"전체 {len(df)}개 거래 항목 중, 제품 분석에서 제외된 관리용 항목은 {len(df) - len(analysis_df)}개 입니다.")

    except Exception as e:
        st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
        st.stop()


    tab1, tab2, tab3 = st.tabs(["📊 지난달 성과 요약", "🤖 다음 달 AI 전략 리포트", "💬 데이터 질문하기"])

    with tab1:
        st.header("지난달 핵심 성과 지표", anchor=False)
        total_sales = df['합계'].sum()
        total_supply = df['공급가액'].sum()
        
        # 운송비용 계산 로직 (월별 이름이 바뀌어도 '택배비' 또는 '운송비' 키워드로 찾음)
        transport_mask = df['품목명(규격)'].str.contains('택배비|운송비', na=False)
        total_transport_cost = df.loc[transport_mask, '합계'].sum()
        
        total_boxes = analysis_df['박스'].sum()
        unique_customers = analysis_df['거래처명'].nunique()

        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("총 매출", f"{total_sales:,.0f} 원")
        col2.metric("총 공급가액", f"{total_supply:,.0f} 원")
        col3.metric("총 판매 박스", f"{total_boxes:,.0f} 개")
        col4.metric("거래처 수", f"{unique_customers} 곳")
        
        st.metric("총 운송비용", f"{total_transport_cost:,.0f} 원", help="'택배비', '운송비'가 포함된 모든 항목의 합계입니다.")
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🏢 상위 거래처 매출 (Top 10)", anchor=False)
            top_10_customers = analysis_df.groupby('거래처명')['합계'].sum().nlargest(10).reset_index()
            fig_bar_cust = px.bar(top_10_customers.sort_values('합계', ascending=True),
                             x='합계', y='거래처명', orientation='h', template="plotly_white", text='합계')
            fig_bar_cust.update_traces(texttemplate='%{x:,.0f}원', textposition='outside')
            fig_bar_cust.update_layout(title_x=0.5, xaxis_title=None, yaxis_title=None)
            st.plotly_chart(fig_bar_cust, use_container_width=True)

        with col2:
            st.subheader("📦 품목별 매출 순위 (Top 10)", anchor=False)
            top_10_products = analysis_df.groupby('제품명')['합계'].sum().nlargest(10).reset_index()
            fig_bar_prod = px.bar(top_10_products.sort_values('합계', ascending=True),
                             x='합계', y='제품명', orientation='h', template="plotly_white", text='합계')
            fig_bar_prod.update_traces(texttemplate='%{x:,.0f}원', textposition='outside')
            fig_bar_prod.update_layout(title_x=0.5, xaxis_title=None, yaxis_title=None)
            st.plotly_chart(fig_bar_prod, use_container_width=True)


    with tab2:
        st.header("🤖 다음 달 비즈니스 전략 AI 리포트", anchor=False)
        st.info("지난달 데이터를 기반으로 AI가 다음 달의 비즈니스 성공을 위한 종합 전략을 수립합니다.")
        
        if st.button("📈 다음 달 전략 리포트 생성", key="generate_strategy"):
            if model:
                with st.spinner('AI가 지난달 실적을 분석하여 다음 달 전략을 수립하고 있습니다...'):
                    report = get_monthly_strategy_report(model, analysis_df)
                    st.markdown(report)
            else:
                st.warning("AI 모델이 연결되지 않았습니다.")
        
        st.divider()

        st.subheader("📉 판매 부진 상품 분석 및 마케팅 전략", anchor=False)
        product_sales = analysis_df.groupby('제품명')['합계'].sum().reset_index()
        low_performers = product_sales[product_sales['합계'] > 0].nsmallest(10, '합계')
        
        st.dataframe(low_performers.style.format({"합계": "{:,.0f} 원"}), use_container_width=True)
        st.info("위는 지난달 매출액 기준 하위 10개 품목입니다(매출 0원 제외). 아래 버튼으로 마케팅 전략을 확인하세요.")

        if st.button("💡 부진 상품 마케팅 전략 생성", key="generate_low_perf_strategy"):
            if model:
                with st.spinner('AI가 부진 상품을 위한 창의적인 마케팅 전략을 구상하고 있습니다...'):
                    strategy = get_low_performer_strategy(model, low_performers)
                    st.markdown(strategy)
            else:
                st.warning("AI 모델이 연결되지 않았습니다.")

    with tab3:
        st.header("💬 AI 어시스턴트에게 질문하기", anchor=False)
        st.info("전체 판매 데이터(할인, 수수료, 운송비 포함)에 대해 궁금한 점을 자유롭게 질문해보세요.")
        
        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        user_question = st.chat_input("질문을 입력하세요... (예: 6월 과세 택배비 총액은?)")

        if user_question:
            st.session_state.messages.append({"role": "user", "content": user_question})
            with st.chat_message("user"):
                st.markdown(user_question)

            if model:
                with st.spinner('AI가 답변을 찾고 있습니다...'):
                    with st.chat_message("assistant"):
                        ai_answer = get_ai_answer(model, df, user_question)
                        st.markdown(ai_answer)
                        st.session_state.messages.append({"role": "assistant", "content": ai_answer})
            else:
                st.warning("AI 모델이 연결되지 않아 답변할 수 없습니다.")
else:
    st.info("👆 상단의 파일 업로드 영역에 지난달 엑셀 파일을 올려주세요.")
    st.markdown("""
    ### ✨ 월간 전략 수립 프로세스
    1.  **지난달 판매 데이터 업로드:** 월 마감 후, '판매현황' 시트가 포함된 엑셀 파일을 업로드합니다.
    2.  **지난달 성과 검토:** '지난달 성과 요약' 탭에서 주요 지표와 매출 순위를 확인합니다.
    3.  **다음 달 전략 수립:** '다음 달 AI 전략 리포트' 탭에서 AI가 생성한 종합 전략과 부진 상품 마케팅 아이디어를 확인하여 다음 달 액션 플랜을 수립합니다.
    """)
