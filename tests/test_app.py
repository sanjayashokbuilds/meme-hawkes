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
        at.text_input[0].input(address).run()
    return at


def test_default_example_renders_a_report():
    at = run()
    assert not at.exception
    assert any("Token" in s.value for s in at.subheader)
    assert len(at.columns) >= 3


def test_bad_address_gets_a_clear_message():
    at = run("not-an-address")
    assert not at.exception
    assert "isn't a Solana address" in at.error[0].value


def test_no_api_key_means_examples_only():
    at = run("11111111111111111111111111111111")  # valid format, not in the sample
    assert not at.exception
    assert any("aren't switched on" in i.value for i in at.info)
