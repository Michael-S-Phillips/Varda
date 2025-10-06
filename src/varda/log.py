import logging
import sys


def info(msg, *args, **kwargs):
    logging.getLogger(_getCallerName()).info(msg, *args, **kwargs)


def debug(msg, *args, **kwargs):
    logging.getLogger(_getCallerName()).debug(msg, *args, **kwargs)


def warning(msg, *args, **kwargs):
    logging.getLogger(_getCallerName()).warning(msg, *args, **kwargs)


def error(msg, *args, **kwargs):
    logging.getLogger(_getCallerName()).error(msg, *args, **kwargs)


def critical(msg, *args, **kwargs):
    logging.getLogger(_getCallerName()).critical(msg, *args, **kwargs)


def _getCallerName(depth: int = 1) -> str | None:

    frame = sys._getframe(depth + 1)
    return frame.f_globals.get("__name__")
