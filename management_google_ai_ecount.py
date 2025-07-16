import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime

# --------------------------------------------------------------------------
# Streamlit 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="Ecount 경영지표 대시보드")

st.title("📈 Ecount ERP 경영지표 대시보드")
st.markdown("이카운트 ERP 데이터를 활용한 실시간 경영 현황 분석")

# --------------------------------------------------------------------------
# 이카운트 ERP API 연동 함수 (USER_ID 추가 및 수정)
# --------------------------------------------------------------------------

BASE_URL = "https://oapi.ecount.com/OAPI/V2"

# API 요청을 위한 공통 페이로드 생성 함수
def create_payload(zone_code, com_code, user_id, api_key):
    """API 요청에 필요한 공통 인증 정보를 생성합니다."""
    return {
        "ZONE": zone_code,
        "COM_CODE": com_code,
        "USER_ID": user_id,
        "API_CERT_KEY": api_key,
        "LAN_TYPE": "ko-KR",
    }

# 세일즈 데이터 로드 함수
@st.cache_data
def get_sales_data(zone_code, com_code, user_id, api_key, start_date, end_date):
    """이카운트에서 판매입력 데이터를 가져옵니다."""
    endpoint = "/Voucher/GetSalesList"
    url = f"{BASE_URL}{endpoint}"
    headers = {'Content-Type': 'application/json'}
    
    payload = create_payload(zone_code, com_code, user_id, api_key)
    payload["Date"] = {"TYPE": "0", "FROM": start_date, "TO": end_date}
    
    try:
        response = requests.post(url, headers=headers, json={"Request": payload})
        response.raise_for_status()
        data = response.json()
        if data.get("Status") == "200" and "Data" in data:
            return pd.DataFrame(data["Data"])
        else:
            st.error(f"판매 데이터 조회 실패: {data.get('Errors', [{}])[0].get('Message', '알 수 없는 오류')}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"API 요청 오류 (판매): {e}")
        return None

# 구매 데이터 로드 함수
@st.cache_data
def get_purchase_data(zone_code, com_code, user_id, api_key, start_date, end_date):
    """이카운트에서 구매입력 데이터를 가져옵니다."""
    endpoint = "/Voucher/GetPurchaseList"
    url = f"{BASE_URL}{endpoint}"
    headers = {'Content-Type': 'application/json'}

    payload = create_payload(zone_code, com_code, user_id, api_key)
    payload["Date"] = {"TYPE": "0", "FROM": start_date, "TO": end_date}

    try:
        response = requests.post(url, headers=headers, json={"Request": payload})
        response.raise_for_status()
        data = response.json()
        if data.get("Status") == "200" and "Data" in data:
            return pd.DataFrame(data["Data"])
        else:
            st.error(f"구매 데이터 조회 실패: {data.get('Errors', [{}])[0].get('Message', '알 수 없는 오류')}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"API 요청 오류 (구매): {e}")
        return None

# 재고 현황 데이터 로드 함수
@st.cache_data
def get_inventory_balance(zone_code, com_code, user_id, api_key, base_date):
    """이카운트에서 품목별 재고 현황을 가져옵니다."""
    endpoint = "/Inventory/GetInventoryBalance"
    url = f"{BASE_URL}{endpoint}"
    headers = {'Content-Type': 'application/json'}

    payload = create_payload(zone_code, com_code, user_id, api_key)
    payload["BASE_DATE"] = base_date

    try:
        response = requests.post(url, headers=headers, json={"Request": payload})
        response.raise_for_status()
        data = response.json()
        if data.get("Status") == "200" and "Data" in data:
            return pd.DataFrame(data["Data"])
        else:
            st.error(f"재고 데이터 조회 실패: {data.get('Errors', [{}])[0].get('Message', '알 수 없는 오류')}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"API 요청 오류 (재고): {e}")
        return None

# --------------------------------------------------------------------------
# 사이드바: 사용자 입력 (USER_ID 입력란 추가)
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ API 정보 입력")
    zone_code = st.text_input("Zone Code (예: KR100)", help="이카운트 로그인 URL의 sbo.ecount.com 앞부분 (예: kr100)")
    com_code = st.text_input("Company Code", help="이카운트 회사코드")
    user_id = st.text_input("Ecount User ID", help="API 권한이 있는 이카운트 로그인 아이디") # <-- 사용자 아이디 입력란 추가
    api_key = st.text_input("API 인증키", type="password", help="이카운트에서 발급받은 API 인증키")

    st.header("🗓️ 조회 기간 설정")
    today = datetime.today()
    default_start_date = today.replace(day=1)
    default_end_date = today

    date_range = st.date_input(
        "조회 기간",
        (default_start_date, default_end_date),
        format="YYYY-MM-DD"
    )

    if len(date_range) == 2:
        start_date_str = date_range[0].strftime("%Y%m%d")
        end_date_str = date_range[1].strftime("%Y%m%d")
    else:
        st.warning("시작일과 종료일을 모두 선택해주세요.")
        st.stop()
        
    search_button = st.button("📊 데이터 조회", type="primary", use_container_width=True)

# --------------------------------------------------------------------------
# 메인 대시보드
# --------------------------------------------------------------------------

if not search_button:
    st.info("사이드바에 정보를 입력하고 '데이터 조회' 버튼을 눌러주세요.")
else:
    # USER_ID 유효성 검사 추가
    if not all([zone_code, com_code, user_id, api_key]):
        st.error("API 정보(Zone Code, Company Code, User ID, API 인증키)를 모두 입력해주세요.")
        st.stop()

    with st.spinner('이카운트에서 데이터를 가져오는 중입니다... 잠시만 기다려주세요.'):
        # API 호출 시 user_id 전달
        sales_df = get_sales_data(zone_code, com_code, user_id, api_key, start_date_str, end_date_str)
        purchase_df = get_purchase_data(zone_code, com_code, user_id, api_key, start_date_str, end_date_str)
        inventory_df = get_inventory_balance(zone_code, com_code, user_id, api_key, end_date_str)

    if sales_df is None or purchase_df is None or inventory_df is None:
        st.warning("데이터를 일부만 가져왔거나 가져오지 못했습니다. 아래 '문제 해결 체크리스트'를 확인해주세요.")
        # 이하 로직은 동일하므로 생략
    else:
        # --- 데이터 전처리 ---
        # 날짜 형식 변환 및 숫자 형식 변환
        for df in [sales_df, purchase_df]:
            if not df.empty:
                df['IO_DATE'] = pd.to_datetime(df['IO_DATE'], format='%Y%m%d')
                df['PROD_AMT'] = pd.to_numeric(df['PROD_AMT'])
        
        if not inventory_df.empty:
            inventory_df['QTY'] = pd.to_numeric(inventory_df['QTY'])
            inventory_df['BAL_AMT'] = pd.to_numeric(inventory_df['BAL_AMT'])

        # --- 1. 주요 지표 (KPI) ---
        st.header("📌 주요 경영 지표 (KPI)")
        
        total_sales = sales_df['PROD_AMT'].sum() if not sales_df.empty else 0
        total_purchase = purchase_df['PROD_AMT'].sum() if not purchase_df.empty else 0
        gross_profit = total_sales - total_purchase
        
        total_inventory_value = inventory_df['BAL_AMT'].sum() if not inventory_df.empty else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("총 매출", f"{total_sales:,.0f} 원")
        col2.metric("총 매입", f"{total_purchase:,.0f} 원")
        col3.metric("매출 이익", f"{gross_profit:,.0f} 원", f"{((gross_profit / total_sales * 100) if total_sales else 0):.2f}%")
        col4.metric("재고 자산 총액", f"{total_inventory_value:,.0f} 원")
        
        st.markdown("---")

        # 이하 시각화 코드는 동일합니다.
        # (이하 생략)
