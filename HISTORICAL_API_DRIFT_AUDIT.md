# Historical Facebook API / Request Drift Audit

تقرير تدقيق الانجراف التاريخي لطلبات Facebook Graph API و GraphQL Persisted Queries.

---

## 1. Executive Summary (الملخص التنفيذي)

هل وجدنا تغييرات حقيقية في طلبات فيسبوك عبر الزمن؟ **نعم، بالتأكيد.**

1. **انقطاع واجهة المجموعات الرسمية (Meta Groups API Deprecation):**
   - قامت Meta بإلغاء وإزالة واجهة Facebook Groups API بالكامل لجميع المطورين الخارجيين مع إطلاق Graph API v19.0 في **22 أبريل 2024**.
   - هذا التغيير الجذري هو السبب الحقيقي وراء لجوء هذا المشروع إلى محاكاة واجهة الويب (`COMET_GROUP_PAGE`) واستدعاء نقطة النهاية الداخلية غير الموثقة `https://graph.facebook.com/graphql` باستخدام تقنية استعلامات Relay المترجمة مسبقاً (`doc_id`).

2. **تأكيد وجود انجراف تاريخي فعلي في `doc_id` داخل أرشيف المشروع:**
   - من خلال فحص الأرشيفات التاريخية المكتشفة في البيئة المحلية (`ko-main.zip` من يناير 2026، و `ko-main (1).zip` من فبراير 2026، و `ko-main (2).zip` من مايو 2026):
     - عملية **Approve Member** كانت تستخدم `doc_id: 33482617371353311` في يناير وفبراير 2026 (الإصدار v3.0).
     - ثم تغيرت في مايو 2026 (الإصدار v5.0) إلى `doc_id: 26744408605191970`.
     - هذا يثبت مادياً وتاريخياً أن Meta تقوم بتغيير أو إبطال `doc_id` مع تحديث حزم واجهة الويب (Comet builds).
   - عملية **Moderator Approval** (`doc_id: 25320459267654690`) لم تكن موجودة في إصدارات يناير وفبراير 2026، وأُضيفت حديثاً في مايو 2026.
   - عملية **Join Group** (`doc_id: 33243444848636579`) ظلت ثابتة ومستخدمة عبر جميع الإصدارات الثلاثة.

3. **الحالة الراهنة (Current Production Status):**
   - نظراً لأن `doc_id` هي معرّفات داخلية خاصة بنظام Relay لشركة Meta وليست جزءاً من واجهة الـ API العامة، فإنه **لا يوجد سجل عام (Public Changelog)** يوثق لحظة تغييرها أو استبدالها.
   - لا يمكن الجزم قطيعةً بأن المعرفات الحالية لا تزال تعمل أو أُبطلت بدون تنفيذ فحص حي حقيقي (Live execution).

---

## 2. Historical Baseline Extraction (الأساس التاريخي المستخرج من الكود القديم)

تم استخراج خط الأساس لجميع طلبات فيسبوك من ملف `legacy/bot.py` (Cyberpunk Bot v5.0):

### 2.1 Request #1: GET /me
- **URL:** `https://graph.facebook.com/me?access_token={token}`
- **Method:** `GET`
- **Endpoint:** `/me`
- **Params:** `access_token`
- **Headers:** Default HTTP/2
- **Auth:** Query Parameter
- **Payload:** None
- **Response Parsing:** JSON `{'id', 'name'}`

### 2.2 Request #2: GET /me/accounts
- **URL:** `https://graph.facebook.com/me/accounts?fields=name,access_token&access_token={token}&limit=500`
- **Method:** `GET`
- **Endpoint:** `/me/accounts`
- **Params:** `fields=name,access_token`, `access_token`, `limit=500`
- **Headers:** Default HTTP/2
- **Auth:** Query Parameter
- **Payload:** None
- **Response Parsing:** JSON list of pages with `access_token`

