# 小爱音箱控制（TTS + 本地控制）

把小爱音箱变成「**长嘴的客户端**」—— 用它对任意文字开口说话。

基于 [MiService](https://github.com/Yonsm/MiService)。

---

## 两条路线

| | TTS 播报（云端） | 本地控制（局域网） |
|---|---|---|
| 脚本 | `tts.py` | `scripts/xiaoai.py` |
| 需要的凭据 | 小米账号（登录态） | 设备 token |
| 走哪里 | MiNA 云端 `micoapi` | 局域网 UDP 54321 |
| 断网可用 | ❌ | ✅ |
| 能力 | 说话、播放、音量 | 属性读写、部分控制 |

**想让音箱说话 → 用 `tts.py`（云端）**

---

## 一、准备

### 1. 安装依赖

```powershell
& "python" -m pip install "git+https://github.com/Yonsm/MiService.git" aiohttp certifi
```

> ⚠️ 必须用 GitHub 版。PyPI 上的 3.0.1 没有 `MiIOLocalService`。

### 2. 确认 Python

这台机器的 `python` 指向微软商店的占位程序（无输出），**必须用完整路径**：

```powershell
& "python" tts.py -l
```

### 3. 首次登录（只需做一次）

```powershell
& "python" login_once.py
```

看到 `验证码:` 提示后，输入手机收到的 6 位数字。

成功后 `~/.mi.token` 会生成，**之后永不再要求验证码**。

> ⚠️ **风控注意**：短时间内反复登录会被小米限制（错误码 `20024`）。
> 如果遇到，**等 1-2 小时**，期间不要重试。

---

## 二、TTS 播报

```powershell
# 说一句话
& "python" tts.py "你好世界"

# 列出所有音箱
& "python" tts.py -l

# 念一个文件
& "python" tts.py -f 文本.txt

# 指定第 2 个音箱
& "python" tts.py -d 2 "指定设备说话"
```

### HTTP 接口（给其他程序调用）

```powershell
& "python" tts.py serve
```

启动后：

```
http://127.0.0.1:8099/say?text=你好
http://127.0.0.1:8099/say?text=你好&did=设备ID
http://127.0.0.1:8099/devices
```

改端口：

```powershell
& "python" tts.py serve --port 9000
```

---

## 三、本地控制（不用云）

见 `scripts/xiaoai.py`，需要设备 token（用 [Xiaomi Cloud Tokens Extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor) 导出一次）。

```powershell
$env:MI_LOCAL = "192.168.1.100:你的32位token"
& "python" scripts\xiaoai.py probe
```

---

## 四、环境变量

脚本支持两种命名：

| 用途 | 变量名 |
|---|---|
| 账号 | `a` 或 `MI_USER` |
| 密码 | `p` 或 `MI_PASS` |

**不要在命令行里明文写密码**，用环境变量：

```powershell
$env:a = "你的账号"
$env:p = "你的密码"
```

或读系统级（如果已设置过）：

```powershell
$env:a = [Environment]::GetEnvironmentVariable('a','Machine')
$env:p = [Environment]::GetEnvironmentVariable('p','Machine')
```

---

## 五、文件说明

| 文件 | 作用 |
|---|---|
| `tts.py` | TTS 客户端（命令行 + HTTP 接口） |
| `login_once.py` | 一次性登录，生成 `~/.mi.token` |
| `mi.py` | MiService 命令包装（自动处理 a/p 映射） |
| `scripts/xiaoai.py` | 本地 miIO 控制（需设备 token） |
| `otp_login.py` | 备用：文件式 OTP 输入 |

---

## 六、排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 命令无输出 | `python` 指向微软商店占位程序 | 用完整路径 `& "python"` |
| `SSL: CERTIFICATE_VERIFY_FAILED` | 缺根证书 | 装 `certifi`（脚本已自动设置） |
| `20024` | 小米风控 | 等 1-2 小时，别重试 |
| `No interactive terminal for OTP` | 非交互环境 | 在真正的 PowerShell 窗口运行 |
| `Login failed` | 登录态过期 | 重跑 `login_once.py` |
| `EOF when reading a line` | 输出被重定向，`input()` 读不到 | 不要重定向输出 |

---

## 七、注意事项

- **`~/.mi.token` 是登录凭据**，等同于你的账号权限，不要分享
- 你的密码如果曾在命令行或日志里出现过，建议修改
- 本地模式不需要账号，但 token 泄露仍可被同网段的人控制设备
