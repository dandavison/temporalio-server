# Contributing

Contributions are welcome! Please open an issue or pull request.

## Making a Release

Releases are published to PyPI automatically via GitHub Actions when a new release is published on GitHub. The process requires maintainer permissions.

1.  **Update Version:**
    *   Ensure the `version` in `pyproject.toml` is updated to the desired new version (e.g., `0.1.1`).
    *   Commit and push this change to the `main` branch.
        ```bash
        # Example
        # (Edit pyproject.toml)
        git add pyproject.toml
        git commit -m "Bump version to 0.1.1"
        git push origin main
        ```

2.  **Create and Push Git Tag:**
    *   Tag the commit corresponding to the new version. Use the version number directly as the tag name (without a `v` prefix).
    *   Push the tag to the remote repository (`origin`).
        ```bash
        # Example for version 0.1.1
        git tag 0.1.1
        git push origin 0.1.1
        ```

3.  **Publish GitHub Release:**
    *   Go to the repository's "Releases" page on GitHub.
    *   Click "Draft a new release".
    *   In the "Choose a tag" dropdown, select the tag you just pushed (e.g., `0.1.1`).
    *   Set the "Release title" (usually the same as the tag, e.g., `0.1.1`).
    *   Add release notes describing the changes.
    *   Click **"Publish release"**.

4.  **Monitor Workflow:**
    *   The "Publish Python Package to PyPI" workflow will automatically trigger.
    *   Monitor its progress under the "Actions" tab of the repository.
    *   If the workflow succeeds, the new version will be available on PyPI.

**Note:** Ensure the [Trusted Publisher configuration](https://docs.pypi.org/trusted-publishers/adding-a-publisher/) is set up correctly on PyPI for this repository and the `publish.yml` workflow. 