import os
import asyncio
import random
import time

from telethon import TelegramClient, events, functions
from telethon.errors import FloodWaitError, RPCError

# ========== [1] 텔레그램 API 설정 ==========
API_ID = int(os.getenv("API_ID", "23353481"))
API_HASH = os.getenv("API_HASH", "3d62dd4e702e42e4c662fb85f96f64b9")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "+818027404273")  # 예시

SESSION_NAME = "my_telethon_session"
client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH,
    timeout=60,
    auto_reconnect=True
)

# ========== [2] 홍보용 계정(마케팅 계정) ==========
MARKETING_USER = "@my_marketing_account"  # 예시: 유저네임 or 정수 ID

# ========== [3] 연결/세션 확인 함수 ==========
async def ensure_connected():
    if not client.is_connected():
        print("[INFO] Telethon is disconnected. Reconnecting...")
        await client.connect()

    if not await client.is_user_authorized():
        print("[WARN] 세션 없음/만료 → OTP 로그인 시도")
        await client.start(phone=PHONE_NUMBER)
        print("[INFO] 재로그인(OTP) 완료")


# ========== [4] keep_alive ==========
async def keep_alive():
    """
    10분 간격 등으로 주기적 호출하여 Telethon 연결 상태 유지
    """
    try:
        await ensure_connected()
        await client(functions.help.GetNearestDcRequest())
        print("[INFO] keep_alive ping success")
    except Exception as e:
        print(f"[ERROR] keep_alive ping fail: {e}")


# ========== [5] 그룹 목록 로드 ==========
async def load_all_groups():
    """
    - 계정이 가입한 모든 그룹/채널을 가져옴
    - 폴더/카테고리 구분 없이 전부
    """
    await ensure_connected()
    dialogs = await client.get_dialogs()
    return [d.id for d in dialogs if d.is_group or d.is_channel]


# ========== [6] '홍보 계정'의 최근 N개 메시지 가져오기 ==========
async def get_recent_messages(user, limit=3):
    """
    - user(예: @my_marketing_account) 로부터 '최근 N개' 메시지 목록을 가져옴
    - 최신 메시지가 msgs[0], 그 다음이 msgs[1] ... 순서가 됨
    - 메시지가 limit보다 적으면 있는 만큼만 반환
    """
    await ensure_connected()
    try:
        msgs = await client.get_messages(user, limit=limit)
        # Telethon은 최신순으로 반환하므로 msgs[0]이 '가장 최근'
        if not msgs:
            print("[WARN] 홍보용 계정에서 메시지를 가져올 수 없습니다.")
            return []
        return msgs
    except RPCError as e:
        print(f"[ERROR] get_recent_messages RPC 에러: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] get_recent_messages 에러: {e}")
        return []


# ========== [7] 모든 그룹에 '홍보 메시지들'을 순환하며 포워딩 ==========
async def forward_cycle_messages():
    """
    1) 홍보용 계정의 최근 N개 메시지를 가져옴(예: N=3 → a, b, c)
    2) 가입된 그룹 리스트를 전부 불러옴
    3) 순차적으로 그룹에 메시지를 포워딩
       - 그룹1 -> msg[0], 그룹2 -> msg[1], 그룹3 -> msg[2], 그룹4 -> msg[0], ...
    4) 그룹 간 30~60초 대기
    """

    # (A) 홍보 계정의 최근 3개 메시지를 가져옴
    marketing_msgs = await get_recent_messages(MARKETING_USER, limit=3)
    if not marketing_msgs:
        print("[WARN] 홍보용 계정 메시지가 없어 전송할 수 없음.")
        return

    # (B) 전체 그룹 목록
    group_list = await load_all_groups()
    if not group_list:
        print("[WARN] 가입된 그룹이 없습니다.")
        return

    print(f"[INFO] {len(marketing_msgs)}개 메시지를 순환하며, {len(group_list)}개 그룹에 전송합니다.")

    # (C) 실제 포워딩
    msg_count = len(marketing_msgs)
    group_count = len(group_list)

    # idx를 0부터 시작해서 msg_count로 모듈러 연산
    msg_idx = 0

    for i, grp_id in enumerate(group_list, start=1):
        # 1) 현재 순번 메시지
        current_msg = marketing_msgs[msg_idx]

        try:
            await client.forward_messages(grp_id, current_msg.id, from_peer=current_msg.sender_id)
            print(f"[INFO] 그룹 {i}/{group_count} → (메시지 {msg_idx}/{msg_count-1}) 포워딩 성공: {grp_id}")
        except FloodWaitError as e:
            print(f"[ERROR] FloodWait: {e}. {e.seconds}초 대기 후 재시도.")
            await asyncio.sleep(e.seconds + 5)
            # 재시도 (간단히 한 번 더 시도)
            try:
                await client.forward_messages(grp_id, current_msg.id, from_peer=current_msg.sender_id)
            except Exception as err2:
                print(f"[ERROR] 재시도 실패: {err2}")

        except RPCError as e:
            print(f"[ERROR] Forward RPCError(chat_id={grp_id}): {e}")

        except Exception as e:
            print(f"[ERROR] Forward 실패(chat_id={grp_id}): {e}")

        # 2) 메시지 인덱스 순환 (0→1→2→0→1→2...)
        msg_idx = (msg_idx + 1) % msg_count

        # 3) 그룹 간 대기 30~60초
        delay = random.randint(30, 60)
        print(f"[INFO] 다음 그룹 전송까지 {delay}초 대기...")
        await asyncio.sleep(delay)

    print("[INFO] 모든 그룹 전송(Forward) 완료 (이번 사이클).")


# ========== [8] 사이클 무한 루프 ==========
async def send_messages_loop():
    """
    - forward_cycle_messages() 실행
    - 사이클 간 1시간 대기
    - 무한 반복
    """
    while True:
        try:
            await ensure_connected()

            # (1) 한 번 전체 그룹에 순환 전송
            await forward_cycle_messages()

            # (2) 사이클 간 1시간 대기
            cycle_delay = 3600  # 1시간 = 3600초
            print(f"[INFO] 이번 사이클 종료. {cycle_delay//3600}시간 후 다시 시작합니다.")
            await asyncio.sleep(cycle_delay)

        except Exception as e:
            print(f"[ERROR] send_messages_loop() 에러: {e}")
            await asyncio.sleep(600)  # 에러 시 10분 후 재시도


# ========== [9] 메인 함수 ==========
async def main():
    # 1) 텔레그램 연결
    await client.connect()
    print("[INFO] client.connect() 완료")

    # 2) 세션 인증
    if not (await client.is_user_authorized()):
        print("[INFO] 세션 없음 or 만료 → OTP 로그인 시도")
        await client.start(phone=PHONE_NUMBER)
        print("[INFO] 첫 로그인 or 재인증 성공")
    else:
        print("[INFO] 이미 인증된 세션 (OTP 불필요)")

    @client.on(events.NewMessage(pattern="/ping"))
    async def ping_handler(event):
        await event.respond("pong!")

    print("[INFO] 텔레그램 로그인(세션) 준비 완료")

    # (A) keep_alive (예: 10분마다)
    async def keep_alive_scheduler():
        while True:
            await keep_alive()
            await asyncio.sleep(600)  # 10분

    # (B) 전송 루프 + keep_alive 병행
    await asyncio.gather(
        send_messages_loop(),
        keep_alive_scheduler()
    )


# ========== [10] 실행 ==========
if __name__ == "__main__":
    asyncio.run(main())
