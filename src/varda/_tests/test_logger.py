from varda._tests.test_logger_helper import testLogger


def testLoggerWrapper():
    testLogger()


if __name__ == "__main__":
    from varda.app.bootstrap import initVarda

    initVarda(startGui=False)


def testLogger():
    # just a lil speed test. on my computer, each

    numLoops = 10000
    timeitWrapper(lambda: logger.info("NEW FASHIONED WAY"), numLoops)
    logger.info("FINAL NEW FASHIONED WAY")

    newLogger = logging.getLogger("varda._test_logger_helper")

    timeitWrapper(lambda: newLogger.info("OLD FASHIONED WAY"), numLoops)


def timeitWrapper(func, number=10000):
    import timeit

    time_taken = timeit.timeit(func, number=number)
    time_microseconds = time_taken * 1_000_000
    time_per_loop_microseconds = time_microseconds / number
    print(
        f"{number} loops, total time: {time_microseconds:.2f} µs, time per loop: {time_per_loop_microseconds:.2f} µs"
    )
