#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
包装脚本：自动读取 .env，转成 MiService 能用的形式，然后发请求。

.env 支持的格式：
    格式1（抓包文本，含 cookie: 行）：
        cookie:
        deviceId=xxx; userId=yyy; serviceToken=zzz; ...

    格式2（单行 Cookie 头）：
        Cookie: deviceId=xxx; userId=yyy; serviceToken=zzz

    格式3（普通 k=v 每行一个）：
        MI_USER=手机号
        MI_PASS=密码

用法：
    python run.py list                  # 列设备（MIoT）
    python run.py mina                  # 列小爱音箱
    python run.py mina "你好"            # TTS 播报
    python run.py info                  # 显示解析到的凭据（脱敏）
"""

import asyncio
import json
import os
import re
import sys

# ---------- 证书 ----------
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

import aiohttp
from miservice import MiAccount, MiIOService, MiNAService

# ---------- .env 位置 ----------
ENV_CANDIDATES = [
    os.path.join(os.path.expanduser("~"), "Desktop", ".env"),
    ".env",
    os.path.join(os.path.dirname(__file__), ".env"),
    os.path.join(os.getcwd(), ".env"),
]

TOKEN_PATH = os.path.expanduser("~/.mi.token")


# ---------- token 存储：只写不删 ----------
class KeepTokenStore:
    """加载/保存 token，但 token 为空时【绝不删除文件】。"""

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


# ---------- .env 解析 ----------
def find_env_file():
    """找到存在的 .env 文件。"""
    for p in ENV_CANDIDATES:
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return p
    return None


def parse_env(path):
    """解析 .env，返回 (cookies, kv)。

    cookies: 浏览器 cookie 字典
    kv:      普通键值对（MI_USER 等）
    """
    raw = open(path, encoding="utf-8", errors="replace").read()
    cookies = {}
    kv = {}

    # --- 尝试找 "cookie:" 行（抓包格式） ---
    lines = raw.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if s.lower() == "cookie:":
            cv = lines[i + 1].strip() if i + 1 < len(lines) else ""
            cookies.update(parse_cookie_string(cv))
        elif s.lower().startswith("cookie:"):
            cookies.update(parse_cookie_string(s[7:].strip()))

    # --- 尝试单行 Cookie: 开头 ---
    if not cookies:
        s = raw.strip()
        if s.lower().startswith("cookie:"):
            cookies = parse_cookie_string(s[7:].strip())
        elif re.search(r"\bdeviceId\s*=", s) and re.search(r"\buserId\s*=", s):
            # 整份文件就是 cookie 字符串
            cookies = parse_cookie_string(s)

    # --- 普通 k=v ---
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k.upper().startswith("MI_") or k in ("a", "p"):
                kv[k] = v

    return cookies, kv


def parse_cookie_string(s):
    d = {}
    for part in s.split(";"):
        part = part.strip()
        if part and "=" in part:
            k, v = part.split("=", 1)
            d[k.strip()] = v.strip()
    return d


# ---------- 构建 MiAccount ----------
async def build_account():
    """从 .env 或已有 token 构建 MiAccount。"""
    env_path = find_env_file()
    cookies = {}
    kv = {}

    if env_path:
        cookies, kv = parse_env(env_path)

    # 优先级：已有 token > .env 里的 cookie > .env 里的账号密码 > 系统环境变量
    existing = None
    if os.path.exists(TOKEN_PATH):
        try:
            existing = json.load(open(TOKEN_PATH, encoding="utf-8"))
        except Exception:
            existing = None

    user = kv.get("MI_USER") or kv.get("a") or os.environ.get("MI_USER") or os.environ.get("a") or ""
    pwd = kv.get("MI_PASS") or kv.get("p") or os.environ.get("MI_PASS") or os.environ.get("p") or ""

    session = aiohttp.ClientSession()
    return session, cookies, existing, user, pwd, env_path


async def get_password_otp(method):
    raise Exception("NEED_OTP_MANUAL")


async def get_services():
    """返回 (session, mina, mio)。

    策略：
    1. 有 ~/.mi.token 且含 micoapi → 直接读
    2. .env 里有 serviceToken → 用它试
    3. 有账号密码 → 登录
    """
    session, cookies, existing, user, pwd, env_path = await build_account()

    print(f"[.env] {env_path or '(未找到)'}")
    if cookies:
        print(f"[.env] cookie 字段: {', '.join(sorted(cookies.keys()))}")
    if user:
        print(f"[.env] 账号: {user[:3]}***")

    acc = MiAccount(session, user or "_", pwd or "_", KeepTokenStore(TOKEN_PATH), get_password_otp)

    # 1) 已有 token
    if existing and "micoapi" in existing:
        acc.token = existing
        print("[token] 使用 ~/.mi.token")
        return session, MiNAService(acc), MiIOService(acc)

    # 2) 用 .env 里的 cookie 构造
    if cookies.get("userId") and cookies.get("serviceToken"):
        acc.token = {
            "deviceId": cookies.get("deviceId", ""),
            "userId": cookies["userId"],
            "passToken": cookies.get("passToken", ""),
            "micoapi": ["", cookies["serviceToken"]],
            "xiaomiio": ["", cookies["serviceToken"]],
        }
        print("[token] 用 .env 里的 serviceToken 构造")
        return session, MiNAService(acc), MiIOService(acc)

    # 3) 登录
    if not user or not pwd:
        session.close()
        print()
        print("错误：没有可用的凭据")
        print("  .env 里需要包含以下任一：")
        print("    - 账号密码：MI_USER=... / MI_PASS=...")
        print("    - 或浏览器 cookie（含 userId + serviceToken）")
        sys.exit(2)

    print("[login] 使用账号密码登录...")
    try:
        await acc.login("micoapi")
    except Exception as e:
        session.close()
        msg = str(e)
        print()
        if "70022" in msg:
            print("错误：70022 短信验证码发送过多，请等待后重试")
        elif "70016" in msg:
            print("错误：70016 登录验证失败")
        elif "No OTP" in msg or "NEED_OTP" in msg:
            print("错误：需要短信验证码，无法在非交互环境输入")
            print("请在真正的 PowerShell 窗口直接运行本脚本")
        else:
            print(f"错误：{msg[:300]}")
        sys.exit(3)

    return session, MiNAService(acc), MiIOService(acc)


# ---------- 命令 ----------
async def cmd_info():
    """显示解析到的凭据（脱敏）。"""
    env_path = find_env_file()
    if not env_path:
        print("未找到 .env")
        return

    cookies, kv = parse_env(env_path)
    print(f"文件: {env_path}")
    print()
    if cookies:
        print("发现 cookie：")
        for k in sorted(cookies):
            v = cookies[k]
            if len(v) > 40:
                print(f"  {k}: [长度 {len(v)}] 前缀={v[:25]}")
            else:
                print(f"  {k}: {v}")
    if kv:
        print()
        print("发现键值对：")
        for k in sorted(kv):
            v = kv[k]
            if k.upper() in ("MI_PASS", "P"):
                print(f"  {k}: [已设置，长度 {len(v)}]")
            else:
                print(f"  {k}: {v}")

    print()
    print("MiService 需要的环境变量：MI_USER / MI_PASS / MI_DID / MI_LOCAL")


async def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    if args[0] == "info":
        await cmd_info()
        return

    session, mina, mio = await get_services()
    try:
        if args[0] == "mina":
            # 小爱音箱
            if len(args) == 1:
                devices = await mina.device_list()
                if not devices:
                    print("没有找到小爱音箱")
                    return
                print(f"找到 {len(devices)} 个音箱：")
                for i, d in enumerate(devices, 1):
                    print(f"  [{i}] {d.get('name')}")
                    print(f"      deviceID: {d.get('deviceID')}")
                    print(f"      hardware: {d.get('hardware')}")
            else:
                text = " ".join(args[1:])
                devices = await mina.device_list()
                if not devices:
                    print("没有找到小爱音箱")
                    return
                did = devices[0].get("deviceID")
                ok = await mina.text_to_speech(did, text)
                print(f"播报{'成功' if ok else '失败'}: {text}")

        elif args[0] == "list":
            devices = await mio.device_list()
            if not devices:
                print("没有找到设备")
                return
            print(f"找到 {len(devices)} 个设备：")
            for d in devices[:20]:
                print(f"  {d.get('name')} | {d.get('model')} | did={d.get('did')}")

        elif args[0] == "raw":
            # 直接调 MiNA 接口
            r = await mina.mina_request(" ".join(args[1:]))
            print(r)

        else:
            print(__doc__)

    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
