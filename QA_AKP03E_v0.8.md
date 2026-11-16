> Historical report; see [TEST_REPORT.md](TEST_REPORT.md) for current release checks.

# QA — 0.8 AKP03E

Synthetic tests verified 1025-byte HID framing, BAT/image chunks, event parsing, six LCDs/three encoders/three side keys, one-use scoped controller pairing, denied admin access, command allowlist, logical TAKE/OSC, heartbeat display and Python/Prompt JS syntax.

Eight dedicated controller tests; combined Prompt/controller run: **16 passed**. Separate monitor regression: **18 passed**; server/player regression also passed. Standalone monitor imports require `PYTHONPATH=.:tests` (use the platform path separator).

No physical `0300:3002` open, firmware orientation, USB reconnect, theatre latency, real dual-Core/VIP takeover or HDMI switching was tested. Before use, run `Test_Controller_AKP03E_Windows.bat` and check every control. TAKE is logical only.
