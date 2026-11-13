import os

# Tests must run without a database.
os.environ["CHECK_DB_ON_STARTUP"] = "false"
