import streamlit as st
import pandas as pd
import plotly.express as px
import google.generativeai as genai
import re

# --- Streamlit 페이지 설정 ---
st.set_page_config(
    page_title="고래미 주식회사 AI 판매 분석 대시보드",
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

@st.cache_data
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
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"Google AI 모델 설정 실패: {e}")
        st.stop()

@st.cache_data
def process_uploaded_file(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file, sheet_name="판매현황", header=1)
        expected_columns = ["일자-No.", "배송상태", "창고명", "거래처코드", "거래처명", "품목코드", "품목명(규격)", "박스", "낱개수량", "단가", "공급가액", "부가세", "외화금액", "합계", "적요", "쇼핑몰고객명", "시리얼/로트No.", "외포장_여부", "전표상태", "전표상태.1", "추가문자형식2", "포장박스", "추가숫자형식1", "사용자지정숫자1", "사용자지정숫자2"]
        df.columns = expected_columns[:len(df.columns)]
        numeric_cols = ["박스", "공급가액", "합계"]
        for col in numeric_cols:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df.dropna(subset=['거래처명', '품목명(규격)', '일자-No.'], inplace=True)
        df['일자'] = pd.to_datetime(df['일자-No.'].astype(str).str.split('-').str[0].str.strip(), errors='coerce')
        df.dropna(subset=['일자'], inplace=True)
        df['년월'] = df['일자'].dt.to_period('M')
        
        # 전체 데이터(df)와 분석용 데이터(analysis_df) 분리
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

def get_comparison_analysis_report(_model, kpi_df, growth_cust, decline_cust, growth_prod, decline_prod, new_cust, lost_prod):
    prompt = f"""
    당신은 '고래미 주식회사'의 수석 데이터 분석가 **'고래미 AI'** 입니다.
    아래 제공된 두 기간의 판매 실적 비교 데이터를 분석하여, 경영진을 위한 실행 중심의 보고서를 작성해주세요.
    ### 1. 주요 성과 비교 (KPI Summary)
    {kpi_df.to_markdown(index=False)}
    ### 2. 주요 변동 사항 분석 (Key Changes Analysis)
    **가. 거래처 동향:**
    - **매출 급상승 TOP3:** {', '.join(growth_cust.head(3)['거래처명'])}
    - **매출 급하락 TOP3:** {', '.join(decline_cust.head(3)['거래처명'])}
    - **신규 거래처 수:** {len(new_cust)} 곳
    **나. 제품 동향:**
    - **매출 급상승 TOP3:** {', '.join(growth_prod.head(3)['제품명'])}
    - **매출 급하락 TOP3:** {', '.join(decline_prod.head(3)['제품명'])}
    - **판매 중단(이탈) 상품 수:** {len(lost_prod)} 종
    ### 3. 종합 분석 및 다음 달 전략 제안
    **가. 무엇이 이런 변화를 만들었는가? (Root Cause Analysis):**
    - 매출이 **상승**했다면, 어떤 업체와 제품이 성장을 주도했나요? 그 이유는 무엇이라고 추측하나요?
    - 매출이 **하락**했다면, 어떤 업체와 제품의 부진이 가장 큰 영향을 미쳤나요?
    - 신규 거래처의 발생과 기존 거래처의 매출 하락 사이에 연관성이 있나요?
    **나. 그래서, 우리는 무엇을 해야 하는가? (Actionable Recommendations):**
    - **(집중 관리)** 매출이 급상승한 거래처와 제품의 성장세를 이어가기 위해 다음 달에 어떤 활동을 해야 할까요?
    - **(위험 관리)** 매출이 급하락한 거래처와 제품에 대해서는 어떤 조치를 취해야 할까요?
    - **(기회 포착)** 신규 거래처를 충성 고객으로 만들기 위한 전략과, 이탈 상품의 재판매 또는 단종 여부 결정에 대한 당신의 의견을 제시해주세요.
    ---
    *보고서는 위 구조와 형식을 반드시 준수하여, 전문가의 시각으로 작성해주세요.*
    """
    try:
        response = _model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 리포트 생성 중 오류: {e}"

