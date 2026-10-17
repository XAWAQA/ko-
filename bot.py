"""
Legacy entry-point wrapper.
Directs execution to the modular app.py implementation.
Original unrefactored bot is preserved in legacy/bot.py.
"""

from app import main

if __name__ == "__main__":
    main()
