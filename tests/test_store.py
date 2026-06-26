from unittest.mock import MagicMock

import app.store as store


def test_merge_lead_data_keeps_existing_when_empty():
    out = store.merge_lead_data({"nome": "Ana"}, {"nome": "", "empresa": "ACME"})
    assert out == {"nome": "Ana", "empresa": "ACME"}


def test_merge_lead_data_overwrites_with_value():
    out = store.merge_lead_data({"nome": "Ana"}, {"nome": "Ana Paula"})
    assert out["nome"] == "Ana Paula"


def test_search_documents_calls_rpc(monkeypatch):
    fake_sb = MagicMock()
    fake_sb.rpc.return_value.execute.return_value.data = [{"content": "x", "metadata": {}}]
    monkeypatch.setattr(store, "_supabase", lambda: fake_sb)

    rows = store.search_documents([0.1, 0.2], 0.6, 5)

    fake_sb.rpc.assert_called_once_with(
        "match_documents",
        {"query_embedding": [0.1, 0.2], "match_threshold": 0.6, "match_count": 5},
    )
    assert rows == [{"content": "x", "metadata": {}}]


def test_create_lead_inserts_when_no_existing(monkeypatch):
    fake_sb = MagicMock()
    fake_sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": 42}]
    monkeypatch.setattr(store, "_supabase", lambda: fake_sb)

    lead_id = store.create_or_update_lead(
        conversation=None,
        lead_data={"nome": "Ana", "necessidade": "site"},
        classificacao={"etiqueta": "quente", "tema": "site"},
        telefone="5511999",
    )
    assert lead_id == 42
