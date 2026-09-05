import pytest
from atlas_redteam.target import AtlasClient, DisallowedTargetError, check_allowed


def test_allowed_targets_pass():
    check_allowed("http://127.0.0.1:8000")
    check_allowed("http://localhost:8000")
    check_allowed("http://127.0.0.1:8000/")  # trailing slash tolerated


def test_disallowed_target_fails_closed():
    with pytest.raises(DisallowedTargetError):
        check_allowed("http://evil.example.com")
    with pytest.raises(DisallowedTargetError):
        check_allowed("http://127.0.0.1:9999")
    with pytest.raises(DisallowedTargetError):
        check_allowed("https://127.0.0.1:8000")  # scheme must match too


def test_atlas_client_refuses_disallowed_host_at_construction():
    with pytest.raises(DisallowedTargetError):
        AtlasClient("http://attacker.example.com")
