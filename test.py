"""
Facebook Page Conversations & Open Inbox Inspector Tool.
Refactored and secured for production compatibility with Python 3.12,
asyncio event loops, safe secret management, and Telegram bot integration.
"""

import asyncio
import io
import logging
import os
import re
import sys
import time
import unicodedata
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Set, Tuple

import aiohttp

# Safe console encoding wrapper for Windows environments
if sys.platform == "win32":
    try:
        os.system("chcp 65001 > nul")
    except Exception:
        pass

if hasattr(sys.stdout, "buffer") and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

# Attempt to load configuration from project config module or environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from config import GRAPH_API_BASE_URL, TELEGRAM_BOT_TOKEN as CFG_TG_TOKEN, OWNER_ID as CFG_OWNER_ID
except ImportError:
    GRAPH_API_BASE_URL = "https://graph.facebook.com"
    CFG_TG_TOKEN = ""
    CFG_OWNER_ID = 1167798421

# -----------------------------------------------------------------------------
# ⚙️ Configuration Defaults (No hardcoded credentials)
# -----------------------------------------------------------------------------
API_VERSION = os.environ.get("FB_API_VERSION", "v18.0")
FB_GRAPH = os.environ.get("GRAPH_API_BASE_URL", f"https://graph.facebook.com/{API_VERSION}").rstrip("/")

DEFAULT_BATCH_SIZE = int(os.environ.get("CONV_BATCH_SIZE", "9"))
DEFAULT_CONCURRENCY = int(os.environ.get("CONV_CONCURRENCY", "5"))
DEFAULT_PAGE_CONV_LIMIT = int(os.environ.get("PAGE_CONV_LIMIT", "499"))
DEFAULT_HTTP_TIMEOUT = float(os.environ.get("CONV_HTTP_TIMEOUT", "30.0"))
DEFAULT_RETRY_ATTEMPTS = int(os.environ.get("CONV_RETRY_ATTEMPTS", "3"))
MAX_BACKOFF_SECONDS = 20.0

