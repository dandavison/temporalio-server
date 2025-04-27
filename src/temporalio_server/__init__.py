# This file makes src/temporalio_server a Python package

import asyncio
import logging
import platform
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
    """Manages a Temporal development server subprocess using an async context manager."""

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
        self.process: Optional[asyncio.subprocess.Process] = None

    @property
    def target(self) -> str:
        """Target string for Temporal Client connection."""
        return f"{self.ip}:{self.port}"

    async def __aenter__(self) -> "DevServer":
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
        # Use asyncio.create_subprocess_exec
        try:
            self.process = await asyncio.create_subprocess_exec(
                args[0],  # Program path
                *args[1:],  # Arguments
                stdout=subprocess.PIPE,  # Capture stdout for potential debugging
                stderr=subprocess.PIPE,  # Capture stderr for readiness/errors
            )
            log.debug(f"Server process started with PID: {self.process.pid}")
        except Exception as e:
            log.error(f"Failed to create server subprocess: {e}", exc_info=True)
            raise RuntimeError("Failed to start Temporal server process") from e

        # Wait for server readiness
        try:
            await self._wait_for_server_ready()
        except Exception:
            log.error("Failed to start Temporal server. Terminating process.")
            await self._terminate_process()
            raise

        log.info(f"Temporal server ready on {self.target}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Terminate the server process."""
        log.info("Shutting down Temporal server...")
        await self._terminate_process()
        log.info("Temporal server shut down.")

    async def _terminate_process(self) -> None:
        """Send signals to terminate the managed asyncio process."""
        if not self.process or self.process.returncode is not None:
            log.debug("Server process already terminated or not started.")
            return

        log.debug(f"Sending SIGTERM to temporal process {self.process.pid}...")
        try:
            self.process.terminate()
            await asyncio.wait_for(self.process.wait(), timeout=10)
            log.debug(
                f"Server process {self.process.pid} terminated gracefully with code {self.process.returncode}."
            )
        except asyncio.TimeoutError:
            log.warning(
                f"Server process {self.process.pid} did not exit gracefully after 10s, sending SIGKILL."
            )
            try:
                self.process.kill()
                # Wait briefly for kill to register
                await asyncio.wait_for(self.process.wait(), timeout=5)
                log.debug(
                    f"Server process {self.process.pid} killed, exit code {self.process.returncode}."
                )
            except asyncio.TimeoutError:
                log.error(
                    f"Server process {self.process.pid} did not terminate even after kill."
                )
            except Exception as inner_e:
                log.error(f"Error waiting for killed process: {inner_e}", exc_info=True)
        except Exception as e:
            # Catch potential errors like ProcessLookupError if already dead
            log.error(
                f"Error terminating server process {self.process.pid}: {e}",
                exc_info=True,
            )
        finally:
            self.process = None

    async def _wait_for_server_ready(self, timeout: float = 30.0) -> None:
        """Wait until the gRPC port is open or timeout expires."""
        if not self.process or not self.process.stderr:
            raise RuntimeError("Server process or stderr not available.")

        start_time = time.monotonic()
        # Task to concurrently read stderr
        stderr_task = asyncio.create_task(self._read_stderr(self.process.stderr))

        try:
            while True:
                # Check if process exited prematurely
                if self.process.returncode is not None:
                    stderr_output = await stderr_task  # Get collected stderr
                    raise RuntimeError(
                        f"Server process exited prematurely with code {self.process.returncode}. Stderr: {stderr_output}"
                    )

                # Check if port is open
                try:
                    reader, writer = await asyncio.open_connection(self.ip, self.port)
                    writer.close()
                    await writer.wait_closed()
                    log.debug(
                        f"Successfully connected to {self.target}, server is ready."
                    )
                    return  # Port is open
                except (ConnectionRefusedError, OSError):
                    pass  # Port not yet open

                # Check timeout
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    stderr_output = await stderr_task
                    raise TimeoutError(
                        f"Server did not become ready on {self.target} within {timeout} seconds. Stderr: {stderr_output}"
                    )

                # Wait briefly before retrying
                await asyncio.sleep(0.2)
        finally:
            # Ensure stderr task is cancelled and awaited
            if not stderr_task.done():
                stderr_task.cancel()
                try:
                    await stderr_task
                except asyncio.CancelledError:
                    pass  # Expected
                except Exception as e:
                    log.warning(f"Error awaiting cancelled stderr task: {e}")

    async def _read_stderr(self, stream: asyncio.StreamReader) -> str:
        """Read stderr stream asynchronously."""
        lines = []
        try:
            while True:
                # Add a timeout to readline to prevent hanging if process closes stderr unexpectedly
                try:
                    line = await asyncio.wait_for(stream.readline(), timeout=1.0)
                except asyncio.TimeoutError:
                    # If timeout occurs, check if process is still running before assuming EOF
                    if self.process and self.process.returncode is None:
                        continue
                    else:
                        log.debug("Stderr readline timeout and process exited.")
                        break  # Process likely exited

                if not line:
                    log.debug("EOF reached on stderr stream.")
                    break
                decoded_line = line.decode(errors="replace").strip()
                lines.append(decoded_line)
                log.debug(f"Server stderr: {decoded_line}")
        except asyncio.CancelledError:
            log.debug("Stderr reading task cancelled.")
            raise  # Re-raise cancellation
        except Exception as e:
            log.warning(f"Error reading server stderr: {e}", exc_info=True)
        return "\n".join(lines)
