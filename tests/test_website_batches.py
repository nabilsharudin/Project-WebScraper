from app.main import (
    MAX_WEBSITE_CHECK_BATCH_SIZE,
    WEBSITE_CHECK_COOLDOWN_SECONDS,
    WEBSITE_CHECK_GROUP_SIZE,
)


def test_large_website_check_is_capped_and_grouped():
    assert MAX_WEBSITE_CHECK_BATCH_SIZE == 30
    assert WEBSITE_CHECK_GROUP_SIZE == 10
    assert WEBSITE_CHECK_COOLDOWN_SECONDS >= 30
