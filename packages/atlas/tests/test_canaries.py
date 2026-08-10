import re

from atlas.canaries import docstore_canary, hr_doc_canary, system_prompt_canary

CANARY_RE = re.compile(r"^MERIDIAN-CANARY-[0-9a-f-]+$")


def test_canaries_match_expected_shape():
    for value in (system_prompt_canary(1337), hr_doc_canary(1337), docstore_canary(1337)):
        assert CANARY_RE.match(value)


def test_canaries_are_deterministic_given_same_seed():
    assert system_prompt_canary(42) == system_prompt_canary(42)
    assert hr_doc_canary(42) == hr_doc_canary(42)
    assert docstore_canary(42) == docstore_canary(42)


def test_canaries_differ_by_label_and_seed():
    values = {
        system_prompt_canary(1337),
        hr_doc_canary(1337),
        docstore_canary(1337),
        system_prompt_canary(7),
    }
    assert len(values) == 4
