# Contributing

Contributions are welcome! Please open an issue or pull request.

## Making a Release

Published via GitHub Actions when a release is published on GitHub.

1.  **Update Version:** Update `version` in `pyproject.toml`, commit, and push.
2.  **Tag:** Create and push a git tag matching the version (e.g., `git tag 0.1.1 && git push origin 0.1.1`).
3.  **Publish GitHub Release:** Use the pushed tag to create a release on GitHub.
4.  **Monitor Workflow:** Check the "Publish Python Package to PyPI" action.

Ensure PyPI Trusted Publisher is configured for this repo and `publish.yml`. 