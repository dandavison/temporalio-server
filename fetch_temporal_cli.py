import logging
import os
import platform
import shutil
import stat
import tarfile
import urllib.request
import zipfile
from pathlib import Path

# Use the import path confirmed by Hatch documentation
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# Set up basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)


class CustomBuildHook(BuildHookInterface):
    """Hatchling build hook to download and package the Temporal CLI binary."""

    CLI_VERSION = "1.3.0"  # Pin the version you want to bundle

    def initialize(self, version, build_data):
        """This method is called before the build process begins."""
        log.info("Initializing Temporal CLI build hook...")

        # Only run for wheel builds as configured in pyproject.toml
        if self.target_name != "wheel":
            log.info(f"Skipping hook for target: {self.target_name}")
            return

        # Determine the target directory within the build environment
        # Hatchling provides the build directory structure.
        # We need to place the binary relative to the package source root.
        # self.root is the project root.
        # The actual source directory is src/temporalio_server, regardless of package name.
        package_dir_name = "temporalio_server"  # Hardcode the source directory name
        self.target_dir = Path(self.root) / "src" / package_dir_name / "bin"
        log.info(f"Target directory for binary: {self.target_dir}")

        # Clean existing target directory if it exists
        if self.target_dir.exists():
            log.info(f"Cleaning existing target directory: {self.target_dir}")
            shutil.rmtree(self.target_dir)

        self.target_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"Created target directory: {self.target_dir}")

        try:
            self.download_and_extract()
            log.info("Temporal CLI binary prepared successfully.")
        except Exception as e:
            log.error(f"Failed to prepare Temporal CLI binary: {e}")
            raise

    def get_platform_mapping(self):
        """Maps Python platform info to Temporal CLI release asset names."""
        # Use platform module directly
        py_system = platform.system().lower()
        goos = py_system
        # Adjust for macOS naming convention in CLI releases
        if goos == "darwin":
            # The actual asset name uses 'darwin', not 'macOS'
            # goos = "macOS" # Incorrect assumption
            pass  # goos is already 'darwin'

        # Determine architecture using platform.machine(), map to GOARCH
        py_arch = platform.machine().lower()
        goarch_map = {
            "x86_64": "amd64",
            "amd64": "amd64",
            "aarch64": "arm64",
            "arm64": "arm64",
        }
        goarch = goarch_map.get(py_arch)

        log.info(f"Determined platform: GOOS={goos}, Arch={py_arch} -> GOARCH={goarch}")

        if not goarch:
            raise RuntimeError(f"Unsupported architecture: {py_arch}")

        archive_ext = ".zip" if goos == "windows" else ".tar.gz"
        # Windows uses .zip primarily, but tar.gz might also exist based on user list?
        # Let's stick to .zip for windows for now as it's more common.
        binary_name = "temporal.exe" if goos == "windows" else "temporal"

        # *** Correct the asset name format to include '_cli_' ***
        asset_name = f"temporal_cli_{self.CLI_VERSION}_{goos}_{goarch}{archive_ext}"
        download_url = f"https://github.com/temporalio/cli/releases/download/v{self.CLI_VERSION}/{asset_name}"

        log.info(
            f"Asset Name: {asset_name}, Download URL: {download_url}, Binary Name: {binary_name}"
        )
        return download_url, asset_name, binary_name, archive_ext

    def download_and_extract(self):
        """Downloads and extracts the Temporal CLI binary."""
        download_url, asset_name, binary_name, archive_ext = self.get_platform_mapping()
        # Use a temporary directory within the build context if possible,
        # otherwise download next to the script or in system temp.
        # Using Path('.') places it relative to where hatch runs, often the project root.
        download_path = Path(".") / asset_name
        final_binary_path = self.target_dir / binary_name

        log.info(f"Downloading {asset_name} from {download_url}...")

        try:
            # Download
            headers = {"User-Agent": "temporalio-server-build/0.1.0"}
            req = urllib.request.Request(download_url, headers=headers)
            with (
                urllib.request.urlopen(req) as response,
                open(download_path, "wb") as out_file,
            ):
                shutil.copyfileobj(response, out_file)
            log.info(f"Downloaded to {download_path}")

            # Extract
            log.info(f"Extracting {binary_name}...")
            if archive_ext == ".tar.gz":
                with tarfile.open(download_path, "r:gz") as tar:
                    member_path = Path(binary_name)  # Assume binary is at root
                    member_found = None
                    for member in tar.getmembers():
                        # Handle potential paths like ./temporal
                        if Path(member.name).name == binary_name:
                            member_found = member
                            break
                    if not member_found:
                        raise FileNotFoundError(
                            f"Binary '{binary_name}' not found in {asset_name}"
                        )

                    # Extract just the binary file to the target directory
                    member_found.name = (
                        binary_name  # Ensure it extracts with the simple name
                    )
                    tar.extract(member_found, path=self.target_dir)

            elif archive_ext == ".zip":
                with zipfile.ZipFile(download_path, "r") as zip_ref:
                    # Need to find the member first to handle potential directory structures
                    member_path_in_zip = None
                    for member_info in zip_ref.infolist():
                        if Path(member_info.filename).name == binary_name:
                            member_path_in_zip = member_info.filename
                            break
                    if not member_path_in_zip:
                        raise FileNotFoundError(
                            f"Binary '{binary_name}' not found in {asset_name}"
                        )

                    # Extract the specific file, placing it directly in target_dir
                    with open(final_binary_path, "wb") as f_out:
                        f_out.write(zip_ref.read(member_path_in_zip))

            log.info(f"Extracted to {final_binary_path}")

            # Make executable (important for non-Windows)
            if platform.system() != "Windows":
                current_stat = os.stat(final_binary_path)
                os.chmod(final_binary_path, current_stat.st_mode | stat.S_IEXEC)
                log.info(f"Made {final_binary_path} executable.")

        finally:
            # Clean up downloaded archive
            if download_path.exists():
                download_path.unlink()
                log.info(f"Cleaned up {download_path}")

    def finalize(self, version, build_data, artifact_path):
        """This method is called after the build process finishes."""
        log.info(
            f"Finalizing build hook for {self.target_name}. Artifact at: {artifact_path}"
        )


# Example usage if run directly (for testing the download/extract logic)
if __name__ == "__main__":
    log.info("Running build hook script directly for testing...")

    # Simulate build environment context for direct execution
    class MockBuildConfig:
        class MockBuilder:
            class MockMetadata:
                name = "temporalio-server"

            metadata = MockMetadata()

        builder = MockBuilder()

    hook = CustomBuildHook(
        root=".",
        config={},
        build_config=MockBuildConfig(),
        build_data={},
        target_name="wheel",
        directory="dist",
    )

    target_test_dir = Path("./temp_build_test_bin")
    hook.target_dir = target_test_dir  # Override target dir for testing

    if hook.target_dir.exists():
        log.info(f"Cleaning existing test target dir: {hook.target_dir}")
        shutil.rmtree(hook.target_dir)
    hook.target_dir.mkdir(parents=True, exist_ok=True)

    try:
        hook.download_and_extract()
        log.info(f"Test download successful. Check contents of {hook.target_dir}")
    except Exception as e:
        log.error(f"Test download failed: {e}", exc_info=True)
