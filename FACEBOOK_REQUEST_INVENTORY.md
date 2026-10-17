# Facebook API Request Inventory & Parity Specification

**Audit Target:** Meta / Facebook Graph & Internal GraphQL Requests  
**Comparison:** `legacy/bot.py` vs. `facebook/client.py` (`FacebookClient`)  
**Status:** ALL 5 LEGACY REQUESTS FULLY PRESERVED & STRUCTURALLY PARALLEL  

---

## Executive Summary

The project interacts with Meta's infrastructure via two distinct request families:
1. **Public Graph API (`v18.0`) REST Endpoints:** Used for identity verification and fetching managed Fan Pages.
2. **Comet Frontend Internal GraphQL (`/graphql`) Endpoints:** Used for group membership and member management actions via Relay persisted queries (`doc_id`).

Every request present in the original single-file `legacy/bot.py` has been extracted into dedicated methods within `facebook/client.py`, wrapped with structured error handling, retry policies, and typed models.

---

## Detailed Request Catalog

### Request 1: Identity & Token Verification (`GET /me`)

- **Primary Role:** Authenticate user Facebook token upon input in Telegram, retrieve basic user profile info.
- **Legacy Location:** `legacy/bot.py` (lines 80–92 inside `auth_token_step`)
- **Refactored Location:** `facebook/client.py` (`FacebookClient.verify_token`)
- **HTTP Method:** `GET`
- **Target URL:** `https://graph.facebook.com/v18.0/me`
- **Query Parameters:**
  - `fields`: `id,name`
- **Headers:**
  - `User-Agent`: Desktop browser profile (`Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36`)
  - `Authorization`: `Bearer <token>` *(Legacy passed `?access_token=<token>` query parameter; refactored uses standard OAuth Bearer header for security and compliance with Meta RFC 6750)*
- **Authentication:** User Access Token (Graph User Token)
- **Timeout:** 15.0 seconds
- **Retry Policy:** 1 immediate retry on connection/timeout error (via `_request_with_retry`)
- **Expected Success Payload:**
  ```json
  {
    "id": "61550890575487",
    "name": "Moweiu Mowei"
  }
  ```
- **Success Condition:** HTTP status 200 and response contains a non-empty `id` field.
- **Error Handling:**
  - HTTP 401/403 or Meta code 190: Returns `AuthError` (Token invalid or expired).
  - HTTP 429 or Meta code 4/17: Returns `RateLimitError`.
  - JSON parse error / missing `id`: Returns `APIError`.

---

### Request 2: Fetch Managed Fan Pages (`GET /me/accounts`)

- **Primary Role:** Retrieve Facebook Pages managed by the authenticated user to allow Page-based group joining.
- **Legacy Location:** `legacy/bot.py` (lines 145–160 inside `choose_source_step`)
- **Refactored Location:** `facebook/client.py` (`FacebookClient.get_fan_pages`)
- **HTTP Method:** `GET`
- **Target URL:** `https://graph.facebook.com/v18.0/me/accounts`
- **Query Parameters:**
  - `fields`: `id,name,access_token`
  - `limit`: `50`
- **Headers:**
  - `User-Agent`: Desktop browser profile
  - `Authorization`: `Bearer <token>` *(Legacy passed `?access_token=<token>` parameter)*
- **Authentication:** User Access Token (`pages_read_engagement`, `pages_show_list`, or `pages_manage_posts` permissions)
- **Timeout:** 15.0 seconds
- **Retry Policy:** 1 retry on connection timeout
- **Expected Success Payload:**
  ```json
  {
    "data": [
      {
        "id": "935593309628051",
        "name": "Aseel Fares",
        "access_token": "EAAD6..."
      }
    ],
    "paging": { "cursors": { ... } }
  }
  ```
- **Success Condition:** HTTP status 200 and JSON contains `data` list (can be empty list if user manages 0 pages).
- **Error Handling:**
  - HTTP 400/403: If permissions are missing, gracefully logs warning and returns empty list `[]`.
  - HTTP 401: Raises `AuthError`.

---

### Request 3: Group Join Mutation (`POST /graphql`)

- **Primary Role:** Join or request to join a Facebook group as Main Profile or as Fan Page actor.
- **Legacy Location:** `legacy/bot.py` (lines 405–425 inside `process_tasks`)
- **Refactored Location:** `facebook/client.py` (`FacebookClient.join_group`)
- **HTTP Method:** `POST`
- **Target URL:** `https://graph.facebook.com/graphql`
- **Payload Format:** `application/x-www-form-urlencoded`
- **Form Parameters:**
  - `doc_id`: `33243444848636579`
  - `variables`: JSON string:
    ```json
    {
      "input": {
        "client_mutation_id": "<uuid-4>",
        "actor_id": "<actor_id>",
        "group_id": "<group_id>",
        "source": "group_profile"
      }
    }
    ```
- **Headers:**
  - `User-Agent`: Desktop browser profile
  - `Authorization`: `Bearer <token>` *(Uses Page token if acting as page, User token if profile)*
  - `Content-Type`: `application/x-www-form-urlencoded`
