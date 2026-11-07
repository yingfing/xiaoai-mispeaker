"""统一入口：把 a/p 映射成 MI_USER/MI_PASS，然后执行 miservice 命令。

用法：
    python mi.py mina                  # 列出音箱
    python mi.py mina "你好"            # TTS 播报
    python mi.py list                  # 列出所有设备
"""
import os
import sys

# 最早把 a/p 映射成 MiService 认识的变量名
if not os.environ.get("MI_USER") and os.environ.get("a"):
    os.environ["MI_USER"] = os.environ["a"]
if not os.environ.get("MI_PASS") and os.environ.get("p"):
    os.environ["MI_PASS"] = os.environ["p"]

# SSL 证书
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

# 交给 miservice 自己的 CLI
sys.argv = ["miservice"] + sys.argv[1:]
from miservice.__main__ import main  # noqa: E402

main()
