# مرجع API — Chatroom Central

آدرس پایه: `http://localhost:8000` (یا دامنه deploy شده)

تمام endpointهای احراز هویت‌شده نیاز به هدر زیر دارند:

```
Authorization: Token <توکن-ادمین-شما>
```

کاربر مرتبط با توکن باید `is_staff=True` داشته باشد.

---

## فهرست

1. [احراز هویت](#احراز-هویت)
2. [API مکالمات](#api-مکالمات)
3. [API پیام‌ها](#api-پیام‌ها)
4. [وب‌هوک‌ها (ورودی)](#وب‌هوک‌ها-ورودی)
5. [Mock provider](#mock-provider)
6. [WebSocket](#websocket)
7. [مدل‌های داده](#مدل‌های-داده)
8. [پاسخ‌های خطا](#پاسخ‌های-خطا)

---

## احراز هویت

### دریافت توکن

```
POST /api/v1/auth/token/
```

**بدنه درخواست:**

```json
{
  "username": "admin",
  "password": "رمز-عبور"
}
```

**موفق (200):**

```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
}
```

**خطاها:**

| وضعیت | دلیل |
|-------|------|
| 400 | نام کاربری یا رمز عبور ارسال نشده |
| 401 | اطلاعات ورود نامعتبر |

---

## API مکالمات

### لیست مکالمات

```
GET /api/v1/conversations/
```

**پارامترهای query:**

| پارامتر | نوع | توضیح |
|---------|-----|-------|
| `mine` | `1` / `true` | فقط مکالماتی که کاربر احراز هویت‌شده participant آن است |

**موفق (200):**

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "source": "telegram-bot",
    "external_contact": "user-12345",
    "last_message": "سلام، کمک می‌خواهم",
    "updated_at": "2026-08-14T12:30:00Z",
    "has_unseen": true
  }
]
```

حداکثر ۱۰۰ مکالمه، مرتب‌شده بر اساس زمان آخرین پیام (جدیدترین اول).

---

### جزئیات مکالمه

```
GET /api/v1/conversations/<uuid>/
```

**موفق (200):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "source": "uuid-of-source",
  "external_contact": "uuid-of-contact",
  "title": null,
  "metadata": {},
  "is_closed": false,
  "created_at": "2026-08-01T10:00:00Z",
  "updated_at": "2026-08-14T12:30:00Z",
  "messages": [
    {
      "id": "msg-uuid",
      "conversation": "conv-uuid",
      "direction": "IN",
      "sender_name": "علی",
      "content": "سلام!",
      "status": "RECEIVED",
      "seen": false,
      "created_at": "2026-08-14T12:00:00Z"
    }
  ]
}
```

پیام‌ها به ترتیب زمانی (`created_at` صعودی) مرتب می‌شوند.

---

### ارسال پاسخ

```
POST /api/v1/conversations/<uuid>/reply/
```

**بدنه درخواست:**

```json
{
  "text": "ممنون از تماس شما! به زودی کمکتان می‌کنیم."
}
```

**موفق (200):**

```json
{
  "id": "new-message-uuid",
  "status": "PENDING",
  "message": {
    "id": "new-message-uuid",
    "direction": "OUT",
    "content": "ممنون از تماس شما!",
    "status": "PENDING"
  }
}
```

پیام برای ارسال در صف Celery قرار می‌گیرد. وضعیت به‌صورت ناهمزمان به `SENT` یا `FAILED` تغییر می‌کند. رویداد `message.new` از طریق WebSocket فوری broadcast می‌شود.

**خطاها:**

| وضعیت | دلیل |
|-------|------|
| 400 | فیلد `text` ارسال نشده |
| 401 | احراز هویت نشده |
| 403 | کاربر staff نیست |
| 404 | مکالمه پیدا نشد |

---

### علامت‌گذاری همه پیام‌ها به‌عنوان seen

```
POST /api/v1/conversations/<uuid>/seen/
```

همه پیام‌های ورودی (`direction=IN`) unseen در مکالمه را seen می‌کند.

**موفق (200):**

```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "marked_seen": 3
}
```

---

## API پیام‌ها

### علامت‌گذاری یک پیام به‌عنوان seen

```
POST /api/v1/messages/<uuid>/seen/
```

**موفق (200):**

```json
{
  "id": "message-uuid",
  "seen": true
}
```

---

## وب‌هوک‌ها (ورودی)

سیستم‌های خارجی پیام‌ها را به این endpoint ارسال می‌کنند. احراز هویت توکن ندارد — به‌جای آن از هدر امضا (اختیاری) استفاده می‌شود.

### دریافت پیام ورودی

```
POST /api/webhooks/<source_slug>/incoming/
```

**هدرها:**

| هدر | الزامی | توضیح |
|-----|--------|-------|
| `Content-Type` | بله | `application/json` |
| `X-Signature` | اگر source secret دارد | باید با `inbound_secret` منبع مطابقت داشته باشد |

**بدنه درخواست:**

```json
{
  "external_user_id": "user-12345",
  "external_message_id": "ext-msg-001",
  "content": "سلام از تلگرام!",
  "thread_id": "optional-thread-id",
  "timestamp": "2026-08-14T12:00:00Z"
}
```

| فیلد | الزامی | توضیح |
|------|--------|-------|
| `external_user_id` | **بله** | شناسه یکتای کاربر در سیستم خارجی |
| `external_message_id` | خیر | کلید idempotency — ID تکراری نادیده گرفته می‌شود |
| `content` | خیر | متن پیام |
| `thread_id` | خیر | پیام‌ها را در یک مکالمه گروه‌بندی می‌کند |
| `timestamp` | خیر | زمان اصلی پیام (در metadata ذخیره می‌شود) |

**موفق (200):**

```json
{
  "status": "ok",
  "message_id": "new-internal-uuid"
}
```

**تکراری (200):**

```json
{
  "status": "duplicate"
}
```

**خطاها:**

| وضعیت | دلیل |
|-------|------|
| 400 | payload نامعتبر |
| 401 | `X-Signature` نامعتبر |
| 404 | slug منبع پیدا نشد یا غیرفعال است |

### راه‌اندازی Source

1. Django admin → **Sources** → Add
2. **Slug** (در URL استفاده می‌شود)، **Display name**، **Inbound secret** (اختیاری)
3. **Outbound endpoint template** — آدرسی که پاسخ‌های ادمین به آن POST می‌شوند

### payload ارسال خروجی

وقتی ادمین پاسخ می‌دهد، Celery به endpoint خروجی منبع POST می‌کند:

```json
{
  "conversation_id": "internal-conversation-uuid",
  "external_user_id": "user-12345",
  "content": "متن پاسخ ادمین",
  "message_id": "internal-message-uuid"
}
```

---

## Mock provider

برای تست محلی، outbound endpoint یک Source را به این آدرس تنظیم کنید:

```
http://web:8000/api/mock/provider/receive/
```

```
POST /api/mock/provider/receive/
```

هر JSON را می‌پذیرد و در stdout لاگ می‌کند. احراز هویت لازم نیست.

---

## WebSocket

### اتصال

```
ws://localhost:8000/ws/admin/?token=<admin-token>
```

در production با WSS:

```
wss://yourdomain.com/ws/admin/?token=<admin-token>
```

### کلاینت → سرور

**Ping (نگه‌داشتن اتصال):**

```json
{"type": "ping"}
```

**پاسخ سرور:**

```json
{"type": "pong"}
```

### رویدادهای سرور → کلاینت

#### `connected`

بلافاصله پس از احراز هویت موفق ارسال می‌شود.

```json
{"type": "connected"}
```

#### `message.new`

پیام جدید (وب‌هوک ورودی یا پاسخ ادمین).

```json
{
  "type": "message.new",
  "conversation_id": "uuid",
  "message": {
    "id": "uuid",
    "direction": "IN",
    "content": "سلام",
    "status": "RECEIVED",
    "seen": false,
    "created_at": "2026-08-14T12:00:00Z"
  },
  "conversation": {
    "id": "uuid",
    "source": "my-bot",
    "external_contact": "user-123",
    "last_message": "سلام",
    "updated_at": "2026-08-14T12:00:00Z",
    "has_unseen": true
  }
}
```

#### `message.updated`

تغییر وضعیت یا seen پیام (مثلاً پس از تحویل Celery).

```json
{
  "type": "message.updated",
  "conversation_id": "uuid",
  "message": {
    "id": "uuid",
    "status": "SENT"
  }
}
```

#### `conversation.updated`

تغییر متادیتای مکالمه (مثلاً mark-seen دسته‌ای).

```json
{
  "type": "conversation.updated",
  "conversation_id": "uuid"
}
```

### خطاهای اتصال

| کد بستن | دلیل |
|---------|------|
| 4001 | توکن نامعتبر یا کاربر staff نیست |

---

## مدل‌های داده

### جهت پیام

| مقدار | معنی |
|-------|------|
| `IN` | ورودی (از سیستم خارجی) |
| `OUT` | خروجی (پاسخ ادمین) |

### وضعیت پیام

| مقدار | معنی |
|-------|------|
| `RECEIVED` | پیام ورودی ذخیره شد |
| `PENDING` | پیام خروجی در صف ارسال |
| `SENT` | با موفقیت به endpoint خارجی تحویل داده شد |
| `FAILED` | ارسال پس از تلاش‌های مجدد ناموفق بود |

---

## پاسخ‌های خطا

DRF خطاها را به این شکل برمی‌گرداند:

```json
{
  "detail": "توضیح خطا"
}
```

یا برای خطاهای اعتبارسنجی:

```json
{
  "field_name": ["پیام خطا"]
}
```

کدهای HTTP رایج:

| کد | معنی |
|----|------|
| 400 | درخواست نامعتبر / خطای اعتبارسنجی |
| 401 | احراز هویت لازم یا نامعتبر |
| 403 | دسترسی رد شد (staff نیست) |
| 404 | منبع پیدا نشد |
| 500 | خطای سرور |

---

## OpenAPI / مستندات تعاملی

وقتی سرور در حال اجراست:

- **OpenAPI JSON:** `/api/schema/`
- **Swagger UI:** `/api/schema/swagger-ui/`
- **ReDoc:** `/api/schema/redoc/`

---

## مثال: جریان کامل یکپارچه‌سازی

```bash
# ۱. دریافت توکن ادمین
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"pass"}' | jq -r .token)

# ۲. شبیه‌سازی وب‌هوک ورودی
curl -X POST http://localhost:8000/api/webhooks/my-bot/incoming/ \
  -H "Content-Type: application/json" \
  -H "X-Signature: my-secret" \
  -d '{"external_user_id":"u1","content":"سلام","thread_id":"t1"}'

# ۳. لیست مکالمات
curl -H "Authorization: Token $TOKEN" \
  http://localhost:8000/api/v1/conversations/

# ۴. پاسخ (CONV_ID را جایگزین کنید)
curl -X POST http://localhost:8000/api/v1/conversations/CONV_ID/reply/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"سلام! چطور می‌توانم کمکتان کنم؟"}'

# ۵. اتصال WebSocket
wscat -c "ws://localhost:8000/ws/admin/?token=$TOKEN"
```
