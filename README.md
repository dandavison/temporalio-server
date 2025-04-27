# Temporal Server Python Wrapper (Experimental)

_[Experimental AI-generated prototype project; not intended for public use]_

[![PyPI version](https://badge.fury.io/py/dandavison-temporalio-server.svg)](https://badge.fury.io/py/dandavison-temporalio-server)

Installs and runs the Temporal development server (`temporal server start-dev`) via Python packaging (`uv`).

Bundles the official pre-compiled `temporal` CLI binary (currently v1.3.0) for your platform within the `dandavison-temporalio-server` distribution package. The Python code is importable as `temporalio_server`.

## Usage

Provides the `temporal-server` command, wrapping `temporal server start-dev`.

### Command Line

Run without persistent install using `uvx`:

```bash
# Run with default settings (ports 7233/8233)
uvx dandavison-temporalio-server temporal-server start-dev

# Run with custom ports
uvx dandavison-temporalio-server temporal-server start-dev --port 7234 --ui-port 8234
```

Install persistently into `uv` tool environment:

```bash
# Install the distribution package
uv tool install dandavison-temporalio-server

# Run the command (may require shell restart/rehash)
temporal-server start-dev
```

### Python (Tests/Scripts)

Provides `temporalio_server.DevServer` async context manager.

Install with `[examples]` extra (includes `temporalio` SDK):

```bash
# Install into project environment
uv pip install 'dandavison-temporalio-server[examples]'

# Or add to pyproject.toml for uv add/sync
# dandavison-temporalio-server = { version = "*", extras = ["examples"] }
```

Example usage:

```python
import asyncio
from temporalio.client import Client
from temporalio_server import DevServer

async def main():
    async with DevServer() as server:
        client = await Client.connect(server.target)
        print(f"Dev server ready at {server.target}")
        # ... use client ...

if __name__ == "__main__":
    asyncio.run(main())
```

See `example.py` for a runnable workflow/activity example.

## Development

*   **Setup:** `uv venv && uv sync --all-extras`
*   **Build:** `uv build`
*   **Run Example:** `uv run python example.py`
