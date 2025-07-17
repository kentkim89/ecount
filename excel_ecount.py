import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import google.generativeai as genai
import re
import requests
import json
from datetime import datetime, timedelta

# --- Streamlit 페이지 설정 ---
st.set_page_config(
    page_title="고래미 주식회사 AI 비즈니스 인텔리전스",
    page_icon="🐳",
    layout="wide"
)

# --- 사용자 정의 영역 ---
EXCLUDED_ITEMS = [
    "경영지원부 기타코드", "추가할인", "픽업할인",
    "KPP 파렛트(빨간색) (N11)", "KPP 파렛트(파란색) (N12)",
    "KPP 파렛트 (빨간색)", "KPP 파렛트 (파란색)",
    "[부재료]NO.320_80g전용_트레이_홈플러스전용_KCP",
    "미니락교 20g 이엔 (세트상품)", "초대리 50g 주비 (세트상품)"
]
EXCLUDED_KEYWORDS_PATTERN = r'택배비|운송비|수수료|쿠폰할인|추가할인|픽업할인'

# --- 데이터 클리닝 및 AI 함수 ---
def clean_product_name(name):
    if not isinstance(name, str): return name
    name = re.sub(r'\[완제품\]|고래미|설래담', '', name, flags=re.I).strip()
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

def configure_google_ai(api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
    except Exception as e:
        st.error(f"Google AI 모델 설정에 실패했습니다: {e}")
        st.stop()

def get_overall_strategy_report(model, df):
    if model is None: return "AI 모델이 설정되지 않았습니다."
    total_supply = df[df['합계'] >= 0]['공급가액'].sum()
    total_sales = df[df['합계'] >= 0]['합계'].sum()
    unique_customers = df['거래처명'].nunique()
    prompt = f"""
    당신은 '고래미 주식회사'의 수석 비즈니스 전략가 **'고래미 AI'** 입니다.
    지난달 판매 데이터를 분석하여, 경영진이 다음 달의 방향을 결정할 수 있도록 명확하고 구조화된 전략 보고서를 작성해주세요.

    **[중요] 아래 제공된 '지난달 핵심 성과 지표'를 반드시 그대로 사용하여 보고서를 작성하세요.**

    ### 지난달 핵심 성과 지표
    - **총 공급가액:** {total_supply:,.0f} 원
    - **총 매출:** {total_sales:,.0f} 원
    - **거래처 수:** {unique_customers} 곳
    - **판매 기간:** {df['일자'].min().strftime('%Y-%m-%d')} ~ {df['일자'].max().strftime('%Y-%m-%d')}

    ### 다음 달 전략 보고서
    
    **1. 월간 성과 요약 (Executive Summary)**
    - 위 핵심 성과 지표를 바탕으로 지난달의 전반적인 성과를 2~3문장으로 요약해주세요.

    **2. 잘한 점 (What Went Well)**
    - **효자 상품:** 매출액 기준 상위 3개 제품을 언급하고, 이 제품들이 성공한 이유를 데이터에 기반하여 분석해주세요.
    - **핵심 고객:** 매출액 기준 상위 3개 거래처를 언급하고, 이들과의 관계가 비즈니스에 어떤 긍정적 영향을 미쳤는지 설명해주세요.

    **3. 개선할 점 (Areas for Improvement)**
    - **성장 필요 상품:** 판매가 부진했던 하위 제품군이나 특정 카테고리를 언급하고, 이것이 전체 실적에 미친 영향을 간략히 분석해주세요.
    - **잠재 리스크:** 특정 거래처나 제품에 대한 매출 의존도가 높다면 그 위험성을 지적하고, 고객 다변화의 필요성을 제기해주세요.

    **4. 다음 달 핵심 실행 과제 (Action Items for Next Month)**
    - 위 분석을 바탕으로, 다음 달에 즉시 실행해야 할 가장 중요한 액션 아이템 3가지를 우선순위와 함께 구체적으로 제안해주세요.
      - 예: (1순위) **효자 상품 A 프로모션 강화:** B고객사를 대상으로 A상품 10+1 프로모션을 제안하여 매출 15% 증대 목표.
      - 예: (2순위) **신규 고객 확보:** C지역의 유사 식당을 타겟으로 신제품 D 샘플 제공 및 초기 할인 혜택 부여.
      - 예: (3순위) **재고 관리 최적화:** 판매 부진 상품 E의 재고 소진을 위한 묶음 할인 기획.

    ---
    *보고서는 위 구조와 형식을 반드시 준수하여, **굵은 글씨**와 글머리 기호(-)를 사용해 가독성을 높여주세요.*
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e: return f"AI 리포트 생성 중 오류: {e}"

def call_naver_datalab(api_id, api_secret, keyword):
    end_date = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=365)).strftime('%Y-%m-%d')
    body = {"startDate": start_date, "endDate": end_date, "timeUnit": "month", "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}]}
    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {"X-Naver-Client-Id": api_id, "X-Naver-Client-Secret": api_secret, "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(body))
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"네이버 데이터랩 API 호출 오류: {e}")
        return None

def call_naver_shopping(api_id, api_secret, keyword):
    url = f"https://openapi.naver.com/v1/search/shop.json?query={keyword}&display=5"
    headers = {"X-Naver-Client-Id": api_id, "X-Naver-Client-Secret": api_secret}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"네이버 쇼핑 API 호출 오류: {e}")
        return None

def get_product_deep_dive_report(model, product_name, internal_rank, datalab_result, shopping_result):
    if model is None: return "AI 모델이 설정되지 않았습니다."

    # --- AI 프롬프트 안정성 강화 ---
    trend_data_section = "**검색량 트렌드 데이터 없음**"
    if datalab_result and datalab_result.get('results') and datalab_result['results'][0].get('data'):
        trend_data_section = f"""- **검색량 트렌드 (최근 1년):** {json.dumps(datalab_result['results'][0]['data'], ensure_ascii=False)}
    *(데이터에서 나타나는 계절적 성수기, 비수기를 분석에 활용하세요.)*"""

    shopping_data_section = "**쇼핑 검색 데이터 없음**"
    if shopping_result and shopping_result.get('items'):
        shopping_data_section = f"""- **주요 경쟁 제품 (상위 5개):**
    ```
    {pd.DataFrame(shopping_result['items'])[['title', 'lprice', 'brand']].to_string()}
    ```
    *(경쟁 제품의 네이밍, 가격대를 분석에 활용하세요.)*"""

    prompt = f"""
    당신은 대한민국 최고의 데이터 기반 마케터 **'고래미 AI'** 입니다.
    우리의 제품인 **'{product_name}'**에 대한 **내부 판매 데이터**와 **외부 시장 데이터**를 종합하여, 심층 분석 및 마케팅 전략을 수립해주세요.

    ### 1. 데이터 종합 분석 (Data Synthesis)

    **가. 내부 성과 (Internal Performance)**
    - **판매 순위:** 우리 회사 전체 제품 중 매출 **{internal_rank}위**의 핵심 제품입니다.

    **나. 외부 시장 현황 (External Market - Source: Naver API)**
    {trend_data_section}
    {shopping_data_section}

    ### 2. '{product_name}' 심층 분석 및 전략 제안

    위 데이터를 바탕으로, 아래 항목에 대해 구체적인 보고서를 작성해주세요.

    **가. SWOT 분석**
    - **Strength (강점):** 내부 성과(예: 높은 판매 순위)를 바탕으로 한 강점은 무엇인가?
    - **Weakness (약점):** 경쟁사 대비 가격, 브랜드 인지도 등에서 약점은 무엇인가?
    - **Opportunity (기회):** 검색량 트렌드(예: 특정 시즌의 검색량 급등)에서 발견되는 기회는 무엇인가?
    - **Threat (위협):** 강력한 경쟁 제품의 존재, 비수기 등 위협 요인은 무엇인가?

    **나. 다음 달 마케팅 액션 플랜 (Action Plan for Next Month)**
    - **1) 타겟 고객:** 어떤 고객을 집중 공략해야 하는가?
    - **2) 핵심 메시지:** 그들에게 어떤 점을 가장 강력하게 어필해야 하는가? (예: "우리 매장 판매 1위!", "지금 가장 많이 찾는 바로 그 제품!")
    - **3) 추천 캠페인:** 위 분석을 바탕으로, 바로 실행할 수 있는 온라인 마케팅 캠페인 1가지를 구체적으로 제안해주세요.

    ---
    *보고서는 위 구조와 형식을 반드시 준수하여, 전문가의 시각으로 작성해주세요.*
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e: return f"AI 전략 보고서 생성 중 오류: {e}"

