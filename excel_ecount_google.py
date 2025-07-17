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
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"Google AI 모델 설정 실패: {e}")
        st.stop()

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
    try: return model.generate_content(prompt).text
    except Exception as e: return f"AI 리포트 생성 중 오류: {e}"

# --- 데이터 처리 함수 ---
def process_dataframe(df):
    expected_columns = ["일자-No.", "배송상태", "창고명", "거래처코드", "거래처명", "품목코드", "품목명(규격)", "박스", "낱개수량", "단가", "공급가액", "부가세", "외화금액", "합계", "적요", "쇼핑몰고객명", "시리얼/로트No.", "외포장_여부", "전표상태", "전표상태.1", "추가문자형식2", "포장박스", "추가숫자형식1", "사용자지정숫자1", "사용자지정숫자2"]
    df.columns = expected_columns[:len(df.columns)]
    numeric_cols = ["박스", "공급가액", "합계"]
    for col in numeric_cols:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    df.dropna(subset=['거래처명', '품목명(규격)', '일자-No.'], inplace=True)
    df['일자'] = pd.to_datetime(df['일자-No.'].astype(str).str.split('-').str[0].str.strip(), errors='coerce')
    df.dropna(subset=['일자'], inplace=True)
    df['년월'] = df['일자'].dt.to_period('M')
    return df

# --- 앱 초기화 ---
st.title("🐳 고래미 주식회사 AI BI 대시보드 (데이터 누적형)")

# 세션 상태 초기화
if 'db_data' not in st.session_state: st.session_state.db_data = pd.DataFrame()
if 'new_df_to_save' not in st.session_state: st.session_state.new_df_to_save = None
if 'upload_key' not in st.session_state: st.session_state.upload_key = 0

# --- API 및 DB 연결 ---
g_model, conn = None, None
try:
    g_model = configure_google_ai(st.secrets["GOOGLE_API_KEY"])
    conn = st.connection("g-sheets-connection", type=GSheetsConnection)
    st.sidebar.success("✅ Google AI & Sheets API가 연결되었습니다.")
except Exception as e:
    st.sidebar.error(f"🚨 API 연결 실패: Secrets 설정을 확인하세요.")
    st.stop()

# --- 데이터 관리 (사이드바) ---
with st.sidebar:
    st.header("데이터 관리")
    
    # 1. Google Sheets에서 현재 데이터 불러오기
    if conn:
        try:
            st.session_state.db_data = conn.read(worksheet="판매현황_원본", usecols=list(range(25)), ttl=10)
            status_df = process_dataframe(st.session_state.db_data.copy())
            st.info(f"**현재 DB 현황:** 총 **{len(status_df)}** 건 데이터")
            st.dataframe(status_df.groupby('년월').size().reset_index(name='데이터 건수').sort_values(by='년월', ascending=False), height=200)
        except Exception:
            st.warning("`판매현황_원본` 시트를 찾을 수 없습니다. 새 데이터를 업로드하여 시작하세요.")
            st.session_state.db_data = pd.DataFrame()
    
    # 2. 신규 데이터 업로드 UI
    uploaded_file = st.file_uploader(
        "📂 **월별 데이터**를 업로드하여 추가/수정하세요.",
        type=["xlsx", "xls"],
        key=f"uploader_{st.session_state.upload_key}"
    )

    if uploaded_file:
        try:
            new_df = pd.read_excel(uploaded_file, sheet_name="판매현황", header=1)
            new_df = process_dataframe(new_df)
            file_months = new_df['년월'].dropna().unique()

            if len(file_months) == 1:
                file_month = file_months[0]
                st.success(f"파일 검증 완료: '{file_month}' 데이터가 확인되었습니다.")
                st.session_state.new_df_to_save = new_df
                st.session_state.month_to_update = file_month
            else:
                st.error("업로드 파일에 여러 월의 데이터가 섞여 있거나, 날짜 형식이 잘못되었습니다.")
                st.session_state.new_df_to_save = None

    # 3. 데이터 저장 버튼
    if st.session_state.new_df_to_save is not None:
        if st.button(f"✅ DB에 '{st.session_state.month_to_update}' 데이터 저장 (덮어쓰기)"):
            with st.spinner("Google Sheets에 데이터를 저장하는 중입니다..."):
                existing_data = st.session_state.get('db_data', pd.DataFrame())
                if not existing_data.empty:
                    # 기존 DB에서 해당 월 데이터 삭제
                    existing_data = process_dataframe(existing_data)
                    existing_data_filtered = existing_data[existing_data['년월'] != st.session_state.month_to_update]
                else:
                    existing_data_filtered = pd.DataFrame()
                
                # 원본 컬럼명으로 재구성하여 저장
                expected_columns = ["일자-No.", "배송상태", "창고명", "거래처코드", "거래처명", "품목코드", "품목명(규격)", "박스", "낱개수량", "단가", "공급가액", "부가세", "외화금액", "합계", "적요", "쇼핑몰고객명", "시리얼/로트No.", "외포장_여부", "전표상태", "전표상태.1", "추가문자형식2", "포장박스", "추가숫자형식1", "사용자지정숫자1", "사용자지정숫자2"]
                df_to_save = pd.concat([existing_data_filtered, st.session_state.new_df_to_save], ignore_index=True)
                df_to_save_final = df_to_save[expected_columns]
                
                conn.update(worksheet="판매현황_원본", data=df_to_save_final)
                st.success(f"'{st.session_state.month_to_update}' 데이터를 성공적으로 저장했습니다!")
                
                # 저장 후 상태 초기화 및 리런
                st.session_state.new_df_to_save = None
                st.session_state.upload_key += 1 # 파일 업로더 키 변경으로 위젯 리셋
                st.rerun()

