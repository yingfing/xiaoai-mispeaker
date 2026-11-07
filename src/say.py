#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小爱音箱 TTS（Python 版，走 MiIO 服务）

为什么不用 MiNA：
    MiNA（api2.mina.mi.com）需要管理员权限的 serviceToken，
    普通账号调用 ubus 会报 `invalid admin`。
    而 MiIO（api.io.mi.com）用 siid-aiid 动作调用，普通账号即可。

用法：
    python say.py "你好世界"
    python say.py -d 979227698 "指定设备"
    python say.py --list            # 列设备
"""

import asyncio
import json
import os
import sys

try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

try:
    import aiohttp
    from miservice import MiAccount, MiIOService
except ImportError:
    print("缺少依赖：")
    print('  pip install "git+https://github.com/Yonsm/MiService.git" aiohttp certifi')
    sys.exit(1)

TOKEN_PATH = os.path.expanduser("~/.mi.token")

# 已知型号的 TTS siid-aiid（来自 xiaomusic const.py 与实测）
# L05B 等用 5-1（文本播报）
TTS_MAP = {
    "L05B": "5-1",
    "L05C": "5-1",
    "LX04": "5-1",
    "LX05": "5-1",
    "L06":  "5-1",
    "L06A": "5-1",
    "LX06": "5-1",
    "OH2":  "5-3",
    "X08A": "5-1",
    "X08C": "5-1",
    "X08E": "5-1",
    "X8F":  "5-1",
    "X4B":  "5-1",
    "X6A":  "5-1",
}
DEFAULT_TTS = "5-1"


class KeepTokenStore:
    def __init__(self, path):
        self.path = path

    async def load_token(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    async def save_token(self, token=None):
        if not token:
            return
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(token, f, indent=2)
        except Exception:
            pass


async def otp(m):
    raise Exception("需要验证码，请先运行 login_once.py 或让 Node 版生成 token")


async def get_mio():
    if not os.path.exists(TOKEN_PATH):
        print(f"错误：找不到 {TOKEN_PATH}")
        print("请先完成登录（可用 Node 版：miservice list）")
        sys.exit(2)

    session = aiohttp.ClientSession()
    acc = MiAccount(session, "_", "_", KeepTokenStore(TOKEN_PATH), otp)
    acc.token = await acc.token_store.load_token()

    if not acc.token:
        session.close()
        print("错误：token 文件无法解析")
        sys.exit(2)

    return session, MiIOService(acc)


async def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    session, mio = await get_mio()
    try:
        # 列设备
        if args[0] in ("--list", "-l"):
            devices = await mio.device_list()
            if not devices:
                print("没有设备")
                return
            print(f"找到 {len(devices)} 个设备：")
            for d in devices:
                print(f"  {d.get('name')} | {d.get('model')} | did={d.get('did')}")
            return

        # 指定设备
        did = None
        if args[0] == "-d":
            if len(args) < 3:
                print("用法: python say.py -d <did> <文字>")
                return
            did = args[1]
            text = " ".join(args[2:])
        else:
            text = " ".join(args)

        # 拿设备信息
        devices = await mio.device_list()
        if not devices:
            print("没有设备")
            return

        target = None
        if did:
            target = next((d for d in devices if str(d.get("did")) == str(did)), None)
        else:
            target = devices[0]

        if not target:
            print(f"找不到设备 did={did}")
            return

        # 推断硬件型号
        model = target.get("model", "")
        hardware = ""
        if "wifispeaker." in model:
            hardware = model.split(".")[-1].upper()

        action = TTS_MAP.get(hardware, DEFAULT_TTS)

        print(f"设备: {target.get('name')} ({hardware})")
        print(f"动作: {action}")
        print(f"文字: {text[:50]}{'...' if len(text) > 50 else ''}")

        # 执行
        # 注意：miot_action 的 iid 是 (siid, aiid) 元组，不是 "5-1" 字符串
        try:
            siid, aiid = action.split("-")
            code = await mio.miot_action(
                target["did"], (int(siid), int(aiid)), [text]
            )
            print()
            # 实测：成功时也返回负数（如 -704220025），
            # 这是小米 miotspec/action 的正常响应，Node 版同样如此。
            # 只有像 code=1 (invalid admin) 或 -8 (data type not valid) 才是失败。
            if code in (0,) or (isinstance(code, int) and code not in (1, -8)):
                print(f"[成功] 音箱应该已播报 (code={code})")
            else:
                print(f"[失败] code={code}")
                print("可尝试其它动作：5-1, 5-3, 5-4")
        except Exception as e:
            print(f"\n失败: {e}")
            print()
            print("排查：")
            print(f"  1. 设备是否在线")
            print(f"  2. 型号 {hardware} 的 TTS 动作是否是 {action}")
            print(f"  3. 试试其他动作: 5-1, 5-3, 5-4")

    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