def get_ai_answer(model, df, question):
    if model is None: return "AI 모델이 설정되지 않았습니다."
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
    except Exception as e: return f"AI 답변 생성 중 오류: {e}"

# --- Streamlit 앱 메인 로직 ---
st.title("🐳 고래미 주식회사 AI 비즈니스 인텔리전스")

g_model, n_id, n_secret = None, None, None
try:
    g_model = configure_google_ai(st.secrets["GOOGLE_API_KEY"])
    n_id = st.secrets["NAVER_CLIENT_ID"]
    n_secret = st.secrets["NAVER_CLIENT_SECRET"]
    st.sidebar.success("✅ Google & Naver API가 연결되었습니다.")
except KeyError as e:
    st.sidebar.error(f"⚠️ API 키 설정 오류: {e}를 Secrets에 추가해주세요.")
except Exception as e:
    st.sidebar.error(f"🚨 API 연결 실패: {e}")

if 'analysis_df' not in st.session_state: st.session_state.analysis_df = None
if 'full_df' not in st.session_state: st.session_state.full_df = None

with st.sidebar:
    st.header("데이터 업로드")
    uploaded_file = st.file_uploader("📂 판매현황 엑셀 파일을 여기에 업로드하세요.", type=["xlsx", "xls"])
    if uploaded_file:
        with st.spinner("데이터를 처리하는 중입니다..."):
            try:
                df = pd.read_excel(uploaded_file, sheet_name="판매현황", header=1)
                expected_columns = ["일자-No.", "배송상태", "창고명", "거래처코드", "거래처명", "품목코드", "품목명(규격)", "박스", "낱개수량", "단가", "공급가액", "부가세", "외화금액", "합계", "적요", "쇼핑몰고객명", "시리얼/로트No.", "외포장_여부", "전표상태", "전표상태.1", "추가문자형식2", "포장박스", "추가숫자형식1", "사용자지정숫자1", "사용자지정숫자2"]
                df.columns = expected_columns[:len(df.columns)]
                numeric_cols = ["박스", "낱개수량", "단가", "공급가액", "부가세", "외화금액", "합계"]
                for col in numeric_cols:
                    if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                df['일자'] = df['일자-No.'].apply(lambda x: str(x).split('-')[0].strip() if pd.notnull(x) else None)
                df['일자'] = pd.to_datetime(df['일자'], errors='coerce', format='%Y/%m/%d')
                df.dropna(subset=['품목코드', '일자', '거래처명', '품목명(규격)'], inplace=True)
                mask_static = df['품목명(규격)'].str.strip().isin(EXCLUDED_ITEMS)
                mask_pattern = df['품목명(규격)'].str.contains(EXCLUDED_KEYWORDS_PATTERN, na=False)
                combined_mask = mask_static | mask_pattern
                analysis_df = df[~combined_mask].copy()
                analysis_df['제품명'] = analysis_df['품목명(규격)'].apply(clean_product_name)
                analysis_df = analysis_df[analysis_df['거래처명'].str.strip() != '']
                analysis_df = analysis_df[analysis_df['제품명'].str.strip() != '']
                st.session_state.analysis_df = analysis_df
                st.session_state.full_df = df
                st.success("데이터 처리가 완료되었습니다!")
            except Exception as e:
                st.error(f"데이터 처리 중 오류: {e}")
                st.session_state.analysis_df = None
                st.session_state.full_df = None

