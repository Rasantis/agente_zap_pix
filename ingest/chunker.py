def chunk_text(text: str, max_chars: int = 2000, overlap_chars: int = 300) -> list[str]:
    if not text or not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(para) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            step = max(1, max_chars - overlap_chars)
            while start < len(para):
                chunks.append(para[start:start + max_chars].strip())
                start += step
            continue

        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current.strip())
            current = current[-overlap_chars:] + "\n\n" + para
        else:
            current = f"{current}\n\n{para}" if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks
