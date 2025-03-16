import os
import asyncio
import random
import schedule
import time

from telethon import TelegramClient, events, functions

# ========== [1] 텔레그램 API 설정 ==========
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")

SESSION_NAME = "my_telethon_session"

# Telethon 클라이언트 생성 (auto_reconnect, ping_interval 설정)
client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH,
    timeout=60,
    auto_reconnect=True,      # 끊기면 자동 재연결
    connection_retries=None,    # 초
    request_retries=None,
    ping_interval=30          # 30초마다 ping → 유휴 해제
)

# ========== [2] 파일 경로 설정 ==========
ADVERT_FILE = "advert_message.txt"   # 광고 문구
COUNTER_FILE = "counter.txt"         # 전송 횟수
IMAGE_FILE = "my_ad_image.jpg"       # 이미지 파일(있으면 이미지+캡션, 없으면 텍스트만)

# ========== [3] 파일 로드/저장 함수들 ==========
def load_base_message():
    """advert_message.txt에서 광고 문구 읽어오기"""
    if not os.path.exists(ADVERT_FILE):
        return "광고 문구가 없습니다."
    with open(ADVERT_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()

def load_counter():
    """counter.txt에서 숫자 읽기. 없으면 1로 시작."""
    if not os.path.exists(COUNTER_FILE):
        return 1
    with open(COUNTER_FILE, "r", encoding="utf-8") as f:
        data = f.read().strip()
        if data.isdigit():
            return int(data)
        return 1

def save_counter(value: int):
    """counter.txt에 숫자 저장"""
    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        f.write(str(value))

# ========== [4] 연결확인/재연결 함수 ==========

async def ensure_connected(client: TelegramClient):
    """
    Telethon 클라이언트가 'disconnected'면 재연결.
    세션 만료 시 재로그인(OTP 없이 .session으로 자동).
    """
    if not client.is_connected():
        print("[INFO] Telethon is disconnected. Reconnecting...")
        await client.connect()

    # 세션 만료(미인증) 시 재로그인
    if not await client.is_user_authorized():
        print("[INFO] 세션 만료? 재로그인 시도 중...")
        await client.start(phone=PHONE_NUMBER)
        print("[INFO] 재로그인 완료")

# ========== [5] keep_alive(핑) 작업 ==========

async def keep_alive(client: TelegramClient):
    """
    주기적으로 호출해 Telethon 연결을 유지하기 위한 간단한 API 호출(핑).
    """
    try:
        await ensure_connected(client)
        # 간단한 Telethon 함수를 호출 (GetNearestDcRequest 등)
        await client(functions.help.GetNearestDcRequest())
        print("[INFO] keep_alive ping success")
    except Exception as e:
        print(f"[ERROR] keep_alive ping fail: {e}")

def keep_alive_wrapper(client: TelegramClient):
    # schedule이 동기이므로, 코루틴 함수를 create_task로 실행
    loop = asyncio.get_running_loop()
    loop.create_task(keep_alive(client))

# ========== [6] '내 계정'이 가입된 모든 그룹/채널 목록 불러오기 ==========

async def load_all_groups(client: TelegramClient):
    group_list = []
    await ensure_connected(client)
    dialogs = await client.get_dialogs()
    for d in dialogs:
        if d.is_group or d.is_channel:
            group_list.append(d.id)
    return group_list

# ========== [7] 실제 메시지 전송 로직 ==========
async def send_ad_messages(client: TelegramClient):
    """
    1) ensure_connected()로 연결상태 확인
    2) 모든 그룹/채널 목록 로드
    3) 광고 문구 + 카운터(Nㅎ) 생성
    4) 이미지+캡션 / 텍스트만 전송
    5) 그룹 간 5~10초 랜덤 대기
    6) counter+1
    """
    try:
        await ensure_connected(client)
        group_list = await load_all_groups(client)
        if not group_list:
            print("[WARN] 가입된 그룹/채널이 없거나 로드 실패.")
            return

        base_msg = load_base_message()
        counter = load_counter()

        for grp_id in group_list:
            final_caption = f"{base_msg}\n\n{counter}ㅎ"
            try:
                if os.path.exists(IMAGE_FILE):
                    await client.send_file(
                        entity=grp_id,
                        file=IMAGE_FILE,
                        caption=final_caption
                    )
                    print(f"[INFO] 전송 성공 (이미지+캡션) → {grp_id} / {counter}ㅎ")
                else:
                    await client.send_message(grp_id, final_caption)
                    print(f"[INFO] 전송 성공 (텍스트만) → {grp_id} / {counter}ㅎ")
            except Exception as e:
                print(f"[ERROR] 전송 실패 (chat_id={grp_id}): {e}")

            delay = random.randint(5, 10)
            print(f"[INFO] 다음 그룹 전송까지 {delay}초 대기...")
            await asyncio.sleep(delay)

        counter += 1
        save_counter(counter)

    except Exception as e:
        print(f"[ERROR] send_ad_messages 전체 에러: {e}")

def job_wrapper(client: TelegramClient):
    loop = asyncio.get_running_loop()
    loop.create_task(send_ad_messages(client))

# ========== [8] 메인 (이벤트 루프) ==========
async def main():
    # (1) 첫 로그인
    await client.start(phone=PHONE_NUMBER)
    print("[INFO] 텔레그램 로그인 성공!")

    @client.on(events.NewMessage(pattern="/ping"))
    async def ping_handler(event):
        await event.respond("pong!")

    # (2) 스케줄 등록
    # 2-1) 광고 전송: 1시간마다
    schedule.every(60).minutes.do(job_wrapper, client)
    # 예: 테스트용 10초마다 => schedule.every(10).seconds.do(job_wrapper, client)

    # 2-2) keep_alive ping: 예) 10분마다
    schedule.every(10).minutes.do(keep_alive_wrapper, client)

    # (3) 무한 루프
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())