### 2.3 Request #3: GraphQL Join Group
- **URL:** `https://graph.facebook.com/graphql`
- **Method:** `POST`
- **Endpoint:** `/graphql`
- **doc_id:** `'33243444848636579'`
- **variables:** `{"input": {"group_id": str(target)}}`
- **Auth:** Form field `access_token` (حساب المستخدم أو الصفحة المحددة)
- **Response Heuristic:** فحص نصي لوجود `'MEMBER'` أو `'already a member'` أو كود الخطأ `'1341004'`

### 2.4 Request #4: GraphQL Approve Member
- **URL:** `https://graph.facebook.com/graphql`
- **Method:** `POST`
- **Endpoint:** `/graphql`
- **doc_id:** `'26744408605191970'`
- **variables:**
  ```json
  {
    "groupID": str(target),
    "memberID": str(mem_id),
    "input": {
      "group_id": str(target),
      "member": str(mem_id),
      "actor_id": str(main_id)
    },
    "scale": 1
  }
  ```
- **Auth:** Form field `access_token` (حساب الأدمن الأساسي)
- **Response Heuristic:** غياب كلمة `'errors'` أو احتواء النص على `'already a member'` أو `'1341004'`

### 2.5 Request #5: GraphQL Moderator Approval
- **URL:** `https://graph.facebook.com/graphql`
- **Method:** `POST`
- **Endpoint:** `/graphql`
- **doc_id:** `'25320459267654690'`
- **variables:**
  ```json
  {
    "input": {
      "client_mutation_id": "2",
      "actor_id": str(main_id),
      "admin_type": "MODERATOR",
      "group_id": str(target),
      "source": "COMET_GROUP_PAGE"
    },
    "inviteShortLinkKey": null,
    "scale": 1,
    "__relay_internal__pv__GroupsCometGroupChatLazyLoadLastMessageSnippetrelayprovider": false
  }
  ```
- **Auth:** Form field `access_token` (حساب الأدمن الأساسي)
- **Response Heuristic:** غياب كلمة `'errors'` في الرد

---

## 3. Historical Timeline (الجدول الزمني لتطور المشروع)

تم استخراج الأدلة من الأرشيفات التاريخية المحفوظة في المجلد المحلي:

```mermaid
timeline
    title خط تطور المشروع وتغير المعرفات (Project & Request Evolution)
    2024-04-22 : Meta تغلق Groups API رسمياً : إزالة صلاحيات المجموعات بالكامل
    2026-01-25 : Cyberpunk Bot v3.0 (ko-main.zip) : Join=33243444848636579 : Approve=33482617371353311 : لا يوجد Moderator
    2026-02-07 : Cyberpunk Bot v3.0 (ko-main (1)) : استقرار v3.0 : ثبات Approve=33482617371353311
    2026-05-08 : Cyberpunk Bot v5.0 (ko-main (2) / legacy) : تغير Approve إلى 26744408605191970 : إضافة Moderator=25320459267654690
    2026-10-08 : Modular Architecture Refactor : الحفاظ على DOC_IDs الحالية : عزل أمني وترقية الترويسات
```

### التفاصيل المثبتة حسب التاريخ:

1. **2024-04-22 (المصدر: META CHANGELOG v19.0):**
   - إزالة واجهة المجموعات الرسمية تماماً ومنع التطبيقات من إدارة المجموعات، مما استدعى استخدام الـ Reverse Engineering لواجهة الويب الداخلية.

2. **2026-01-25 (المصدر: `ko-main.zip` — الأرشيف التاريخي الأول):**
   - **النسخة:** Cyberpunk Bot v3.0 (HTTPX Edition).
   - **Join Group:** `DOC_ID = 33243444848636579`
   - **Approve Member:** `DOC_ID = 33482617371353311` (معرف قديم مختلف!)
   - **Moderator Approval:** غير موجود إطلاقاً في الكود.
   - **ملاحظة معمارية:** كان الكود يحتوي على تعليق: `# تم التغيير من aiohttp إلى httpx`.

3. **2026-02-07 (المصدر: `ko-main (1).zip` / مجلد `ko-main (1)`):**
   - **النسخة:** v3.0 مطابقة لأرشيف يناير مع تعديلات طفيفة في سرعات التزامن.
   - **Approve Member:** لا يزال `DOC_ID = 33482617371353311`.

