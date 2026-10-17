"""
Main application entry point for the Telegram Bot.
Validates environment configuration, configures services, and runs polling.
"""

import os
import signal
import sys
import time
import telebot

from access.manager import access_manager
from bot.handlers import register_handlers
from bot.state import state_manager
from config import (
    CPU_CORES,
    MAX_RAM_MB,
    TELEGRAM_BOT_TOKEN,
    validate_config,
)
from facebook.client import FacebookClient
from utils.logging import logger
from utils.system import has_uvloop, try_install_uvloop
from workers.engine import WorkerEngine


def create_app() -> telebot.TeleBot:
    """Creates and wires all application components."""
    # 1. Validate required environment configuration
    validate_config()

    # 2. Try activating uvloop if available
    try_install_uvloop()

    # 3. Ensure required data directories exist
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(project_root, "data"), exist_ok=True)
    os.makedirs(os.path.join(project_root, "data", "ff_checker"), exist_ok=True)

    # 4. Initialize bot and service components
    bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=False)
    fb_client = FacebookClient()
    engine = WorkerEngine(bot=bot, fb_client=fb_client, state=state_manager)

    # 5. Register handlers with access manager
    register_handlers(
        bot=bot,
        engine=engine,
        state=state_manager,
        fb_client=fb_client,
        access_mgr=access_manager,
    )

    return bot


def graceful_shutdown(signum, frame, bot: telebot.TeleBot) -> None:
    """Handles graceful termination on SIGINT or SIGTERM."""
    logger.info("Graceful shutdown signal received. Terminating running tasks...")
    # Stop polling
    try:
        bot.stop_polling()
    except Exception:
        pass
    sys.exit(0)


def main() -> None:
    """Main runner function."""
    bot = create_app()

    # Setup signal traps
    signal.signal(signal.SIGINT, lambda s, f: graceful_shutdown(s, f, bot))
    signal.signal(signal.SIGTERM, lambda s, f: graceful_shutdown(s, f, bot))

    loop_engine = "uvloop" if has_uvloop() else "asyncio"
    print("=" * 50)
    print("🤖 Cyberpunk Bot v5.0 - MODULAR ENGINE")
    print(f"⚡ Loop: {loop_engine}")
    print(f"🖥️  {CPU_CORES} vCPU | {MAX_RAM_MB}MB RAM")
    print(f"🔗 {CPU_CORES} parallel HTTP clients")
    print("=" * 50)

    while True:
        try:
            bot.infinity_polling(
                timeout=60,
                long_polling_timeout=60,
                allowed_updates=["message", "callback_query"],
            )
        except KeyboardInterrupt:
            graceful_shutdown(None, None, bot)
        except Exception as exc:
            logger.warning("Polling error: %s | Restarting in 3s...", exc)
            time.sleep(3)


if __name__ == "__main__":
    main()
