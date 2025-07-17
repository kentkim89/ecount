import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
import re

# --- Streamlit 페이지 설정 ---
st.set_page_config(
    page_title="고래미 주식회사 AI BI 대시보드",
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

def process_and_analyze_data(df):
    """정제 및 분석용 데이터프레임을 생성하는 중앙 함수"""
    df.dropna(subset=['거래처명', '품목명(규격)', '일자-No.'], inplace=True)
    df['일자'] = pd.to_datetime(df['일자-No.'].apply(lambda x: str(x).split('-').strip()), errors='coerce')
    df.dropna(subset=['일자'], inplace=True)
    df['년월'] = df['일자'].dt.to_period('M')
    mask_static = df['품목명(규격)'].str.strip().isin(EXCLUDED_ITEMS)
    mask_pattern = df['품목명(규격)'].str.contains(EXCLUDED_KEYWORDS_PATTERN, na=False)
    combined_mask = mask_static | mask_pattern
    analysis_df = df[~combined_mask].copy()
    analysis_df['제품명'] = analysis_df['품목명(규격)'].apply(clean_product_name)
    analysis_df = analysis_df[analysis_df['제품명'].str.strip() != '']
    return analysis_df

def get_comparison_analysis_report(model, kpi_df, growth_cust, decline_cust, growth_prod, decline_prod, new_cust, lost_prod):
    if model is None: return "AI 모델이 연결되지 않았습니다."
    prompt = f"""
    당신은 '고래미 주식회사'의 수석 데이터 분석가 **'고래미 AI'** 입니다.
    아래 제공된 두 기간의 판매 실적 비교 데이터를 분석하여, 경영진을 위한 실행 중심의 보고서를 작성해주세요.
    ### 1. 주요 성과 비교 (KPI Summary)
    {kpi_df.to_markdown(index=False)}
    ### 2. 주요 변동 사항 분석 (Key Changes Analysis)
    **가. 거래처 동향:** 매출 급상승 TOP3: {', '.join(growth_cust.head(3)['거래처명'])}, 매출 급하락 TOP3: {', '.join(decline_cust.head(3)['거래처명'])}, 신규 거래처 수: {len(new_cust)} 곳
    **나. 제품 동향:** 매출 급상승 TOP3: {', '.join(growth_prod.head(3)['제품명'])}, 매출 급하락 TOP3: {', '.join(decline_prod.head(3)['제품명'])}, 판매 중단 상품 수: {len(lost_prod)} 종
    ### 3. 종합 분석 및 다음 달 전략 제안
    **가. 무엇이 이런 변화를 만들었는가? (Root Cause Analysis):** 매출이 **상승**했다면, 어떤 업체와 제품이 성장을 주도했나요? 그 이유는 무엇이라고 추측하나요? 매출이 **하락**했다면, 어떤 업체와 제품의 부진이 가장 큰 영향을 미쳤나요?
    **나. 그래서, 우리는 무엇을 해야 하는가? (Actionable Recommendations):** **(집중 관리)** 성장세를 이어가기 위한 활동은? **(위험 관리)** 부진 항목에 대한 조치는? **(기회 포착)** 신규 거래처를 충성 고객으로 만들 전략은?
    ---
    *보고서는 위 구조와 형식을 반드시 준수하여, 전문가의 시각으로 작성해주세요.*
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e: return f"AI 리포트 생성 중 오류: {e}"

# --- Streamlit 앱 메인 로직 ---
st.title("🐳 고래미 주식회사 AI BI 대시보드 (데이터 누적형)")

g_model = None
conn = None
try:
    g_model = configure_google_ai(st.secrets["GOOGLE_API_KEY"])
    conn = st.connection("g-sheets-connection", type=GSheetsConnection)
    st.sidebar.success("✅ Google AI & Sheets API가 연결되었습니다.")
except Exception as e:
    st.sidebar.error(f"🚨 API 연결 실패: Secrets 설정을 확인하세요. ({e})")

# --- 데이터 관리 (사이드바) ---
with st.sidebar:
    st.header("데이터 관리")
    
    if conn:
        try:
            existing_data = conn.read(worksheet="판매현황_원본", usecols=list(range(25)), ttl="10s")
            existing_data.columns = ["일자-No.", "배송상태", "창고명", "거래처코드", "거래처명", "품목코드", "품목명(규격)", "박스", "낱개수량", "단가", "공급가액", "부가세", "외화금액", "합계", "적요", "쇼핑몰고객명", "시리얼/로트No.", "외포장_여부", "전표상태", "전표상태.1", "추가문자형식2", "포장박스", "추가숫자형식1", "사용자지정숫자1", "사용자지정숫자2"]
            existing_data['년월'] = pd.to_datetime(existing_data['일자-No.'].astype(str).str.split('-').str.str.strip(), errors='coerce').dt.to_period('M')
            st.info(f"**현재 저장된 데이터:**\n- 총 **{len(existing_data)}** 건\n- 기간: **{existing_data['년월'].min()} ~ {existing_data['년월'].max()}**")
            st.session_state.db_data = existing_data
        except Exception:
            st.warning("`판매현황_원본` 시트를 찾을 수 없습니다. 새 데이터를 업로드하여 시작하세요.")
            st.session_state.db_data = pd.DataFrame()
    
    uploaded_file = st.file_uploader("📂 **신규 월별 데이터**를 업로드하여 추가/수정하세요.", type=["xlsx", "xls"])
    if uploaded_file and conn:
        new_df = pd.read_excel(uploaded_file, sheet_name="판매현황", header=1)
        new_df.columns = ["일자-No.", "배송상태", "창고명", "거래처코드", "거래처명", "품목코드", "품목명(규격)", "박스", "낱개수량", "단가", "공급가액", "부가세", "외화금액", "합계", "적요", "쇼핑몰고객명", "시리얼/로트No.", "외포장_여부", "전표상태", "전표상태.1", "추가문자형식2", "포장박스", "추가숫자형식1", "사용자지정숫자1", "사용자지정숫자2"][:len(new_df.columns)]
        new_df['년월'] = pd.to_datetime(new_df['일자-No.'].astype(str).str.split('-').str.str.strip(), errors='coerce').dt.to_period('M')
        
        updated_month = new_df['년월'].dropna().unique()
        
        if 'db_data' in st.session_state and updated_month in st.session_state.db_data['년월'].unique():
            if st.button(f"덮어쓰기: {updated_month} 데이터 업데이트"):
                existing_data_filtered = st.session_state.db_data[st.session_state.db_data['년월'] != updated_month]
                updated_df = pd.concat([existing_data_filtered, new_df], ignore_index=True)
                conn.update(worksheet="판매현황_원본", data=updated_df)
                st.success(f"{updated_month} 데이터를 성공적으로 업데이트했습니다!")
                st.rerun()
        else:
            if st.button(f"추가하기: {updated_month} 데이터 저장"):
                updated_df = pd.concat([st.session_state.db_data, new_df], ignore_index=True)
                conn.update(worksheet="판매현황_원본", data=updated_df)
                st.success(f"{updated_month} 데이터를 성공적으로 추가했습니다!")
                st.rerun()

# --- 메인 대시보드 ---
if 'db_data' in st.session_state and not st.session_state.db_data.empty:
    full_df = st.session_state.db_data
    analysis_df = process_and_analyze_data(full_df.copy())
    
    unique_months = sorted(analysis_df['년월'].unique(), reverse=True)
    
    if len(unique_months) >= 2:
        st.header("기간 선택")
        c1, c2 = st.columns(2)
        selected_curr_month = c1.selectbox("**이번달 (기준 월)**", unique_months, index=0, key='current_month')
        selected_prev_month = c2.selectbox("**지난달 (비교 월)**", unique_months, index=1, key='previous_month')

        if selected_curr_month != selected_prev_month:
            curr_df = analysis_df[analysis_df['년월'] == selected_curr_month]
            prev_df = analysis_df[analysis_df['년월'] == selected_prev_month]
            full_curr_df = full_df[full_df['년월'] == selected_curr_month]
            full_prev_df = full_df[full_df['년월'] == selected_prev_month]

            tab1, tab2, tab3 = st.tabs(["📊 성과 비교 대시보드", "📈 장기 추세 분석", "🤖 AI 종합 분석"])

            with tab1:
                st.header(f"{selected_curr_month} vs {selected_prev_month} 성과 비교", anchor=False)
                kpi_data = []
                for period, df_full, df_analysis in [(selected_prev_month.strftime('%Y-%m'), full_prev_df, prev_df), (selected_curr_month.strftime('%Y-%m'), full_curr_df, curr_df)]:
                    kpi_data.append({'기간': period, '총 공급가액': df_full['공급가액'].sum(), '총 매출': df_full['합계'].sum(), '총 판매 박스': df_analysis['박스'].sum(), '거래처 수': df_analysis['거래처명'].nunique()})
                prev_kpi, curr_kpi = kpi_data, kpi_data
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("총 공급가액", f"{curr_kpi['총 공급가액']:,.0f} 원", f"{curr_kpi['총 공급가액'] - prev_kpi['총 공급가액']:,.0f} 원")
                c2.metric("총 매출", f"{curr_kpi['총 매출']:,.0f} 원", f"{curr_kpi['총 매출'] - prev_kpi['총 매출']:,.0f} 원")
                c3.metric("총 판매 박스", f"{curr_kpi['총 판매 박스']:,.0f} 개", f"{curr_kpi['총 판매 박스'] - prev_kpi['총 판매 박스']:,.0f} 개")
                c4.metric("거래처 수", f"{curr_kpi['거래처 수']} 곳", f"{curr_kpi['거래처 수'] - prev_kpi['거래처 수']} 곳")
                
                prev_cust_sales = prev_df.groupby('거래처명')['합계'].sum()
                curr_cust_sales = curr_df.groupby('거래처명')['합계'].sum()
                cust_comparison = pd.merge(prev_cust_sales, curr_cust_sales, on='거래처명', how='outer', suffixes=(f'_{selected_prev_month}', f'_{selected_curr_month}')).fillna(0)
                cust_comparison['변동액'] = cust_comparison[f'합계_{selected_curr_month}'] - cust_comparison[f'합계_{selected_prev_month}']
                
                prev_prod_sales = prev_df.groupby('제품명')['합계'].sum()
                curr_prod_sales = curr_df.groupby('제품명')['합계'].sum()
                prod_comparison = pd.merge(prev_prod_sales, curr_prod_sales, on='제품명', how='outer', suffixes=(f'_{selected_prev_month}', f'_{selected_curr_month}')).fillna(0)
                prod_comparison['변동액'] = prod_comparison[f'합계_{selected_curr_month}'] - prod_comparison[f'합계_{selected_prev_month}']
                
                top_growth_cust = cust_comparison.nlargest(10, '변동액').reset_index()
                top_decline_cust = cust_comparison.nsmallest(10, '변동액').reset_index()
                top_growth_prod = prod_comparison.nlargest(10, '변동액').reset_index()
                top_decline_prod = prod_comparison.nsmallest(10, '변동액').reset_index()
                
                st.divider()
                c1, c2 = st.columns(2)
                with c1: st.subheader("📈 매출 급상승 업체 TOP 10"); st.dataframe(top_growth_cust)
                with c2: st.subheader("📉 매출 급하락 업체 TOP 10"); st.dataframe(top_decline_cust)
                c1, c2 = st.columns(2)
                with c1: st.subheader("🚀 매출 급상승 상품 TOP 10"); st.dataframe(top_growth_prod)
                with c2: st.subheader("🐌 매출 급하락 상품 TOP 10"); st.dataframe(top_decline_prod)

            with tab2:
                st.header("장기 추세 분석", anchor=False)
                monthly_sales = analysis_df.groupby('년월')['합계'].sum().reset_index()
                monthly_sales['년월'] = monthly_sales['년월'].dt.to_timestamp()
                fig = px.line(monthly_sales, x='년월', y='합계', title='전체 기간 월별 매출 추이', markers=True)
                fig.update_layout(yaxis_title="월 총매출(원)", xaxis_title="년월")
                st.plotly_chart(fig, use_container_width=True)

            with tab3:
                st.header("AI 종합 분석 리포트", anchor=False)
                if st.button("📈 비교 분석 기반 AI 리포트 생성"):
                    if g_model:
                        with st.spinner("고래미 AI가 선택된 두 달치 데이터를 비교 분석하여 전략을 수립하고 있습니다..."):
                            kpi_df = pd.DataFrame(kpi_data)
                            prev_cust_set = set(prev_cust_sales.index); curr_cust_set = set(curr_cust_sales.index)
                            prev_prod_set = set(prev_prod_sales.index); curr_prod_set = set(curr_prod_sales.index)
                            new_customers = list(curr_cust_set - prev_cust_set)
                            lost_products = list(prev_prod_set - curr_prod_set)
                            report = get_comparison_analysis_report(g_model, kpi_df, top_growth_cust, top_decline_cust, top_growth_prod, top_decline_prod, new_customers, lost_products)
                            st.markdown(report)
                    else: st.warning("AI 모델이 연결되지 않았습니다.")

        else:
            st.error("기준 월과 비교 월은 다르게 선택해야 합니다.")
    else:
        st.warning("저장된 데이터가 2개월 미만입니다. 데이터를 더 추가하여 비교 분석을 활성화하세요.")
else:
    # --- 오타 수정된 부분 ---
    st.info("👈 사이드바에서 판매현황 엑셀 파일을 업로드하여 분석을 시작하세요.")
