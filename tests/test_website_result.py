from app.scraper import WebsiteResult


def test_website_result_can_signal_a_respectful_batch_stop():
    result = WebsiteResult(
        "https://people.utm.my/example/",
        "error",
        note="Website timed out; batch paused to respect UTM.",
        stop_batch=True,
    )
    assert result.stop_batch is True
