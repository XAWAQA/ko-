# Request-by-Request Audit Report (تدقيق ومطابقة طلبات HTTP)

تم إعداد هذا التقرير لإجراء تدقيق ومقارنة تفصيلية (Request-by-Request) بين الكود الأصلي القديم في `legacy/bot.py` والكود المنظم في `facebook/client.py` و `workers/engine.py` و `bot/handlers.py`.

---

## 1. حصر وفحص جميع طلبات HTTP الأصلية (Original Requests Extraction)

تم فحص الكود المصدري في `legacy/bot.py` بالكامل بحثاً عن أي استدعاءات لمكتبات الشبكة (`httpx`, `requests`, `client.get`, `client.post`). 
وتم حصر **5 طلبات HTTP فعلية** تتصل بشبكة فيسبوك:

### Request #1: فحص رمز الوصول (Verify Access Token)
- **الموقع في الكود الأصلي:** `legacy/bot.py` (الأسطر 170-174) داخل دالة `verify()` في معالج `login`.
- **طريقة الطلب (HTTP Method):** `GET`
- **الرابط (URL):** `https://graph.facebook.com/me?access_token={token}`
- **نقطة النهاية (Endpoint):** `/me`
- **معاملات الاستعلام (Query Parameters):** `access_token=[REDACTED]`
- **جسم الطلب (Payload/Body):** فارغ (None).
- **الترويسات (Headers):** الافتراضية لمكتبة `httpx` (بدون ترويسات مخصصة).
- **آلية المصادقة (Auth):** تمرير التوكن مباشرة داخل الـ Query String في الرابط.
- **المهلة (Timeout):** `10.0` ثوانٍ.
- **إعادة المحاولة (Retries):** محاولة واحدة (لا توجد إعادة محاولة).
- **تحليل الرد (Response Parsing):**
  - فحص `resp.status_code == 200`
  - استخراج JSON وقراءة `data['id']` و `data['name']`.
- **شروط النجاح (Success Condition):** كود الحالة 200 واحتواء الرد على `id` و `name`.
- **معالجة الأخطاء (Error Handling):** `except:` عام يطبع رسالة `⚠️ CONNECTION ERROR`.

---

### Request #2: جلب الصفحات المدارة (Fetch Managed Pages)
- **الموقع في الكود الأصلي:** `legacy/bot.py` (الأسطر 253-257) داخل دالة `fetch()` في معالج `src_pages`.
- **طريقة الطلب (HTTP Method):** `GET`
- **الرابط (URL):** `https://graph.facebook.com/me/accounts?fields=name,access_token&access_token={token}&limit=500`
- **نقطة النهاية (Endpoint):** `/me/accounts`
- **معاملات الاستعلام (Query Parameters):**
  - `fields=name,access_token`
  - `access_token=[REDACTED]`
  - `limit=500`
- **جسم الطلب (Payload/Body):** فارغ (None).
- **الترويسات (Headers):** الافتراضية لمكتبة `httpx`.
- **آلية المصادقة (Auth):** تمرير التوكن داخل الـ Query String.
- **المهلة (Timeout):** `15.0` ثانية.
- **إعادة المحاولة (Retries):** محاولة واحدة.
- **تحليل الرد (Response Parsing):**
  - استخراج `data.get('data', [])`
  - إنشاء قائمة بكل صفحة تحتوي على: `id`, `name`, `access_token`.
- **معالجة الأخطاء (Error Handling):** `except:` عام يطبع رسالة `⚠️ SCAN FAILED`.

---

### Request #3: طلب الانضمام للمجموعات (Join Groups Mutation)
- **الموقع في الكود الأصلي:** `legacy/bot.py` (الأسطر 452-456، 521-540) داخل دالة `fire()` في `process_async`.
- **طريقة الطلب (HTTP Method):** `POST`
- **الرابط (URL):** `https://graph.facebook.com/graphql`
- **نقطة النهاية (Endpoint):** `/graphql`
- **معاملات الاستعلام (Query Parameters):** لا توجد.
- **جسم الطلب (Payload/Form Data):**
  ```python
  {
      'access_token': item['token'],
      'variables': json.dumps({"input": {"group_id": str(item['target'])}}),
      'doc_id': '33243444848636579'
  }
  ```
- **الترويسات (Headers):** `Content-Type: application/x-www-form-urlencoded` (تلقائي من httpx data).
- **آلية المصادقة (Auth):** حقل `access_token` داخل جسم طلب الـ POST (توكن الحساب أو الصفحة المختارة).
- **المهلة (Timeout):** `REQUEST_TIMEOUT` (`12.0` ثانية).
- **إعادة المحاولة (Retries):** 3 محاولات (`RETRY_ATTEMPTS = 3`) مع فترات انتظار `[0.3, 0.7, 1.5]` ثانية.
- **تحليل الرد (Response Parsing):**
  - فحص نص الرد (`rt = response.text`):
  - `if 'MEMBER' in rt or 'already a member' in rt.lower() or '1341004' in rt: res = True`
