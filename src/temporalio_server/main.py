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
    """Entry point for the temporalio-server script."""
    # Define binary_path outside try block for potential use in except block
    binary_path_str = "<not found>"  # Default value if get_binary_path fails
    try:
        # Use the imported function to find the binary
        binary_path = get_binary_path()
        binary_path_str = str(binary_path)  # Convert Path to string for subprocess

        # Pass all command-line arguments received by this script
        # directly to the temporal binary, prepending 'server'
        # Add --log-level error to suppress WARN messages from the server itself
        args = [binary_path_str] + ["server", "--log-level", "error"] + sys.argv[1:]

        log.info(f"Executing: {' '.join(args)}")

        # Execute the binary
        process = subprocess.Popen(args)

        # Wait for the process to complete, ignoring KeyboardInterrupt
        exit_code = None
        while exit_code is None:
            try:
                exit_code = process.wait()  # Wait indefinitely until child exits
            except KeyboardInterrupt:
                # OS sent SIGINT to child too. Instead of waiting for graceful
                # shutdown, immediately kill the child process to prevent
                # further logging during its shutdown sequence.
                log.info("KeyboardInterrupt caught; killing temporal process...")
                process.kill()  # Send SIGKILL (or equivalent)
                exit_code = process.wait()  # Collect exit code after kill
                log.info(f"temporal process killed, exit code {exit_code}.")
                # Break the loop as the process is now guaranteed to be terminated
                break

        log.info(f"temporal process exited with code {exit_code}")
        sys.exit(exit_code)

    except FileNotFoundError:
        # Use binary_path_str which holds the path string if get_binary_path succeeded
        log.error(
            f"Error: Failed to execute binary at '{binary_path_str}'. Ensure it exists and is executable.",
            exc_info=True,
        )
        sys.exit(1)
    except Exception as e:
        log.error(f"Error executing temporal binary: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()
