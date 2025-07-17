import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import google.generativeai as genai
import re
import requests # 네이버 API 호출을 위한 라이브러리
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

# --- 데이터 클리닝 및 AI 함수 (이전과 동일) ---
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

def configure_google_ai(api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
    except Exception as e:
        st.error(f"Google AI 모델 설정에 실패했습니다: {e}")
        st.stop()

# --- 네이버 API 호출 함수 ---
def call_naver_datalab(api_id, api_secret, keyword):
    end_date = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=365)).strftime('%Y-%m-%d')
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": "month",
        "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}]
    }
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
    url = f"https://openapi.naver.com/v1/search/shop.json?query={keyword}&display=10"
    headers = {"X-Naver-Client-Id": api_id, "X-Naver-Client-Secret": api_secret}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"네이버 쇼핑 API 호출 오류: {e}")
        return None

# --- AI 전략 분석 함수 ---
def get_market_analysis_report(model, keyword, datalab_result, shopping_result):
    if model is None: return "AI 모델이 설정되지 않았습니다."

    prompt = f"""
    당신은 대한민국 최고의 데이터 기반 마케터 **'고래미 AI'** 입니다.
    아래 제공된 **네이버 실시간 시장 데이터**를 분석하여, '{keyword}' 키워드에 대한 마케팅 전략 보고서를 작성해주세요.

    ### 1. 시장 데이터 (Source: Naver API)

    **가. 검색량 트렌드 (최근 1년, 월별)**
    - 데이터: {json.dumps(datalab_result['results'][0]['data'], ensure_ascii=False)}
    - 분석: 데이터에서 나타나는 계절적 성수기, 비수기 또는 특별한 급등/급락 지점을 짚어주세요.

    **나. 쇼핑 검색 결과 (상위 10개)**
    - 경쟁 제품 리스트:
    ```
    {pd.DataFrame(shopping_result['items'])[['title', 'lprice', 'brand']].to_string()}
    ```
    - 분석: 경쟁 제품들의 네이밍 특징, 평균 가격대, 주요 브랜드를 간략히 요약해주세요.

    ### 2. 마케팅 전략 제안

    위 시장 데이터를 바탕으로, 아래 항목에 대해 구체적이고 실행 가능한 전략을 제시해주세요.

    **가. 타겟 고객 프로필 (Target Persona)**
    - 어떤 고객이 '{keyword}'를 검색할지, 그들의 니즈(Needs)는 무엇일지 구체적으로 묘사해주세요.

    **나. 핵심 마케팅 메시지 (Core Message)**
    - 이 타겟 고객의 마음을 사로잡을 수 있는 한 문장의 핵심적인 광고 메시지는 무엇일까요?

    **다. 실행 가능한 캠페인 아이디어 (Top 3)**
    - **1) (콘텐츠)** 블로그나 인스타그램에 발행할 콘텐츠 아이디어 (제목 또는 주제 포함)
    - **2) (프로모션)** 경쟁사와 차별화될 수 있는 매력적인 판매 프로모션 아이디어
    - **3) (광고)** 네이버 검색 광고에 사용할 광고 문구 (제목과 설명)

    ---
    *보고서는 위 구조와 형식을 반드시 준수하여, 전문가의 시각으로 작성해주세요.*
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 전략 보고서 생성 중 오류가 발생했습니다: {e}"

# --- Streamlit 앱 메인 로직 ---
st.title("🐳 고래미 주식회사 AI 비즈니스 인텔리전스")

# --- API 키 설정 ---
g_model, n_id, n_secret = None, None, None
try:
    g_model = configure_google_ai(st.secrets["GOOGLE_API_KEY"])
    n_id = st.secrets["NAVER_CLIENT_ID"]
    n_secret = st.secrets["NAVER_CLIENT_SECRET"]
    st.sidebar.success("✅ Google & Naver API가 연결되었습니다.")
except KeyError as e:
    st.sidebar.error(f"⚠️ API 키 설정 오류: {e}를 Streamlit Cloud Secrets에 추가해주세요.")
except Exception as e:
    st.sidebar.error(f"🚨 API 연결 실패: {e}")

# --- 탭 구성 ---
tab1, tab2, tab3 = st.tabs(["📊 내부 성과 대시보드", "📈 시장 트렌드 분석 (Naver x AI)", "💬 AI 어시스턴트"])


with tab1:
    st.header("내부 성과 대시보드", anchor=False)
    uploaded_file = st.file_uploader("📂 지난달 판매현황 엑셀 파일을 업로드하세요.", type=["xlsx", "xls"], key="sales_uploader")

    if uploaded_file:
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

            st.success("내부 데이터 로딩 및 전처리가 완료되었습니다.")

            st.subheader("지난달 핵심 성과 지표", anchor=False)
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

        except Exception as e:
            st.error(f"내부 데이터 처리 중 오류: {e}")

with tab2:
    st.header("시장 트렌드 분석 (Naver x AI)", anchor=False)
    st.info("시장의 실시간 목소리를 듣고, 데이터 기반 마케팅 전략을 수립합니다.")
    keyword = st.text_input("분석할 키워드를 입력하세요 (예: 밀키트, 스테이크, 캠핑음식)", "밀키트")

    if st.button("📈 시장 분석 시작", key="market_analysis"):
        if not all([g_model, n_id, n_secret]):
            st.warning("API 키가 모두 설정되어야 합니다. 사이드바의 연결 상태를 확인해주세요.")
        else:
            with st.spinner(f"'{keyword}' 키워드로 네이버 데이터를 수집하고 AI가 분석 중입니다..."):
                datalab_result = call_naver_datalab(n_id, n_secret, keyword)
                shopping_result = call_naver_shopping(n_id, n_secret, keyword)

                if datalab_result and shopping_result:
                    st.subheader(f"'{keyword}' 검색량 트렌드 (최근 1년)")
                    df_datalab = pd.DataFrame(datalab_result['results'][0]['data'])
                    df_datalab['period'] = pd.to_datetime(df_datalab['period'])
                    fig_datalab = px.line(df_datalab, x='period', y='ratio', title=f"'{keyword}' 월별 검색량 비율", markers=True)
                    st.plotly_chart(fig_datalab, use_container_width=True)

                    st.divider()
                    st.subheader("AI 마케팅 전략 보고서 (by 고래미 AI)")
                    report = get_market_analysis_report(g_model, keyword, datalab_result, shopping_result)
                    st.markdown(report)
                else:
                    st.error("데이터를 가져오는 데 실패했습니다. API 설정이나 키워드를 확인해주세요.")

with tab3:
    st.header("AI 어시스턴트 (내부 데이터 질문)", anchor=False)
    st.info("업로드된 엑셀 파일의 내용에 대해 궁금한 점을 질문해보세요.")
    # (세션 관리 및 채팅 로직은 이전과 동일하게 유지)
