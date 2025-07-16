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
# 이카운트 ERP API 연동 함수 (디버깅 기능 강화)
# --------------------------------------------------------------------------

BASE_URL = "https://oapi.ecount.com/OAPI/V2"

# API 요청을 위한 공통 페이로드 생성 함수
def create_payload(zone_code, com_code, user_id, api_key):
    return {
        "ZONE": zone_code,
        "COM_CODE": com_code,
        "USER_ID": user_id,
        "API_CERT_KEY": api_key,
        "LAN_TYPE": "ko-KR",
    }

@st.cache_data
def get_api_data(endpoint, payload_data):
    """API 데이터를 가져오는 통합 함수"""
    url = f"{BASE_URL}{endpoint}"
    headers = {'Content-Type': 'application/json'}
    
    # ★★★ 디버깅 포인트: 어떤 데이터를 보내는지 화면에 출력 ★★★
    st.subheader(f"📡 {endpoint} API 요청 정보:")
    st.json({"Request": payload_data})
    
    try:
        response = requests.post(url, headers=headers, json={"Request": payload_data})
        response.raise_for_status()
        data = response.json()
        if data.get("Status") == "200" and "Data" in data:
            st.success(f"{endpoint} 데이터 수신 성공!")
            return pd.DataFrame(data["Data"])
        else:
            st.error(f"{endpoint} 데이터 조회 실패: {data.get('Errors', [{}])[0].get('Message', '알 수 없는 오류')}")
            # ★★★ 디버깅 포인트: 서버의 전체 응답을 출력 ★★★
            st.subheader(f"🚨 {endpoint} API 서버 응답:")
            st.json(data) 
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"API 요청 중 네트워크 오류 발생 ({endpoint}): {e}")
        return None
    except Exception as e:
        st.error(f"데이터 처리 중 알 수 없는 오류 발생 ({endpoint}): {e}")
        return None


# --------------------------------------------------------------------------
# 사이드바: 사용자 입력
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ API 정보 입력")
    zone_code = st.text_input("Zone Code (예: KR100)", help="이카운트 로그인 URL의 sbo.ecount.com 앞부분 (예: kr100)")
    com_code = st.text_input("Company Code", help="이카운트 회사코드")
    user_id = st.text_input("Ecount User ID", help="API 권한이 있는 이카운트 로그인 아이디")
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
    if not all([zone_code, com_code, user_id, api_key]):
        st.error("API 정보(Zone Code, Company Code, User ID, API 인증키)를 모두 입력해주세요.")
        st.stop()

    with st.spinner('이카운트에서 데이터를 가져오는 중입니다...'):
        # 판매 데이터
        sales_payload = create_payload(zone_code, com_code, user_id, api_key)
        sales_payload["Date"] = {"TYPE": "0", "FROM": start_date_str, "TO": end_date_str}
        sales_df = get_api_data("/Voucher/GetSalesList", sales_payload)
        
        # 구매 데이터
        purchase_payload = create_payload(zone_code, com_code, user_id, api_key)
        purchase_payload["Date"] = {"TYPE": "0", "FROM": start_date_str, "TO": end_date_str}
        purchase_df = get_api_data("/Voucher/GetPurchaseList", purchase_payload)

        # 재고 데이터
        inventory_payload = create_payload(zone_code, com_code, user_id, api_key)
        inventory_payload["BASE_DATE"] = end_date_str
        inventory_df = get_api_data("/Inventory/GetInventoryBalance", inventory_payload)
        
    if sales_df is None or purchase_df is None or inventory_df is None:
        st.error("데이터 조회에 실패했습니다. 위에 출력된 API 요청 정보와 서버 응답을 확인하고, 아래 '최종 체크리스트'를 점검해주세요.")
        st.stop()
        
    # 데이터가 정상적으로 로드된 경우, 이후 로직 실행 (이하 코드는 이전과 동일)
    # ... (데이터 처리 및 시각화 코드) ...
