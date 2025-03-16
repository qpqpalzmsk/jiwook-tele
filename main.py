import os
import asyncio
import random
import schedule
import time

from telethon import TelegramClient, events, functions

# ========== [1] 텔레그램 API 설정 ==========
API_ID = int(os.getenv("API_ID", "123456"))
API_HASH = os.getenv("API_HASH", "abcdef1234567890abcdef1234567890")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "+821012345678")

SESSION_NAME = "my_telethon_session"

# ----- Telethon 클라이언트 생성 -----
# 여기서 'ping_interval', 'connection_retries', 'request_retries' 등
# 호환 안 되는 파라미터는 제거.
# 'timeout=60' 정도만 유지해보겠습니다.
client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH,
    timeout=60,          # 한 번의 연결/응답 최대 대기 시간(초)
    auto_reconnect=True  # 연결 끊기면 자동 재연결 시도
)

# ========== [2] 파일 경로 설정 ==========
ADVERT_FILE = "advert_message.txt"   # 광고 문구
COUNTER_FILE = "counter.txt"         # 전송 횟수
IMAGE_FILE = "my_ad_image.jpg"       # 이미지 파일(있으면 이미지+캡션, 없으면 텍스트만)

# ========== [3] 파일 로드/저장 함수들 ==========

def load_base_message():
    if not os.path.exists(ADVERT_FILE):
        return "광고 문구가 없습니다."
    with open(ADVERT_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()

def load_counter():
    if not os.path.exists(COUNTER_FILE):
        return 1
    with open(COUNTER_FILE, "r", encoding="utf-8") as f:
        data = f.read().strip()
        return int(data) if data.isdigit() else 1

def save_counter(value: int):
    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        f.write(str(value))

# ========== [4] 연결확인/재연결 함수 ==========

async def ensure_connected(client: TelegramClient):
    """
    Telethon이 'disconnected'면 재연결.
    세션 만료 시 재로그인(.session)으로 OTP 없이.
    """
    if not client.is_connected():
        print("[INFO] Telethon is disconnected. Reconnecting...")
        await client.connect()

    # 인증 만료 시 재로그인
    if not await client.is_user_authorized():
        print("[INFO] 세션 만료? 재로그인 시도 중...")
        await client.start(phone=PHONE_NUMBER)
        print("[INFO] 재로그인 완료")

# ========== [5] keep_alive(핑) 작업 ==========

async def keep_alive(client: TelegramClient):
    """
    주기적으로 호출 → 간단한 API를 실행해 유휴 상태 방지 (예: help.GetNearestDcRequest).
    """
    try:
        await ensure_connected(client)
        # 아무 가벼운 함수나 호출해서 서버와 통신
        await client(functions.help.GetNearestDcRequest())
        print("[INFO] keep_alive ping success")
    except Exception as e:
        print(f"[ERROR] keep_alive ping fail: {e}")

def keep_alive_wrapper(client: TelegramClient):
    loop = asyncio.get_running_loop()
    loop.create_task(keep_alive(client))

# ========== [6] '내 계정' 가입된 모든 그룹/채널 목록 불러오기 ==========

async def load_all_groups(client: TelegramClient):
    await ensure_connected(client)
    dialogs = await client.get_dialogs()
    group_list = [d.id for d in dialogs if d.is_group or d.is_channel]
    return group_list

# ========== [7] 실제 메시지 전송 로직 ==========
async def send_ad_messages(client: TelegramClient):
    """
    1) ensure_connected()로 연결상태 확인
    2) 광고 문구 + 카운터(Nㅎ)
    3) 그룹마다 이미지 or 텍스트 전송
    4) 그룹 간 5~10초 대기
    5) counter+1
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
                    await client.send_file(grp_id, IMAGE_FILE, caption=final_caption)
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
    # (테스트하려면 아래 처럼 짧게)
    # schedule.every(10).seconds.do(job_wrapper, client)

    # 2-2) keep_alive: 10분마다
    schedule.every(10).minutes.do(keep_alive_wrapper, client)

    # (3) 무한 루프
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())