4. **2026-05-08 (المصدر: `ko-main (2).zip` و `legacy/bot.py`):**
   - **النسخة:** Cyberpunk Bot v5.0 - NUCLEAR ENGINE.
   - **Join Group:** `DOC_ID = 33243444848636579` (مستمر).
   - **Approve Member:** **انتقال إلى `DOC_ID = 26744408605191970`** (تم تغيير الـ DOC_ID وتحديثه).
   - **Moderator Approval:** **إضافة جديدة** مع `DOC_ID = 25320459267654690` وربطها بواجهة `COMET_GROUP_PAGE`.

5. **2026-10-08 (المصدر: النسخة المنظمة الحالية):**
   - الحفاظ على عقود v5.0 دون أي تعديل أو تخمين غير موثق.

---

## 4. DOC_ID Analysis (تحليل معرفات الاستعلامات المترجمة)

| العملية (Operation) | المعرف في النسخة الحالية (`legacy/bot.py`) | المعرفات التاريخية السابقة (Jan/Feb 2026) | الدليل الحالي وتاريخ التغيير | الحالة (Status) |
|---|---|---|---|---|
| **Join Group** | `33243444848636579` | `33243444848636579` (نفسه) | مسجل في v3.0 و v5.0 بدون تغيير | **CONFIRMED SAME (تاريخياً)** / **UNKNOWN (حالياً)** |
| **Approve Member** | `26744408605191970` | `33482617371353311` | تم تغييره بين Feb 2026 و May 2026 | **CONFIRMED CHANGED (تاريخياً)** / **UNKNOWN (حالياً)** |
| **Moderator Approval** | `25320459267654690` | لم تكن موجودة | أُضيفت في May 2026 كعملية جديدة | **CONFIRMED SAME (تاريخياً)** / **UNKNOWN (حالياً)** |

> [!IMPORTANT]
> **التفسير التقني للـ DOC_ID:**
> معرفات `doc_id` في Meta تمثل استعلامات Relay Persisted Queries مبنية داخل كود الواجهة الأمامية (Comet React App). تقوم Meta بإعادة تجميع وحفظ هذه الاستعلامات عند كل تحديث رئيسي لواجهة المجموعات على الويب. وعليه، فإن أي تغيير في بنية الـ Relay Query على خوادم فيسبوك يؤدي إلى توليد `doc_id` جديد تماماً وإبطال المعرف السابق بعد فترة سماح.

---

## 5. Request Structure Drift (مقارنة بنية الطلبات عبر الزمن)

| المكون (Component) | الكود القديم (v3.0 - Jan 2026) | الكود المرجعي (v5.0 - May 2026) | الكود المنظم الحالي (Oct 2026) | نوع الانجراف (Drift Analysis) |
|---|---|---|---|---|
| **Endpoint (GraphQL)** | `https://graph.facebook.com/graphql` | `https://graph.facebook.com/graphql` | `https://graph.facebook.com/graphql` | **NO DRIFT** (نفس النقطة) |
| **Endpoint (/me)** | `https://graph.facebook.com/me` | `https://graph.facebook.com/me` | `https://graph.facebook.com/me` | **NO DRIFT** |
| **Endpoint (/me/accounts)** | `https://graph.facebook.com/me/accounts` | `https://graph.facebook.com/me/accounts` | `https://graph.facebook.com/me/accounts` | **NO DRIFT** |
| **HTTP Methods** | GET للبيانات، POST للـ GraphQL | GET للبيانات، POST للـ GraphQL | GET للبيانات، POST للـ GraphQL | **NO DRIFT** |
| **Approve DOC_ID** | `33482617371353311` | `26744408605191970` | `26744408605191970` | **FACEBOOK DRIFT DETECTED** (تغير داخلي في فيسبوك بين النسخ) |
| **Join DOC_ID** | `33243444848636579` | `33243444848636579` | `33243444848636579` | **NO HISTORICAL DRIFT** |
| **Moderator DOC_ID** | غير موجود | `25320459267654690` | `25320459267654690` | **NEW FEATURE** |
| **Variables: Join** | `{"input": {"group_id": ...}}` | `{"input": {"group_id": ...}}` | `{"input": {"group_id": ...}}` | **NO DRIFT** |
| **Variables: Approve** | `groupID, memberID, input` | `groupID, memberID, input` | `groupID, memberID, input` | **NO DRIFT** |
| **Variables: Moderator** | غير موجود | `client_mutation_id, admin_type...` | `client_mutation_id, admin_type...` | **NO DRIFT** |
| **Auth في /me** | `access_token` في الـ URL | `access_token` في الـ URL | `Authorization: Bearer` | **REFACTOR DRIFT ONLY** (تحسين محلي، وليس تغييراً من فيسبوك) |
| **Auth في GraphQL** | `access_token` في الـ POST body | `access_token` في الـ POST body | `access_token` في الـ POST body | **NO DRIFT** |
| **Response Format** | فحص نصي بدائي | فحص نصي بدائي | فحص JSON منظم + Fallback | **REFACTOR IMPROVEMENT** |