# --- 앱 초기화 ---
st.title("🐳 고래미 주식회사 AI 판매 분석 대시보드")
g_model = None
try:
    g_model = configure_google_ai(st.secrets["GOOGLE_API_KEY"])
    st.sidebar.success("✅ AI 모델이 성공적으로 연결되었습니다.")
except KeyError:
    st.sidebar.error("⚠️ GOOGLE_API_KEY를 Secrets에 추가해주세요.")
except Exception as e:
    st.sidebar.error(f"🚨 AI 모델 연결 실패: {e}")

# --- 데이터 업로드 ---
with st.sidebar:
    st.header("데이터 업로드")
    uploaded_file = st.file_uploader("📂 판매현황 엑셀 파일을 업로드하세요.", type=["xlsx", "xls"])

# --- 메인 대시보드 ---
if uploaded_file:
    with st.spinner("대용량 파일을 처리하는 중입니다. 잠시만 기다려주세요..."):
        full_df, analysis_df = process_uploaded_file(uploaded_file)
    
    if analysis_df is not None:
        st.success("파일 처리 완료! 분석을 시작합니다.")
        unique_months = sorted(analysis_df['년월'].unique(), reverse=True)
        
        if len(unique_months) >= 2:
            tab1, tab2, tab3 = st.tabs(["[1] 장기 추세 분석", "[2] 성과 비교 분석", "[3] AI 종합 분석"])

            with tab1:
                st.header("장기 추세 분석")
                st.info("업로드된 파일의 전체 기간에 대한 성과 추이를 확인합니다.")
                monthly_sales = analysis_df.groupby('년월')['합계'].sum().reset_index()
                monthly_sales['년월'] = monthly_sales['년월'].dt.to_timestamp()
                fig = px.line(monthly_sales, x='년월', y='합계', title='전체 기간 월별 매출 추이', markers=True, template="plotly_white")
                fig.update_layout(yaxis_title="월 총매출(원)", xaxis_title="년월")
                st.plotly_chart(fig, use_container_width=True)

            with tab2:
                st.header("성과 비교 분석")
                st.info("비교하고 싶은 두 기간을 선택하여 성과를 분석하세요.")
                c1, c2 = st.columns(2)
                curr_month_select = c1.selectbox("**이번달 (기준 월)**", unique_months, index=0)
                prev_month_select = c2.selectbox("**지난달 (비교 월)**", unique_months, index=1)

                if curr_month_select != prev_month_select:
                    curr_df = analysis_df[analysis_df['년월'] == curr_month_select]
                    prev_df = analysis_df[analysis_df['년월'] == prev_month_select]
                    full_curr_df = full_df[full_df['년월'] == curr_month_select]
                    full_prev_df = full_df[full_df['년월'] == prev_month_select]

                    # KPI 계산
                    kpi_data = []
                    for period, df_full_period, df_analysis_period in [(prev_month_select.strftime('%Y-%m'), full_prev_df, prev_df), (curr_month_select.strftime('%Y-%m'), full_curr_df, curr_df)]:
                        kpi_data.append({'기간': period, '총 공급가액': df_full_period['공급가액'].sum(), '총 매출': df_full_period['합계'].sum(), '총 판매 박스': df_analysis_period['박스'].sum(), '거래처 수': df_analysis_period['거래처명'].nunique()})
                    prev_kpi, curr_kpi = kpi_data[0], kpi_data[1]
                    
                    st.subheader(f"{curr_month_select} vs {prev_month_select} 핵심 지표 비교")
                    c1,c2,c3,c4 = st.columns(4)
                    c1.metric("총 공급가액", f"{curr_kpi['총 공급가액']:,.0f} 원", f"{curr_kpi['총 공급가액'] - prev_kpi['총 공급가액']:,.0f} 원")
                    c2.metric("총 매출", f"{curr_kpi['총 매출']:,.0f} 원", f"{curr_kpi['총 매출'] - prev_kpi['총 매출']:,.0f} 원")
                    c3.metric("총 판매 박스", f"{curr_kpi['총 판매 박스']:,.0f} 개", f"{curr_kpi['총 판매 박스'] - prev_kpi['총 판매 박스']:,.0f} 개")
                    c4.metric("거래처 수", f"{curr_kpi['거래처 수']} 곳", f"{curr_kpi['거래처 수'] - prev_kpi['거래처 수']} 곳")

                    # 비교 테이블 생성
                    st.divider()
                    prev_cust_sales = prev_df.groupby('거래처명')['합계'].sum()
                    curr_cust_sales = curr_df.groupby('거래처명')['합계'].sum()
                    cust_comparison = pd.merge(prev_cust_sales, curr_cust_sales, on='거래처명', how='outer', suffixes=(f'_{prev_month_select}', f'_{curr_month_select}')).fillna(0)
                    cust_comparison['변동액'] = cust_comparison[f'합계_{curr_month_select}'] - cust_comparison[f'합계_{prev_month_select}']
                    
                    prev_prod_sales = prev_df.groupby('제품명')['합계'].sum()
                    curr_prod_sales = curr_df.groupby('제품명')['합계'].sum()
                    prod_comparison = pd.merge(prev_prod_sales, curr_prod_sales, on='제품명', how='outer', suffixes=(f'_{prev_month_select}', f'_{curr_month_select}')).fillna(0)
                    prod_comparison['변동액'] = prod_comparison[f'합계_{curr_month_select}'] - prod_comparison[f'합계_{prev_month_select}']
                    
                    top_growth_cust = cust_comparison.nlargest(10, '변동액').reset_index()
                    top_decline_cust = cust_comparison.nsmallest(10, '변동액').reset_index()
                    top_growth_prod = prod_comparison.nlargest(10, '변동액').reset_index()
                    top_decline_prod = prod_comparison.nsmallest(10, '변동액').reset_index()
                    
                    c1, c2 = st.columns(2)
                    with c1: st.subheader("📈 매출 급상승 업체 TOP 10"); st.dataframe(top_growth_cust.style.format(formatter="{:,.0f}"))
                    with c2: st.subheader("📉 매출 급하락 업체 TOP 10"); st.dataframe(top_decline_cust.style.format(formatter="{:,.0f}"))
                    c1, c2 = st.columns(2)
                    with c1: st.subheader("🚀 매출 급상승 상품 TOP 10"); st.dataframe(top_growth_prod.style.format(formatter="{:,.0f}"))
                    with c2: st.subheader("🐌 매출 급하락 상품 TOP 10"); st.dataframe(top_decline_prod.style.format(formatter="{:,.0f}"))
                else:
                    st.warning("비교할 두 기간을 다르게 선택해주세요.")

            with tab3:
                st.header("AI 종합 분석")
                if 'curr_month_select' in locals() and 'prev_month_select' in locals() and curr_month_select != prev_month_select:
                    st.info(f"`{curr_month_select}`와 `{prev_month_select}`의 비교 데이터를 기반으로 AI가 종합 분석 및 전략을 제안합니다.")
                    if st.button("📈 AI 비교 분석 리포트 생성"):
                        if g_model:
                            with st.spinner("고래미 AI가 데이터를 비교 분석하여 전략을 수립하고 있습니다..."):
                                prev_cust_set = set(prev_df['거래처명'].unique()); curr_cust_set = set(curr_df['거래처명'].unique())
                                prev_prod_set = set(prev_df['제품명'].unique()); curr_prod_set = set(curr_df['제품명'].unique())
                                new_customers = list(curr_cust_set - prev_cust_set)
                                lost_products = list(prev_prod_set - curr_prod_set)
                                report = get_comparison_analysis_report(g_model, pd.DataFrame(kpi_data), top_growth_cust, top_decline_cust, top_growth_prod, top_decline_prod, new_customers, lost_products)
                                st.markdown(report)
                        else:
                            st.warning("AI 모델이 연결되지 않았습니다.")
                else:
                    st.warning("먼저 `성과 비교 분석` 탭에서 비교할 두 기간을 선택해주세요.")
        else:
            st.warning("파일에 최소 2개월 이상의 데이터가 있어야 비교 분석이 가능합니다.")
else:
    st.info("👈 사이드바에서 판매현황 엑셀 파일을 업로드하여 분석을 시작하세요.")
