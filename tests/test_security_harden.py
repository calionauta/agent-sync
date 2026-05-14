
from agent_sync.validators import validate_repo_name, validate_github_url

def test_validators_newline_injection():
    # These should fail with newlines
    assert validate_repo_name("owner/repo\n") is False
    assert validate_repo_name("owner/repo\r") is False
    assert validate_github_url("https://github.com/owner/repo\n") is False

    # Valid ones should still pass
    assert validate_repo_name("owner/repo") is True
    assert validate_github_url("https://github.com/owner/repo") is True

def test_validators_argument_injection_prevention():
    # validators already prevent leading hyphens
    assert validate_repo_name("-bad/repo") is False
    assert validate_github_url("https://github.com/-bad/repo") is False


