#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用浏览器 cookie 里的 passToken 换取 MiService 完整登录态（免密码、免短信验证码）

原理：
    小米的 `passToken` 是长期有效的免密登录凭据。
    MiService 的 _serviceLogin() 支持带上它：
        cookies['userId'] = token['userId']
        cookies['passToken'] = token['passToken']
    这样就能直接走 serviceLogin → 拿到 ssecurity → 换取 micoapi 的 serviceToken，
    完全不需要账号密码，也不会触发短信验证码。

用法：
    python from_passtoken.py                        # 从 tmp/.env 读取
    python from_passtoken.py path/to/cookie.txt     # 指定文件
    python from_passtoken.py --cookie "userId=x; passToken=y"

前置：
    pip install "git+https://github.com/Yonsm/MiService.git" aiohttp certifi
"""

import asyncio
import json
import os
import re
import sys

TOKEN_PATH = os.path.expanduser("~/.mi.token")

try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

try:
    import aiohttp
    from miservice import MiAccount
except ImportError:
    print('缺少依赖: pip install "git+https://github.com/Yonsm/MiService.git" aiohttp certifi')
    sys.exit(1)


def parse_cookie_string(s):
    d = {}
    for part in s.split(";"):
        part = part.strip()
        if part and "=" in part:
            k, v = part.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def extract_cookie(raw):
    """从抓包文本提取 cookie。"""
    lines = raw.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if re.match(r"^cookie:\s*$", s, re.I):
            if i + 1 < len(lines):
                return parse_cookie_string(lines[i + 1].strip())
        elif s.lower().startswith("cookie:"):
            return parse_cookie_string(s[7:].strip())
    # 也可能整个文件就是 cookie 字符串
    return parse_cookie_string(raw)


async def otp_callback(method):
    """理论上不会调用（用 passToken 免密）；万一调用说明 passToken 失效了。"""
    print()
    print("! passToken 无效，小米要求短信验证。")
    print("  这需要人工输入验证码，请在自己终端里运行 login_once.py。")
    return ""


async def main():
    args = sys.argv[1:]

    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return

    if args and args[0] == "--cookie":
        if len(args) < 2:
            print("错误: --cookie 后面要跟 cookie 字符串")
            return
        cookies = parse_cookie_string(args[1])
    else:
        path = args[0] if args else ".env"
        if not os.path.exists(path):
            print(f"文件不存在: {path}")
            print("用法: python from_passtoken.py [cookie文件]")
            return
        raw = open(path, encoding="utf-8", errors="replace").read()
        cookies = extract_cookie(raw)

    user_id = cookies.get("userId")
    pass_token = cookies.get("passToken")

    print("解析 cookie：")
    print(f"  userId:    {'有' if user_id else '缺失'}")
    print(f"  passToken: {'有 (长度 %d)' % len(pass_token) if pass_token else '缺失'}")

    if not user_id or not pass_token:
        print()
        print("错误：需要 userId 和 passToken 两个 cookie")
        print("获取方法：浏览器登录小米账号后，F12 → Network → 任一 account.xiaomi.com 请求 → 复制 Cookie 头")
        return

    print()
    print("正在用 passToken 换取登录态（免密码）...")

    async with aiohttp.ClientSession() as session:
        account = MiAccount(session, "_", "_", str(TOKEN_PATH), otp_callback)
        # 手动塞入 passToken
        account.token = {
            "deviceId": cookies.get("deviceId", ""),
            "userId": user_id,
            "passToken": pass_token,
        }

        try:
            ok = await account.login("micoapi")
        except Exception as e:
            msg = str(e)
            print()
            print("失败：")
            if "No OTP" in msg or "OTP" in msg:
                print("  passToken 已失效，需要重新登录（走短信验证）")
            elif "70022" in msg or "70016" in msg:
                print("  小米风控/验证码频率限制，请稍后再试")
            else:
                print(f"  {msg[:300]}")
            return

        if not ok:
            print("登录失败")
            return

        print()
        print("=" * 50)
        print(f"[OK] 登录态已生成: {TOKEN_PATH}")
        print("=" * 50)

        # 显示结构
        try:
            t = json.load(open(TOKEN_PATH, encoding="utf-8"))
            print()
            print("token 内容：")
            for k, v in t.items():
                if isinstance(v, list):
                    print(f"  {k}: [ssecurity={'有' if v[0] else '空'}, serviceToken 长度 {len(v[1]) if len(v) > 1 else 0}]")
                elif isinstance(v, str) and len(v) > 20:
                    print(f"  {k}: [长度 {len(v)}]")
                else:
                    print(f"  {k}: {v}")
        except Exception:
            pass

    print()
    print("现在可以用：")
    print("    python tts.py -l          # 列出音箱")
    print('    python tts.py "你好"       # 播报')


if __name__ == "__main__":
    asyncio.run(main())