logger = logging.getLogger("fb-conversations-checker")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# -----------------------------------------------------------------------------
# 🛡️ Custom Structured Exceptions
# -----------------------------------------------------------------------------
class FacebookGraphError(Exception):
    """Base error for Facebook Graph API interactions."""
    def __init__(self, message: str, code: Optional[int] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class FacebookAuthError(FacebookGraphError):
    """Raised on invalid, expired, or revoked access tokens (Code 190, HTTP 401/403)."""
    pass


class FacebookPermissionError(FacebookGraphError):
    """Raised when token lacks required permissions (e.g. pages_messaging, code 200)."""
    pass


class FacebookRateLimitError(FacebookGraphError):
    """Raised when Facebook rate limit is hit and retries are exhausted."""
    pass


# -----------------------------------------------------------------------------
# 🛠️ Helper Utilities
# -----------------------------------------------------------------------------
def now_ts() -> str:
    """Returns formatted current timestamp."""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def mask_token(token: Optional[str]) -> str:
    """Masks secrets for safe logging and error reporting."""
    if not token:
        return "<none>"
    s = str(token).strip()
    if len(s) <= 8:
        return "***"
    return f"{s[:4]}...{s[-4:]}"


def fix_arabic_display(text: Any) -> str:
    """Normalizes Arabic/Unicode strings for reliable terminal display."""
    if not text:
        return ""
    try:
        return unicodedata.normalize("NFKC", str(text))
    except Exception:
        return str(text)


def chunked(iterable: List[Any], n: int):
    """Yield successive n-sized chunks from iterable."""
    for i in range(0, len(iterable), n):
        yield iterable[i : i + n]


def escape_markdown(text: Any) -> str:
    """
    Safely escapes special characters for Telegram's standard Markdown (v1) mode.
    Escapes unescaped _, *, `, and [ without double-escaping.
    Preserves all other characters and exact display.
    """
    if text is None:
        return ""
    s = str(text)
    # Normalize pre-escaped markdown characters to prevent double-escaping
    s = re.sub(r"\\([_*`\[])", r"\1", s)
    # Escape markdown v1 special characters
    return re.sub(r"([_*`\[])", r"\\\1", s)


# -----------------------------------------------------------------------------
# 🔍 Heuristic & Strict Analysis: Is Conversation Open?
# -----------------------------------------------------------------------------
def conv_is_open(conv: Dict[str, Any]) -> bool:
    """
    Determines whether a Facebook Page conversation is open/active.

    Rules:
    1. If 'unread_count' is present and > 0, it is definitely OPEN.
    2. If 'folder' is explicitly 'inbox', it is OPEN. If in ('done', 'spam', 'archived'), it is CLOSED.
    3. Tags inspection:
       - If any closed keyword ("done", "closed", "archived", "resolved", "spam") matches -> CLOSED (False).
       - If any explicit open keyword ("inbox", "open", "active", "unread", "follow_up", "needs_reply", "pending") matches -> OPEN (True).
    4. An arbitrary tag (e.g. 'vip', 'lead', 'product') without unread messages or an explicit
       open indicator does NOT make a conversation open. Default is False.
    """
    if not isinstance(conv, dict):
        return False

    try:
        # 1. Unread count inspection
        unread = conv.get("unread_count")
        if unread is not None:
            try:
                if int(unread) > 0:
                    return True
            except (ValueError, TypeError):
                pass

        # 2. Folder attribute check (if provided by API)
        folder = str(conv.get("folder", "")).strip().lower()
        if folder in ("done", "closed", "spam", "archived"):
            return False
        if folder == "inbox":
            return True

        # 3. Tags attribute extraction and evaluation
        tags_raw = conv.get("tags")
        tag_items: List[Any] = []
        if isinstance(tags_raw, dict):
            tag_items = tags_raw.get("data", [])
        elif isinstance(tags_raw, list):
            tag_items = tags_raw

        tag_names: Set[str] = set()
        for t in tag_items:
            if isinstance(t, dict):
                name = t.get("name") or t.get("tag") or ""
                if name:
                    tag_names.add(str(name).strip().lower())
            elif isinstance(t, str) and t.strip():
                tag_names.add(t.strip().lower())

        if tag_names:
            closed_keywords = {"done", "closed", "archived", "resolved", "spam"}
            if any(ck in tn for tn in tag_names for ck in closed_keywords):
                return False

            open_keywords = {"inbox", "open", "active", "unread", "follow_up", "needs_reply", "pending"}
            if any(ok in tn for tn in tag_names for ok in open_keywords):
                return True

        # By default, absent unread messages or confirmed open state, conversation is not considered open
        return False
    except Exception as exc:
        logger.debug("conv_is_open error for conv %s: %s", conv.get("id"), exc)
        return False


# -----------------------------------------------------------------------------
# 🌐 Resilient HTTP Client with Retries & Graph Error Handling
# -----------------------------------------------------------------------------
async def fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    retry: int = DEFAULT_RETRY_ATTEMPTS,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
) -> Dict[str, Any]:
    """
    Performs HTTP GET with exponential backoff for transient failures.
    Identifies and raises specific exceptions for Auth and Permission errors.
    """
    params = dict(params or {})
    attempt = 0

    while attempt < retry:
        attempt += 1
        try:
            client_timeout = aiohttp.ClientTimeout(total=timeout, connect=10.0)
            async with session.get(url, params=params, timeout=client_timeout) as resp:
                status = resp.status
                try:
                    payload = await resp.json()
                except Exception:
                    raw_text = await resp.text()
                    payload = {"error": {"message": raw_text[:200], "code": status}}

                # 1. Check for Graph API explicit error object
                if isinstance(payload, dict) and "error" in payload:
                    err = payload["error"]
                    err_code = err.get("code")
                    err_msg = err.get("message", "Unknown Graph API Error")

                    # Authentication / Token expiration (OAuthException code 190)
                    if err_code == 190 or status in (401, 403):
                        raise FacebookAuthError(f"Facebook Token Expired or Invalid: {err_msg}", code=err_code, status_code=status)

                    # Permission errors (code 200 / (#200))
                    if err_code == 200:
                        raise FacebookPermissionError(f"Missing permissions for resource: {err_msg}", code=err_code, status_code=status)

                    # Rate limit error codes (4, 17, 341, 368, 613) or HTTP 429
                    if status == 429 or err_code in (4, 17, 341, 368, 613):
                        if attempt < retry:
                            wait = min(MAX_BACKOFF_SECONDS, 1.0 * (2 ** (attempt - 1)))
                            logger.warning("[%s] Rate limit hit on %s (attempt %s/%s) - waiting %.1fs", now_ts(), url, attempt, retry, wait)
                            await asyncio.sleep(wait)
                            continue
                        raise FacebookRateLimitError(f"Meta rate limit exceeded: {err_msg}", code=err_code, status_code=status)

                    # Transient server errors (500, 502, 503, 504) -> retryable even with error body
                    if status in (500, 502, 503, 504) and attempt < retry:
                        wait = min(MAX_BACKOFF_SECONDS, 1.0 * (2 ** (attempt - 1)))
                        logger.warning("[%s] HTTP %s on %s (attempt %s/%s) - waiting %.1fs", now_ts(), status, url, attempt, retry, wait)
                        await asyncio.sleep(wait)
                        continue

                    if not (200 <= status < 300):
                        raise FacebookGraphError(f"Graph API Error ({err_code}): {err_msg}", code=err_code, status_code=status)

                # 2. Success HTTP Status
                if 200 <= status < 300:
                    return payload

                # 3. HTTP Server errors without error body (500, 502, 503, 504) -> retryable
                if status in (429, 500, 502, 503, 504) and attempt < retry:
                    wait = min(MAX_BACKOFF_SECONDS, 1.0 * (2 ** (attempt - 1)))
                    logger.warning("[%s] HTTP %s on %s (attempt %s/%s) - waiting %.1fs", now_ts(), status, url, attempt, retry, wait)
                    await asyncio.sleep(wait)
                    continue

                raise FacebookGraphError(f"HTTP {status} response from Graph API", status_code=status)

        except (FacebookAuthError, FacebookPermissionError, FacebookRateLimitError):
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            if attempt >= retry:
                logger.warning("[%s] Network failure on %s after %s attempts: %s", now_ts(), url, attempt, exc)
                raise FacebookGraphError(f"Network error after {retry} attempts: {exc}")
            wait = min(MAX_BACKOFF_SECONDS, 1.0 * (2 ** (attempt - 1)))
            logger.info("[%s] Network glitch on %s (attempt %s/%s) - retrying in %.1fs", now_ts(), url, attempt, retry, wait)
            await asyncio.sleep(wait)

    raise FacebookGraphError("Request failed after retries")