- **شروط إعادة المحاولة:**
  - عند `429` أو وجود `rate limit`: زيادة عداد الـ retried والانتظار مع jitter عشوائي.
  - عند استثناءات الشبكة والمهلة (`TimeoutException`, `ConnectError`, `ReadError`, `WriteError`, `PoolTimeout`): انتظار وإعادة المحاولة.
  - عند `400` أو `403`: التوقف فوراً بدون إعادة محاولة.

---

### Request #4: قبول طلبات انضمام الأعضاء (Approve Members Mutation)
- **الموقع في الكود الأصلي:** `legacy/bot.py` (الأسطر 458-471، 521-540) داخل دالة `fire()`.
- **طريقة الطلب (HTTP Method):** `POST`
- **الرابط (URL):** `https://graph.facebook.com/graphql`
- **نقطة النهاية (Endpoint):** `/graphql`
- **معاملات الاستعلام (Query Parameters):** لا توجد.
- **جسم الطلب (Payload/Form Data):**
  ```python
  {
      'access_token': main_token,
      'variables': json.dumps({
          "groupID": str(item['target']),
          "memberID": str(item['mem_id']),
          "input": {
              "group_id": str(item['target']),
              "member": str(item['mem_id']),
              "actor_id": str(main_id)
          },
          "scale": 1
      }),
      'doc_id': '26744408605191970'
  }
  ```
- **الترويسات (Headers):** الافتراضية.
- **آلية المصادقة (Auth):** `main_token` لحساب الأدمن داخل الـ POST body.
- **المهلة (Timeout):** `12.0` ثانية.
- **إعادة المحاولة (Retries):** حتى 3 محاولات مثل Join.
- **تحليل الرد (Response Parsing):**
  - `if 'errors' not in rt or 'already a member' in rt.lower() or '1341004' in rt: res = True`

---

### Request #5: تعيين مشرفين للمجموعات (Moderator Approval Mutation)
- **الموقع في الكود الأصلي:** `legacy/bot.py` (الأسطر 473-488، 521-540) داخل دالة `fire()`.
- **طريقة الطلب (HTTP Method):** `POST`
- **الرابط (URL):** `https://graph.facebook.com/graphql`
- **نقطة النهاية (Endpoint):** `/graphql`
- **معاملات الاستعلام (Query Parameters):** لا توجد.
- **جسم الطلب (Payload/Form Data):**
  ```python
  {
      'access_token': main_token,
      'doc_id': '25320459267654690',
      'variables': json.dumps({
          "input": {
              "client_mutation_id": "2",
              "actor_id": str(main_id),
              "admin_type": "MODERATOR",
              "group_id": str(item['target']),
              "source": "COMET_GROUP_PAGE"
          },
          "inviteShortLinkKey": None,
          "scale": 1,
          "__relay_internal__pv__GroupsCometGroupChatLazyLoadLastMessageSnippetrelayprovider": False
      })
  }
  ```
- **الترويسات (Headers):** الافتراضية.
- **آلية المصادقة (Auth):** `main_token` داخل الـ POST body.
- **المهلة (Timeout):** `12.0` ثانية.
- **إعادة المحاولة (Retries):** حتى 3 محاولات.
- **تحليل الرد (Response Parsing):**
  - `if 'errors' not in rt: res = True`

---

## 2. جدول حصر الطلبات والمطابقة (Request Inventory Table)

| # | الوصف الأصلي للطلب | Method | Endpoint | Auth | تفاصيل الـ Payload | الموقع في الكود الجديد | الحالة (Status) |
|---|--------------------|--------|----------|------|--------------------|------------------------|-----------------|
| 1 | Verify Access Token | `GET` | `/me` | Query Param ➔ Header | لا يوجد | `facebook/client.py::verify_token` | **CHANGED** (أمني) |
| 2 | Fetch Accounts/Pages | `GET` | `/me/accounts` | Query Param ➔ Header | `fields=name,access_token&limit=500` | `facebook/client.py::get_pages` | **CHANGED** (أمني) |
| 3 | GraphQL Join Group | `POST` | `/graphql` | Body `access_token` | `doc_id: 33243444848636579` | `facebook/client.py` & `workers/engine.py` | **PASS** |
| 4 | GraphQL Approve Member | `POST` | `/graphql` | Body `access_token` | `doc_id: 26744408605191970` | `facebook/client.py` & `workers/engine.py` | **PASS** |
| 5 | GraphQL Mod Approval | `POST` | `/graphql` | Body `access_token` | `doc_id: 25320459267654690` | `facebook/client.py` & `workers/engine.py` | **PASS** |

