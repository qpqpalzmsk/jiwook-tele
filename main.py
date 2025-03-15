import os
import asyncio
import random
import schedule
import time

from telethon import TelegramClient, events

# ========== [1] 텔레그램 API 설정 ==========
API_ID = int(os.getenv("API_ID", "25406586"))
API_HASH = os.getenv("API_HASH", "6db86b75255c9c998a19583f80a525bb")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "+819026176332")

SESSION_NAME = "jiwook"

# ========== [2] 파일 경로 설정 ==========
ADVERT_FILE = "advert_message.txt"   # 광고 문구
COUNTER_FILE = "counter.txt"         # 전송 횟수
IMAGE_FILE = "my_ad_image.jpg"       # 이미지 파일 (있으면 이미지+캡션, 없으면 텍스트만)

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

# ========== [4] '내 계정'이 가입된 모든 그룹/채널 목록 불러오기 ==========

async def load_all_groups(client: TelegramClient):
    """
    현재 계정이 참여 중인 대화(Dialog) 중
    그룹 or 채널만 골라서 리스트로 반환.
    """
    group_list = []
    dialogs = await client.get_dialogs()

    for d in dialogs:
        if d.is_group or d.is_channel:
            group_list.append(d.id)  # -1001234567890 형태
    return group_list

# ========== [5] 실제 메시지 전송 로직 (조건 분기: 이미지 유무) ==========
async def send_ad_messages(client: TelegramClient):
    """
    1) '내 계정'이 참여 중인 모든 그룹/채널 목록 불러오기
    2) 광고 문구 + 전송 횟수(Nㅎ) 생성
    3) 이미지 파일이 존재하면 send_file(이미지+캡션),
       없으면 send_message(텍스트만) 전송
    4) 그룹 간 5~10초 랜덤 지연
    5) 모든 전송 후 counter +1
    """
    group_list = await load_all_groups(client)
    if not group_list:
        print("[WARN] 가입된 그룹/채널이 없거나, 불러오지 못했습니다.")
        return

    base_msg = load_base_message()
    counter = load_counter()

    for grp_id in group_list:
        final_caption = f"{base_msg}\n\n{counter}ㅎ"

        try:
            if os.path.exists(IMAGE_FILE):
                # 이미지 파일이 있으면 send_file() + caption
                await client.send_file(
                    entity=grp_id,
                    file=IMAGE_FILE,
                    caption=final_caption
                )
                print(f"[INFO] 전송 성공 (이미지+캡션) → {grp_id} / {counter}ㅎ")
            else:
                # 이미지가 없으면 텍스트만 전송
                await client.send_message(grp_id, final_caption)
                print(f"[INFO] 전송 성공 (텍스트만) → {grp_id} / {counter}ㅎ")
        except Exception as e:
            print(f"[ERROR] 전송 실패 (chat_id={grp_id}): {e}")

        # 그룹 간 5~10초 랜덤 대기
        delay = random.randint(5, 10)
        print(f"[INFO] 다음 전송까지 {delay}초 대기...")
        await asyncio.sleep(delay)

    # 모든 대상에 전송 완료 후 counter +1
    counter += 1
    save_counter(counter)

# ========== [6] schedule → 코루틴 호출 래퍼 ==========
def job_wrapper(client: TelegramClient):
    """
    schedule (동기)에서 이 함수를 호출.
    이미 실행 중인 이벤트 루프에 create_task() 등록 -> 중첩 run 방지
    """
    loop = asyncio.get_running_loop()
    loop.create_task(send_ad_messages(client))

# ========== [7] 메인 함수 (이벤트 루프) ==========
async def main():
    # 1) 텔레그램 로그인
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start(phone=PHONE_NUMBER)
    print("[INFO] 텔레그램 로그인 성공!")

    # (선택) 특정 명령 핸들러 예시 (/ping)
    @client.on(events.NewMessage(pattern="/ping"))
    async def ping_handler(event):
        await event.respond("pong!")

    # 2) 스케줄 설정 (예: 30분마다)
    schedule.every(1).hours.do(job_wrapper, client)
    # 테스트용으로 짧게 하려면:
    # schedule.every(10).seconds.do(job_wrapper, client)

    # 3) 무한 루프: schedule.run_pending() 주기적 호출
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())