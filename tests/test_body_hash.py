from body_hash import calculate_body_hash


def test_body_hash_ignores_case_and_whitespace() -> None:
    assert calculate_body_hash("  ACME\nSTORE ") == calculate_body_hash("acme store")


def test_body_hash_changes_when_message_content_changes() -> None:
    assert calculate_body_hash("Charged $10") != calculate_body_hash("Charged $11")
