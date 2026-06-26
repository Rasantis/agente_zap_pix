import ingest.ingest as ing


def test_load_documents_reads_txt_and_md(tmp_path):
    (tmp_path / "a.txt").write_text("Conteúdo A", encoding="utf-8")
    (tmp_path / "faq.md").write_text("Pergunta? Resposta.", encoding="utf-8")
    (tmp_path / "ignora.xyz").write_text("nope", encoding="utf-8")

    docs = ing.load_documents(str(tmp_path))
    textos = sorted(t for t, _ in docs)
    assert textos == ["Conteúdo A", "Pergunta? Resposta."]
    assert all("fonte" in meta for _, meta in docs)


def test_ingest_chunks_embeds_and_upserts(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("Parágrafo um.\n\nParágrafo dois.", encoding="utf-8")

    upserts = []
    monkeypatch.setattr(ing, "chunk_text", lambda text: ["c1", "c2"])
    monkeypatch.setattr(ing.gemini_client, "embed_text", lambda text, task_type: [0.1])
    monkeypatch.setattr(ing.store, "insert_document",
                        lambda content, metadata, embedding: upserts.append(content))
    monkeypatch.setattr(ing.store, "clear_documents", lambda: upserts.append("CLEARED"))

    count = ing.ingest(str(tmp_path), reset=True)

    assert count == 2
    assert upserts[0] == "CLEARED"
    assert "c1" in upserts and "c2" in upserts
