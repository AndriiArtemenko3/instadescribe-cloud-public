"""Provider spend-bound configuration, independent of any network call."""

import pytest


def test_provider_bounds_keep_legacy_defaults(monkeypatch):
    from api_settings import _bounded_env_int

    monkeypatch.delenv("INSTASCRIBE_MAX_PROVIDER_CALLS", raising=False)
    assert _bounded_env_int("INSTASCRIBE_MAX_PROVIDER_CALLS", 100, maximum=100) == 100


@pytest.mark.parametrize("raw", ["0", "01", "+1", " 1", "1 ", "6.0", "six", "7"])
def test_provider_call_bound_rejects_noncanonical_or_over_g12_limit(monkeypatch, raw):
    from api_settings import _bounded_env_int

    monkeypatch.setenv("G12_TEST_BOUND", raw)
    with pytest.raises(RuntimeError, match="Invalid G12_TEST_BOUND") as exc:
        _bounded_env_int("G12_TEST_BOUND", 6, maximum=6)
    assert raw not in str(exc.value)


def test_g12_provider_bounds_accept_exact_values(monkeypatch):
    from api_settings import _bounded_env_int

    monkeypatch.setenv("G12_CALLS", "6")
    monkeypatch.setenv("G12_TOKENS", "8000")
    assert _bounded_env_int("G12_CALLS", 100, maximum=100) == 6
    assert _bounded_env_int("G12_TOKENS", 20000, maximum=20000) == 8000


def test_safe_response_applies_output_bound_and_stops_before_extra_call(monkeypatch):
    import api_settings

    captured: list[dict] = []

    class Responses:
        @staticmethod
        def create(**kwargs):
            captured.append(kwargs)
            return object()

    class Client:
        responses = Responses()

    monkeypatch.setattr(api_settings, "MAX_CALLS", 2)
    monkeypatch.setattr(api_settings, "DEFAULT_MAX_TOKENS", 8000)
    monkeypatch.setattr(api_settings, "_call_count", 0)

    api_settings.safe_create_response(Client(), model="gpt-4.1")
    api_settings.safe_create_response(Client(), model="gpt-4.1")
    with pytest.raises(RuntimeError, match="Exceeded MAX_CALLS=2"):
        api_settings.safe_create_response(Client(), model="gpt-4.1")

    assert len(captured) == 2
    assert all(call["max_output_tokens"] == 8000 for call in captured)
