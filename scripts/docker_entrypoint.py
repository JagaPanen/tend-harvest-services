"""Docker entrypoint: wait for Postgres, seed, run uvicorn."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time


def wait_for_postgres(host: str, port: int, attempts: int = 60) -> None:
    print(f"Waiting for Postgres at {host}:{port}...", flush=True)
    for i in range(attempts):
        try:
            with socket.create_connection((host, port), timeout=2):
                print("Postgres is ready.", flush=True)
                return
        except OSError:
            time.sleep(1)
    raise SystemExit(f"Postgres did not become ready after {attempts}s")


def main() -> None:
    host = os.environ.get("DATABASE_HOST", "postgres")
    port = int(os.environ.get("DATABASE_PORT", "5432"))
    wait_for_postgres(host, port)

    print("Seeding demo org / catalog / template scenario...", flush=True)
    subprocess.check_call([sys.executable, "-m", "app.seed"])

    print("Starting uvicorn on :8009", flush=True)
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8009",
            "--proxy-headers",
        ],
    )


if __name__ == "__main__":
    main()
