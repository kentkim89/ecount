import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# Streamlit 앱 제목
st.title("고래미 주식회사 판매 현황 대시보드")

# 파일 업로더
uploaded_file = st.file_uploader("엑셀 파일을 업로드하세요 (판매현황 시트)", type=["xlsx", "xls"])

if uploaded_file is not None:
    # 엑셀 파일 읽기
    try:
        df = pd.read_excel(uploaded_file, sheet_name="판매현황", header=1)  # row2가 헤더이므로 header=1
    except Exception as e:
        st.error(f"파일 읽기 오류: {e}")
        st.stop()

    # 데이터 클리닝
    # 필요한 컬럼 선택 (헤더 기반)
    columns = [
        "일자-No.", "배송상태", "창고명", "거래처코드", "거래처명", "품목코드", "품목명(규격)",
        "박스", "낱개수량", "단가", "공급가액", "부가세", "외화금액", "합계", "적요",
        "쇼핑몰고객명", "시리얼/로트No.", "외포장_여부", "전표상태", "전표상태.1",
        "추가문자형식2", "포장박스", "추가숫자형식1", "사용자지정숫자1", "사용자지정숫자2"
    ]
    if len(df.columns) < len(columns):
        st.warning("컬럼 수가 예상보다 적습니다. 데이터를 확인하세요.")
    else:
        df.columns = columns  # 컬럼 이름 강제 설정

    # 숫자 컬럼 변환 (NaN 처리)
    numeric_cols = ["박스", "낱개수량", "단가", "공급가액", "부가세", "외화금액", "합계", "추가숫자형식1", "사용자지정숫자1", "사용자지정숫자2"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 일자 추출 (일자-No.에서 날짜 부분만)
    df['일자'] = df['일자-No.'].apply(lambda x: str(x).split('-')[0].strip() if pd.notnull(x) else None)
    df['일자'] = pd.to_datetime(df['일자'], errors='coerce', format='%Y/%m/%d')

    # 총계 행 제거 (마지막 행들이 총계일 수 있음)
    df = df.dropna(subset=['품목코드'])  # 품목코드가 없는 행 제거 (총계 등)

    # 경영 지표 계산
    total_sales = df['합계'].sum()
    total_vat = df['부가세'].sum()
    total_supply = df['공급가액'].sum()
    total_boxes = df['박스'].sum()
    total_items = df['낱개수량'].sum()
    unique_customers = df['거래처명'].nunique()
    top_products = df.groupby('품목명(규격)')['합계'].sum().sort_values(ascending=False).head(5)
    top_customers = df.groupby('거래처명')['합계'].sum().sort_values(ascending=False).head(5)
    daily_sales = df.groupby('일자')['합계'].sum().reset_index()

    # 대시보드 섹션
    st.header("경영 지표 요약")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("총 매출 (합계)", f"{total_sales:,.0f} 원")
        st.metric("총 부가세", f"{total_vat:,.0f} 원")
    with col2:
        st.metric("총 공급가액", f"{total_supply:,.0f} 원")
        st.metric("총 판매 박스", f"{total_boxes:,.0f} 개")
    with col3:
        st.metric("총 판매 낱개", f"{total_items:,.0f} 개")
        st.metric("고유 거래처 수", unique_customers)

    st.header("상위 품목 매출")
    st.dataframe(top_products.reset_index().rename(columns={'합계': '매출액'}))

    st.header("상위 거래처 매출")
    st.dataframe(top_customers.reset_index().rename(columns={'합계': '매출액'}))

    # 시각화
    st.header("일자별 매출 추이")
    if not daily_sales.empty:
        fig_line = px.line(daily_sales, x='일자', y='합계', title='일자별 총 매출')
        st.plotly_chart(fig_line)
    else:
        st.info("일자별 데이터가 없습니다.")

    st.header("품목별 매출 분포 (상위 10개)")
    top_10_products = df.groupby('품목명(규격)')['합계'].sum().sort_values(ascending=False).head(10).reset_index()
    fig_pie = px.pie(top_10_products, values='합계', names='품목명(규격)', title='상위 10 품목 매출 비율')
    st.plotly_chart(fig_pie)

    st.header("거래처별 매출 바 차트 (상위 10개)")
    top_10_customers = df.groupby('거래처명')['합계'].sum().sort_values(ascending=False).head(10).reset_index()
    fig_bar = px.bar(top_10_customers, x='거래처명', y='합계', title='상위 10 거래처 매출')
    st.plotly_chart(fig_bar)

    # 전체 데이터 테이블
    st.header("전체 데이터")
    st.dataframe(df)

    # 다운로드 버튼
    st.header("데이터 다운로드")
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Processed_Data', index=False)
    output.seek(0)
    st.download_button(label="처리된 데이터 다운로드 (Excel)", data=output, file_name="processed_sales.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.info("엑셀 파일을 업로드하여 대시보드를 생성하세요. 데이터 형식은 제공된 예시와 유사해야 합니다.")
```