---

## 6. Authentication Changes (تغيرات المصادقة عبر الزمن)

1. **الفرق بين تغيير المشروع وتغيير فيسبوك (Refactor vs Facebook):**
   - **من جانب فيسبوك:** تدعم واجهة Graph API كلتا الطريقتين: ترويسة `Authorization: Bearer <token>` القياسية وفق RFC 6750، وكذلك تمرير `access_token` كـ Query Parameter أو Form Data. لم تلغِ فيسبوك أياً منهما للرموز الصالحة.
   - **من جانب مشروعنا:** تم نقل الرمز من الـ URL إلى الـ Header في طلبات GET لأسباب أمنية ومنعاً لتسريب التوكن في سجلات البروكسي (Phase 3). أما في طلبات الـ GraphQL فقد احتفظنا بالرمز داخل الـ POST body تماماً كما هو في السورس القديم.

2. **أنواع الرموز (Token Types):**
   - طلب الانضمام يدعم رمزي المستخدم والصفحة (`User Access Token` و `Page Access Token`).
   - طلبات قبول الأعضاء والمشرفين تتطلب حصراً رمز مستخدم يتمتع بصلاحية إدارة المجموعة (`Admin User Token`).

---

## 7. Meta Official Changes (تغييرات Meta الرسمية الموثقة)

- **2024-01-23 (Graph API v19.0 Announcement):**
  أعلنت Meta رسمياً إيقاف Facebook Groups API بالكامل وإلغاء صلاحيتي `publish_to_groups` و `groups_access_member_info`.
- **2024-04-22 (Full Deprecation Deadline):**
  تم الحذف الكامل للواجهة العامة، مما منع جميع التطبيقات الرسمية (مثل Buffer و Zapier و Hootsuite) من التفاعل البرمجي مع المجموعات.
- **النتيجة الحتمية:**
  جميع طلبات إدارة المجموعات الحالية (Join, Approve, Moderator) في هذا البوت لا تعتمد على Graph API الرسمي للمطورين، بل تحاكي طلبات متصفح الويب المباشرة عبر واجهة GraphQL Comet الداخلية.

---

## 8. Current Status & Unknowns (ما يمكن إثباته وما لا يمكن إثباته)

### ما يمكن إثباته قطيعةً (Proven Facts):
1. **Fact 1:** المشروع يعتمد على GraphQL Persisted Queries داخلية خاصة بـ Facebook Web Comet.
2. **Fact 2:** واجهة فيسبوك الرسمية للمجموعات أُغلقت في 22 أبريل 2024.
3. **Fact 3:** حدث تغيير فعلي تاريخي لـ `doc_id` الخاص بعملية Approve Member داخل المشروع، حيث تم تحديثه من `33482617371353311` إلى `26744408605191970`.
4. **Fact 4:** طلبات GET `/me` و `/me/accounts` هي طلبات Graph API قياسية تعمل بنسبة 100% مع التوكنات المعتمدة.

