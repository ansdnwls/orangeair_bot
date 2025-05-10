import streamlit as st
from datetime import datetime, timedelta, timezone, date
import smtplib
from email.message import EmailMessage
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image
import io
import json

# ──────────────────────────────────────────────────────────────
if "step" not in st.session_state:
    st.session_state.step = 1
if "data" not in st.session_state:
    st.session_state.data = {}
if "units" not in st.session_state:
    st.session_state.units = []
if "photos" not in st.session_state:
    st.session_state.photos = []
if "total_price" not in st.session_state:
    st.session_state.total_price = 0

# ──────────────────────────────────────────────────────────────
def send_email_html(subject, body_html, to_email, files=[]):
    from_email = st.secrets["EMAIL_USER"]
    app_password = st.secrets["EMAIL_PASS"]

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    msg.add_alternative(body_html, subtype='html')

    for file in files[:5]:
        maintype, subtype = 'image', 'jpeg'
        msg.add_attachment(file['content'], maintype=maintype, subtype=subtype, filename=file['name'])

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(from_email, app_password)
        smtp.send_message(msg)

def compress_images(files):
    compressed = []
    for file in files[:5]:
        img = Image.open(file)
        img = img.convert("RGB")
        img.thumbnail((1280, 960))
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85)
        buf.seek(0)
        compressed.append({'name': file.name, 'content': buf.read()})
    return compressed

def get_reserved_slots(calendar_id: str):
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    credentials_info = json.loads(st.secrets["CALENDAR_CREDENTIALS"])
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=credentials)

    now = datetime.now(timezone.utc).isoformat()
    max_date = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=now,
        timeMax=max_date,
        maxResults=100,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    reserved = []
    for event in events_result.get('items', []):
        start_dt = event['start'].get('dateTime')
        if not start_dt:
            continue
        dt = datetime.fromisoformat(start_dt)
        date_str = dt.date().isoformat()
        hour = dt.time().hour
        if hour < 12:
            time_str = "오전 9시"
        elif 12 <= hour < 15:
            time_str = "오후 1시"
        elif 15 <= hour < 18:
            time_str = "오후 4시"
        else:
            time_str = "오후 6시이후(벽걸이만가능)"
        reserved.append({"date": date_str, "time": time_str})
    return reserved
# ──────────────────────────────────────────────────────────────
def step_main():
    query_params = st.query_params
    referrer = query_params.get("ref", [None])[0]
    st.session_state.data["recommender"] = referrer if referrer else ""

    st.title("🍊 에어컨 상담 챗봇")
    st.header("무엇을 도와드릴까요?")
    option = st.radio("선택해주세요", ["가정용 에어컨청소", "업소용 에어컨청소", "AS 문의", "친구추천 이벤트"])
    if st.button("다음으로"):
        if option == "가정용 에어컨청소":
            st.session_state.data["usage"] = "가정용"
            st.session_state.step = 2
        elif option == "업소용 에어컨청소":
            st.session_state.data["usage"] = "업체용"
            st.session_state.step = 3
        elif option == "AS 문의":
            st.session_state.step = 6
        else:  # 친구추천 이벤트
            st.session_state.step = 7


