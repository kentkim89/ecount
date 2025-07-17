import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import google.generativeai as genai
import re

# --- Streamlit 페이지 설정 ---
st.set_page_config(
    page_title="고래미 주식회사 AI 비교 분석 대시보드",
    page_icon="🐳",
    layout="wide"
)

# --- 사용자 정의 영역 및 함수 ---
EXCLUDED_ITEMS = [
    "경영지원부 기타코드", "추가할인", "픽업할인",
    "KPP 파렛트(빨간색) (N11)", "KPP 파렛트(파란색) (N12)",
    "KPP 파렛트 (빨간색)", "KPP 파렛트 (파란색)",
    "[부재료]NO.320_80g전용_트레이_홈플러스전용_KCP",
    "미니락교 20g 이엔 (세트상품)", "초대리 50g 주비 (세트상품)"
]
EXCLUDED_KEYWORDS_PATTERN = r'택배비|운송비|수수료|쿠폰할인|추가할인|픽업할인'

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

def process_uploaded_file(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file, sheet_name="판매현황", header=1)
        expected_columns = ["일자-No.", "배송상태", "창고명", "거래처코드", "거래처명", "품목코드", "품목명(규격)", "박스", "낱개수량", "단가", "공급가액", "부가세", "외화금액", "합계", "적요", "쇼핑몰고객명", "시리얼/로트No.", "외포장_여부", "전표상태", "전표상태.1", "추가문자형식2", "포장박스", "추가숫자형식1", "사용자지정숫자1", "사용자지정숫자2"]
        df.columns = expected_columns[:len(df.columns)]
        numeric_cols = ["박스", "공급가액", "합계"]
        for col in numeric_cols:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df.dropna(subset=['거래처명', '품목명(규격)', '일자-No.'], inplace=True)
        # 오류 방지를 위해 to_datetime 전에 에러 핸들링 강화
        df['일자'] = pd.to_datetime(df['일자-No.'].apply(lambda x: str(x).split('-').strip()), errors='coerce')
        df.dropna(subset=['일자'], inplace=True) # 날짜 변환 실패한 행 제거
        df['년월'] = df['일자'].dt.to_period('M')

        mask_static = df['품목명(규격)'].str.strip().isin(EXCLUDED_ITEMS)
        mask_pattern = df['품목명(규격)'].str.contains(EXCLUDED_KEYWORDS_PATTERN, na=False)
        combined_mask = mask_static | mask_pattern
        
        analysis_df = df[~combined_mask].copy()
        analysis_df['제품명'] = analysis_df['품목명(규격)'].apply(clean_product_name)
        analysis_df = analysis_df[analysis_df['제품명'].str.strip() != '']
        return df, analysis_df
    except Exception as e:
        st.error(f"파일 처리 중 오류: {e}")
        return None, None

