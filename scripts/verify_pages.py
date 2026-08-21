"""验证：分辨率档位已封顶 0.98、时长已补全 4..15。"""
import urllib.request

paths = ["/", "/i2v", "/r2v"]
checks = {
    "应移除-1.2M": "1.2M",
    "应移除-1.5M": "1.5M",
    "应移除-2.0M": "2.0M",
    "应有-0.98M原生": "0.98M 原生",
    "应有-0.5M": "0.5M",
    "应有-0.9M": "0.9M",
    "应有-时长6s": "6s",
    "应有-时长7s": "7s",
    "应有-时长11s": "11s",
    "应有-时长13s": "13s",
    "应有-时长14s": "14s",
    "应有-H3-Regenerate-2K说明": "H3-Regenerate-2K",
}
for path in paths:
    html = urllib.request.urlopen("http://127.0.0.1:18080" + path).read().decode("utf-8")
    print(f"\n=== {path} ===")
    for label, pat in checks.items():
        print(f"  [{'有' if pat in html else '无'}] {label}")