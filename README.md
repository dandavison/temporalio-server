# Temporal Server Python Wrapper (Experimental)

_[Experimental AI-generated prototype project; not intended for public use]_

[![PyPI version](https://badge.fury.io/py/dandavison-temporalio-server.svg)](https://badge.fury.io/py/dandavison-temporalio-server) <!-- Placeholder badge -->

This package provides a convenient way to install and run the [Temporal](https://temporal.io/) development server (`temporal server start-dev`) via the Python packaging ecosystem, particularly leveraging [uv](https://github.com/astral-sh/uv).

It bundles the official pre-compiled `temporal` CLI binary (currently v1.3.0) for your platform within a Python distribution package named `dandavison-temporalio-server`. The actual Python code is importable as `temporalio_server`.

## Usage

This package provides the `temporal-server` command, which acts as a wrapper around the underlying `temporal server start-dev` command.

### Running the Server (Command Line)

The easiest way to run the latest development server without installing it persistently is using `uvx`:

```bash
# Install/run dandavison-temporalio-server, execute its 'temporal-server' command
uvx dandavison-temporalio-server temporal-server start-dev

# Run with custom ports
uvx dandavison-temporalio-server temporal-server start-dev --port 7234 --ui-port 8234
```

Alternatively, you can install the tool persistently:

```bash
# Install the distribution package
uv tool install dandavison-temporalio-server

# Now run the 'temporal-server' command it provides
# (may require shell restart or `uv tool update-shell` first)
temporal-server start-dev
```

### Using the Server in Python (Tests/Scripts)

This package also provides an `async` context manager (`temporalio_server.DevServer`) for programmatically starting and stopping the development server.

To use the `DevServer` context manager, you need to install the distribution package `dandavison-temporalio-server` with the `[examples]` extra, which includes the `temporalio` Python SDK dependency:

```bash
# Install the distribution package with extras
uv pip install 'dandavison-temporalio-server[examples]'

# Or, if using uv project management, add it to your pyproject.toml:
# uv add 'dandavison-temporalio-server[examples]'
```

Example usage in Python (importing from the source module name):

```python
import asyncio
import logging
# Ensure temporalio SDK is installed via the [examples] extra
from temporalio.client import Client
# Import from the source module name
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

See `example.py` in the repository for a runnable example.

## Development

This project uses [`uv`](https://github.com/astral-sh/uv) for environment management and [`hatchling`](https://hatch.pypa.io/latest/) as the build backend.

*   **Setup:** `uv venv && uv sync --all-extras` (to install dev dependencies if any are added)
*   **Build:** `uv build`
*   **Run Example:** `uv run python example.py`
