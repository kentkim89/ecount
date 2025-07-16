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
# 이카운트 ERP API 연동 함수 (로직 수정 및 강화)
# --------------------------------------------------------------------------

BASE_URL = "https://oapi.ecount.com/OAPI/V2"

# @st.cache_data # 디버깅을 위해 캐시 기능 일시 비활성화
def get_api_data(endpoint, request_body):
    """API 데이터를 가져오는 통합 함수 (JSON 구조 수정)"""
    url = f"{BASE_URL}{endpoint}"
    headers = {'Content-Type': 'application/json'}
    
    # ★★★ 디버깅 포인트: 어떤 데이터를 보내는지 화면에 출력 ★★★
    st.subheader(f"📡 {endpoint} API 요청 정보:")
    st.json(request_body) # 서버로 보낼 전체 JSON 구조를 그대로 출력
    
    try:
        # request_body를 그대로 json 파라미터에 전달
        response = requests.post(url, headers=headers, json=request_body)
        response.raise_for_status() # 2xx가 아닌 응답 코드일 경우 예외 발생
        data = response.json()
        
        if data.get("Status") == "200" and "Data" in data:
            st.success(f"✅ {endpoint} 데이터 수신 성공!")
            return pd.DataFrame(data["Data"])
        else:
            st.error(f"🚨 {endpoint} API 응답 오류: {data.get('Errors', [{}])[0].get('Message', '알 수 없는 오류')}")
            st.subheader(f"🔍 {endpoint} 서버 상세 응답:")
            st.json(data) 
            return None
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP 오류 발생 ({endpoint}): Status {e.response.status_code}")
        st.json(e.response.json())
        return None
    except Exception as e:
        st.error(f"요청/처리 중 알 수 없는 오류 발생 ({endpoint}): {e}")
        return None

# --------------------------------------------------------------------------
# 사이드바: 사용자 입력
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ API 정보 입력")
    # 입력 값의 앞뒤 공백을 자동으로 제거하도록 strip() 추가
    zone_code = st.text_input("Zone Code (예: KR100)", key="zone").strip()
    com_code = st.text_input("Company Code", key="com").strip()
    user_id = st.text_input("Ecount User ID", key="user").strip()
    api_key = st.text_input("API 인증키", type="password", key="api").strip()

    st.header("🗓️ 조회 기간 설정")
    today = datetime.today()
    start_date = st.date_input("조회 시작일", today.replace(day=1))
    end_date = st.date_input("조회 종료일", today)
    
    start_date_str = start_date.strftime("%Y%m%d")
    end_date_str = end_date.strftime("%Y%m%d")
        
    search_button = st.button("📊 데이터 조회", type="primary", use_container_width=True)

# --------------------------------------------------------------------------
# 메인 대시보드
# --------------------------------------------------------------------------
if not search_button:
    st.info("사이드바에 정보를 입력하고 '데이터 조회' 버튼을 눌러주세요.")
else:
    if not all([zone_code, com_code, user_id, api_key]):
        st.error("API 정보 4가지를 모두 입력해주세요.")
        st.stop()

    with st.spinner('이카운트에서 데이터를 가져오는 중입니다...'):
        # API 요청 본문을 각 API에 맞게 구성
        common_payload = {
            "ZONE": zone_code, "COM_CODE": com_code, "USER_ID": user_id,
            "API_CERT_KEY": api_key, "LAN_TYPE": "ko-KR"
        }
        
        # 판매 데이터 요청
        sales_request = {"Request": {**common_payload, "Date": {"TYPE": "0", "FROM": start_date_str, "TO": end_date_str}}}
        sales_df = get_api_data("/Voucher/GetSalesList", sales_request)
        
        # 구매 데이터 요청
        purchase_request = {"Request": {**common_payload, "Date": {"TYPE": "0", "FROM": start_date_str, "TO": end_date_str}}}
        purchase_df = get_api_data("/Voucher/GetPurchaseList", purchase_request)

        # 재고 데이터 요청
        inventory_request = {"Request": {**common_payload, "BASE_DATE": end_date_str}}
        inventory_df = get_api_data("/Inventory/GetInventoryBalance", inventory_request)
        
    if sales_df is None or purchase_df is None or inventory_df is None:
        st.error("### 데이터 조회 실패\n위에 출력된 API 요청 정보와 서버 응답을 확인하고, 아래 **'최종 확인 체크리스트'**를 반드시 점검해주세요.")
        st.stop()
    
    # (이하 데이터 처리 및 시각화 코드는 생략)
