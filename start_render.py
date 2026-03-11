import os
import subprocess
import sys


VALID_BOOL_STRINGS = {"", "0", "1", "f", "false", "n", "no", "off", "on", "t", "true", "y", "yes"}


def main() -> int:
    port = os.environ.get("PORT", "8000")
    env = os.environ.copy()

    debug_value = str(env.get("DEBUG", "")).strip().lower()
    if debug_value not in VALID_BOOL_STRINGS:
        env["DEBUG"] = "false"

    cmd = [
        sys.executable,
        "-m",
        "chainlit",
        "run",
        "ui.py",
        "--headless",
        "--host",
        "0.0.0.0",
        "--port",
        port,
    ]

    completed = subprocess.run(cmd, env=env, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
