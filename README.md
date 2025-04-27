# Temporal Server Python Wrapper

_[Experimental AI-generated prototype project; not intended for public use]_

[![PyPI version](https://badge.fury.io/py/temporalio-server.svg)](https://badge.fury.io/py/temporalio-server) <!-- Placeholder badge -->

This package provides a convenient way to install and run the [Temporal](https://temporal.io/) development server (`temporal server start-dev`) via the Python packaging ecosystem, particularly leveraging [uv](https://github.com/astral-sh/uv).

It bundles the official pre-compiled `temporal` CLI binary (currently v1.3.0) for your platform within a Python package.

## Usage

This package provides the `temporalio-server` command, which acts as a wrapper around the underlying `temporal server start-dev` command.

### Running the Server (Command Line)

The easiest way to run the latest development server without installing it persistently is using `uvx`:

```bash
# Run the server with default settings (ports 7233/8233)
# Note: uvx downloads and runs the package in a temporary environment.
# You can pass arguments directly to 'start-dev'.
uvx temporalio-server start-dev

# Run with custom ports
uvx temporalio-server start-dev --port 7234 --ui-port 8234
```

Alternatively, you can install the `temporalio-server` command persistently into uv's managed tool environment:

```bash
# Install the tool
uv tool install temporalio-server

# Now run it directly (may require shell restart or `uv tool update-shell` first)
temporalio-server start-dev
```

### Using the Server in Python (Tests/Scripts)

This package also provides an `async` context manager (`temporalio_server.DevServer`) for programmatically starting and stopping the development server, useful for integration tests or automation scripts.

To use the `DevServer` context manager, you need to install the package with the `[examples]` extra, which includes the `temporalio` Python SDK dependency needed for most testing scenarios:

```bash
# Install with the extra dependencies into your project environment
uv pip install 'temporalio-server[examples]'

# Or, if using uv project management, add it to your pyproject.toml:
# uv add 'temporalio-server[examples]'
```

Example usage in Python:

```python
import asyncio
import logging
# Ensure temporalio is installed via the [examples] extra
from temporalio.client import Client
from temporalio_server import DevServer

logging.basicConfig(level=logging.INFO)

async def main():
    logging.info("Starting dev server...")
    # Start server, waits until ready, stops on exit
    async with DevServer(log_level="info") as server:
        logging.info(f"Dev server ready at {server.target}")

        # Connect a client (requires temporalio SDK installed)
        client = await Client.connect(server.target)
        logging.info("Client connected.")

        # ... your code using the client ...
        logging.info("Example task finished.")

    logging.info("Dev server stopped.")

if __name__ == "__main__":
    asyncio.run(main())
```

See `example.py` in the repository for a runnable example involving a workflow and activity.

## Development

This project uses [`uv`](https://github.com/astral-sh/uv) for environment management and [`hatchling`](https://hatch.pypa.io/latest/) as the build backend.

*   **Setup:** `uv venv && uv sync --all-extras` (to install dev dependencies if any are added)
*   **Build:** `uv build`
*   **Run Example:** `uv run python example.py`
