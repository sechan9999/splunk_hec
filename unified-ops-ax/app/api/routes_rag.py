from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.connectors.graph_client import GraphConfigError
from app.connectors.local_folder import LocalFolderConnector
from app.db import get_session
from app.domain.schemas import IngestFolderIn, IngestIn, RagQueryIn
from app.rag.ingest import ingest_document
from app.rag.service import answer

router = APIRouter(prefix="/rag", tags=["rag"])


def _ingest_source_docs(session: Session, connector) -> dict:
    ingested = []
    for src in connector.list_documents():
        doc = ingest_document(
            session, title=src.title, content=src.content, acl=src.acl,
            source=src.meta.get("source", connector.source),
            external_id=src.external_id, uri=src.uri, meta=src.meta,
        )
        ingested.append({"document_id": doc.id, "title": doc.title, "acl": doc.acl})
    session.commit()
    return {"ingested": ingested, "count": len(ingested)}


@router.post("/ingest")
def ingest(body: IngestIn, session: Session = Depends(get_session)):
    doc = ingest_document(session, title=body.title, content=body.content, acl=body.acl, source=body.source)
    session.commit()
    return {"document_id": doc.id, "chunks": len(doc.chunks), "acl": doc.acl}


@router.post("/ingest/folder")
def ingest_folder(body: IngestFolderIn, session: Session = Depends(get_session)):
    connector = LocalFolderConnector(body.path)
    ingested = []
    for src in connector.list_documents():
        doc = ingest_document(
            session, title=src.title, content=src.content, acl=src.acl,
            source=connector.source, external_id=src.external_id, uri=src.uri,
        )
        ingested.append({"document_id": doc.id, "title": doc.title, "acl": doc.acl})
    session.commit()
    return {"ingested": ingested, "count": len(ingested)}


@router.post("/ingest/sharepoint")
def ingest_sharepoint(session: Session = Depends(get_session)):
    from app.connectors.sharepoint import build_sharepoint_connector

    try:
        connector = build_sharepoint_connector()
    except GraphConfigError as exc:
        raise HTTPException(400, str(exc))
    return _ingest_source_docs(session, connector)


@router.post("/ingest/teams")
def ingest_teams(session: Session = Depends(get_session)):
    from app.connectors.sharepoint import build_teams_connector

    try:
        connector = build_teams_connector()
    except GraphConfigError as exc:
        raise HTTPException(400, str(exc))
    return _ingest_source_docs(session, connector)


@router.post("/query")
def query(body: RagQueryIn):
    return answer(body.query, role=body.role, employee_id=body.employee_id, k=body.k)
