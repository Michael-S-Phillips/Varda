import os

# Run Qt headless for tests in this directory.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
