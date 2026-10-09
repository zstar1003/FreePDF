"""Start Windows frozen diagnostics before dependency runtime hooks run."""

import sys

if getattr(sys, "frozen", False) and "--multiprocessing-fork" not in sys.argv:
    from utils.diagnostics import get_logger, initialize_logging

    # A windowed application may inherit a cp1252 console from a launcher.
    # LogStream preserves Unicode in the UTF-8 log and tolerates console errors.
    initialize_logging(capture_console=True)
    get_logger("startup").info("dependency runtime hooks starting")