# --- 메인 대시보드 ---
tab1, tab2, tab3 = st.tabs(["[1] 장기 추세 분석", "[2] 성과 비교 분석", "[3] AI 종합 분석"])

if 'db_data' in st.session_state and not st.session_state.db_data.empty:
    full_df = st.session_state.db_data.copy()
    analysis_df = process_and_analyze_data(full_df.copy())
    unique_months = sorted(analysis_df['년월'].unique(), reverse=True)

    with tab1:
        st.header("장기 추세 분석")
        st.info("데이터베이스에 저장된 전체 기간의 성과 추이를 확인합니다.")
        monthly_sales = analysis_df.groupby('년월')['합계'].sum().reset_index()
        monthly_sales['년월'] = monthly_sales['년월'].dt.to_timestamp()
        fig = px.line(monthly_sales, x='년월', y='합계', title='전체 기간 월별 매출 추이', markers=True)
        fig.update_layout(yaxis_title="월 총매출(원)", xaxis_title="년월")
        st.plotly_chart(fig, use_container_width=True)

    if len(unique_months) >= 2:
        with tab2:
            st.header("성과 비교 분석")
            st.info("비교하고 싶은 두 기간을 선택하여 성과를 분석하세요.")
            c1, c2 = st.columns(2)
            curr_month_select = c1.selectbox("**이번달 (기준 월)**", unique_months, index=0, key='compare_current')
            prev_month_select = c2.selectbox("**지난달 (비교 월)**", unique_months, index=1, key='compare_previous')

            if curr_month_select != prev_month_select:
                curr_df = analysis_df[analysis_df['년월'] == curr_month_select]
                prev_df = analysis_df[analysis_df['년월'] == prev_month_select]
                full_curr_df = full_df[full_df['년월'] == curr_month_select]
                full_prev_df = full_df[full_df['년월'] == prev_month_select]

                # (이하 비교 분석 로직)
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

                # (이하 테이블 및 차트 로직)
                st.divider()
                # ... (이전 코드의 테이블 및 차트 생성 로직 복사) ...
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

        with tab3:
            st.header("AI 종합 분석")
            if len(unique_months) >= 2:
                st.info("`성과 비교 분석` 탭에서 선택된 두 기간의 비교 데이터를 기반으로 AI가 종합 분석 및 전략을 제안합니다.")
                if st.button("📈 AI 비교 분석 리포트 생성"):
                    if g_model:
                        with st.spinner("고래미 AI가 데이터를 비교 분석하여 전략을 수립하고 있습니다..."):
                            kpi_df = pd.DataFrame(kpi_data)
                            prev_cust_set = set(prev_df['거래처명'].unique()); curr_cust_set = set(curr_df['거래처명'].unique())
                            prev_prod_set = set(prev_df['제품명'].unique()); curr_prod_set = set(curr_df['제품명'].unique())
                            new_customers = list(curr_cust_set - prev_cust_set)
                            lost_products = list(prev_prod_set - curr_prod_set)
                            report = get_comparison_analysis_report(g_model, pd.DataFrame(kpi_data), top_growth_cust, top_decline_cust, top_growth_prod, top_decline_prod, new_customers, lost_products)
                            st.markdown(report)
                    else: st.warning("AI 모델이 연결되지 않았습니다.")
            else:
                st.warning("AI 분석을 위해서는 최소 2개월치의 데이터가 필요합니다.")
    else:
        st.warning("데이터베이스에 최소 2개월치의 데이터가 없습니다. '[1] 데이터 관리' 탭에서 데이터를 추가해주세요.")

else:
    st.info("👈 사이드바에서 판매현황 엑셀 파일을 업로드하여 분석을 시작하세요.")
