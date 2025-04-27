import logging
import subprocess
import sys

# Import the helper from the __init__ module
from . import get_binary_path

# Set up basic logging
logging.basicConfig(
    level=logging.WARN, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)


def run():
    """Entry point for the temporal-server script."""
    binary_path_str = "<not found>"
    try:
        binary_path = get_binary_path()
        binary_path_str = str(binary_path)

        # Prepend 'server' and default log level
        args = [binary_path_str] + ["server", "--log-level", "error"] + sys.argv[1:]

        log.info(f"Executing: {' '.join(args)}")
        process = subprocess.Popen(args)

        exit_code = None
        while exit_code is None:
            try:
                exit_code = process.wait()
            except KeyboardInterrupt:
                log.info("KeyboardInterrupt caught; killing temporal process...")
                process.kill()
                exit_code = process.wait()
                log.info(f"temporal process killed, exit code {exit_code}.")
                break

        log.info(f"temporal process exited with code {exit_code}")
        sys.exit(exit_code)

    except FileNotFoundError:
        log.error(f"Error: Failed to execute binary at '{binary_path_str}'.")
        sys.exit(1)
    except Exception as e:
        log.error(f"Error executing temporal binary: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()