# -----------------------------------------------------------------------------
# 📄 Pages Retrieval with Cursor Pagination
# -----------------------------------------------------------------------------
async def get_pages(
    session: aiohttp.ClientSession,
    user_access_token: str,
    limit: int = 100,
    stop_checker: Optional[Callable[[], bool]] = None,
) -> List[Dict[str, str]]:
    """
    Fetches all managed Facebook pages for the account, supporting cursor pagination.
    Supports clean cancellation via stop_checker before requests and between cursor pages.
    """
    if not user_access_token:
        raise FacebookAuthError("User access token is empty or missing.")

    if stop_checker and stop_checker():
        logger.info("get_pages cancelled before initial request.")
        return []

    url = f"{FB_GRAPH}/me/accounts"
    params = {"access_token": user_access_token, "fields": "id,name,access_token", "limit": limit}

    pages: List[Dict[str, str]] = []
    seen_ids: Set[str] = set()

    data = await fetch_json(session, url, params=params)

    while True:
        items = data.get("data", []) if isinstance(data, dict) else []
        for item in items:
            pid = str(item.get("id", ""))
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                pages.append({
                    "id": pid,
                    "name": fix_arabic_display(item.get("name", "Unnamed Page")),
                    "access_token": str(item.get("access_token", user_access_token)),
                })

        if stop_checker and stop_checker():
            logger.info("get_pages cancelled between paging requests (retaining %s partial pages).", len(pages))
            break

        paging = data.get("paging", {}) if isinstance(data, dict) else {}
        next_url = paging.get("next")
        if next_url and len(pages) < 2000:
            if stop_checker and stop_checker():
                logger.info("get_pages cancelled before next cursor request (retaining %s partial pages).", len(pages))
                break
            try:
                data = await fetch_json(session, next_url, params={})
            except Exception as exc:
                logger.warning("[%s] Error while paging accounts: %s (stopping at %s pages)", now_ts(), exc, len(pages))
                break
        else:
            break

    return pages


