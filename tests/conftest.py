# tests/conftest.py
import os

# Set the offscreen mode globally for all tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"
