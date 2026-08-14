# Chatroom Central

یک هاب مرکزی چت که پیام‌ها را از سیستم‌های خارجی از طریق وب‌هوک دریافت می‌کند، به ادمین اجازه مشاهده و پاسخ از یک رابط مدرن می‌دهد، و پاسخ‌های خروجی را به‌صورت ناهمزمان با Celery ارسال می‌کند.

**زبان‌ها:** [English](README.md) · [فارسی](README.fa.md)  
**مرجع API:** [انگلیسی](docs/API.md) · [فارسی](docs/API.fa.md)

---

## امکانات

- **وب‌هوک ورودی** — دریافت پیام از تلگرام، ربات‌های سفارشی یا هر منبع HTTP
- **رابط ادمین (SPA)** — UI تیره با React؛ لیست مکالمات، جستجو و ارسال پاسخ
- **به‌روزرسانی لحظه‌ای** — WebSocket (Django Channels + ASGI) پیام‌های جدید را فوری ارسال می‌کند
- **ارسال ناهمزمان** — Worker سلری پاسخ‌ها را با تلاش مجدد به endpointهای خارجی می‌فرستد
- **احراز هویت توکن** — DRF TokenAuth برای API و WebSocket
- **مستندات OpenAPI** — Swagger UI و ReDoc
- **Docker Compose** — استک کامل: Django (ASGI)، Celery، Redis، Postgres، فرانت‌اند، nginx

---

## معماری

```
سیستم‌های خارجی ──POST webhook──► Django API
                                      │
                                      ├──► PostgreSQL
                                      ├──► Celery ──POST──► Endpointهای خارجی
                                      └──► Redis Channel Layer ──WebSocket──► SPA ادمین
```

| جزء | فناوری |
|-----|--------|
| بک‌اند | Django 4.2 + DRF + Daphne (ASGI) |
| Realtime | Django Channels + Redis |
| تسک‌ها | Celery 5 + Redis broker |
| دیتابیس | PostgreSQL (Docker) / SQLite (محلی) |
| فرانت‌اند | React 18 + Vite + Bootstrap 5 |
| پروکسی | nginx |

---

## راه‌اندازی سریع (Docker Compose)

### ۱. تنظیم محیط

```bash
cp .env.example .env
# فایل .env را ویرایش کنید — DJANGO_SECRET_KEY و سایر مقادیر را تنظیم کنید
```

### ۲. ساخت و اجرا

```bash
docker compose build
docker compose up -d
```

### ۳. راه‌اندازی دیتابیس

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

### ۴. باز کردن برنامه

- **رابط ادمین:** http://localhost:8000
- **پنل Django admin:** http://localhost:8000/admin/
- **Swagger UI:** http://localhost:8000/api/schema/swagger-ui/
- **ReDoc:** http://localhost:8000/api/schema/redoc/

### ۵. داده نمونه (اختیاری)

```bash
docker compose exec web python manage.py generate_sample_data --count 10
```

---

## راه‌اندازی محلی (virtualenv)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Redis را اجرا کنید (برای Channels و Celery لازم است)
# مثال: docker run -d -p 6379:6379 redis:7

python manage.py migrate
python manage.py createsuperuser

# ترمینال ۱ — سرور ASGI
daphne -b 0.0.0.0 -p 8000 project.asgi:application

# ترمینال ۲ — Worker سلری
celery -A project worker -l info

