"""Small Chroma-compatible adapter for durable PostgreSQL retrieval.

The JSON vector representation also permits testing on SQLite. Production
ranking runs inside PostgreSQL with pgvector; no index is stored on local disk.
"""
import json

import numpy as np
from sqlalchemy import cast, Text, bindparam

from app.core.config import get_settings
from app.database.database import get_db_context
from app.database.models import StoredChunk


class PostgresCollection:
    def __init__(self, name):
        self.name = name
        settings = get_settings()
        self.model = f"{settings.embedding_backend}:{settings.remote_embedding_model}:{settings.remote_embedding_dimension}"

    def _query(self, db, where=None, ids=None):
        query = db.query(StoredChunk).filter_by(collection=self.name)
        if ids is not None:
            query = query.filter(StoredChunk.id.in_(ids))
        if where:
            # All current callers filter by document ownership before retrieval.
            if set(where) != {"document_id"}:
                raise ValueError("Unsupported vector filter")
            value = where["document_id"]
            if isinstance(value, dict):
                if set(value) != {"$in"}:
                    raise ValueError("Unsupported document filter")
                query = query.filter(StoredChunk.document_id.in_(value["$in"]))
            else:
                query = query.filter_by(document_id=value)
        return query

    def count(self):
        with get_db_context() as db:
            return self._query(db).count()

    def add(self, ids, documents, embeddings, metadatas):
        if not (len(ids) == len(documents) == len(embeddings) == len(metadatas)):
            raise ValueError("Chunk batch lengths differ")
        with get_db_context() as db:
            for id, content, vector, metadata in zip(ids, documents, embeddings, metadatas):
                if not vector or not np.isfinite(vector).all():
                    raise ValueError("Invalid embedding")
                db.add(StoredChunk(id=id, collection=self.name,
                    document_id=metadata["document_id"], content=content,
                    metadata_json=metadata, embedding=vector, embedding_model=self.model))
            db.commit()

    def get(self, where=None, include=None, limit=None, ids=None):
        include = include or ["documents", "metadatas"]
        with get_db_context() as db:
            query = self._query(db, where, ids).order_by(StoredChunk.id)
            rows = query.limit(limit).all() if limit is not None else query.all()
            result = {"ids": [row.id for row in rows]}
            for key, attribute in [("documents", "content"), ("metadatas", "metadata_json"), ("embeddings", "embedding")]:
                if key in include:
                    result[key] = [getattr(row, attribute) for row in rows]
            return result

    def update(self, ids, metadatas):
        with get_db_context() as db:
            for id, metadata in zip(ids, metadatas):
                row = self._query(db, ids=[id]).first()
                if row:
                    row.metadata_json = metadata
            db.commit()

    def delete(self, where=None, ids=None):
        with get_db_context() as db:
            self._query(db, where, ids).delete(synchronize_session=False)
            db.commit()

    def query(self, query_embeddings, n_results=5, where=None, include=None):
        result = {key: [] for key in ("ids", "documents", "metadatas", "distances")}
        with get_db_context() as db:
            for vector in query_embeddings:
                query = self._query(db, where).filter_by(embedding_model=self.model)
                if db.bind.dialect.name == "postgresql":
                    distance = cast(cast(StoredChunk.embedding, Text), _Vector()).op("<=>")(
                        cast(bindparam("query_vector", json.dumps(vector)), _Vector()))
                    pairs = query.add_columns(distance.label("distance")).order_by(distance).limit(n_results).all()
                else:
                    # Test-only fallback; the cloud profile requires PostgreSQL.
                    v = np.asarray(vector)
                    def cosine(row):
                        e = np.asarray(row.embedding)
                        norm = np.linalg.norm(v) * np.linalg.norm(e)
                        return 1 - float(np.dot(v, e) / norm) if norm else 1.0
                    pairs = sorted(((r, cosine(r)) for r in query.all()), key=lambda p: p[1])[:n_results]
                result["ids"].append([row.id for row, _ in pairs])
                result["documents"].append([row.content for row, _ in pairs])
                result["metadatas"].append([row.metadata_json for row, _ in pairs])
                result["distances"].append([float(d) for _, d in pairs])
        return result


from sqlalchemy.types import UserDefinedType


class _Vector(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):
        return "vector"
