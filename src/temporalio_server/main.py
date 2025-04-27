import logging
import platform
import subprocess
import sys
from importlib import resources  # More robust way to find package data
from pathlib import Path

# Set up basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)


def get_binary_path() -> Path:
    """Finds the path to the bundled temporal binary."""
    binary_name = "temporal.exe" if platform.system() == "Windows" else "temporal"
    try:
        # Use importlib.resources to reliably find files within the package
        # This requires Python 3.9+ and the directory to be a package (have __init__.py)
        # It searches relative to the 'temporalio_server' package location.
        # We need to navigate to the 'bin' directory *within* the package.

        # For Python 3.9+, resources.files gives a Traversable
        package_files = resources.files("temporalio_server")
        binary_traversable = package_files / "bin" / binary_name

        # Use as_file() to get a guaranteed filesystem path context manager
        with resources.as_file(binary_traversable) as binary_path:
            if not binary_path.is_file():
                raise FileNotFoundError(
                    f"Binary path resolved by as_file is not a file: {binary_path}"
                )

            log.info(f"Found binary path: {binary_path}")
            # Return the Path object obtained from the context manager
            return binary_path

    except (
        ModuleNotFoundError,
        FileNotFoundError,
        NotADirectoryError,
        TypeError,
    ) as e:  # Catch potential errors
        log.error(
            f"Error: Could not find or access the bundled temporal binary '{binary_name}'. Package structure issue or missing binary? Details: {e}",
            exc_info=True,
        )
        sys.exit(1)
    except Exception as e:
        log.error(f"Unexpected error finding binary path: {e}", exc_info=True)
        sys.exit(1)


def run():
    """Entry point for the temporalio-server script."""
    # Define binary_path outside try block for potential use in except block
    binary_path_str = "<not found>"  # Default value if get_binary_path fails
    try:
        binary_path = get_binary_path()
        binary_path_str = str(binary_path)  # Convert Path to string for subprocess

        # Pass all command-line arguments received by this script
        # directly to the temporal binary
        args = [binary_path_str] + sys.argv[1:]

        log.info(f"Executing: {' '.join(args)}")

        # Execute the binary
        # Use Popen for more control, or run for simplicity if output capture isn't needed initially.
        # Ensure PATH is preserved. On Windows, shell=True might be needed depending on execution context,
        # but avoid if possible for security. Use full path to binary.
        process = subprocess.Popen(args)

        # Wait for the process to complete and capture the exit code
        process.wait()
        log.info(f"temporal process exited with code {process.returncode}")
        sys.exit(process.returncode)  # Exit with the same code as the temporal CLI

    except FileNotFoundError:
        # Use binary_path_str which holds the path string if get_binary_path succeeded
        log.error(
            f"Error: Failed to execute binary at '{binary_path_str}'. Ensure it exists and is executable.",
            exc_info=True,
        )
        sys.exit(1)
    except KeyboardInterrupt:
        log.info("Received KeyboardInterrupt, exiting.")
        # Let the finally block handle cleanup if needed, exit gracefully
        sys.exit(0)
    except Exception as e:
        log.error(f"Error executing temporal binary: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Allows running the module directly for testing (python -m temporalio_server.main ...)
    run()