# -----------------------------------------------------------------------------
# 💬 Conversations Pagination & Scanning
# -----------------------------------------------------------------------------
async def iterate_conversation_batches(
    session: aiohttp.ClientSession,
    page_id: str,
    page_token: str,
    limit: int = DEFAULT_PAGE_CONV_LIMIT,
    stop_checker: Optional[Callable[[], bool]] = None,
) -> AsyncGenerator[Tuple[List[Dict[str, Any]], bool, Optional[str]], None]:
    """
    Yields (conversations_batch, is_partial, error_note) iteratively.
    Gracefully handles pagination errors so partial counts are not discarded.
    Checks stop_checker between batches to halt before next network requests.
    """
    if stop_checker and stop_checker():
        yield [], True, "stopped"
        return

    url = f"{FB_GRAPH}/{page_id}/conversations"
    params = {"access_token": page_token, "fields": "id,unread_count,tags,folder", "limit": limit}

    try:
        data = await fetch_json(session, url, params=params)
    except FacebookAuthError:
        yield [], True, "auth_error"
        return
    except FacebookPermissionError:
        yield [], True, "permission_denied"
        return
    except Exception as exc:
        logger.warning("[%s] Error fetching initial conversations for page %s: %s", now_ts(), page_id, exc)
        yield [], True, str(exc)
        return

    while True:
        items = data.get("data", []) if isinstance(data, dict) else []
        paging = data.get("paging", {}) if isinstance(data, dict) else {}
        next_url = paging.get("next")

        if not next_url:
            yield items, False, None
            break

        yield items, False, None

        if stop_checker and stop_checker():
            yield [], True, "stopped"
            break

        try:
            data = await fetch_json(session, next_url, params={})
        except Exception as exc:
            logger.warning("[%s] Warning paging conversations for page %s: %s (yielding partial)", now_ts(), page_id, exc)
            yield [], True, f"paging_error:{exc}"
            break


