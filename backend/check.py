"""Run all backend checks in order; stop at the first failure. Usage: uv run python check.py"""

import subprocess
import sys

STEPS = [
    ("ruff check", ["ruff", "check", "."]),
    ("ruff format --check", ["ruff", "format", "--check", "."]),
    ("mypy", ["mypy", "app", "tests"]),
    ("pytest", ["pytest"]),
]


def main() -> int:
    for name, args in STEPS:
        print(f"==> {name}", flush=True)
        code = subprocess.run([sys.executable, "-m", *args]).returncode
        if code != 0:
            print(f"FAILED: {name} (exit code {code})", flush=True)
            return code
    print("All backend checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
