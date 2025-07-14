import logging
import inspect
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
    # return inspect.getmodule(inspect.currentframe().f_back).__name__
    # frame = inspect.currentframe()
    # if not frame:
    #     return default
    #
    # # Go back up the stack to the caller (or caller's caller, etc.)
    # # (add 1 to depth to account for this function itself)
    # for _ in range(depth + 1):
    #     if not (frame := frame.f_back):
    #         return default
    #
    # if module := inspect.getmodule(frame):
    #     return module.__name__
    #
    # return default