async def process_page(
    session: aiohttp.ClientSession,
    page: Dict[str, Any],
    limit: int = DEFAULT_PAGE_CONV_LIMIT,
    stop_checker: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    """
    Processes all conversations for a single page and counts open/active conversations.
    Supports clean cancellation via stop_checker while retaining collected partial results.
    """
    page_id = str(page.get("id", ""))
    page_name = fix_arabic_display(page.get("name", "<Unnamed>"))
    page_token = page.get("access_token")

    if not page_token:
        logger.warning("[%s] Page '%s' (%s) missing page access token. Skipped.", now_ts(), page_name, page_id)
        return {
            "id": page_id,
            "name": page_name,
            "open_convs": 0,
            "total_scanned": 0,
            "status": "no_page_token",
            "note": "no_page_token",
        }

    if stop_checker and stop_checker():
        return {
            "id": page_id,
            "name": page_name,
            "open_convs": 0,
            "total_scanned": 0,
            "status": "stopped",
            "note": "stopped",
        }

    logger.info("[%s] Scanning page '%s' (%s)...", now_ts(), page_name, page_id)
    total = 0
    open_count = 0
    is_partial = False
    error_note = "ok"

    try:
        try:
            batch_gen = iterate_conversation_batches(
                session, page_id, page_token, limit=limit, stop_checker=stop_checker
            )
        except TypeError:
            batch_gen = iterate_conversation_batches(
                session, page_id, page_token, limit=limit
            )

        async for batch, partial_flag, note in batch_gen:
            if partial_flag:
                is_partial = True
                if note:
                    error_note = note
            if batch:
                for conv in batch:
                    total += 1
                    if conv_is_open(conv):
                        open_count += 1

            if stop_checker and stop_checker():
                is_partial = True
                error_note = "stopped"
                break

        if error_note in ("stopped", "cancelled") or (stop_checker and stop_checker()):
            final_status = "stopped"
            error_note = "stopped"
        elif is_partial:
            final_status = "partial"
        else:
            final_status = "ok" if error_note == "ok" else "error"

        logger.info(
            "[%s] Completed page '%s': %s scanned, %s open (status=%s)",
            now_ts(), page_name, total, open_count, final_status
        )
        return {
            "id": page_id,
            "name": page_name,
            "open_convs": open_count,
            "total_scanned": total,
            "status": final_status,
            "note": error_note,
        }
    except Exception as exc:
        logger.exception("Error processing page '%s': %s", page_name, exc)
        return {
            "id": page_id,
            "name": page_name,
            "open_convs": open_count,
            "total_scanned": total,
            "status": "error",
            "note": str(exc),
        }


# -----------------------------------------------------------------------------
# 📬 Telegram Reporting Helper
# -----------------------------------------------------------------------------
async def send_telegram_report(
    session: aiohttp.ClientSession,
    bot_token: str,
    chat_id: str,
    results: List[Dict[str, Any]],
) -> None:
    """
    Sends structured Telegram report safely with message chunking and no secret leaks.
    """
    if not bot_token or not chat_id:
        return

    total_pages = len(results)
    total_scanned_all = sum(r.get("total_scanned", 0) for r in results)
    total_open_all = sum(r.get("open_convs", 0) for r in results)

    has_stopped = any(r.get("status") in ("stopped", "cancelled") for r in results)
    title = "⏹️ **تقرير فحص محادثات صفحات فيسبوك (متوقف)**" if has_stopped else "📊 **تقرير فحص محادثات صفحات فيسبوك**"

    lines = [
        title,
        "━" * 25,
        f"📄 إجمالي الصفحات: `{total_pages}`",
        f"💬 إجمالي المحادثات المفحوصة: `{total_scanned_all}`",
        f"📬 إجمالي المحادثات المفتوحة: `{total_open_all}`",
        "━" * 25,
        "",
    ]

    for r in results:
        p_name = fix_arabic_display(r.get("name", "<Unnamed>"))
        status = r.get("status", "ok")
        scanned = r.get("total_scanned", 0)
        opened = r.get("open_convs", 0)

        if status == "ok":
            icon = "✅"
            status_desc = "مكتمل"
        elif status == "partial":
            icon = "⚠️"
            status_desc = "جزئي (توقف بسبب قيود/خطأ تصفح)"
        elif status in ("stopped", "cancelled"):
            icon = "⏹️"
            status_desc = "تم الإيقاف"
        elif status in ("auth_error", "permission_denied"):
            icon = "🔒"
            status_desc = "خطأ صلاحيات"
        else:
            icon = "❌"
            status_desc = "خطأ"

        safe_name = escape_markdown(p_name)
        lines.append(f"{icon} **{safe_name}**")
        lines.append(f"   • مفتوحة: `{opened}` | مفحوصة: `{scanned}` | الحالة: `{status_desc}`\n")

    max_len = 3500
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    chunks: List[str] = []
    curr_chunk = ""
    for line in lines:
        if len(curr_chunk) + len(line) + 2 > max_len:
            chunks.append(curr_chunk)
            curr_chunk = line + "\n"
        else:
            curr_chunk += line + "\n"
    if curr_chunk:
        chunks.append(curr_chunk)

    for chunk in chunks:
        payload = {"chat_id": str(chat_id), "text": chunk, "parse_mode": "Markdown"}
        try:
            async with session.post(url, data=payload, timeout=15) as resp:
                if not (200 <= resp.status < 300):
                    txt = await resp.text()
                    logger.warning("Telegram send failed (HTTP %s): %s", resp.status, txt[:200])
        except Exception as exc:
            logger.warning("Failed sending Telegram message chunk: %s", exc)


# -----------------------------------------------------------------------------
# 🖥️ Interactive Page Selector (CLI Mode)
# -----------------------------------------------------------------------------
def select_pages_interactive(pages: List[Dict[str, Any]], selected_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Selects target pages interactively or programmatically.
    If stdin is not a TTY (non-interactive/test runner), defaults cleanly to all pages.
    """
    if not pages:
        return []

    # Programmatic selection (e.g. from Telegram bot or arguments)
    if selected_ids is not None:
        sel_set = set(str(x).strip() for x in selected_ids)
        if "all" in sel_set:
            return pages
        return [p for p in pages if str(p.get("id")) in sel_set]

    # Non-interactive terminal fallback (prevents hanging in tests or background jobs)
    if not sys.stdin.isatty():
        return pages

    print("\n" + "=" * 60)
    print("📄 الصفحات المتاحة في الحساب:")
    print("=" * 60)
    for idx, page in enumerate(pages, 1):
        p_name = fix_arabic_display(page.get("name", "<Unnamed>"))
        print(f" {idx}. {p_name} (ID: {page.get('id')})")
    print("=" * 60)
    print("الخيارات: رقم صفحة، عدة أرقام مفصولة بفاصلة (1,2)، 'all' للكل، 'quit' للخروج.")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("🔍 اختر الصفحات: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n❌ تم الإلغاء.")
            return []

        if not user_input or user_input.lower() == "quit":
            return []
        if user_input.lower() == "all":
            return pages

        try:
            indices = [int(x.strip()) - 1 for x in user_input.split(",") if x.strip()]
            if any(i < 0 or i >= len(pages) for i in indices):
                print("❌ رقم غير صالح! يرجى إدخال رقم من القائمة.")
                continue
            return [pages[i] for i in indices]
        except ValueError:
            print("❌ إدخال غير صالح! استخدم أرقامًا مفصولة بفواصل (مثال: 1,3,4)")


# -----------------------------------------------------------------------------
# 🚀 High-Level Pipeline & Event Loop Protection
# -----------------------------------------------------------------------------
async def scan_pages_conversations(
    fb_user_token: str,
    selected_page_ids: Optional[List[str]] = None,
    tg_bot_token: Optional[str] = None,
    tg_chat_id: Optional[str] = None,
    concurrency: int = DEFAULT_CONCURRENCY,
    batch_size: int = DEFAULT_BATCH_SIZE,
    http_timeout: float = DEFAULT_HTTP_TIMEOUT,
    stop_checker: Optional[Callable[[], bool]] = None,
) -> List[Dict[str, Any]]:
    """
    Main asynchronous pipeline for scanning page conversations and generating reports.
    Supports graceful cancellation between page batches and conversation fetches.
    """
    if not fb_user_token:
        raise FacebookAuthError("Facebook User Access Token is required.")

    if stop_checker and stop_checker():
        logger.info("Scan cancelled before initialization.")
        return []

    connector = aiohttp.TCPConnector(limit_per_host=concurrency * 2)
    timeout = aiohttp.ClientTimeout(total=http_timeout * 3)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        try:
            all_pages = await get_pages(session, fb_user_token, stop_checker=stop_checker)
        except TypeError:
            all_pages = await get_pages(session, fb_user_token)
        if not all_pages:
            logger.info("No pages found for the account.")
            return []

        if stop_checker and stop_checker():
            logger.info("Scan cancelled after fetching accounts.")
            return []

        chosen_pages = select_pages_interactive(all_pages, selected_ids=selected_page_ids)
        if not chosen_pages:
            logger.info("No pages selected.")
            return []

        results: List[Dict[str, Any]] = []
        sem = asyncio.Semaphore(max(1, concurrency))

        async def worker(p: Dict[str, Any]) -> Dict[str, Any]:
            async with sem:
                return await process_page(session, p, stop_checker=stop_checker)

        for batch in chunked(chosen_pages, max(1, batch_size)):
            if stop_checker and stop_checker():
                logger.info("Scan cancelled before next batch of pages.")
                break
            tasks = [asyncio.create_task(worker(p)) for p in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=False)
            results.extend(batch_results)
            if stop_checker and stop_checker():
                logger.info("Scan cancelled after processing page batch.")
                break
            await asyncio.sleep(0.2)

        # Telegram reporting if credentials provided
        if tg_bot_token and tg_chat_id:
            await send_telegram_report(session, tg_bot_token, tg_chat_id, results)

        return results


def run_async(coro: Any) -> Any:
    """
    Executes an async coroutine safely across all contexts.
    If an event loop is already running (e.g. within bot polling or async framework),
    it executes cleanly in a separate worker thread without throwing
    'RuntimeError: This event loop is already running'.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


def main() -> None:
    """
    CLI execution entry point. Loads secrets safely from environment.
    """
    fb_token = os.environ.get("FB_USER_ACCESS_TOKEN", "").strip()
    tg_bot = os.environ.get("TELEGRAM_BOT_TOKEN", CFG_TG_TOKEN).strip()
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID", str(CFG_OWNER_ID)).strip()

    if not fb_token:
        # Check if argument or prompt available
        if len(sys.argv) > 1 and sys.argv[1].startswith("EAA"):
            fb_token = sys.argv[1].strip()
        elif sys.stdin.isatty():
            try:
                fb_token = input("🔑 أدخل Facebook User Access Token: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n❌ تم الإلغاء.")
                sys.exit(1)

    if not fb_token:
        print("❌ خطأ: يرجى تمرير FB_USER_ACCESS_TOKEN في المتغيرات البيئية أو كمعامل للسكربت.")
        print("مثال: export FB_USER_ACCESS_TOKEN='EAAB...' أو $env:FB_USER_ACCESS_TOKEN='EAAB...'")
        sys.exit(1)

    print(f"\n🚀 بدء فحص محادثات الصفحات (Token: {mask_token(fb_token)})...")
    try:
        results = run_async(scan_pages_conversations(
            fb_user_token=fb_token,
            tg_bot_token=tg_bot,
            tg_chat_id=tg_chat,
        ))

        print("\n" + "=" * 60)
        print("📊 النتائج الإجمالية:")
        print("=" * 60)
        for r in results:
            p_name = fix_arabic_display(r.get("name", "<Unnamed>"))
            print(f"• {p_name}: {r.get('open_convs')} محادثة مفتوحة (إجمالي المفحوص: {r.get('total_scanned')}) [{r.get('status')}]")
        print("=" * 60 + "\n")

    except FacebookAuthError as exc:
        print(f"\n❌ خطأ مصادقة: التوكن منتهي الصلاحية أو غير صالح ({exc})")
        sys.exit(2)
    except Exception as exc:
        logger.exception("Fatal error during execution: %s", exc)
        sys.exit(3)


if __name__ == "__main__":
    main()
