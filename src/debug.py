import time

DEBUG = True


class Profiler:
    """
    A simple profiler to measure the time elapsed between two points in the code.

    Usage:
        profiler = Profiler()
        # Code to be profiled
        profiler("Part 1 elapsed") # Output - Part 1 time elapsed: 0.1234 ms
        # More code to be profiled
        profiler("Part 2 time elapsed") # Output - Part 2 time elapsed: 0.1234 ms
    """
    DISABLE = False  # Set this flag to True to disable the profiler

    def __init__(self):
        """
        Initialize the profiler with the current time.
        """
        self.timeStarted = time.perf_counter()

    def __call__(self, *args):
        """
        Measure and print the time elapsed since the last call or initialization.

        If the DISABLE flag is set to True, the function will return without doing
        anything.

        @param:
            *args: Optional positional arguments. If provided, the first argument
            will be used as the message prefix.
        """
        if self.DISABLE:
            return
        time_elapsed = (time.perf_counter() - self.timeStarted) * 1000
        if len(args) > 0:
            print(f"{args[0]}: {time_elapsed: 0.4f} ms")
        else:
            print(f"Time elapsed: {time_elapsed: 0.4f} ms")
        self.timeStarted = time.perf_counter()
