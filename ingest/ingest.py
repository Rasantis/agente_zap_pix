import pathlib
import sys

from app import gemini_client, store
from ingest.chunker import chunk_text


def _read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_pdf(path: pathlib.Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def _read_docx(path: pathlib.Path) -> str:
    import docx

    document = docx.Document(str(path))
    return "\n\n".join(p.text for p in document.paragraphs if p.text.strip())


LOADERS = {
    ".txt": _read_text,
    ".md": _read_text,
    ".pdf": _read_pdf,
    ".docx": _read_docx,
}


def load_documents(folder: str) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for path in sorted(pathlib.Path(folder).rglob("*")):
        if not path.is_file():
            continue
        loader = LOADERS.get(path.suffix.lower())
        if not loader:
            continue
        text = loader(path)
        if text and text.strip():
            out.append((text, {"fonte": path.name}))
    return out


def ingest(folder: str, reset: bool = False) -> int:
    if reset:
        store.clear_documents()

    total = 0
    for text, metadata in load_documents(folder):
        for chunk in chunk_text(text):
            embedding = gemini_client.embed_text(chunk, task_type="RETRIEVAL_DOCUMENT")
            store.insert_document(chunk, dict(metadata), embedding)
            total += 1
    return total


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--reset"]
    reset = "--reset" in sys.argv
    folder = args[0] if args else "./conhecimento"
    count = ingest(folder, reset=reset)
    print(f"Indexados {count} chunks de '{folder}'.")