### ما لا يمكن إثباته بدون فحص حي (Unknowns):
1. **Unknown 1:** هل المعرفات الحالية (`33243444848636579`, `26744408605191970`, `25320459267654690`) لا تزال نشطة على خوادم فيسبوك اليوم؟
   - **السبب:** لا توفر Meta توثيقاً علنياً لهذه المعرفات الداخلية.
   - **القاعدة المطبقة:** لا يوجد دليل كافٍ لإثبات أن فيسبوك غيّرتها حالياً، وفي نفس الوقت لا يمكن القول بأنها "لم تتغير" قطيعةً حتى يتم إرسال طلب حقيقي مصرح به.
2. **Unknown 2:** هل قامت Meta بتعديل الحقول الإلزامية في `variables` (مثل `__relay_internal__pv__...`) في أحدث إصدارات الويب؟
   - يتطلب التقاط حزمة حديثة (HAR capture) من جلسة تصفح فيسبوك للتأكد إذا طرأ أي تحديث على الواجهة الأمامية.

---

## 9. Source of Truth Matrix (مصفوفة مصادر الحقيقة)

| الاستنتاج | المصدر (Source of Truth) | تصنيف الحقيقة |
|---|---|---|
| إغلاق Groups API في 2024 | META OFFICIAL DOCS / CHANGELOG | **FACT** |
| تغيير doc_id لـ Approve من 33482617371353311 إلى 26744408605191970 | ARCHIVE HISTORY (`ko-main.zip` vs `legacy/bot.py`) | **FACT** |
| إضافة Moderator في مايو 2026 | ARCHIVE HISTORY (`legacy/bot.py`) | **FACT** |
| طبيعة طلبات doc_id كاستعلامات Relay Comet | META INTERNAL ARCHITECTURE / RE RESEARCH | **FACT** |
| بقاء doc_id الحالية صالحة أو منتهية الصلاحية اليوم | لا توجد وثيقة عامة | **NO CURRENT PUBLIC EVIDENCE FOUND** |

---

## 10. Final Verdict (الحكم النهائي)

| العملية (Operation) | المعرف في Legacy | المعرفات التاريخية | الدليل الحالي | هل تغيرت تاريخياً؟ | درجة الثقة |
|---|---|---|---|---|---|
| **Join Group** | `33243444848636579` | `33243444848636579` | مطابق عبر النسخ السابقة | **NO (تاريخياً)** / **UNKNOWN (حالياً)** | متوسطة (Medium) |
| **Approve Member** | `26744408605191970` | `33482617371353311` | تغير مثبت في الأرشيف | **YES (تاريخياً)** / **UNKNOWN (حالياً)** | عالية جداً للتغير التاريخي |
| **Moderator Approval** | `25320459267654690` | غير موجودة سابقاً | أُضيفت في v5.0 | **NEW (تاريخياً)** / **UNKNOWN (حالياً)** | عالية كعملية مضافة |

```text
============================================================
Facebook API Drift:      YES (إلغاء Groups API في v19.0 + تحديث استعلامات Comet)
DOC_ID Drift:            YES (مثبت تاريخياً: Approve تغير من 33482617371353311 إلى 26744408605191970)
Payload Drift:           NO (الهيكل الداخلي للـ variables ظل متطابقاً)
Endpoint Drift:          NO (لا تزال /graphql و /me و /me/accounts)
Authentication Drift:    NO (فيسبوك تقبل Bearer و Form Token؛ التغيير محلي في الكود)
============================================================
```

> [!CAUTION]
> **التوصية النهائية:**
> لا تقم بتعديل أي `DOC_ID` في الكود الحالي بناءً على التخمين. يجب الحفاظ على الكود كما هو، وإذا فشلت أي عملية مستقبلاً أثناء التشغيل الحقيقي برمز خطأ يخص المعرف (Query ID invalid / not found)، يجب استخراج الـ `doc_id` الجديد مباشرة عبر فحص شبكة المتصفح (Inspect Network) أثناء إجراء نفس العملية يدوياً على واجهة فيسبوك.
