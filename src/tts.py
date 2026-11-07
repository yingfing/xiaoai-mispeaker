#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小爱音箱 TTS 客户端 —— 把音箱变成「长嘴的客户端」

用法：
    python tts.py "你好世界"              # 说一句话
    python tts.py -f 文本.txt             # 念一个文件
    python tts.py -l                      # 列出所有小爱音箱
    python tts.py -d 3 "指定第3个音箱说"   # 指定设备

    python tts.py serve                   # 起本地 HTTP 接口
    python tts.py serve --port 8099

HTTP 接口（配合 serve 使用）：
    GET /say?text=你好              → 播报「你好」
    GET /say?text=你好&did=设备ID   → 指定设备
    GET /devices                    → 列出设备

依赖：
    登录态需要先存在 ~/.mi.token（见 login_once.py）

说明：
    - 账号密码从环境变量 a/p 或 MI_USER/MI_PASS 读取
    - 本脚本不打印账号密码
    - TTS 走 MiNA 云端服务（sid=micoapi），需要登录态
"""

import asyncio
import json
import os
import sys

# ---------- 环境准备：把 a/p 映射成 MiService 认识的变量名 ----------
if not os.environ.get("MI_USER") and os.environ.get("a"):
    os.environ["MI_USER"] = os.environ["a"]
if not os.environ.get("MI_PASS") and os.environ.get("p"):
    os.environ["MI_PASS"] = os.environ["p"]

# SSL 证书（Windows 上 Python 常缺根证书）
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

try:
    import aiohttp
    from miservice import MiAccount, MiNAService
except ImportError:
    print("缺少依赖。请安装：")
    print('  pip install "git+https://github.com/Yonsm/MiService.git" aiohttp certifi')
    sys.exit(1)


TOKEN_PATH = os.path.expanduser("~/.mi.token")


async def otp_callback(method: str) -> str:
    """需要验证码时提示输入。"""
    print()
    print("=" * 46)
    print(f"小米要求验证（{method}）")
    print("请查看手机短信，输入验证码")
    print("=" * 46)
    try:
        return input("验证码: ").strip()
    except EOFError:
        print("\n当前不是交互终端，无法输入验证码。")
        print("请在真正的 PowerShell 窗口里运行本脚本。")
        return ""


async def get_mina_service():
    """返回 MiNAService。

    优先使用已保存的登录态（~/.mi.token），只有在没有时才走账号密码登录。
    这样从 cookie 生成的 token 可以直接用，不会触发短信验证码。
    """
    user = os.environ.get("MI_USER", "").strip()
    passwd = os.environ.get("MI_PASS", "").strip()

    # 检查是否已有登录态
    has_token = os.path.exists(TOKEN_PATH) and os.path.getsize(TOKEN_PATH) > 10

    if not has_token and (not user or not passwd):
        print("错误：没有登录态，也没有账号密码")
        print(f"  - 需要 {TOKEN_PATH}（用 from_cookie.py 或 login_once.py 生成）")
        print("  - 或设置环境变量 a/p（MI_USER/MI_PASS）")
        sys.exit(2)

    session = aiohttp.ClientSession()

    # 【重要】MiService 在 401 时会调用 token_store.save_token() 且不传参数，
    # 那个分支会【删除 token 文件】。这里用内存型 token_store 包一层，
    # 避免我们手上仅有的一份凭据被静默删掉。
    class _SafeTokenStore:
        def __init__(self, path):
            self.path = path

        async def load_token(self):
            try:
                with open(self.path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None

        async def save_token(self, token=None):
            if token:
                # 只允许写入，不允许删除
                try:
                    with open(self.path, "w", encoding="utf-8") as f:
                        json.dump(token, f)
                except Exception:
                    pass
            # token 为空时什么都不做 —— 关键：不删除文件
            return

    account = MiAccount(session, user or "_", passwd or "_", _SafeTokenStore(str(TOKEN_PATH)), otp_callback)

    if has_token:
        # 直接加载 token，不登录
        try:
            account.token = await account.token_store.load_token()
        except Exception:
            account.token = None

        if account.token and "micoapi" in account.token:
            # 先验证 token 是否真的可用（避免 401 后自动重新登录触发 OTP）
            ok = await _verify_token(account)
            if ok:
                return session, MiNAService(account)
            # token 无效：明确告知，而不是偷偷走登录
            session.close()
            _print_token_invalid()
            sys.exit(4)
        elif account.token:
            print("提示：token 中缺少 micoapi 凭据")
        else:
            print("提示：token 文件内容无法解析")

    # 没有可用 token → 走登录
    if not user or not passwd:
        session.close()
        print("错误：登录态不可用，且未提供账号密码")
        sys.exit(2)

    try:
        await account.login("micoapi")
    except Exception as e:
        msg = str(e)
        session.close()
        if "20024" in msg:
            print("错误：小米账号被风控限制（20024）")
            print("请等待 1-2 小时后再试，期间不要重复尝试登录。")
        elif "No OTP code provided" in msg or "EOF" in msg:
            print("错误：需要短信验证码，但当前环境无法输入")
            print("请在真正的 PowerShell 窗口里直接运行本脚本（不要用管道重定向）。")
        else:
            print(f"登录失败：{msg[:300]}")
        sys.exit(3)

    return session, MiNAService(account)


async def _verify_token(account) -> bool:
    """验证 token 是否真的能调用 MiNA API。

    不验证的话，401 会触发 MiService 内部的自动重新登录，
    进而弹短信验证码，在非交互环境下必然失败且提示误导。
    """
    try:
        # 用最轻量的接口试探，relogin=False 避免 401 后自动重新登录
        await account.mi_request(
            "micoapi",
            "https://api2.mina.mi.com/admin/v2/device_list?master=0&limit=1",
            None,
            {},
            relogin=False,
        )
        return True
    except Exception:
        return False


def _print_token_invalid():
    """token 失效时的准确说明。"""
    print()
    print("=" * 56)
    print("登录态无效（serviceToken 已失效或被拒绝）")
    print("=" * 56)
    print()
    print("原因：")
    print("  MiNA（小爱音箱服务）需要专属的 serviceToken，")
    print("  它只能通过账号密码登录换取（用 ssecurity 签名），")
    print("  浏览器 cookie 里的 serviceToken 属于账号中心，不能用于此。")
    print()
    print("解决：")
    print("  在【真正的 PowerShell 窗口】里运行（不要加管道）：")
    print()
    print("    cd src")
    print("    python login_once.py")
    print()
    print("  看到「验证码:」后输入手机短信里的 6 位数字。")
    print("  成功后 ~/.mi.token 会被写入正确的凭据，之后无需再登录。")
    print()
    print("注意：如果提示 20024（风控），请等 1-2 小时再试。")


async def list_devices(mina, session):
    """列出小爱音箱。"""
    try:
        devices = await mina.device_list()
    except Exception as e:
        print(f"获取设备列表失败：{e}")
        return []

    if not devices:
        print("没有找到小爱音箱设备")
        return []

    print(f"找到 {len(devices)} 个设备：")
    print()
    for i, d in enumerate(devices, 1):
        name = d.get("name", "?")
        did = d.get("deviceID", "?")
        hw = d.get("hardware", "?")
        print(f"  [{i}] {name}")
        print(f"      型号: {hw}")
        print(f"      DID:  {did}")
        print()
    return devices


async def say_text(mina, text, did=None):
    """TTS 播报。"""
    if not text:
        print("错误：文本为空")
        return False
    try:
        # MiNAService.text_to_speech(did, text)
        await mina.text_to_speech(did, text)
        preview = text[:40] + ("..." if len(text) > 40 else "")
        print(f"✅ 已播报: {preview}")
        return True
    except Exception as e:
        print(f"播报失败：{e}")
        return False


# ---------- HTTP 服务模式 ----------
async def serve(port: int):
    """起一个本地 HTTP 接口，供其他程序调用。"""
    try:
        from aiohttp import web
    except ImportError:
        print("需要 aiohttp")
        return

    session, mina = await get_mina_service()

    async def handle_say(request):
        text = request.query.get("text", "").strip()
        did = request.query.get("did") or None
        if not text:
            return web.json_response({"ok": False, "error": "缺少 text 参数"}, status=400)
        try:
            await mina.text_to_speech(did, text)
            return web.json_response({"ok": True, "said": text})
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)

    async def handle_devices(request):
        try:
            devices = await mina.device_list()
            out = [{"name": d.get("name"), "did": d.get("deviceID"),
                    "hardware": d.get("hardware")} for d in devices]
            return web.json_response({"ok": True, "devices": out})
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)

    app = web.Application()
    app.router.add_get("/say", handle_say)
    app.router.add_get("/devices", handle_devices)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()

    print()
    print("=" * 46)
    print(f"TTS 服务已启动: http://127.0.0.1:{port}")
    print("=" * 46)
    print(f"  播报:   http://127.0.0.1:{port}/say?text=你好")
    print(f"  设备:   http://127.0.0.1:{port}/devices")
    print()
    print("Ctrl+C 退出")

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await runner.cleanup()
        await session.close()


async def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        return

    # serve 模式
    if args[0] == "serve":
        port = 8099
        if "--port" in args:
            i = args.index("--port")
            if i + 1 < len(args):
                port = int(args[i + 1])
        await serve(port)
        return

    session, mina = await get_mina_service()
    try:
        if args[0] in ("-l", "--list", "list"):
            await list_devices(mina, session)

        elif args[0] == "-f":
            if len(args) < 2:
                print("用法: python tts.py -f <文件>")
                return
            path = args[1]
            if not os.path.exists(path):
                print(f"文件不存在: {path}")
                return
            with open(path, encoding="utf-8") as f:
                text = f.read().strip()
            await say_text(mina, text)

        elif args[0] == "-d":
            if len(args) < 3:
                print('用法: python tts.py -d <序号|DID> "文本"')
                return
            devices = await mina.device_list()
            target = args[1]
            did = target
            if target.isdigit():
                idx = int(target) - 1
                if 0 <= idx < len(devices):
                    did = devices[idx].get("deviceID")
                else:
                    print(f"序号越界，共 {len(devices)} 个设备")
                    return
            await say_text(mina, " ".join(args[2:]), did)

        else:
            await say_text(mina, " ".join(args))

    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