# ترمینال ۳ — سرور توسعه فرانت‌اند
cd frontend && npm install && npm run dev
```

سرور توسعه در http://localhost:3000 اجرا می‌شود و `/api` و `/ws` را به Django پروکسی می‌کند.

---

## احراز هویت

### دریافت توکن

```bash
curl -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "رمز-عبور"}'
```

پاسخ:

```json
{"token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"}
```

در تمام درخواست‌های محافظت‌شده:

```
Authorization: Token <توکن-شما>
```

برای WebSocket، توکن را در query string بفرستید:

```
ws://localhost:8000/ws/admin/?token=<توکن-شما>
```

> کاربر باید `is_staff=True` داشته باشد (superuser یا staff).

---

## رویدادهای WebSocket

پس از ورود به `/ws/admin/?token=<token>` متصل شوید. سرور رویدادهای JSON ارسال می‌کند:

| رویداد | توضیح |
|--------|-------|
| `connected` | اتصال برقرار شد |
| `message.new` | پیام ورودی یا خروجی جدید |
| `message.updated` | تغییر وضعیت یا seen پیام |
| `conversation.updated` | تغییر متادیتای مکالمه |
| `pong` | پاسخ به `ping` کلاینت |

مثال payload برای `message.new`:

```json
{
  "type": "message.new",
  "conversation_id": "uuid",
  "message": { "id": "...", "content": "...", "direction": "IN", ... },
  "conversation": { "id": "...", "last_message": "...", "has_unseen": true, ... }
}
```

SPA از WebSocket برای به‌روزرسانی لحظه‌ای استفاده می‌کند و در صورت قطع اتصال، هر ۶۰ ثانیه polling HTTP انجام می‌دهد.

---

## یکپارچه‌سازی وب‌هوک (مثال سریع)

### ۱. ایجاد Source در Django admin

- **Slug:** `my-bot`
- **Inbound secret:** `my-secret-key` (اختیاری)
- **Outbound endpoint:** آدرسی که پاسخ‌ها به آن POST می‌شوند

### ۲. ارسال پیام ورودی

```bash
curl -X POST http://localhost:8000/api/webhooks/my-bot/incoming/ \
  -H "Content-Type: application/json" \
  -H "X-Signature: my-secret-key" \
  -d '{
    "external_user_id": "user-123",
    "external_message_id": "msg-001",
    "content": "سلام از سیستم خارجی!",
    "thread_id": "thread-abc"
  }'
```

### ۳. پاسخ از SPA یا API

```bash
curl -X POST http://localhost:8000/api/v1/conversations/<conversation-uuid>/reply/ \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d '{"text": "ممنون از پیام شما!"}'
```

برای مرجع کامل endpointها به [docs/API.fa.md](docs/API.fa.md) مراجعه کنید.

---

## متغیرهای محیطی

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `DJANGO_SECRET_KEY` | `dev-secret` | کلید مخفی Django |
| `DJANGO_DEBUG` | `False` | حالت دیباگ |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | هاست‌های مجاز |
| `DJANGO_DB_ENGINE` | sqlite | موتور دیتابیس |
| `DJANGO_DB_NAME` | `db.sqlite3` | نام دیتابیس |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Broker سلری |
| `CHANNEL_LAYERS_REDIS` | همان Celery | Redis برای Channels |
| `NGX_EXTERNAL_PORT` | `8000` | پورت nginx روی host |

---

## بهبودهای رابط کاربری

- **حفظ موقعیت اسکرول** — هنگام خواندن پیام‌های قدیمی‌تر، با رفرش به بالا پرش نمی‌کند
- **اسکرول هوشمند** — فقط وقتی پیام جدید می‌آید و در پایین هستید، به آخر می‌رود
- **علامت‌گذاری seen دسته‌ای** — یک درخواست API به‌جای یکی برای هر پیام
- **جستجو** — فیلتر مکالمات بر اساس مخاطب، منبع یا آخرین پیام
- **نشانگر اتصال** — وضعیت Live / Connecting / Offline
- **وضعیت پیام** — پیام‌های خروجی: در حال ارسال / ارسال شد / خطا
- **دکمه خروج** — در هدر اضافه شده

---

## عیب‌یابی

| مشکل | راه‌حل |
|------|--------|
| WebSocket آفلاین است | Redis را اجرا کنید و `CHANNEL_LAYERS_REDIS` را تنظیم کنید |
| خطای 401 | کاربر باید staff باشد؛ توکن را بررسی کنید |
| تغییرات فرانت دیده نمی‌شود | image فرانت‌اند را rebuild کنید |
| تسک‌های Celery اجرا نمی‌شوند | لاگ worker: `docker compose logs worker` |
| پرش اسکرول هنگام رفرش | فرانت‌اند جدید را deploy کنید |

---

## ساختار پروژه

```
chatroom-central/
├── chatcore/           # اپ Django (مدل‌ها، viewها، consumerها، taskها)
├── project/            # پروژه Django (settings، asgi، celery)
├── frontend/           # SPA React (Vite)
├── nginx/              # تنظیمات reverse proxy
├── docs/               # مستندات API (انگلیسی + فارسی)
├── docker-compose.yml
├── requirements.txt
└── README.fa.md
```

---

## مجوز

MIT — آزاد برای نمونه‌سازی و آزمایش.
