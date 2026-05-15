# semantic_cache.py
"""
Semantic Caching with Vector Database
시맨틱 캐싱 - 벡터 데이터베이스 활용

단순 텍스트 일치가 아닌 유사 질문 기반 캐싱으로
응답 속도를 극대화합니다.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import time


@dataclass
class CacheEntry:
    """캐시 엔트리 (Cache Entry)"""
    query: str
    response: Any
    embedding: List[float]
    model: str
    created_at: datetime
    access_count: int = 0
    last_accessed: datetime = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class EmbeddingProvider:
    """임베딩 제공자 추상 클래스"""
    
    def embed(self, text: str) -> List[float]:
        raise NotImplementedError


class OpenAIEmbedding(EmbeddingProvider):
    """OpenAI 임베딩"""
    
    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self._client = None
        
    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI()
            except ImportError:
                raise ImportError("pip install openai")
        return self._client
    
    def embed(self, text: str) -> List[float]:
        client = self._get_client()
        response = client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding


class SentenceTransformerEmbedding(EmbeddingProvider):
    """로컬 SentenceTransformer 임베딩 (무료)"""
    
    def __init__(self, model: str = "all-MiniLM-L6-v2"):
        self.model_name = model
        self._model = None
    
    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                raise ImportError("pip install sentence-transformers")
        return self._model
    
    def embed(self, text: str) -> List[float]:
        model = self._get_model()
        return model.encode(text).tolist()


class SimpleEmbedding(EmbeddingProvider):
    """간단한 TF-IDF 기반 임베딩 (폴백용)"""
    
    def __init__(self, dim: int = 128):
        self.dim = dim
    
    def embed(self, text: str) -> List[float]:
        """해시 기반 간단한 임베딩 생성"""
        import hashlib
        
        # 단어별 해시 생성
        words = text.lower().split()
        embedding = [0.0] * self.dim
        
        for word in words:
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            for i in range(self.dim):
                embedding[i] += ((h >> i) & 1) * 2 - 1
        
        # 정규화
        magnitude = sum(x*x for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]
        
        return embedding


class VectorStore:
    """벡터 저장소 추상 클래스"""
    
    def add(self, id: str, embedding: List[float], metadata: Dict) -> None:
        raise NotImplementedError
    
    def search(self, embedding: List[float], top_k: int = 5) -> List[Tuple[str, float, Dict]]:
        raise NotImplementedError
    
    def delete(self, id: str) -> bool:
        raise NotImplementedError


class ChromaVectorStore(VectorStore):
    """Chroma 벡터 저장소"""
    
    def __init__(self, collection_name: str = "semantic_cache"):
        self.collection_name = collection_name
        self._client = None
        self._collection = None
    
    def _get_collection(self):
        if self._collection is None:
            try:
                import chromadb
                self._client = chromadb.Client()
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
            except ImportError:
                raise ImportError("pip install chromadb")
        return self._collection
    
    def add(self, id: str, embedding: List[float], metadata: Dict) -> None:
        collection = self._get_collection()
        collection.add(
            ids=[id],
            embeddings=[embedding],
            metadatas=[metadata]
        )
    
    def search(self, embedding: List[float], top_k: int = 5) -> List[Tuple[str, float, Dict]]:
        collection = self._get_collection()
        results = collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["distances", "metadatas"]
        )
        
        output = []
        if results["ids"] and results["ids"][0]:
            for i, id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0
                similarity = 1 - distance  # cosine distance to similarity
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                output.append((id, similarity, metadata))
        
        return output
    
    def delete(self, id: str) -> bool:
        try:
            collection = self._get_collection()
            collection.delete(ids=[id])
            return True
        except:
            return False


class InMemoryVectorStore(VectorStore):
    """메모리 기반 벡터 저장소 (개발/테스트용)"""
    
    def __init__(self, max_size: int = 10000):
        self._store: Dict[str, Tuple[List[float], Dict]] = {}
        self._max_size = max_size
    
    def add(self, id: str, embedding: List[float], metadata: Dict) -> None:
        if len(self._store) >= self._max_size:
            # LRU: 가장 오래된 것 삭제
            oldest = next(iter(self._store))
            del self._store[oldest]
        
        self._store[id] = (embedding, metadata)
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        dot = sum(x*y for x, y in zip(a, b))
        norm_a = sum(x*x for x in a) ** 0.5
        norm_b = sum(x*x for x in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a * norm_b > 0 else 0
    
    def search(self, embedding: List[float], top_k: int = 5) -> List[Tuple[str, float, Dict]]:
        results = []
        for id, (stored_emb, metadata) in self._store.items():
            similarity = self._cosine_similarity(embedding, stored_emb)
            results.append((id, similarity, metadata))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def delete(self, id: str) -> bool:
        if id in self._store:
            del self._store[id]
            return True
        return False


class SemanticCache:
    """시맨틱 캐시 (Semantic Cache)
    
    벡터 유사도 기반으로 유사한 질문에 대한 응답을 재사용합니다.
    """
    
    def __init__(
        self,
        embedding_provider: EmbeddingProvider = None,
        vector_store: VectorStore = None,
        similarity_threshold: float = 0.92,
        max_cache_size: int = 10000,
        ttl_hours: int = 24
    ):
        """시맨틱 캐시 초기화
        
        Args:
            embedding_provider: 임베딩 제공자
            vector_store: 벡터 저장소
            similarity_threshold: 캐시 히트 임계값 (0.0~1.0)
            max_cache_size: 최대 캐시 크기
            ttl_hours: 캐시 유효 시간
        """
        self.embedding_provider = embedding_provider or SimpleEmbedding()
        self.vector_store = vector_store or InMemoryVectorStore(max_cache_size)
        self.similarity_threshold = similarity_threshold
        self.ttl_hours = ttl_hours
        
        # 캐시 데이터 저장소
        self._cache_data: Dict[str, CacheEntry] = {}
        
        # 통계
        self._stats = {
            "hits": 0,
            "misses": 0,
            "semantic_hits": 0,  # 유사 질문 히트
            "exact_hits": 0,     # 정확 일치 히트
            "total_saved_cost": 0.0,
            "total_saved_latency_ms": 0
        }
    
    def _generate_id(self, query: str, model: str) -> str:
        """캐시 ID 생성"""
        content = f"{model}:{query}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get(
        self,
        query: str,
        model: str = None,
        check_semantic: bool = True
    ) -> Optional[Tuple[Any, float, str]]:
        """캐시에서 응답 조회
        
        Args:
            query: 쿼리 문자열
            model: 모델 이름 (None이면 모든 모델)
            check_semantic: 시맨틱 검색 사용 여부
            
        Returns:
            Optional[Tuple]: (응답, 유사도, 히트 타입) 또는 None
        """
        # 1. 정확 일치 확인
        cache_id = self._generate_id(query, model or "any")
        if cache_id in self._cache_data:
            entry = self._cache_data[cache_id]
            if self._is_valid(entry):
                entry.access_count += 1
                entry.last_accessed = datetime.now()
                self._stats["hits"] += 1
                self._stats["exact_hits"] += 1
                try:
                    from splunk_telemetry import get_telemetry
                    get_telemetry().emit_cache_hit(
                        model=model or entry.model,
                        cache_key=cache_id,
                        saved_cost=entry.metadata.get("estimated_cost", 0.0),
                        saved_latency_ms=entry.metadata.get("latency_ms", 0.0)
                    )
                except Exception:
                    pass
                return entry.response, 1.0, "exact"

        # 2. 시맨틱 검색
        if check_semantic:
            try:
                query_embedding = self.embedding_provider.embed(query)
                results = self.vector_store.search(query_embedding, top_k=3)

                for cached_id, similarity, metadata in results:
                    if similarity >= self.similarity_threshold:
                        if model and metadata.get("model") != model:
                            continue

                        if cached_id in self._cache_data:
                            entry = self._cache_data[cached_id]
                            if self._is_valid(entry):
                                entry.access_count += 1
                                entry.last_accessed = datetime.now()
                                self._stats["hits"] += 1
                                self._stats["semantic_hits"] += 1
                                try:
                                    from splunk_telemetry import get_telemetry
                                    get_telemetry().emit_cache_hit(
                                        model=model or entry.model,
                                        cache_key=cached_id,
                                        saved_cost=entry.metadata.get("estimated_cost", 0.0),
                                        saved_latency_ms=entry.metadata.get("latency_ms", 0.0)
                                    )
                                except Exception:
                                    pass
                                return entry.response, similarity, "semantic"
            except Exception as e:
                print(f"⚠️ Semantic search error: {e}")

        self._stats["misses"] += 1
        try:
            from splunk_telemetry import get_telemetry
            get_telemetry().emit_cache_miss(model=model or "unknown", cache_key=cache_id)
        except Exception:
            pass
        return None
    
    def set(
        self,
        query: str,
        response: Any,
        model: str,
        estimated_cost: float = 0,
        latency_ms: int = 0,
        metadata: Dict = None
    ) -> str:
        """응답 캐싱
        
        Args:
            query: 쿼리 문자열
            response: 응답 데이터
            model: 모델 이름
            estimated_cost: 추정 비용
            latency_ms: 레이턴시 (밀리초)
            metadata: 추가 메타데이터
            
        Returns:
            str: 캐시 ID
        """
        try:
            # 임베딩 생성
            embedding = self.embedding_provider.embed(query)
            
            cache_id = self._generate_id(query, model)
            
            # 캐시 엔트리 생성
            entry = CacheEntry(
                query=query,
                response=response,
                embedding=embedding,
                model=model,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                metadata={
                    "estimated_cost": estimated_cost,
                    "latency_ms": latency_ms,
                    **(metadata or {})
                }
            )
            
            self._cache_data[cache_id] = entry
            
            # 벡터 저장소에 추가
            self.vector_store.add(
                id=cache_id,
                embedding=embedding,
                metadata={
                    "model": model,
                    "query_preview": query[:100],
                    "created_at": entry.created_at.isoformat()
                }
            )
            
            return cache_id
            
        except Exception as e:
            print(f"⚠️ Cache set error: {e}")
            return ""
    
    def _is_valid(self, entry: CacheEntry) -> bool:
        """캐시 유효성 확인"""
        age_hours = (datetime.now() - entry.created_at).total_seconds() / 3600
        return age_hours < self.ttl_hours
    
    def invalidate(self, query: str, model: str = None) -> bool:
        """캐시 무효화"""
        cache_id = self._generate_id(query, model or "any")
        if cache_id in self._cache_data:
            del self._cache_data[cache_id]
            self.vector_store.delete(cache_id)
            return True
        return False
    
    def clear(self):
        """전체 캐시 초기화"""
        self._cache_data.clear()
        self._stats = {k: 0 for k in self._stats}
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0
        
        return {
            **self._stats,
            "total_requests": total,
            "hit_rate": hit_rate,
            "hit_rate_percent": f"{hit_rate * 100:.1f}%",
            "cache_size": len(self._cache_data),
            "semantic_hit_ratio": (
                self._stats["semantic_hits"] / self._stats["hits"]
                if self._stats["hits"] > 0 else 0
            )
        }


# === 테스트 ===
def test_semantic_cache():
    """시맨틱 캐시 테스트"""
    print("=" * 60)
    print("🧠 Semantic Cache Test")
    print("=" * 60)
    
    cache = SemanticCache(
        similarity_threshold=0.85
    )
    
    # 테스트 쿼리들
    queries = [
        ("What is machine learning?", "gpt-4"),
        ("Explain machine learning to me", "gpt-4"),  # 유사
        ("What's ML?", "gpt-4"),  # 유사
        ("How does Python work?", "gpt-4"),  # 다름
        ("What is machine learning?", "gpt-4"),  # 정확 일치
    ]
    
    # 첫 번째 쿼리 캐싱
    print("\n📝 Caching first query...")
    cache.set(
        query=queries[0][0],
        response={"answer": "Machine learning is a subset of AI..."},
        model=queries[0][1],
        estimated_cost=0.002,
        latency_ms=1500
    )
    
    # 나머지 쿼리 테스트
    for query, model in queries:
        result = cache.get(query, model)
        if result:
            response, similarity, hit_type = result
            print(f"\n✅ HIT ({hit_type})")
            print(f"   Query: {query[:40]}...")
            print(f"   Similarity: {similarity:.2%}")
        else:
            print(f"\n❌ MISS")
            print(f"   Query: {query[:40]}...")
    
    # 통계
    print("\n" + "=" * 60)
    print("📊 Cache Statistics")
    print("=" * 60)
    stats = cache.get_stats()
    print(f"   Hit Rate: {stats['hit_rate_percent']}")
    print(f"   Semantic Hits: {stats['semantic_hits']}")
    print(f"   Exact Hits: {stats['exact_hits']}")
    print(f"   Misses: {stats['misses']}")
    
    print("\n✅ Semantic Cache Test Complete!")


if __name__ == "__main__":
    test_semantic_cache()
