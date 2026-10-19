"""Code-engine tests. Docker-dependent tests are opt-in.

Set ``TATTVA_TEST_DOCKER=1`` to run the tests that actually execute a command
inside the sandbox (requires Docker and pulls the sandbox image once).
"""

from __future__ import annotations

import os

import pytest

from tattva_swarm import sandbox

DOCKER_TESTS = os.environ.get("TATTVA_TEST_DOCKER") == "1"


def test_backend_status_shape():
    st = sandbox.backend_status()
    assert set(st) == {"rust_engine", "docker_cli", "image", "selected"}
    assert st["selected"] in (None, "rust", "docker")
    assert st["image"]


def test_empty_command_rejected():
    with pytest.raises(sandbox.CodeEngineError):
        sandbox.run_code("   ")


def test_find_engine_env_override(monkeypatch, tmp_path):
    fake = tmp_path / "tattva-engine"
    fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    monkeypatch.setenv("TATTVA_ENGINE_BIN", str(fake))
    assert sandbox.find_engine_binary() == str(fake)


@pytest.mark.skipif(not DOCKER_TESTS, reason="set TATTVA_TEST_DOCKER=1 (needs Docker + image pull)")
def test_echo_inside_sandbox():
    res = sandbox.run_code("echo hello-sandbox && printf 'to-stderr' 1>&2", timeout_s=60)
    assert res.backend in ("rust", "docker")
    assert res.exit_code == 0
    assert "hello-sandbox" in res.stdout
    assert "to-stderr" in res.stderr


@pytest.mark.skipif(not DOCKER_TESTS, reason="set TATTVA_TEST_DOCKER=1 (needs Docker + image pull)")
def test_timeout_is_enforced():
    res = sandbox.run_code("sleep 30", timeout_s=3)
    assert res.timed_out is True
    assert res.exit_code == 124
