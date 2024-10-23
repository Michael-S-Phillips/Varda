import time

DEBUG = True

class Profiler:
    DISABLE = False

    def __init__(self):
        self.timeStarted = time.perf_counter()

    def __call__(self, *args, **kwargs):
        if self.DISABLE:
            return
        time_elapsed = (time.perf_counter() - self.timeStarted) * 1000
        if len(args) > 0:
            print(f"{args[0]}: {time_elapsed: 0.4f} ms")
        else:
            print(f"Time elapsed: {time_elapsed: 0.4f} ms")
        self.timeStarted = time.perf_counter()
