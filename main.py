import os
import asyncio
import random
import schedule
import time

from telethon import TelegramClient, events, functions

# ========== [1] 텔레그램 API 설정 (환경변수 or 직접 값) ==========
API_ID = int(os.getenv("API_ID", "23353481"))
API_HASH = os.getenv("API_HASH", "3d62dd4e702e42e4c662fb85f96f64b9")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "+818027404273")

SESSION_NAME = "my_telethon_session"

client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH,
    timeout=60,          # 한 번의 연결/응답 최대 대기
    auto_reconnect=True  # 끊기면 자동 재연결
)

# ========== [2] A/B 메시지 내용 ==========
MESSAGE_A = """🚀 +888 해텔 문의받습니다! 🚀

✅ 텔레그램 최저가 보장! 어디에서도 이 가격과 퀄리티를 찾을 수 없습니다.

✅ 해외 프리미엄 계정 보유! 신뢰도 100%, 터짐 걱정 없는 안정적인 계정만 제공합니다.

✅ 선텔 100% 보장! 막힘 없이, 제한 없이, 원하는 대로 사용하세요!

👀 다른 곳에서 비싸게 사고 후회하지 마세요.

📩 문의 및 구매:
🔹 @nojiwooks | @H_ae_Tae

💥 확실한 계정, 최저가 보장! 지금 바로 문의하세요! 💥
"""

MESSAGE_B = """갠돈.급전 빌려드립니다

10~1000까지 가능합니다
신속하고 깔끔하게 해드립니다
카톡정지자도 가능합니다
사고자도 내용만 좋으면 최대한 승인내드립니다.
06년생도 받습니다 24시간 상담가능
문의는 @BAOS003 @nojiwooks

24시간 편히 문의주세요

무직도ok 원금미변사고자만 아니면 최대승인내드립니다
맡겨만 주시면 최선을다해서 승인내드리겠습니다!
"""

# ========== [3] 전송 대상 그룹 링크 (3개) ==========
GROUP_LIST = [
    "https://t.me/+FRt9D-N_GCplZDU0",
    "https://t.me/+Q4Am-DVzsaNiMzE0",
    "https://t.me/+FWWSPKkIgTtjNzZl"
]

# 그룹 간 전송 시 몇 초씩 대기?
GROUP_DELAY_RANGE = (2, 5)  # 2~5초 랜덤

# ========== [4] 메시지 전송 함수 ==========

async def ensure_connected(client: TelegramClient):
    """텔레그램 연결·세션 확인"""
    if not client.is_connected():
        print("[INFO] Reconnecting...")
        await client.connect()

    # 세션 만료 시 OTP 필요
    if not await client.is_user_authorized():
        print("[WARN] 세션이 만료 or 없음 -> OTP 로그인 시도")
        await client.start(phone=PHONE_NUMBER)
        print("[INFO] 재로그인 성공")

async def send_message_to_all_groups(text: str):
    """
    3개 그룹에 text 메시지를 전송.
    그룹 간 2~5초 랜덤 지연
    """
    await ensure_connected(client)

    for grp in GROUP_LIST:
        try:
            await client.send_message(grp, text)
            print(f"[INFO] 전송 성공 => {grp} | '{text[:10]}...'")
        except Exception as e:
            print(f"[ERROR] {grp} 전송 실패: {e}")

        delay = random.randint(*GROUP_DELAY_RANGE)
        print(f"[INFO] 다음 그룹 전송 전 {delay}초 대기...")
        await asyncio.sleep(delay)

# ========== [5] A/B 메시지 번갈아 전송: 45~65분 대기 ==========

WAIT_MIN = 45  # 분
WAIT_MAX = 65  # 분

async def cycle_messages():
    """
    A 메시지 보낸 후 45~65분 대기 -> B 메시지 -> 45~65분 대기 -> A...
    무한 반복
    """
    msg_index = 0  # 0 => A, 1 => B

    while True:
        # 어떤 메시지를 보낼지 결정
        current_msg = MESSAGE_A if (msg_index == 0) else MESSAGE_B
        msg_label = "A" if (msg_index == 0) else "B"

        print(f"[CYCLE] 시작: {msg_label} 메시지 전송")
        await send_message_to_all_groups(current_msg)

        # 45~65분 랜덤 대기
        wait_minutes = random.randint(WAIT_MIN, WAIT_MAX)
        wait_seconds = wait_minutes * 60
        print(f"[CYCLE] {msg_label} 메시지 끝. 다음 메시지 전까지 {wait_minutes}분 대기")
        await asyncio.sleep(wait_seconds)

        # 메시지 A/B 토글
        msg_index = 1 - msg_index

# ========== [6] 메인 함수 ==========

async def main():
    # 초기 연결/세션
    await client.connect()
    if not await client.is_user_authorized():
        print("[INFO] 세션없음 -> OTP 로그인 시도")
        await client.start(phone=PHONE_NUMBER)
        print("[INFO] 첫 로그인 완료")
    else:
        print("[INFO] 이미 세션 인증됨")

    # 무한 반복 (A → 대기 → B → 대기 → A...)
    await cycle_messages()

if __name__ == "__main__":
    asyncio.run(main())