import shutil
import subprocess
from pathlib import Path

import pytest


def test_docker_compose_config_is_valid():
    if shutil.which("docker") is None:
        pytest.skip("docker is not available")

    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["docker", "compose", "config"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