# ──────────────────────────────────────────────────────────────
def step_ac_info():
    usage = st.session_state.data.get("usage")
    st.header("🏷️ 에어컨 정보 입력")
    st.markdown("*보유하신 에어컨이 많으면 하단 추가버튼을 눌러 모두 추가하시고 예약하기 버튼을 누르세요*")

    base_price = {"벽걸이": 70000, "스탠드": 120000, "투인원(벽걸이+스탠드)": 180000, "1way": 80000, "2way": 90000, "4way": 130000}

    with st.form("unit_form"):
        brand = st.selectbox("제조사", ["삼성", "LG", "캐리어", "대우", "기타브랜드"])
        ac_type = st.selectbox("종류", ["벽걸이", "스탠드", "투인원(벽걸이+스탠드)", "1way", "2way", "4way"])
        count = st.number_input("대수", 1, 10, 1)
        photos = st.file_uploader("사진 업로드 (최대 5장)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("추가")
        with col2:
            reset = st.form_submit_button("초기화")

    if submit:
        unit_price = base_price.get(ac_type, 50000) * count
        st.session_state.units.append({"brand": brand, "type": ac_type, "count": count, "price": unit_price})
        st.session_state.total_price += unit_price
        st.session_state.photos.extend(photos)

    if reset:
        st.session_state.units.clear()
        st.session_state.total_price = 0
        st.session_state.photos.clear()


    if st.session_state.units:
        st.write("### 추가된 목록")
        for unit in st.session_state.units:
            st.write(f"- {unit['brand']} {unit['type']} × {unit['count']}대 → {unit['price']:,}원")
        st.write(f"**합계: {st.session_state.total_price:,}원**")
        if usage == "업체용":
            st.info("💬 대량구매 시 할인 적용 (유선협의)")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("예약하기로 이동"):
            st.session_state.step = 4
    with col2:
        if st.button("뒤로가기"):
            st.session_state.step -= 1

# ──────────────────────────────────────────────────────────────
def step_reservation():
    st.header("📅 예약하기")
    calendar_id = '10cef97013e86d8ea27c14b12285e096af036f9c015e6b05f60a78eb1370a748@group.calendar.google.com'
    reserved_slots = get_reserved_slots(calendar_id)

    def is_disabled(date, time_label):
        return any(slot["date"] == str(date) and slot["time"] == time_label for slot in reserved_slots)

    time_options = ["오전 9시", "오후 1시", "오후 4시", "오후 6시이후(벽걸이만가능)", "아무 때나"]
    today = date.today()
    max_date = today + timedelta(days=90)

    st.markdown("하단에 희망하는 **3가지 날짜**를 선택해주세요")
    date1 = st.date_input("첫 번째 희망 날짜", today, min_value=today, max_value=max_date)
    time1 = st.radio("첫 번째 희망 시간", [t for t in time_options if not is_disabled(date1, t) or t == "아무 때나"])
    date2 = st.date_input("두 번째 희망 날짜", today, min_value=today, max_value=max_date)
    time2 = st.radio("두 번째 희망 시간", [t for t in time_options if not is_disabled(date2, t) or t == "아무 때나"])
    date3 = st.date_input("세 번째 희망 날짜", today, min_value=today, max_value=max_date)
    time3 = st.radio("세 번째 희망 시간", [t for t in time_options if not is_disabled(date3, t) or t == "아무 때나"])

    address = st.text_input("주소")
    parking = st.radio("주차 가능 여부 (불가능 시 주차비를 청구할 수 있습니다)", ["가능", "불가능"])
    notes = st.text_area("특이사항 (예: 현관 비밀번호 0000입니다.)")
    name = st.text_input("주문자 이름")
    phone = st.text_input("주문자 전화번호")
    recommender = st.session_state.data.get("recommender", "")

    if st.button("예약 신청 완료"):
        placeholder = st.empty()
        placeholder.info("신청서 전송 중입니다. 잠시만 기다려주세요...")

        compressed_files = compress_images(st.session_state.photos)
        summary = "<br>".join([f"- {u['brand']} {u['type']} × {u['count']}대 → {u['price']:,}원" for u in st.session_state.units])
        body_html = f"""
        <html><body>
        <h2>📩 에어컨 예약 신청</h2>
        <p>이름: {name}<br>전화번호: <a href="tel:{phone}">{phone}</a><br>주소: {address}<br>
        <a href="https://map.naver.com/v5/search/{address}">[네이버 지도]</a> |
        <a href="https://map.kakao.com/?q={address}">[카카오맵]</a><br>주차: {parking}</p>
        <p>에어컨:<br>{summary}<br>합계: {st.session_state.total_price:,}원</p>
        <p>희망일:<br>{date1.strftime("%Y/%m/%d (%A)")} {time1}<br>{date2.strftime("%Y/%m/%d (%A)")} {time2}<br>{date3.strftime("%Y/%m/%d (%A)")} {time3}</p>
        <p>특이사항:<br>{notes}</p><p>추천인:<br>{recommender}</p></body></html>
        """
        send_email_html("[에어컨 예약 신청]", body_html, "orangeair2025@gmail.com", compressed_files)

        import time
        time.sleep(2)
        placeholder.success("예약 신청이 접수되었습니다!")
        time.sleep(2)
        placeholder.info("🎉 친구 추천 이벤트에 참여해보세요!")

        st.session_state.show_recommend_button = True

    if st.session_state.get("show_recommend_button"):
        if st.button("추천 이벤트 참여하기"):
            st.session_state.step = 7
            st.session_state.show_recommend_button = False
            st.rerun()

    if st.button("뒤로가기"):
        st.session_state.step -= 1

# ──────────────────────────────────────────────────────────────
def step_recommend():
    st.header("🎉 친구 추천 이벤트")
    my_phone = st.text_input("내 전화번호 (추천 링크 생성용)", "")
    if my_phone:
        ref_link = f"https://airconbot.com/?ref={my_phone}"
        st.text_input("추천 링크", ref_link)
        st.markdown("👉 친구에게 위 링크를 복사해 보내주세요!")
        st.markdown("📢 친구가 이 링크로 예약하고 청소 완료하면 ☕ 커피 쿠폰을 드립니다!")
    if st.button("메인으로 돌아가기"):
        st.session_state.step = 1

# ──────────────────────────────────────────────────────────────
def step_as():
    st.header("🛠️ AS 문의")
    address = st.text_input("지역")
    phone = st.text_input("연락처")
    visit = st.text_input("방문했던 날짜 (예: 2024-05-01)")
    problem = st.text_area("증상 (자세히)")
    photos = st.file_uploader("증상 사진 첨부 (최대 5장)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

    if st.button("AS 문의 등록"):
        st.info("신청서 전송 중입니다. 잠시만 기다려주세요...")
        compressed_files = compress_images(photos)
        body_html = f"""
        <html><body>
        <h2>📩 에어컨 AS 문의 접수</h2>
        <p><b>지역:</b> {address}<br>
        <a href="https://map.naver.com/v5/search/{address}">[네이버 지도]</a> |
        <a href="https://map.kakao.com/?q={address}">[카카오맵]</a><br>
        <b>연락처:</b> <a href="tel:{phone}">{phone}</a><br>
        <b>방문일:</b> {visit}</p>
        <p><b>증상</b><br>{problem}</p>
        </body></html>
        """
        send_email_html("[에어컨 AS 문의]", body_html, "orangeair2025@gmail.com", compressed_files)
        st.success("AS 문의가 접수되었습니다.")
        st.session_state.step = 1

# ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="에어컨 상담 챗봇", layout="centered")
if st.session_state.step == 1:
    step_main()
elif st.session_state.step == 2:
    step_ac_info()
elif st.session_state.step == 3:
    step_ac_info()
elif st.session_state.step == 4:
    step_reservation()
elif st.session_state.step == 6:
    step_as()
elif st.session_state.step == 7:
    step_recommend()
