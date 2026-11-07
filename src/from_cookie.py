#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从浏览器 cookie 生成 MiService 的 token 文件（免 OTP 验证码）

原理：
    MiService 发请求时只需要两个 cookie：
        userId       + serviceToken
    见 miservice/miaccount.py:308
        cookies = {'userId': self.token['userId'], 'serviceToken': self.token[sid][1]}

    所以只要能拿到浏览器的 cookie，就能直接构造 ~/.mi.token，
    完全跳过账号密码登录和短信验证码。

用法：
    1. 把浏览器抓到的 Cookie 存成文件（一行，格式 k1=v1; k2=v2; ...）
       例如 cookie.txt

    2. python from_cookie.py cookie.txt
       或
       python from_cookie.py --cookie "deviceId=xxx; userId=123; serviceToken=yyy"

    3. 生成 ~/.mi.token，然后就能直接用 tts.py

安全说明：
    - 本脚本只读取你提供的 cookie 文件，不上传任何东西
    - 生成的 ~/.mi.token 等同账号权限，注意保管
"""

import json
import os
import re
import sys

TOKEN_PATH = os.path.expanduser("~/.mi.token")

# MiService 需要的 sid（服务标识）
# minaservice 用 micoapi，miioservice 用 xiaomiio
SIDS = ["micoapi", "xiaomiio"]


def parse_cookie_string(s: str) -> dict:
    """解析 'k1=v1; k2=v2' 形式的 cookie。"""
    d = {}
    for part in s.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        d[k.strip()] = v.strip()
    return d


def extract_from_capture(raw: str) -> dict:
    """从抓包文本里提取 cookie（支持 'cookie:' 换行格式）。"""
    lines = raw.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if re.match(r"^cookie:\s*$", s, re.I):
            if i + 1 < len(lines):
                return parse_cookie_string(lines[i + 1].strip())
        elif s.lower().startswith("cookie:"):
            return parse_cookie_string(s[7:].strip())
    return {}


def build_token(cookies: dict) -> dict:
    """构造 MiService token 结构。"""
    user_id = cookies.get("userId")
    service_token = cookies.get("serviceToken")
    pass_token = cookies.get("passToken")
    device_id = cookies.get("deviceId", "")

    missing = []
    if not user_id:
        missing.append("userId")
    if not service_token:
        missing.append("serviceToken")
    if missing:
        raise ValueError("缺少必需字段: " + ", ".join(missing))

    token = {
        "deviceId": device_id,
        "userId": user_id,
        "passToken": pass_token or "",
    }

    # 每个服务都存一份 (ssecurity, serviceToken)
    # ssecurity 用于签名，浏览器 cookie 里没有，但 mi_request 只在 relogin 时才用，
    # 有 serviceToken 就能直接发请求，所以这里填占位值
    for sid in SIDS:
        token[sid] = ["", service_token]

    return token


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return

    cookies = {}

    if args[0] == "--cookie":
        if len(args) < 2:
            print("错误：--cookie 后面要跟 cookie 字符串")
            return
        cookies = parse_cookie_string(args[1])
    else:
        path = args[0]
        if not os.path.exists(path):
            print(f"文件不存在: {path}")
            return
        raw = open(path, encoding="utf-8", errors="replace").read()
        # 先尝试当纯 cookie 字符串解析
        cookies = parse_cookie_string(raw)
        if "userId" not in cookies or "serviceToken" not in cookies:
            # 再尝试当抓包文本解析
            cookies = extract_from_capture(raw)

    if not cookies:
        print("未能从输入中解析出 cookie")
        return

    print("解析到 cookie 字段：")
    for k in sorted(cookies):
        print(f"    {k}: 长度 {len(cookies[k])}")

    try:
        token = build_token(cookies)
    except ValueError as e:
        print()
        print(f"错误：{e}")
        print()
        print("需要至少包含 userId 和 serviceToken 两个 cookie。")
        print("获取方法：浏览器登录小米账号后，F12 → Network → 任意 account.xiaomi.com 请求 → 复制 Cookie 头")
        return

    # 备份已有 token
    if os.path.exists(TOKEN_PATH):
        backup = TOKEN_PATH + ".bak"
        os.replace(TOKEN_PATH, backup)
        print(f"\n已备份旧 token 到 {backup}")

    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(token, f)

    print()
    print("=" * 50)
    print(f"[OK] 已生成 token: {TOKEN_PATH}")
    print("=" * 50)
    print()
    print("现在可以直接用了：")
    print('    python tts.py -l           # 列出音箱')
    print('    python tts.py "你好"        # 播报')


if __name__ == "__main__":
    main()
