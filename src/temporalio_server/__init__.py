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


def get_binary_path() -> Path:
    """Find the path to the bundled temporal binary."""
    binary_name = "temporal.exe" if platform.system() == "Windows" else "temporal"
    try:
        package_files = resources.files("temporalio_server")
        binary_traversable = package_files / "bin" / binary_name
        with resources.as_file(binary_traversable) as binary_path:
            if not binary_path.is_file():
                raise FileNotFoundError(f"Binary not found at path: {binary_path}")
            return binary_path
    except (ModuleNotFoundError, FileNotFoundError, NotADirectoryError, TypeError) as e:
        log.error(
            f"Could not find bundled temporal binary '{binary_name}'. Build failed? {e}"
        )
        raise FileNotFoundError("Temporal CLI binary not found.") from e
    except Exception as e:
        log.error(f"Error finding binary path: {e}")
        raise


class DevServer:
    """Manages a Temporal development server subprocess via async context manager."""

    def __init__(
        self,
        *,  # Force keyword args
        port: int = 7233,
        ui_port: int = 8233,
        metrics_port: Optional[int] = 0,
        db_filename: Optional[str] = None,
        namespace: Sequence[str] = ("default",),
        ip: str = "127.0.0.1",
        log_level: str = "warn",
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
        return f"{self.ip}:{self.port}"

    async def __aenter__(self) -> "DevServer":
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
            args.extend(("--metrics-port", str(self.metrics_port)))
        for ns in self.namespace:
            args.extend(("--namespace", ns))
        args.extend(self.extra_args)

        log.info(f"Starting Temporal server: {' '.join(args)}")
        try:
            self.process = await asyncio.create_subprocess_exec(
                args[0],
                *args[1:],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            log.debug(f"Server process started [PID: {self.process.pid}]")
        except Exception as e:
            raise RuntimeError("Failed to start Temporal server process") from e

        try:
            await self._wait_for_server_ready()
        except Exception:
            log.error("Server failed to start. Terminating process.")
            await self._terminate_process()
            raise

        log.info(f"Temporal server ready on {self.target}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        log.info("Shutting down Temporal server...")
        await self._terminate_process()
        log.info("Temporal server shut down.")

    async def _terminate_process(self) -> None:
        if not self.process or self.process.returncode is not None:
            return

        pid = self.process.pid  # Store pid in case self.process becomes None
        log.debug(f"Sending SIGTERM to temporal process [PID: {pid}]...")
        try:
            self.process.terminate()
            await asyncio.wait_for(self.process.wait(), timeout=10)
            log.debug(
                f"Server process [PID: {pid}] terminated gracefully [Code: {self.process.returncode}]."
            )
        except asyncio.TimeoutError:
            log.warning(
                f"Server process [PID: {pid}] did not exit gracefully after 10s. Sending SIGKILL."
            )
            try:
                self.process.kill()
                await asyncio.wait_for(self.process.wait(), timeout=5)
                log.debug(
                    f"Server process [PID: {pid}] killed [Code: {self.process.returncode}]."
                )
            except asyncio.TimeoutError:
                log.error(
                    f"Server process [PID: {pid}] did not terminate after SIGKILL."
                )
            except Exception as inner_e:
                log.error(f"Error waiting for killed process [PID: {pid}]: {inner_e}")
        except Exception as e:
            log.error(f"Error terminating server process [PID: {pid}]: {e}")
        finally:
            self.process = None

    async def _wait_for_server_ready(self, timeout: float = 30.0) -> None:
        if not self.process or not self.process.stderr:
            raise RuntimeError("Server process/stderr not available.")

        start_time = time.monotonic()
        stderr_task = asyncio.create_task(self._read_stderr(self.process.stderr))
        stderr_output = ""

        try:
            while True:
                if self.process.returncode is not None:
                    stderr_output = await stderr_task
                    raise RuntimeError(
                        f"Server process exited prematurely [Code: {self.process.returncode}]. Stderr: {stderr_output}"
                    )

                try:
                    _, writer = await asyncio.open_connection(self.ip, self.port)
                    writer.close()
                    await writer.wait_closed()
                    log.debug(
                        f"Successfully connected to {self.target}. Server is ready."
                    )
                    return
                except (ConnectionRefusedError, OSError):
                    pass  # Wait and retry

                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    stderr_output = await stderr_task
                    raise TimeoutError(
                        f"Server did not become ready on {self.target} within {timeout:.1f}s. Stderr: {stderr_output}"
                    )

                await asyncio.sleep(0.2)
        finally:
            if not stderr_task.done():
                stderr_task.cancel()
                try:
                    await stderr_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    log.warning(f"Error awaiting cancelled stderr task: {e}")

    async def _read_stderr(self, stream: asyncio.StreamReader) -> str:
        lines = []
        try:
            while True:
                try:
                    line_bytes = await asyncio.wait_for(stream.readline(), timeout=1.0)
                except asyncio.TimeoutError:
                    if self.process and self.process.returncode is None:
                        continue
                    break  # Process likely exited

                if not line_bytes:
                    break
                line = line_bytes.decode(errors="replace").strip()
                lines.append(line)
                log.debug(f"Server stderr: {line}")
        except asyncio.CancelledError:
            log.debug("Stderr reading task cancelled.")
            raise
        except Exception as e:
            log.warning(f"Error reading server stderr: {e}")
        return "\n".join(lines)