def get_comparison_analysis_report(model, kpi_df, growth_cust, decline_cust, growth_prod, decline_prod, new_cust, lost_prod):
    if model is None: return "AI 모델이 연결되지 않았습니다."
    
    prompt = f"""
    당신은 '고래미 주식회사'의 수석 데이터 분석가 **'고래미 AI'** 입니다.
    아래 제공된 두 기간의 판매 실적 비교 데이터를 분석하여, 경영진을 위한 실행 중심의 보고서를 작성해주세요.

    ### 1. 주요 성과 비교 (KPI Summary)
    {kpi_df.to_markdown(index=False)}

    ### 2. 주요 변동 사항 분석 (Key Changes Analysis)
    **가. 거래처 동향**
    - **매출 급상승 TOP3:** {', '.join(growth_cust.head(3)['거래처명'])}
    - **매출 급하락 TOP3:** {', '.join(decline_cust.head(3)['거래처명'])}
    - **신규 거래처 수:** {len(new_cust)} 곳

    **나. 제품 동향**
    - **매출 급상승 TOP3:** {', '.join(growth_prod.head(3)['제품명'])}
    - **매출 급하락 TOP3:** {', '.join(decline_prod.head(3)['제품명'])}
    - **판매 중단(이탈) 상품 수:** {len(lost_prod)} 종

    ### 3. 종합 분석 및 다음 달 전략 제안
    위 데이터를 바탕으로 아래 질문에 대해 심층적으로 답변해주세요.

    **가. 무엇이 이런 변화를 만들었는가? (Root Cause Analysis)**
    - 매출이 **상승**했다면, 어떤 업체와 제품이 성장을 주도했나요? 그 이유는 무엇이라고 추측하나요?
    - 매출이 **하락**했다면, 어떤 업체와 제품의 부진이 가장 큰 영향을 미쳤나요?
    - 신규 거래처의 발생과 기존 거래처의 매출 하락 사이에 연관성이 있나요?

    **나. 그래서, 우리는 무엇을 해야 하는가? (Actionable Recommendations)**
    - **(집중 관리)** 매출이 급상승한 거래처와 제품의 성장세를 이어가기 위해 다음 달에 어떤 활동을 해야 할까요? (예: 프로모션 연장, 물량 확대 제안)
    - **(위험 관리)** 매출이 급하락한 거래처와 제품에 대해서는 어떤 조치를 취해야 할까요? (예: 해피콜, 원인 파악, 재고 소진 계획)
    - **(기회 포착)** 신규 거래처를 충성 고객으로 만들기 위한 전략과, 이탈 상품의 재판매 또는 단종 여부 결정에 대한 당신의 의견을 제시해주세요.

    ---
    *보고서는 위 구조와 형식을 반드시 준수하여, 전문가의 시각으로 작성해주세요.*
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 리포트 생성 중 오류: {e}"

# --- Streamlit 앱 메인 로직 ---
st.title("🐳 고래미 주식회사 AI 비교 분석 대시보드")

g_model = None
try:
    g_model = configure_google_ai(st.secrets["GOOGLE_API_KEY"])
    st.sidebar.success("✅ AI 모델이 성공적으로 연결되었습니다.")
except KeyError:
    st.sidebar.error("⚠️ GOOGLE_API_KEY가 없습니다. Secrets에 추가해주세요.")
except Exception:
    st.sidebar.error("🚨 AI 모델 연결에 실패했습니다.")

with st.sidebar:
    st.header("1. 데이터 업로드")
    uploaded_file = st.file_uploader("📂 판매현황 엑셀 파일을 업로드하세요.", type=["xlsx", "xls"])
    
    # 세션 스테이트 초기화
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False

    if uploaded_file:
        full_df, analysis_df = process_uploaded_file(uploaded_file)
        if full_df is not None:
            st.session_state.full_df = full_df
            st.session_state.analysis_df = analysis_df
            st.session_state.data_loaded = True
            
            unique_months = sorted(analysis_df['년월'].unique(), reverse=True)
            if len(unique_months) >= 2:
                st.header("2. 분석할 월 선택")
                # 월 선택 위젯에 key를 부여하여 상태 유지
                selected_curr_month = st.selectbox("**이번달 (기준 월)**", unique_months, index=0, key='current_month')
                selected_prev_month = st.selectbox("**지난달 (비교 월)**", unique_months, index=1, key='previous_month')
                
                if selected_curr_month == selected_prev_month:
                    st.warning("기준 월과 비교 월은 다르게 선택해야 합니다.")
                    st.session_state.analysis_ready = False
                else:
                    st.session_state.analysis_ready = True
                    st.success("월 선택 완료! 탭을 확인하세요.")
            else:
                st.warning("파일에 최소 2개월 이상의 데이터가 있어야 비교 분석이 가능합니다.")
                st.session_state.analysis_ready = False
        else:
            st.session_state.data_loaded = False
            st.session_state.analysis_ready = False


# --- 메인 대시보드 ---
if 'analysis_ready' in st.session_state and st.session_state.analysis_ready:
    curr_month = st.session_state.current_month
    prev_month = st.session_state.previous_month

    full_curr_df = st.session_state.full_df[st.session_state.full_df['년월'] == curr_month]
    full_prev_df = st.session_state.full_df[st.session_state.full_df['년월'] == prev_month]
    curr_df = st.session_state.analysis_df[st.session_state.analysis_df['년월'] == curr_month]
    prev_df = st.session_state.analysis_df[st.session_state.analysis_df['년월'] == prev_month]
    
    tab1, tab2 = st.tabs([" 성과 비교 대시보드", " AI 종합 분석 및 예측"])

    with tab1:
        st.header(f"{curr_month} vs {prev_month} 성과 비교", anchor=False)
        
        kpi_data = []
        for period, df_full, df_analysis in [(prev_month.strftime('%Y-%m'), full_prev_df, prev_df), (curr_month.strftime('%Y-%m'), full_curr_df, curr_df)]:
            kpi_data.append({
                '기간': period,
                '총 공급가액': df_full['공급가액'].sum(),
                '총 매출': df_full['합계'].sum(),
                '총 판매 박스': df_analysis['박스'].sum(),
                '거래처 수': df_analysis['거래처명'].nunique()
            })
        
        prev_kpi, curr_kpi = kpi_data, kpi_data
        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("총 공급가액", f"{curr_kpi['총 공급가액']:,.0f} 원", f"{curr_kpi['총 공급가액'] - prev_kpi['총 공급가액']:,.0f} 원")
        col2.metric("총 매출", f"{curr_kpi['총 매출']:,.0f} 원", f"{curr_kpi['총 매출'] - prev_kpi['총 매출']:,.0f} 원")
        col3.metric("총 판매 박스", f"{curr_kpi['총 판매 박스']:,.0f} 개", f"{curr_kpi['총 판매 박스'] - prev_kpi['총 판매 박스']:,.0f} 개")
        col4.metric("거래처 수", f"{curr_kpi['거래처 수']} 곳", f"{curr_kpi['거래처 수'] - prev_kpi['거래처 수']} 곳")
        st.divider()

        prev_cust_sales = prev_df.groupby('거래처명')['합계'].sum()
        curr_cust_sales = curr_df.groupby('거래처명')['합계'].sum()
        prev_prod_sales = prev_df.groupby('제품명')['합계'].sum()
        curr_prod_sales = curr_df.groupby('제품명')['합계'].sum()

        cust_comparison = pd.merge(prev_cust_sales, curr_cust_sales, on='거래처명', how='outer', suffixes=(f'_{prev_month}', f'_{curr_month}')).fillna(0)
        cust_comparison['변동액'] = cust_comparison[f'합계_{curr_month}'] - cust_comparison[f'합계_{prev_month}']
        
        prod_comparison = pd.merge(prev_prod_sales, curr_prod_sales, on='제품명', how='outer', suffixes=(f'_{prev_month}', f'_{curr_month}')).fillna(0)
        prod_comparison['변동액'] = prod_comparison[f'합계_{curr_month}'] - prod_comparison[f'합계_{prev_month}']

        top_growth_cust = cust_comparison.nlargest(10, '변동액').reset_index()
        top_decline_cust = cust_comparison.nsmallest(10, '변동액').reset_index()
        top_growth_prod = prod_comparison.nlargest(10, '변동액').reset_index()
        top_decline_prod = prod_comparison.nsmallest(10, '변동액').reset_index()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📈 매출 급상승 업체 TOP 10", anchor=False)
            st.dataframe(top_growth_cust.style.format({f'합계_{prev_month}': '{:,.0f}', f'합계_{curr_month}': '{:,.0f}', '변동액': '{:+,.0f}'}))
        with col2:
            st.subheader("📉 매출 급하락 업체 TOP 10", anchor=False)
            st.dataframe(top_decline_cust.style.format({f'합계_{prev_month}': '{:,.0f}', f'합계_{curr_month}': '{:,.0f}', '변동액': '{:+,.0f}'}))
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🚀 매출 급상승 상품 TOP 10", anchor=False)
            st.dataframe(top_growth_prod.style.format({f'합계_{prev_month}': '{:,.0f}', f'합계_{curr_month}': '{:,.0f}', '변동액': '{:+,.0f}'}))
        with col2:
            st.subheader("🐌 매출 급하락 상품 TOP 10", anchor=False)
            st.dataframe(top_decline_prod.style.format({f'합계_{prev_month}': '{:,.0f}', f'합계_{curr_month}': '{:,.0f}', '변동액': '{:+,.0f}'}))
        
        prev_cust_set = set(prev_cust_sales.index); curr_cust_set = set(curr_cust_sales.index)
        prev_prod_set = set(prev_prod_sales.index); curr_prod_set = set(curr_prod_sales.index)
        new_customers = list(curr_cust_set - prev_cust_set)
        lost_products = list(prev_prod_set - curr_prod_set)

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("✨ 신규 거래처", anchor=False); st.dataframe(pd.DataFrame(new_customers, columns=["거래처명"]), height=200)
        with col2:
            st.subheader("👋 판매 중단(이탈) 상품", anchor=False); st.dataframe(pd.DataFrame(lost_products, columns=["제품명"]), height=200)

    with tab2:
        st.header(f"AI 종합 분석 및 { (curr_month + 1).strftime('%Y-%m') } 예측", anchor=False)
        st.info("지난 두 달간의 데이터를 기반으로 다음 달의 성과를 예측하고, AI가 종합적인 전략을 제시합니다.")
        
        growth_rate = (curr_kpi['총 매출'] / prev_kpi['총 매출']) if prev_kpi['총 매출'] > 0 else 1
        predicted_sales = curr_kpi['총 매출'] * growth_rate
        
        prod_comparison['성장률'] = (prod_comparison[f'합계_{curr_month}'] / prod_comparison[f'합계_{prev_month}']).fillna(1)
        prod_comparison.loc[prod_comparison['성장률'] == float('inf'), '성장률'] = 1.5
        prod_comparison['다음달_예상매출'] = prod_comparison[f'합계_{curr_month}'] * prod_comparison['성장률']
        top_predicted_prod = prod_comparison.nlargest(10, '다음달_예상매출').reset_index()

        st.subheader("🔮 다음 달 성과 예측", anchor=False)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("다음 달 예상 총 매출", f"{predicted_sales:,.0f} 원", f"{predicted_sales - curr_kpi['총 매출']:+,.0f} 원 vs {curr_month.strftime('%Y-%m')}", help=f"{prev_month.strftime('%Y-%m')} 대비 성장률 {growth_rate:.2%}를 적용한 예측치입니다.")
        with col2:
            st.markdown(f"**🔥 { (curr_month + 1).strftime('%Y-%m') } 주력 판매 예상 상품 TOP 10**")
            st.dataframe(top_predicted_prod[['제품명', '다음달_예상매출']].style.format({'다음달_예상매출': '{:,.0f}'}), height=300)

        st.divider()
        st.subheader("🤖 AI 종합 분석 리포트 (by 고래미 AI)", anchor=False)
        
        if st.button("📈 비교 분석 리포트 생성"):
            if g_model:
                with st.spinner("고래미 AI가 두 달치 데이터를 비교 분석하여 전략을 수립하고 있습니다..."):
                    kpi_df = pd.DataFrame([prev_kpi, curr_kpi])
                    report = get_comparison_analysis_report(g_model, kpi_df, top_growth_cust, top_decline_cust, top_growth_prod, top_decline_prod, new_customers, lost_products)
                    st.markdown(report)
            else:
                st.warning("AI 모델이 연결되지 않았습니다.")
else:
    # --- 오타 수정된 부분 ---
    st.info("👈 사이드바에서 판매현황 엑셀 파일을 업로드하고, 분석할 두 개의 월을 선택하여 비교 분석을 시작하세요.")