---

## 3. المقارنة الدقيقة (Exact Comparison)

### 3.1 مقارنة الـ URLs و Endpoints
- **Request #1:** الأصل: `https://graph.facebook.com/me?access_token=...` | الجديد: `https://graph.facebook.com/me` (نفس النطاق ونقطة النهاية).
- **Request #2:** الأصل: `https://graph.facebook.com/me/accounts?...` | الجديد: `https://graph.facebook.com/me/accounts?fields=name,access_token&limit=500` (نفس النطاق ونقطة النهاية).
- **Requests #3, #4, #5:** الأصل: `https://graph.facebook.com/graphql` | الجديد: `https://graph.facebook.com/graphql` (**تطابق 100% تام**).

### 3.2 مقارنة الـ HTTP Methods
- الطلب 1: `GET` (مطابق)
- الطلب 2: `GET` (مطابق)
- الطلبات 3 و 4 و 5: `POST` (مطابقة تماماً)

### 3.3 مقارنة معاملات الاستعلام (Query Parameters)
- في الطلب 1: تم حذف `access_token` من الرابط ونقله إلى ترويسة `Authorization: Bearer [REDACTED]` تنفيذاً للمتطلبات الأمنية في Phase 3.
- في الطلب 2: تم الاحتفاظ بمعاملات `fields=name,access_token` و `limit=500`، ونُقل التوكن إلى الترويسة.
- في الطلبات 3 و 4 و 5: لا توجد معاملات استعلام في القديم أو الجديد.

