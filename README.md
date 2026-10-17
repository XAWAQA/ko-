# 🤖 Cyberpunk Telegram Bot (Modular Edition)

بوت تيليجرام لإدارة وتنسيق مجموعات وصفحات فيسبوك بأسلوب غير متزامن وعالي التوازي.

---

## 📖 English Guide

### 1. Overview
A high-throughput, concurrent Telegram bot interface for Facebook group and page management tasks:
- **⚡ CONNECT GROUPS**: Request to join Facebook groups via personal profile or managed pages.
- **🛡️ APPROVE MEMBERS**: Process pending member approvals for groups.
- **👑 MODERATOR APPROVAL**: Send moderator invites/approvals to designated groups.
- **📟 SYSTEM INFO**: Real-time server and runtime dashboard.
- **🚫 TERMINATE / 🔌 DISCONNECT**: Task cancellation and complete session credential purge.

### 2. Prerequisites & Python Version
- **Python Version**: `3.10+` (officially verified on `Python 3.10.13` and `3.12+`).
- **Operating System**: Windows, Linux, or macOS.

### 3. Installation
```bash
# 1. Clone repository & navigate to directory
cd ko-main

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# On Windows (cmd):
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

### 4. Environment Variables
Sensitive tokens and configuration must be set via environment variables (never committed to code):

| Variable | Description | Required | Default |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Token provided by `@BotFather` | **Yes** | None |
| `MAX_RAM_MB` | Displayed memory limit | No | `8192` |
| `REQUEST_TIMEOUT` | Facebook HTTP request timeout (seconds) | No | `12.0` |
| `RETRY_ATTEMPTS` | Number of retry attempts on rate limits/network | No | `3` |
| `GRAPH_API_BASE_URL` | Facebook Graph API base URL | No | `https://graph.facebook.com` |

#### Setting the token:
- **Windows (Command Prompt):**
  ```cmd
  set TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
  ```
- **Windows (PowerShell):**
  ```powershell
  $env:TELEGRAM_BOT_TOKEN="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
  ```
- **Linux / macOS:**
  ```bash
  export TELEGRAM_BOT_TOKEN="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
  ```

### 5. Running the Bot
```bash
python app.py
```
*(Legacy `python bot.py` is also supported as an entry point redirecting to `app.py`).*

### 6. Deployment (Procfile)
For platforms such as Heroku, Railway, or Docker:
```text
worker: python app.py
```

### 7. Testing
Run the offline test suite (all Facebook requests are strictly mocked):
```bash
python -m pytest -v
```

### 8. Project Structure
```text
ko-main/
├── app.py                     # Main application entry point
├── config.py                  # Environment config and startup validation
├── requirements.txt           # Python dependencies
├── runtime.txt                # Deployment Python runtime specification
├── Procfile                   # Cloud worker process definition
├── README.md                  # Documentation (Arabic & English)
├── PROJECT_AUDIT.md           # Comprehensive architectural & security audit
├── IMPLEMENTATION_REPORT.md   # Refactoring & implementation verification report
├── legacy/
│   └── bot.py                 # Exact untouched legacy backup
├── bot/
│   ├── __init__.py
│   ├── handlers.py            # Telegram handlers & message processing
│   ├── keyboards.py           # Telegram keyboards & UI components
│   └── state.py               # Thread-safe in-memory session manager
├── facebook/
│   ├── __init__.py
│   ├── client.py              # Graph API HTTP client & MockFacebookClient
│   └── models.py              # Data classes & OperationStatus enums
├── workers/
│   ├── __init__.py
│   ├── engine.py              # Concurrent worker engine & retry scheduler
│   └── progress.py            # Premium ASCII progress bar & final report
├── utils/
│   ├── __init__.py
│   ├── logging.py             # Redacted, safe structured logging
│   ├── system.py              # Cross-platform CPU/RAM info (psutil)
│   └── validation.py          # Input ID extraction & token validation
└── tests/
    ├── __init__.py
    ├── test_config.py          # Config loading & missing token tests
    ├── test_validation.py      # Input parsing & token format tests
    ├── test_state.py           # State management & disconnect cleanup tests
    ├── test_progress.py        # Progress display & report formatting tests
    ├── test_facebook_client.py # HTTP 429, 500, 401, timeout & mock tests
    └── test_worker_engine.py   # Concurrency, retries, cancellation tests
```

### 9. Troubleshooting
- **Error: `TELEGRAM_BOT_TOKEN is not configured`**:
  Set the `TELEGRAM_BOT_TOKEN` environment variable before launching.
- **`⚠️ uvloop not found`**:
  Normal on Windows (uvloop is Unix-only). The engine automatically falls back to standard Python `asyncio`.
- **Facebook Rate Limits (HTTP 429)**:
  The engine automatically applies exponential backoff with jitter and retries.

---

## 🇸🇦 الدليل بالعربية

### 1. نبذة عن المشروع
بوت تيليجرام لإدارة مجموعات وصفحات فيسبوك بتصميم معياري غير متزامن:
- **⚡ CONNECT GROUPS**: الانضمام للجروبات عبر الحساب الشخصي أو الصفحات.
- **🛡️ APPROVE MEMBERS**: قبول طلبات الانضمام المعلقة.
- **👑 MODERATOR APPROVAL**: إرسال دعوات وتعيين المشرفين.
- **📟 SYSTEM INFO**: عرض لوحة تحكم السيرفر والمواصفات.
- **🚫 TERMINATE / 🔌 DISCONNECT**: إيقاف المهام وحذف الجلسة والرموز الحساسة من الذاكرة فوراً.

### 2. متطلبات التشغيل
- بيئة بايثون `Python 3.10+`.
- نظام تشغيل Windows أو Linux أو macOS.

### 3. التثبيت والتشغيل
```bash
# إنشاء وتفعيل البيئة الافتراضية
python -m venv .venv
.venv\Scripts\activate   # على ويندوز
# source .venv/bin/activate  # على لينكس

# تثبيت الحزم
pip install -r requirements.txt

# ضبط الرمز السري للبوت
set TELEGRAM_BOT_TOKEN=your_bot_token_here

# تشغيل البوت
python app.py
```

### 4. الاختبارات (Testing)
جميع الاختبارات تعمل محلياً بدون إرسال أي طلبات حقيقية لخوادم فيسبوك:
```bash
python -m pytest -v
```
