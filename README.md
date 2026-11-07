# 小爱音箱控制（TTS + 本地控制）

把小爱音箱变成「**长嘴的客户端**」—— 用它对任意文字开口说话。

基于 [MiService](https://github.com/Yonsm/MiService)。

---

## 两条路线

| | TTS 播报（云端） | 本地控制（局域网） |
|---|---|---|
| 脚本 | `src/tts.py` | `src/xiaoai.py` |
| 需要的凭据 | 小米账号（登录态） | 设备 token |
| 走哪里 | MiNA 云端 `micoapi` | 局域网 UDP 54321 |
| 断网可用 | ❌ | ✅ |
| 能力 | 说话、播放、音量 | 属性读写、部分控制 |

**想让音箱说话 → 用 `tts.py`（云端）**

---

## 安全设计

本项目**不在代码中硬编码任何凭据**，全部通过环境变量注入：

| 变量 | 用途 |
|---|---|
| `MI_USER` | 小米账号（手机号或小米ID） |
| `MI_PASS` | 密码 |
| `MI_LOCAL` | 局域网设备地址，格式 `<IP>:<32位token>` |

### 配置方式

**Bash / Linux:**
```bash
cp .env.example .env
# 编辑 .env 填入真实值
set -a && . ./.env && set +a
```

**PowerShell:**
```powershell
$env:MI_USER  = "你的手机号"
$env:MI_PASS  = "你的密码"
$env:MI_LOCAL = "192.168.1.100:你的32位设备token"
```

**systemd 服务**（推荐生产用法）:
```ini
[Service]
EnvironmentFile=/etc/mi-tts.env
ExecStart=/usr/bin/python3 tts.py serve
```

> ⚠️ `.env`、`env.ps1`、`*.token`、`.mi.token` 已在 `.gitignore` 中屏蔽，
> 但仍请提交前 `git status` 自查一遍。

---

## 目录结构

```
.
├── src/
│   ├── tts.py            云端 TTS 播报（主入口，支持 serve 模式）
│   ├── xiaoai.py         局域网直连控制（UDP 54321）
│   ├── run.py            统一 CLI
│   ├── say.py            简短播报封装
│   ├── mi.py             MiService 初始化辅助
│   ├── login_once.py     一次性登录，成功后落盘 token
│   ├── from_cookie.py    从浏览器 Cookie 导入登录态
│   ├── from_passtoken.py 从 passToken 导入登录态
│   └── otp_login.py      验证码（OTP）登录
├── node/
│   └── get_history*.js   对话历史抓取（Node.js 版实验脚本）
└── docs/
    └── README.md         详细使用说明
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install "git+https://github.com/Yonsm/MiService.git" aiohttp certifi
```

> ⚠️ 必须用 GitHub 版。PyPI 上的 3.0.1 没有 `MiIOLocalService`。

### 2. 首次登录（仅需一次）

```bash
python src/login_once.py
```

成功后 token 会落盘，之后不再要求验证码。

### 3. 让音箱说话

```bash
python src/tts.py "你好世界"
python src/tts.py -l                  # 列出设备
python src/tts.py -f 文本.txt          # 朗读文件
python src/tts.py -d 2 "指定设备说话"   # 指定设备
```

### 4. HTTP 服务模式

```bash
python src/tts.py serve --port 9000
```

### 5. 局域网直连（断网可用）

```bash
python src/xiaoai.py probe            # 探测设备
```

详细说明见 [docs/README.md](docs/README.md)。

---

## 常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| 命令无输出 | `python` 指向微软商店占位程序 | 用完整路径或装真 Python |
| 登录报 `20024` | 触发风控，要求验证码 | 等待一段时间或改用 `from_cookie.py` |
| 局域网连不上 | token 或 IP 错误 | 重新导出 token，确认同一网段 |
| 播报无声 | 设备被占用 / 音量 0 | 先 `-l` 确认设备在线 |

---

## License

仅供个人学习使用。使用前请确认符合小米服务条款。
