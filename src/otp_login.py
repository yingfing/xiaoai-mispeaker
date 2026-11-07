import asyncio, os, time
import aiohttp
from miservice import MiAccount

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

async def otp_cb(method):
    # 通知父进程：需要验证码
    with open(os.path.join(BASE, "otp_request.flag"), "w") as f:
        f.write(method)
    print("OTP_REQUIRED", flush=True)
    # 轮询等待用户提供验证码
    path = os.path.join(BASE, "otp_code.txt")
    for _ in range(600):  # 最多等 10 分钟
        await asyncio.sleep(1)
        if os.path.exists(path):
            with open(path) as f:
                code = f.read().strip()
            if code:
                print("OTP_GOT", flush=True)
                return code
    raise Exception("等待验证码超时")

async def main():
    user = os.environ.get("a"); pwd = os.environ.get("p")
    async with aiohttp.ClientSession() as s:
        acc = MiAccount(s, user, pwd, otp_callback=otp_cb)
        try:
            ok = await acc.login("micoapi")
            print("LOGIN_RESULT:", ok, flush=True)
        except Exception as e:
            print("LOGIN_ERROR:", str(e)[:300], flush=True)

asyncio.run(main())