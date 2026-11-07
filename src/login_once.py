#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小米账号登录（一次性），成功后登录态保存到 ~/.mi.token

用法：
    python login_once.py

说明：
    - 账号密码从环境变量 a / p 读取（也可用 MI_USER / MI_PASS）
    - 首次登录小米会要求短信验证码（OTP），需要你看着手机输入 6 位数字
    - 成功后 passToken 存在 ~/.mi.token，之后所有命令都不再需要验证码
    - 本脚本不会打印账号或密码
"""

import asyncio
import os
import sys

try:
    from miservice import MiAccount
except ImportError:
    print('缺少 miservice。请安装 GitHub 版：')
    print('  pip install "git+https://github.com/Yonsm/MiService.git"')
    sys.exit(1)

try:
    import aiohttp
except ImportError:
    print("缺少 aiohttp： pip install aiohttp")
    sys.exit(1)


def get_credential(primary: str, fallback: str) -> str:
    """优先读 primary，其次 fallback。"""
    v = os.environ.get(primary) or os.environ.get(fallback) or ""
    return v.strip()


async def otp_callback(method: str) -> str:
    """从标准输入读验证码。"""
    print()
    print("=" * 50)
    print(f"小米要求验证（{method}）")
    print("请查看手机短信，输入收到的验证码")
    print("=" * 50)
    try:
        code = input("验证码: ").strip()
    except EOFError:
        print("\n无法读取输入（不是交互终端）")
        print("请在真正的 PowerShell 窗口里运行本脚本")
        return ""
    return code


async def main():
    user = get_credential("a", "MI_USER")
    passwd = get_credential("p", "MI_PASS")

    if not user:
        print("错误：未找到账号（环境变量 a 或 MI_USER）")
        sys.exit(2)
    if not passwd:
        print("错误：未找到密码（环境变量 p 或 MI_PASS）")
        sys.exit(2)

    print(f"账号: {user[:3]}***{user[-2:]}（已脱敏）")
    print("正在登录小米账号...")
    print()

    # SSL 证书
    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
        os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    except ImportError:
        pass

    async with aiohttp.ClientSession() as session:
        account = MiAccount(session, user, passwd, otp_callback=otp_callback)
        try:
            ok = await account.login("micoapi")
        except Exception as e:
            print()
            print(f"登录失败：{e}")
            print()
            msg = str(e).lower()
            if "rate" in msg or "too many" in msg:
                print("原因：登录尝试过于频繁，小米临时限制。")
                print("建议：等 1 小时后再试。")
            elif "otp" in msg or "code" in msg:
                print("原因：验证码不正确或已过期。")
                print("建议：重新运行，输新的验证码。")
            sys.exit(3)

        if not ok:
            print("登录未成功")
            sys.exit(3)

        print()
        print("=" * 50)
        print("✅ 登录成功")
        print("=" * 50)
        print("登录态已保存，之后不再需要验证码。")
        print()
        print("接下来可以试：")
        print('  python -m miservice mina                  # 列出音箱')
        print('  python -m miservice mina "你好，我是小爱"   # TTS 播报')


if __name__ == "__main__":
    asyncio.run(main())
