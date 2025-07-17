import logging
import sys


def info(msg, *args):
    logging.getLogger(_getCallerName(1)).info(msg, *args)


def debug(msg, *args):
    logging.getLogger(_getCallerName(1)).debug(msg, *args)


def warning(msg, *args):
    logging.getLogger(_getCallerName(1)).warning(msg, *args)


def error(msg, *args):
    logging.getLogger(_getCallerName(1)).error(msg, *args)


def critical(msg, *args):
    logging.getLogger(_getCallerName(1)).critical(msg, *args)


def _getCallerName(depth: int = 1) -> str | None:

    frame = sys._getframe(depth + 1)
    return frame.f_globals.get("__name__")
