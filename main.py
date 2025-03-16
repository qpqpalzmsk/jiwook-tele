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

SESSION_NAME = "my_telethon_session"  # .session 파일 이름(예: my_telethon_session.session)

# Telethon 클라이언트 생성 (이미 .session이 있을 때 재사용)
# 여기서는 불필요한 파라미터 (ping_interval, etc.)를 뺐고,
# timeout만 예시로 60초 줍니다.
client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH,
    timeout=60,
    auto_reconnect=True
)

# ========== [2] 파일 경로 설정 ==========
ADVERT_FILE = "advert_message.txt"
COUNTER_FILE = "counter.txt"
IMAGE_FILE = "my_ad_image.jpg"

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
    이미 .session이 있으면 OTP 없이 재인증.
    """
    if not client.is_connected():
        print("[INFO] Telethon is disconnected. Reconnecting...")
        await client.connect()

    # 만약 세션 만료 등으로 미인증이면, 여기서 다시 start() => OTP?
    # 다만, ideally .session이 살아있으면 아래가 false.
    if not await client.is_user_authorized():
        print("[WARN] 세션이 만료 or 없는 상태? phone=PHONE_NUMBER 재인증 시도")
        await client.start(phone=PHONE_NUMBER)
        print("[INFO] 재로그인 완료")

# ========== [5] 주기적 keep_alive (유휴 방지) ==========

async def keep_alive(client: TelegramClient):
    try:
        await ensure_connected(client)
        # 간단한 API 호출
        await client(functions.help.GetNearestDcRequest())
        print("[INFO] keep_alive ping success")
    except Exception as e:
        print(f"[ERROR] keep_alive ping fail: {e}")

def keep_alive_wrapper(client: TelegramClient):
    loop = asyncio.get_running_loop()
    loop.create_task(keep_alive(client))

# ========== [6] '내 계정'이 가입된 그룹/채널 불러오기 ==========

async def load_all_groups(client: TelegramClient):
    await ensure_connected(client)
    dialogs = await client.get_dialogs()
    return [d.id for d in dialogs if d.is_group or d.is_channel]

# ========== [7] 메시지 전송 로직 ==========

async def send_ad_messages(client: TelegramClient):
    """
    - ensure_connected()
    - load_all_groups
    - 광고 문구 + 카운터
    - 이미지+캡션 / 텍스트 전송
    - 그룹 간 5~10초 쉬고
    - counter+1
    """
    try:
        await ensure_connected(client)
        group_list = await load_all_groups(client)
        if not group_list:
            print("[WARN] 가입된 그룹/채널이 없는 것 같습니다.")
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

# ========== [8] 메인 ==========

async def main():
    # (A) 먼저 client.connect() (비동기 연결 시도)
    await client.connect()
    print("[INFO] client.connect() 완료")

    # (B) 이미 인증된 세션인지 확인
    if not (await client.is_user_authorized()):
        print("[INFO] 세션이 없거나 만료 -> OTP 로그인 시도")
        await client.start(phone=PHONE_NUMBER)
        print("[INFO] 첫 로그인 or 재인증 성공")
    else:
        print("[INFO] 이미 인증된 세션, OTP 불필요")

    @client.on(events.NewMessage(pattern="/ping"))
    async def ping_handler(event):
        await event.respond("pong!")

    print("[INFO] 텔레그램 로그인(세션) 준비 완료")

    # 스케줄 등록
    schedule.every(60).minutes.do(job_wrapper, client)  # 1시간마다 광고
    schedule.every(10).minutes.do(keep_alive_wrapper, client)  # 10분마다 ping

    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())