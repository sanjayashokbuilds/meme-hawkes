"""The web app runs headless: default example, a bad address, and no API key."""

from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("MEME_HAWKES_OFFLINE", "1")  # never touch the network in tests


def run(address: str = ""):
    at = streamlit_testing.AppTest.from_file(APP, default_timeout=60)
    at.run()
    if address:
        at.text_input[0].input(address)
        at.button[0].click().run()   # the address box is a form: it applies when Analyse is pressed
    return at


def page_text(at) -> str:
    return " ".join(m.value for m in at.markdown)


def test_default_example_renders_a_report():
    at = run()
    assert not at.exception
    text = page_text(at)
    assert "of this token's trades were set off by earlier trades" in text
    assert "<svg" in text and "<circle" in text            # the cascade figure is there
    assert "Mistaken for a frenzy" in text                  # story links are there


def test_story_link_opens_that_token():
    at = streamlit_testing.AppTest.from_file(APP, default_timeout=60)
    at.query_params["token"] = next(m for m in __import__("json").load(open(
        Path(APP).parents[1] / "data/processed/app_examples.json")) if m.startswith("DoMDTY"))
    at.run()
    assert not at.exception and "DoMDTY" in page_text(at)


def test_bad_address_gets_a_clear_message():
    at = run("not-an-address")
    assert not at.exception
    assert "isn't a Solana address" in page_text(at)


def test_no_api_key_means_examples_only():
    at = run("11111111111111111111111111111111")  # valid format, not in the sample
    assert not at.exception
    assert "aren't switched on" in page_text(at)