- **Authentication:** Page Token (for page actor) or User Token (for profile actor)
- **Timeout:** 15.0 seconds
- **Retry Policy:** 3 attempts with exponential backoff on transient errors (HTTP 5xx, timeouts)
- **Success Conditions:**
  - HTTP 200 AND JSON does not contain top-level `"errors"` block.
  - SPECIAL COMPATIBILITY RULE: If JSON contains error subcode `2422002` or error summary `"You are already a member of this group"`, legacy behavior classifies this as **SUCCESS** (`OperationStatus.SUCCESS` with note `Already Member`).
- **Failure Conditions:**
  - Action Blocked / Checkpoint (Meta codes 368, 1404xxx).
  - Group Not Found / Privacy Mismatch (Meta codes 100, 1675xxx).

---

### Request 4: Approve Group Member (`POST /graphql`)

- **Primary Role:** Approve a pending user application to join an admin-controlled group.
- **Legacy Location:** `legacy/bot.py` (lines 430–450 inside `process_tasks`)
- **Refactored Location:** `facebook/client.py` (`FacebookClient.approve_member`)
- **HTTP Method:** `POST`
- **Target URL:** `https://graph.facebook.com/graphql`
- **Payload Format:** `application/x-www-form-urlencoded`
- **Form Parameters:**
  - `doc_id`: `26744408605191970` *(Baseline from legacy/bot.py v5.0)*
  - `variables`: JSON string:
    ```json
    {
      "input": {
        "client_mutation_id": "<uuid-4>",
        "actor_id": "<admin_user_id>",
        "group_id": "<group_id>",
        "target_id": "<user_id_to_approve>",
        "source": "group_pending_members"
      }
    }
    ```
- **Headers:**
  - `User-Agent`: Desktop browser profile
  - `Authorization`: `Bearer <token>`
  - `Content-Type`: `application/x-www-form-urlencoded`
- **Authentication:** Admin/Moderator User Access Token
- **Timeout:** 15.0 seconds
- **Retry Policy:** 3 attempts with backoff on network errors
- **Success Condition:** HTTP 200 AND no `errors` in response payload.
- **Failure Condition:** Target not found, already approved, lack of admin privileges, or AST hash invalidation.

---

### Request 5: Moderator Group Approval / Role Transition (`POST /graphql`)

- **Primary Role:** Transition pending member or manage moderator approval in admin-moderator configured groups.
- **Legacy Location:** `legacy/bot.py` (lines 455–475 inside `process_tasks`)
- **Refactored Location:** `facebook/client.py` (`FacebookClient.moderator_approval`)
- **HTTP Method:** `POST`
- **Target URL:** `https://graph.facebook.com/graphql`
- **Payload Format:** `application/x-www-form-urlencoded`
- **Form Parameters:**
  - `doc_id`: `25320459267654690`
  - `variables`: JSON string:
    ```json
    {
      "input": {
        "client_mutation_id": "<uuid-4>",
        "actor_id": "<admin_user_id>",
        "group_id": "<group_id>",
        "target_id": "<target_user_id>",
        "source": "member_list"
      }
    }
    ```
- **Headers:**
  - `User-Agent`: Desktop browser profile
  - `Authorization`: `Bearer <token>`
  - `Content-Type`: `application/x-www-form-urlencoded`
- **Authentication:** Group Admin/Moderator User Access Token
- **Timeout:** 15.0 seconds
- **Retry Policy:** 3 attempts with backoff
- **Success Condition:** HTTP 200 and no top-level `errors`.
- **Failure Condition:** Graph authorization error or Relay doc_id mutation failure.

---

## Request Parity Matrix

| Attribute | Legacy Implementation (`legacy/bot.py`) | Refactored Implementation (`facebook/client.py`) | Parity Status | Rationale |
|---|---|---|---|---|
| **Request 1 Endpoint** | `https://graph.facebook.com/v18.0/me` | `https://graph.facebook.com/v18.0/me` | **PASS** | Exact match |
| **Request 1 Auth** | `?access_token=...` | `Authorization: Bearer ...` | **PASS** | Meta-standard upgrade; prevents token in query logs |
| **Request 2 Endpoint** | `https://graph.facebook.com/v18.0/me/accounts` | `https://graph.facebook.com/v18.0/me/accounts` | **PASS** | Exact match |
| **Request 2 Fields** | `id,name,access_token` | `id,name,access_token` | **PASS** | Exact match |
| **Request 3 DOC_ID** | `33243444848636579` | `33243444848636579` | **PASS** | Exact match |
| **Request 3 Payload** | `doc_id, variables: {input: ...}` | `doc_id, variables: {input: ...}` | **PASS** | Exact JSON serialization match |
| **Request 4 DOC_ID** | `26744408605191970` | `26744408605191970` | **PASS** | Exact match |
| **Request 5 DOC_ID** | `25320459267654690` | `25320459267654690` | **PASS** | Exact match |
| **Already Member Fallback** | Subcode `2422002` treated as OK | Subcode `2422002` treated as OK | **PASS** | Exact behavior preserved |
| **Connection Timeout** | 10s default in `httpx` | 15s configured in `config.py` | **PASS** | Resilient improvement under latency |
| **Retry Strategy** | Ad-hoc single retry | Exponential backoff (1s, 2s, 4s) | **PASS** | Resilient improvement |
