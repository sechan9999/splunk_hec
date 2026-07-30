"""Working connector for local files. Sidecar `<name>.acl` (comma-separated
principals) sets a document's ACL; absent = public. Good for MVP demos and
air-gapped/on-prem ingestion."""
from __future__ import annotations

from pathlib import Path

from app.connectors.base import SourceDocument

_TEXT_SUFFIXES = {".txt", ".md", ".csv", ".log"}


class LocalFolderConnector:
    source = "local"

    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def list_documents(self) -> list[SourceDocument]:
        docs: list[SourceDocument] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
                continue
            acl_file = path.with_suffix(path.suffix + ".acl")
            acl = (
                [p.strip() for p in acl_file.read_text(encoding="utf-8").split(",") if p.strip()]
                if acl_file.exists()
                else []
            )
            docs.append(
                SourceDocument(
                    external_id=str(path.relative_to(self.root)),
                    title=path.stem,
                    content=path.read_text(encoding="utf-8", errors="ignore"),
                    acl=acl,
                    uri=path.as_uri(),
                )
            )
        return docs
