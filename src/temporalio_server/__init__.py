# This file makes src/temporalio_server a Python package

import logging
import platform
import socket
import subprocess
import time
from importlib import resources
from pathlib import Path
from typing import List, Optional, Sequence

log = logging.getLogger(__name__)


# Moved from main.py
def get_binary_path() -> Path:
    """Finds the path to the bundled temporal binary."""
    binary_name = "temporal.exe" if platform.system() == "Windows" else "temporal"
    try:
        package_files = resources.files("temporalio_server")
        binary_traversable = package_files / "bin" / binary_name
        with resources.as_file(binary_traversable) as binary_path:
            if not binary_path.is_file():
                raise FileNotFoundError(
                    f"Binary path resolved by as_file is not a file: {binary_path}"
                )
            log.debug(f"Found binary path: {binary_path}")
            return binary_path
    except (ModuleNotFoundError, FileNotFoundError, NotADirectoryError, TypeError) as e:
        log.error(
            f"Could not find or access bundled temporal binary '{binary_name}'. Build process may have failed. Details: {e}",
            exc_info=True,
        )
        raise FileNotFoundError("Temporal CLI binary not found.") from e
    except Exception as e:
        log.error(f"Unexpected error finding binary path: {e}", exc_info=True)
        raise


class DevServer:
    """Manages a Temporal development server subprocess using a context manager."""

    def __init__(
        self,
        *,  # Force keyword arguments
        port: int = 7233,
        ui_port: int = 8233,
        metrics_port: Optional[int] = 0,  # Default to dynamic
        db_filename: Optional[str] = None,
        namespace: Sequence[str] = ("default",),
        ip: str = "127.0.0.1",
        log_level: str = "warn",  # Keep default less verbose
        extra_args: Sequence[str] = (),
    ) -> None:
        """Initialize the DevServer manager.

        Args:
            port: Port for the frontend gRPC service.
            ui_port: Port for the Web UI.
            metrics_port: Port for metrics endpoint. Defaults to dynamic.
            db_filename: File path for the SQLite DB. Defaults to in-memory.
            namespace: List of namespaces to create. Defaults to ['default'].
            ip: IP address to bind services to.
            log_level: Log level for the server process (debug, info, warn, error).
            extra_args: List of additional string arguments to pass to `temporal server start-dev`.
        """
        self.port = port
        self.ui_port = ui_port
        self.metrics_port = metrics_port
        self.db_filename = db_filename
        self.namespace = namespace
        self.ip = ip
        self.log_level = log_level
        self.extra_args = extra_args
        self.process: Optional[subprocess.Popen] = None

    @property
    def target(self) -> str:
        """Target string for Temporal Client connection."""
        return f"{self.ip}:{self.port}"

    def __enter__(self) -> "DevServer":
        """Start the server process and wait for it to be ready."""
        binary_path = get_binary_path()
        args: List[str] = [
            str(binary_path),
            "server",
            "start-dev",
            "--ip",
            self.ip,
            "--port",
            str(self.port),
            "--ui-port",
            str(self.ui_port),
            "--log-level",
            self.log_level,
        ]
        if self.db_filename:
            args.extend(("--db-filename", self.db_filename))
        if self.metrics_port is not None:
            # Metrics port 0 means dynamic, but we need to pass the flag
            # For None, we don't pass the flag at all.
            args.extend(("--metrics-port", str(self.metrics_port)))

        for ns in self.namespace:
            args.extend(("--namespace", ns))

        args.extend(self.extra_args)

        log.info(f"Starting Temporal server: {' '.join(args)}")
        # Start process - capture stderr to check for readiness/errors if needed
        self.process = subprocess.Popen(args, stderr=subprocess.PIPE)

        # Wait for server readiness
        try:
            self._wait_for_server_ready()
        except Exception:
            log.error("Failed to start Temporal server. Terminating process.")
            self._terminate_process()
            raise  # Re-raise the exception

        log.info(f"Temporal server ready on {self.target}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Terminate the server process."""
        log.info("Shutting down Temporal server...")
        self._terminate_process()
        log.info("Temporal server shut down.")

    def _terminate_process(self) -> None:
        """Send signals to terminate the managed process."""
        if not self.process or self.process.poll() is not None:
            log.debug("Server process already terminated or not started.")
            return

        log.debug("Sending SIGINT/terminate() to temporal process...")
        self.process.terminate()  # SIGTERM on POSIX, TerminateProcess on Win
        try:
            exit_code = self.process.wait(timeout=10)
            log.debug(f"Server process terminated gracefully with code {exit_code}.")
        except subprocess.TimeoutExpired:
            log.warning(
                "Server process did not exit gracefully after 10s, sending SIGKILL/kill()."
            )
            self.process.kill()
            try:
                exit_code = self.process.wait(timeout=5)  # Wait for kill confirmation
                log.debug(f"Server process killed, exit code {exit_code}.")
            except subprocess.TimeoutExpired:
                log.error("Server process did not terminate even after kill.")
        except Exception as e:
            log.error(f"Error during server shutdown: {e}", exc_info=True)
        finally:
            self.process = None  # Ensure process is marked as None

    def _wait_for_server_ready(self, timeout: float = 30.0) -> None:
        """Wait until the gRPC port is open or timeout expires."""
        if not self.process:
            raise RuntimeError("Server process not started.")

        start_time = time.monotonic()
        while True:
            # Check if process exited prematurely
            if self.process.poll() is not None:
                stderr_output = ""
                if self.process.stderr:
                    try:
                        stderr_output = self.process.stderr.read().decode(
                            errors="replace"
                        )
                    except Exception:
                        pass  # Ignore errors reading stderr
                raise RuntimeError(
                    f"Server process exited prematurely with code {self.process.returncode}. Stderr: {stderr_output}"
                )

            # Check if port is open
            try:
                with socket.create_connection(
                    (self.ip, self.port), timeout=0.1
                ) as sock:
                    log.debug(
                        f"Successfully connected to {self.target}, server is ready."
                    )
                    return  # Port is open
            except (socket.timeout, ConnectionRefusedError, OSError):
                pass  # Port not yet open

            # Check timeout
            if time.monotonic() - start_time >= timeout:
                raise TimeoutError(
                    f"Server did not become ready on {self.target} within {timeout} seconds."
                )

            # Wait briefly before retrying
            time.sleep(0.2)
