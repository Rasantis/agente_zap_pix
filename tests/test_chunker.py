from ingest.chunker import chunk_text


def test_empty_returns_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_short_text_single_chunk():
    out = chunk_text("Parágrafo curto.", max_chars=2000)
    assert out == ["Parágrafo curto."]


def test_long_text_splits_with_overlap():
    paras = "\n\n".join(f"Parágrafo número {i} com algum conteúdo." for i in range(200))
    out = chunk_text(paras, max_chars=500, overlap_chars=100)
    assert len(out) > 1
    # cada chunk respeita o limite com folga do overlap
    assert all(len(c) <= 500 + 100 for c in out)


def test_huge_paragraph_hard_split():
    out = chunk_text("x" * 1200, max_chars=500, overlap_chars=100)
    assert len(out) >= 3