tab1, tab2, tab3, tab4 = st.tabs(["[1] 내부 성과 요약", "[2] AI 종합 전략 리포트", "[3] 제품 심층 분석 (시장 연동)", "[4. AI 어시스턴트]"])

if st.session_state.analysis_df is None:
    st.info("👈 사이드바에서 판매현황 엑셀 파일을 업로드하여 분석을 시작하세요.")
else:
    analysis_df = st.session_state.analysis_df
    df = st.session_state.full_df

    with tab1:
        st.header("[1] 지난달 핵심 성과 요약", anchor=False)
        total_supply = df['공급가액'].sum()
        total_sales = df['합계'].sum()
        total_export = df['외화금액'].sum()
        total_boxes = analysis_df['박스'].sum()
        unique_customers = analysis_df['거래처명'].nunique()
        st.divider()
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("총 공급가액", f"{total_supply:,.0f} 원")
        col2.metric("총 매출", f"{total_sales:,.0f} 원", help="공급가액 + 부가세")
        col3.metric("수출 금액", f"{total_export:,.2f} USD")
        col4.metric("총 판매 박스", f"{total_boxes:,.0f} 개")
        col5.metric("거래처 수", f"{unique_customers} 곳")
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🏢 상위 거래처 매출 (Top 10)", anchor=False)
            top_10_customers = analysis_df.groupby('거래처명')['합계'].sum().nlargest(10).reset_index()
            fig_bar_cust = px.bar(top_10_customers.sort_values('합계', ascending=True), x='합계', y='거래처명', orientation='h', template="plotly_white", text='합계')
            fig_bar_cust.update_traces(texttemplate='%{x:,.0f}원', textposition='outside')
            fig_bar_cust.update_layout(title_x=0.5, xaxis_title=None, yaxis_title=None)
            st.plotly_chart(fig_bar_cust, use_container_width=True)
        with col2:
            st.subheader("📦 품목별 매출 순위 (Top 10)", anchor=False)
            top_10_products = analysis_df.groupby('제품명')['합계'].sum().nlargest(10).reset_index()
            fig_bar_prod = px.bar(top_10_products.sort_values('합계', ascending=True), x='합계', y='제품명', orientation='h', template="plotly_white", text='합계')
            fig_bar_prod.update_traces(texttemplate='%{x:,.0f}원', textposition='outside')
            fig_bar_prod.update_layout(title_x=0.5, xaxis_title=None, yaxis_title=None)
            st.plotly_chart(fig_bar_prod, use_container_width=True)
    
    with tab2:
        st.header("[2] AI 종합 전략 리포트 (내부 데이터 기반)", anchor=False)
        st.info("지난달 내부 판매 실적을 바탕으로 AI가 비즈니스 전략을 수립합니다.")
        if st.button("📈 종합 전략 리포트 생성", key="overall_strategy"):
            if g_model:
                with st.spinner("고래미 AI가 내부 데이터를 분석하여 종합 전략을 수립하고 있습니다..."):
                    report = get_overall_strategy_report(g_model, analysis_df)
                    st.markdown(report)
            else: st.warning("AI 모델이 연결되지 않았습니다.")

    with tab3:
        st.header("[3] 제품 심층 분석 (시장 연동)", anchor=False)
        st.info("우리 제품과 외부 시장 데이터를 결합하여, 제품별 맞춤 마케팅 전략을 도출합니다.")
        
        product_list = sorted(analysis_df['제품명'].unique())
        selected_product = st.selectbox("분석할 제품을 선택하세요.", product_list)

        if st.button(f"'{selected_product}' 시장 분석 시작", key="deep_dive"):
            if not all([g_model, n_id, n_secret]):
                st.warning("API 키가 모두 설정되어야 합니다.")
            else:
                with st.spinner(f"'{selected_product}'에 대한 내/외부 데이터를 종합 분석 중입니다..."):
                    product_ranks = analysis_df.groupby('제품명')['합계'].sum().rank(method='dense', ascending=False).astype(int)
                    internal_rank = product_ranks.get(selected_product, '순위권 외')
                    
                    datalab_result = call_naver_datalab(n_id, n_secret, selected_product)
                    shopping_result = call_naver_shopping(n_id, n_secret, selected_product)

                    st.subheader(f"'{selected_product}' 시장 데이터 분석")
                    col1, col2 = st.columns(2)
                    
                    # --- 오류 수정: 데이터 유효성 검사 후 차트 생성 ---
                    with col1:
                        st.markdown("**네이버 검색량 트렌드 (1년)**")
                        if datalab_result and datalab_result.get('results') and datalab_result['results'][0].get('data'):
                            df_datalab = pd.DataFrame(datalab_result['results'][0]['data'])
                            df_datalab['period'] = pd.to_datetime(df_datalab['period'])
                            fig_datalab = px.line(df_datalab, x='period', y='ratio', markers=True)
                            fig_datalab.update_layout(yaxis_title="상대적 검색량", xaxis_title=None)
                            st.plotly_chart(fig_datalab, use_container_width=True)
                        else:
                            st.warning(f"'{selected_product}'에 대한 네이버 검색량 트렌드 데이터를 찾을 수 없습니다.")
                    with col2:
                        st.markdown("**네이버 쇼핑 경쟁 제품 (상위 5개)**")
                        if shopping_result and shopping_result.get('items'):
                            df_shopping = pd.DataFrame(shopping_result['items'])[['title', 'lprice', 'brand']]
                            df_shopping.rename(columns={'title': '제품명', 'lprice': '최저가(원)', 'brand': '브랜드'}, inplace=True)
                            st.dataframe(df_shopping, use_container_width=True)
                        else:
                            st.warning(f"'{selected_product}'에 대한 네이버 쇼핑 데이터를 찾을 수 없습니다.")
                    
                    st.divider()
                    st.subheader("AI 심층 분석 및 전략 제안 (by 고래미 AI)")
                    report = get_product_deep_dive_report(g_model, selected_product, internal_rank, datalab_result, shopping_result)
                    st.markdown(report)

    with tab4:
        st.header("[4] AI 어시스턴트 (전체 데이터 질문)", anchor=False)
        st.info("엑셀 원본 데이터 전체에 대해 궁금한 점을 질문해보세요. (할인, 수수료 등 포함)")
        
        if "messages" not in st.session_state: st.session_state.messages = []
        for message in st.session_state.messages:
            with st.chat_message(message["role"]): st.markdown(message["content"])

        user_question = st.chat_input("질문을 입력하세요...")
        if user_question:
            st.session_state.messages.append({"role": "user", "content": user_question})
            with st.chat_message("user"): st.markdown(user_question)
            if g_model:
                with st.spinner("AI가 답변을 생성 중입니다..."):
                    with st.chat_message("assistant"):
                        answer = get_ai_answer(g_model, df, user_question)
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
            else: st.warning("AI 모델이 연결되지 않았습니다.")
