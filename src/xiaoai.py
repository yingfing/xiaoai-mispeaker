#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小爱音箱本地控制脚本（基于 MiService 的 MiIOLocalService）

用法：
    1. 先在环境变量里配置（token 不写进代码、不进版本库）：
       Windows PowerShell:
         $env:MI_LOCAL = "192.168.1.100:你的32位设备token"
       Linux / macOS:
         export MI_LOCAL="192.168.1.100:你的32位设备token"

    2. 然后：
       python xiaoai.py probe                 # ★ 先跑这个：探测设备支持哪些方法
       python xiaoai.py info                  # 查设备信息
       python xiaoai.py get volume            # 读音量（属性名按型号可能不同）
       python xiaoai.py set volume=60         # 设音量
       python xiaoai.py tts "你好世界"         # TTS 播报（动作调用 siid=5）
       python xiaoai.py exec "查询天气"        # 执行文本指令，音箱会语音回应
       python xiaoai.py exec "关灯" 0         # 执行文本指令，静默不回应
       python xiaoai.py call miIO.info        # 调任意原始方法
       python xiaoai.py call set_power '["on"]'

说明：
    - 本脚本只走局域网 UDP 54321，不经过小米云，因此不需要 MI_USER/MI_PASS。
    - 但 token 本身需要先用 Xiaomi Cloud Tokens Extractor 从小米云导出一次。
    - 属性名/编号（siid-piid）与型号强相关，见 const.py 与 miservice spec 输出。
    - 依赖必须装 GitHub 版（PyPI 的 3.0.1 没有 MiIOLocalService）：
        pip install "git+https://github.com/Yonsm/MiService.git"
"""

import asyncio
import os
import sys

try:
    from miservice import MiIOLocalService
except ImportError as e:
    print("导入 miservice 失败：" + str(e))
    print()
    print("注意：必须装 GitHub 版（PyPI 的 3.0.1 没有 MiIOLocalService）：")
    print('  pip install "git+https://github.com/Yonsm/MiService.git"')
    print()
    print("验证： python -c \"from miservice import MiIOLocalService; print('OK')\"")
    sys.exit(1)


def get_local_config():
    """从环境变量读 IP 与 token。"""
    v = os.environ.get("MI_LOCAL", "").strip()
    if not v:
        print("错误：未设置环境变量 MI_LOCAL")
        print('  格式: MI_LOCAL="<设备局域网IP>:<token>"')
        print('  例:   MI_LOCAL="192.168.1.100:你的32位设备token"')
        sys.exit(2)
    if ":" not in v:
        print(f"错误：MI_LOCAL 格式不对，应为 <IP>:<token>，当前值: {v}")
        sys.exit(2)
    ip, token = v.rsplit(":", 1)
    return ip.strip(), token.strip()


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    ip, token = get_local_config()
    svc = MiIOLocalService(ip, token, timeout=3, retries=3)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    try:
        if cmd == "info":
            # miIO.info 是所有 miIO 设备都支持的基础方法
            r = await svc.send("miIO.info")
            print(r)

        elif cmd == "get":
            if not args:
                print("用法: get <prop>[,<prop>...]")
                return
            props = [p.strip() for p in args[0].split(",")]
            r = await svc.get_props(props)
            for k, v in zip(props, r):
                print(f"{k} = {v}")

        elif cmd == "set":
            if not args:
                print("用法: set <prop=value>[,<prop=value>...]")
                return
            items = []
            for item in args[0].split(","):
                if "=" not in item:
                    print(f"错误：{item} 缺少 =")
                    return
                k, val = item.split("=", 1)
                items.append((k.strip(), val.strip()))
            r = await svc.set_props(items)
            print(r)

        elif cmd == "tts":
            if not args:
                print('用法: tts "要播报的话"')
                return
            # 注意：TTS 的方法名/编号与型号强相关。这里按 MiService README 的
            # 「siid=5 文本播报」来调。若你的型号不支持，会返回错误，
            # 此时请用 `call` 直接试其它方法名（如 play_text）。
            r = await svc.send("5", [args[0]])
            print(r)

        elif cmd == "exec":
            if not args:
                print('用法: exec "指令" [1回应/0静默]')
                return
            text = args[0]
            silent = args[1] if len(args) > 1 else "1"
            # siid=5, aiid=4 = 执行文本指令（相当于对小爱说话）
            r = await svc.send("5-4", [text, silent])
            print(r)

        elif cmd == "probe":
            # 自动探测：逐个尝试常见方法，看设备支持哪些
            candidates = [
                ("miIO.info", []),
                ("get_prop", ["volume"]),
                ("get_prop", ["status"]),
                ("get_prop", ["play_state"]),
                ("get_prop", ["power"]),
                ("get_prop", ["mute"]),
                ("miIO.miot_spec", []),
            ]
            print("开始探测（不支持的会显示失败，属正常）：")
            ok, fail = 0, 0
            for method, params in candidates:
                label = f"{method}({','.join(map(str, params))})" if params else method
                try:
                    r = await svc.send(method, params)
                    print(f"  ✅ {label} => {str(r)[:120]}")
                    ok += 1
                except Exception as e:
                    msg = str(e)
                    print(f"  ❌ {label} => {msg[:100]}")
                    fail += 1
            print()
            print(f"支持 {ok} 个 / 不支持 {fail} 个")
            print("提示：不同型号支持的属性名不同，可用 miIO.miot_spec 查完整能力表。")

        elif cmd == "call":
            if not args:
                print("用法: call <method> [params_json]")
                return
            method = args[0]
            import json
            params = json.loads(args[1]) if len(args) > 1 else []
            r = await svc.send(method, params)
            print(r)

        else:
            print(__doc__)
    except TimeoutError as e:
        print(f"超时：{e}")
        print("  排查：1) 设备是否开机联网  2) IP 是否为局域网地址（不是公网）  3) token 是否正确")
    except Exception as e:
        print(f"失败：{e}")


if __name__ == "__main__":
    asyncio.run(main())
