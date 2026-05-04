from src.db import client as db_client


def test_get_supabase_client_prefers_service_role_key(monkeypatch):
    captured = {}
    sentinel = object()

    def fake_create_client(url, key):
        captured["url"] = url
        captured["key"] = key
        return sentinel

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setattr(db_client, "load_env", lambda: None)
    monkeypatch.setattr(db_client, "create_client", fake_create_client)
    monkeypatch.setattr(db_client, "_client", None)

    assert db_client.get_supabase_client() is sentinel
    assert captured == {
        "url": "https://test.supabase.co",
        "key": "service-role-key",
    }


def test_get_supabase_client_falls_back_to_anon_key(monkeypatch):
    captured = {}
    sentinel = object()

    def fake_create_client(url, key):
        captured["url"] = url
        captured["key"] = key
        return sentinel

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setattr(db_client, "load_env", lambda: None)
    monkeypatch.setattr(db_client, "create_client", fake_create_client)
    monkeypatch.setattr(db_client, "_client", None)

    assert db_client.get_supabase_client() is sentinel
    assert captured == {
        "url": "https://test.supabase.co",
        "key": "anon-key",
    }
