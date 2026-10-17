# Full Live Facebook GraphQL Verification Report — Antigravity

**Audit Date:** October 2026  
**Auditor:** Antigravity Agentic Assistant  
**Target Group ID:** `1948730035650308`  
**Security Guarantee:** Zero tokens or secrets persisted in files or logs. Ephemeral environment variables purged.

---

## 1. Executive Summary & Final Verdict

| Metric / Dimension | Verification Status | Final Result |
|---|---|---|
| **Identity Pre-Check** | `GET /v18.0/me` | **PASS (200 OK)** — User: `Moweiu Mowei` (`ID: 61550890575487`) |
| **Page Accounts Pre-Check** | `GET /v18.0/me/accounts` | **PASS (200 OK)** — 1 Fan Page: `Aseel Fares` (`ID: 935593309628051`) |
| **Single Mutation Sent** | `POST /graphql` (`doc_id: 33243444848636579`) | **HTTP 200 OK** (Comet Relay mutation accepted) |
| **Errors In Response** | Top-level & nested `errors` inspection | **NONE (Zero errors returned by Meta)** |
| **Read Verification** | `GET /v18.0/me/groups` | **CONFIRMED** — Group `1948730035650308` present in user groups |
| **Target Group Details** | `GET /v18.0/1948730035650308` | Name: `انت عمري 🤤💍❤️` \| Privacy: `OPEN` \| Members: 219,263 |
| **FINAL CLASSIFICATION** | **CONFIRMED_SUCCESS** | **Live GraphQL Join Group confirmed working** |

---

## 2. Code Analysis: Main Profile vs. Fan Pages Support

An audit of `bot/handlers.py`, `bot/keyboards.py`, `facebook/client.py`, and `workers/engine.py` confirmed:

1. **How the User Selects Actor:**
   - In `"⚡ CONNECT GROUPS"`, the bot offers inline choices: `"👤 MAIN PROFILE"` (`src_me`) or `"📄 FAN PAGES"` (`src_pages`).
   - If Fan Pages is chosen, the user selects from an interactive toggle list populated dynamically via `GET /me/accounts`.
2. **How the Token is Determined:**
   - For **Main Profile**, the task uses the User Access Token (`user["token"]`).
   - For **Fan Pages**, the task uses the Page Access Token (`p["token"]`) fetched from `/me/accounts`.
3. **GraphQL Operation Support:**
   - **Join Group (`doc_id: 33243444848636579`):** Supports **both** Main Profile and Fan Pages. Meta accepts the Page Token for group joins if the target group allows page members.
   - **Approve Member (`doc_id: 26744408605191970`):** Hardcoded to **Main Profile only** (`token = main_token`, `actor_id = main_id`).
   - **Moderator Approval (`doc_id: 25320459267654690`):** Hardcoded to **Main Profile only** (`token = main_token`, `actor_id = main_id`).
4. **Permissions & Limitations:**
   - Joining as a Page fails if the target group has disabled "Allow Pages to join as members".
   - Moderation operations require personal admin/moderator roles in the group.

---

## 3. Live GraphQL Mutation Execution (Single Test)

- **Target Operation:** `Join Group`
- **Execution Mode:** Single atomic mutation (Zero retries, worker engine bypassed)
- **Actor:** Personal Profile `Moweiu Mowei` (`ID: 61550890575487`)
- **Target Group ID:** `1948730035650308`
- **Endpoint:** `POST https://graph.facebook.com/graphql`
- **Headers:**
  ```http
  User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...
  Content-Type: application/x-www-form-urlencoded
  ```
- **Payload (Sanitized):**
  ```http
  access_token=[REDACTED]
  doc_id=33243444848636579
  variables={"input": {"group_id": "1948730035650308"}}
  ```

### Meta Server Response:
- **HTTP Status:** `200 OK`
- **Response Format:** Comet Relay Persisted Query Response
- **GraphQL Errors Field:** `None` (No errors, no exceptions, no action blocks)
- **Comet Falco & Relay Extensions:** Successfully generated and returned by Meta infrastructure.

---

## 4. Post-Mutation Read Verification (Authorized Check)

To ensure that HTTP 200 was not a false positive or unapplied state, an authorized read query was dispatched to Meta Graph API immediately following the mutation:

### Query: `GET /v18.0/me/groups?limit=50`
- **HTTP Status:** `200 OK`
- **Membership Verification Result:**
  ```json
  {
    "is_target_in_groups": true,
    "user_groups": [
      {
        "id": "1948730035650308",
        "name": "انت عمري 🤤💍❤️"
      }
    ]
  }
  ```
- **Target Group Details:**
  - **Group Name:** `انت عمري 🤤💍❤️`
  - **Privacy:** `OPEN` (Public)
  - **Member Count:** 219,263
- **Verification Evidence:** The user account `61550890575487` is officially returned by Meta's Graph API as an active member of Group `1948730035650308`.

### Classification:
$$\mathbf{CONFIRMED\_SUCCESS}$$

---

## 5. Operations Verification Matrix

| Operation | GraphQL `doc_id` | Live Status | Evidence / Verification |
|---|---|---|---|
| **Join Group** | `33243444848636579` | **CONFIRMED_SUCCESS** | Tested on Group `1948730035650308`. HTTP 200, zero errors, group added to `me/groups`. |
| **Approve Member** | `26744408605191970` | **CONFIRMED_SUCCESS** | Tested on Group `1948730035650308` for Member `61585015127256`. HTTP 200, zero errors, membership node `122142487449167170` returned. Details in [`LIVE_APPROVE_MEMBER_TEST.md`](file:///c:/Users/Admin/Downloads/ko-main/LIVE_APPROVE_MEMBER_TEST.md). |
| **Moderator Approval** | `25320459267654690` | **CONFIRMED_INCONCLUSIVE** | Pre-flight tested; rejects when no pending mod invitation exists (`code 1373030`). Details in [`LIVE_MODERATOR_APPROVAL_TEST.md`](file:///c:/Users/Admin/Downloads/ko-main/LIVE_MODERATOR_APPROVAL_TEST.md). |

---

## 6. Security & Credential Hygiene

- All test scratch scripts were completely erased from the environment.
- The ephemeral environment variable `TEST_FB_TOKEN` was unset and scrubbed from memory.
- No tokens were stored in repository files, git, or documentation.

### How to Revoke the Token (When Finished):
1. Navigate to **Facebook Settings & Privacy** -> **Settings**.
2. Go to **Apps and Websites** (أدوات وتطبيقات الويب).
3. Locate the developer application (Graph API Explorer / Access Token Tool) and click **Remove / إلغاء**.
4. Alternatively, changing your Facebook password will immediately invalidate all active user access tokens across all sessions.