### 3.4 مقارنة جسم الطلب والـ Payload (Request Body)
- **طلب Join (#3):**
  - `doc_id`: `33243444848636579` (متطابق حرفياً).
  - `variables`: `{"input": {"group_id": str(target)}}` (متطابق بالبنية والأنواع).
- **طلب Approve (#4):**
  - `doc_id`: `26744408605191970` (متطابق حرفياً).
  - `variables`: يحتوي على `groupID`, `memberID`, كائن `input` المتضمن `group_id`, `member`, `actor_id`، وقيمة `scale: 1` (متطابق بالبنية والمفاتيح والقيم).
- **طلب Moderator (#5):**
  - `doc_id`: `25320459267654690` (متطابق حرفياً).
  - `variables`: كائن `input` يحتوي على `client_mutation_id: "2"`, `actor_id`, `admin_type: "MODERATOR"`, `group_id`, `source: "COMET_GROUP_PAGE"`, بالإضافة إلى `inviteShortLinkKey: None`, `scale: 1`, والمفتاح الطويل الخاص بـ relay provider كـ `False`. (متطابق حرفياً بنسبة 100%).

---

## 4. مقارنة تدفق الطلبات (Request Flow Sequence)

تم فحص تسلسل العمليات وترتيب الاعتماديات في الكود الجديد:
1. **تسجيل الدخول:** المستخدم يرسل التوكن ➔ تنفيذ Request #1 للتحقق وجلب الاسم والـ ID ➔ تخزين الجلسة والانتقال لـ `S_MENU`.
2. **الانضمام بالصفحات (Join with Pages):** المستخدم يضغط `⚡ CONNECT GROUPS` ثم `📄 FAN PAGES` ➔ تنفيذ Request #2 لجلب الصفحات والـ Tokens التابعة لها ➔ عرض القائمة وتحديد الصفحات ➔ إدخال المعرفات ➔ اختيار السرعة ➔ تنفيذ Request #3 لكل (Target × Actor).
3. **الانضمام بالحساب الشخصي:** تنفيذ Request #3 مباشرة باستخدام `user['id']` و `user['token']`.
4. **قبول الأعضاء (Approve):** إدخال المجموعات ➔ إدخال الأعضاء ➔ تنفيذ Request #4 لكل (Group × Member) باستخدام `main_token` و `main_id`.
5. **تعيين المشرفين (Moderator):** إدخال المجموعات ➔ تنفيذ Request #5 لكل مجموعة باستخدام `main_token` و `main_id`.

**النتيجة:** تسلسل الاعتماديات وترتيب تدفق البيانات متطابق تماماً مع الكود الأصلي.

---

## 5. مقارنة آلية إعادة المحاولة (Retries Comparison)

| الخاصية | الكود الأصلي (`legacy/bot.py`) | الكود الجديد (`workers/engine.py` / `facebook/client.py`) | المقارنة |
|---|---|---|---|
| عدد المحاولات | 3 محاولات | 3 محاولات (`RETRY_ATTEMPTS`) | **مطابق (PASS)** |
| المهلة (Timeout) | `12.0` ثانية | `12.0` ثانية (`REQUEST_TIMEOUT`) | **مطابق (PASS)** |
| فترات الـ Backoff | `[0.3, 0.7, 1.5]` | `[0.3, 0.7, 1.5]` مع عشوائية (Jitter) | **مطابق (PASS)** |
| التعامل مع 429 | إعادة محاولة مع انتظار | تصنيف `RATE_LIMIT` وإعادة محاولة | **مطابق (PASS)** |
| التعامل مع 5xx | لم يكن مميزاً صراحة كـ 5xx | تصنيف `SERVER_ERROR` كـ Retryable | **تحسين منظم (PASS)** |
| التعامل مع 400 و 403 | التوقف الفوري (break) | التوقف الفوري (`is_retryable = False`) | **مطابق (PASS)** |
| أخطاء الشبكة والمهلة | إعادة محاولة | إعادة محاولة (`is_retryable = True`) | **مطابق (PASS)** |

---

## 6. توثيق الاختلافات المسجلة (Documented Differences)

بناءً على القاعدة (DO NOT MODIFY ORIGINAL REQUESTS SILENTLY)، تم توثيق الاختلافين التاليين:

### Difference #1: طريقة تمرير التوكن في Request #1 (`/me`)
- **الحالة:** `CHANGED`
- **الأصل:** `GET https://graph.facebook.com/me?access_token=[REDACTED]`
- **الجديد:** `GET https://graph.facebook.com/me` مع ترويسة `Authorization: Bearer [REDACTED]`
- **سبب التغيير:** الالتزام بمتطلبات Phase 3 الأمنية ("ممنوع طباعة tokens في logs أو تمرير credentials غير مشفرة"). تمرير التوكن في الـ Query String يُعرّضه للتسجيل في سيرفرات البروكسي والشبكة. معيار OAuth2 الرسمي لفيسبوك يدعم الترويسة بشكل كامل.
- **الأثر (Impact):** زيادة الأمان بدون أي تغيير في صلاحية التوكن أو البيانات المرجعة من فيسبوك.

### Difference #2: طريقة تمرير التوكن في Request #2 (`/me/accounts`)
- **الحالة:** `CHANGED`
- **الأصل:** `GET https://graph.facebook.com/me/accounts?fields=name,access_token&access_token=[REDACTED]&limit=500`
- **الجديد:** `GET https://graph.facebook.com/me/accounts?fields=name,access_token&limit=500` مع ترويسة `Authorization: Bearer [REDACTED]`
- **سبب التغيير:** نفس السبب الأمني للطلب الأول.
- **الأثر (Impact):** معتمد رسمياً من Meta Graph API وأكثر أماناً.

---

## 7. فحص الطلبات المفقودة والإضافية (Missing & Extra Requests Check)

- **الطلبات المفقودة (Missing Requests):** **0** (لا يوجد أي طلب في `legacy/bot.py` تم حذفه أو إغفاله).
- **الطلبات الإضافية (Extra Requests):** **0** (لم تتم إضافة أي طلبات خارجية أو اتصالات زائدة).

---

## 8. اختبارات لقطات الطلبات (Request Snapshot Tests)

تم إنشاء ملف اختبارات متخصص:
`tests/test_request_snapshots.py`
يقوم باعتراض كافة الطلبات الصادرة بواسطة Mock HTTP Client، وتطهير القيم الديناميكية (استبدال التوكنات بـ `<ACCESS_TOKEN>` والمعرفات بـ `<GROUP_ID>`, `<MEMBER_ID>`, `<ACTOR_ID>`)، ومقارنتها حرفياً مع العقود المستخرجة من `legacy/bot.py`.

نتائج الاختبارات:
- `test_snapshot_request_1_verify_token`: **PASSED**
- `test_snapshot_request_2_get_pages`: **PASSED**
- `test_snapshot_request_3_graphql_join`: **PASSED**
- `test_snapshot_request_4_graphql_approve`: **PASSED**
- `test_snapshot_request_5_graphql_moderator`: **PASSED**

---

## 9. إحصائيات التدقيق (Request Count Summary)

```text
Original HTTP requests:           5
Refactored equivalent requests:   5
Missing:                          0
Changed (Security Header):        2
Extra:                            0
Unverified:                       0
```

---

## 10. الحكم النهائي لسلامة الطلبات (Legacy Request Parity)

## Legacy Request Parity: PASS

- **جميع طلبات GraphQL الثلاثة (Join, Approve, Moderator) متطابقة بنسبة 100% حرفياً وهيكلياً في الـ doc_id والـ variables ومصدر التوكن.**
- **طلبا التحقق وجلب الصفحات تم الحفاظ على نقطتي النهاية والمعاملات الخاصة بهما مع ترقية أسلوب المصادقة إلى ترويسة `Bearer` القياسية.**
- **عدد الطلبات المفقودة: 0.**
- **عدد الطلبات الزائدة: 0.**
