# cache_manager.py
"""
캐시 매니저 (레이턴시 개선)
Cache Manager (Latency Improvement)

응답 캐싱을 통해 레이턴시를 개선하고 비용을 절감합니다.
Redis 또는 메모리 기반 캐시를 지원합니다.
"""

import hashlib
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime
from abc import ABC, abstractmethod

try:
    from .config import Config
except ImportError:
    from config import Config


class CacheBackend(ABC):
    """캐시 백엔드 추상 클래스 (Abstract Cache Backend)"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """캐시에서 값 조회"""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Dict[str, Any], ttl: int = 3600):
        """캐시에 값 저장"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """캐시에서 값 삭제"""
        pass
    
    @abstractmethod
    def clear(self):
        """캐시 전체 삭제"""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        pass


class MemoryCache(CacheBackend):
    """메모리 기반 캐시 (In-Memory Cache)
    
    개발 및 테스트 환경에서 사용합니다.
    """
    
    def __init__(self, max_size: int = 1000):
        """메모리 캐시 초기화
        
        Args:
            max_size: 최대 캐시 크기
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """캐시에서 값 조회
        
        Args:
            key: 캐시 키
            
        Returns:
            Optional[Dict]: 캐시된 값 또는 None
        """
        if key in self._cache:
            entry = self._cache[key]
            
            # TTL 확인
            if entry["expires_at"] > time.time():
                self._hits += 1
                entry["access_count"] += 1
                return entry["value"]
            else:
                # 만료됨
                del self._cache[key]
        
        self._misses += 1
        return None
    
    def set(self, key: str, value: Dict[str, Any], ttl: int = 3600):
        """캐시에 값 저장
        
        Args:
            key: 캐시 키
            value: 저장할 값
            ttl: 캐시 유효 시간 (초)
        """
        # 캐시 크기 제한 확인
        if len(self._cache) >= self._max_size:
            self._evict_oldest()
        
        self._cache[key] = {
            "value": value,
            "expires_at": time.time() + ttl,
            "created_at": time.time(),
            "access_count": 0
        }
    
    def _evict_oldest(self):
        """가장 오래된 항목 삭제 (LRU)"""
        if not self._cache:
            return
        
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k]["created_at"]
        )
        del self._cache[oldest_key]
    
    def delete(self, key: str) -> bool:
        """캐시에서 값 삭제
        
        Args:
            key: 캐시 키
            
        Returns:
            bool: 삭제 성공 여부
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self):
        """캐시 전체 삭제"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회
        
        Returns:
            Dict: 캐시 통계
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0
        
        return {
            "type": "memory",
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "hit_rate_percent": f"{hit_rate * 100:.1f}%"
        }


class RedisCache(CacheBackend):
    """Redis 기반 캐시 (Redis Cache)
    
    프로덕션 환경에서 사용합니다.
    """
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        password: str = None,
        prefix: str = "mcp_agent:"
    ):
        """Redis 캐시 초기화
        
        Args:
            host: Redis 호스트
            port: Redis 포트
            password: Redis 비밀번호
            prefix: 키 접두사
        """
        self._prefix = prefix
        self._connected = False
        self._hits = 0
        self._misses = 0
        
        try:
            import redis
            self._client = redis.Redis(
                host=host or Config.REDIS_HOST,
                port=port or Config.REDIS_PORT,
                password=password or Config.REDIS_PASSWORD,
                decode_responses=True
            )
            # 연결 테스트
            self._client.ping()
            self._connected = True
        except Exception as e:
            print(f"⚠️ Redis connection failed: {e}")
            print("Falling back to memory cache...")
            self._client = None
    
    def _make_key(self, key: str) -> str:
        """키에 접두사 추가"""
        return f"{self._prefix}{key}"
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """캐시에서 값 조회"""
        if not self._connected:
            self._misses += 1
            return None
        
        try:
            value = self._client.get(self._make_key(key))
            if value:
                self._hits += 1
                return json.loads(value)
        except Exception:
            pass
        
        self._misses += 1
        return None
    
    def set(self, key: str, value: Dict[str, Any], ttl: int = 3600):
        """캐시에 값 저장"""
        if not self._connected:
            return
        
        try:
            self._client.setex(
                self._make_key(key),
                ttl,
                json.dumps(value, ensure_ascii=False)
            )
        except Exception as e:
            print(f"⚠️ Redis set error: {e}")
    
    def delete(self, key: str) -> bool:
        """캐시에서 값 삭제"""
        if not self._connected:
            return False
        
        try:
            return self._client.delete(self._make_key(key)) > 0
        except Exception:
            return False
    
    def clear(self):
        """캐시 전체 삭제 (접두사가 있는 키만)"""
        if not self._connected:
            return
        
        try:
            keys = self._client.keys(f"{self._prefix}*")
            if keys:
                self._client.delete(*keys)
        except Exception:
            pass
        
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0
        
        stats = {
            "type": "redis",
            "connected": self._connected,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "hit_rate_percent": f"{hit_rate * 100:.1f}%"
        }
        
        if self._connected:
            try:
                keys = self._client.keys(f"{self._prefix}*")
                stats["size"] = len(keys)
            except Exception:
                pass
        
        return stats


class CacheManager:
    """캐시 매니저 (Cache Manager)
    
    응답 캐싱을 관리하고 캐시 키 생성을 담당합니다.
    """
    
    def __init__(self, use_redis: bool = False, ttl: int = None):
        """캐시 매니저 초기화
        
        Args:
            use_redis: Redis 사용 여부
            ttl: 기본 TTL (초)
        """
        self._ttl = ttl or Config.CACHE_TTL
        
        if use_redis:
            backend = RedisCache()
            if not backend._connected:
                backend = MemoryCache()
        else:
            backend = MemoryCache()
        
        self._backend: CacheBackend = backend
    
    @staticmethod
    def generate_cache_key(
        prompt: str,
        model: str,
        temperature: float = 0.0
    ) -> str:
        """캐시 키 생성
        
        동일한 입력에 대해 동일한 키를 생성합니다.
        
        Args:
            prompt: 프롬프트
            model: 모델 이름
            temperature: 온도 설정
            
        Returns:
            str: 캐시 키
        """
        key_content = f"{model}:{temperature}:{prompt}"
        return hashlib.sha256(key_content.encode()).hexdigest()
    
    def get(self, prompt: str, model: str, temperature: float = 0.0) -> Optional[Dict[str, Any]]:
        """캐시된 응답 조회
        
        Args:
            prompt: 프롬프트
            model: 모델 이름
            temperature: 온도 설정
            
        Returns:
            Optional[Dict]: 캐시된 응답 또는 None
        """
        if not Config.CACHE_ENABLED:
            return None
        
        key = self.generate_cache_key(prompt, model, temperature)
        return self._backend.get(key)
    
    def set(
        self,
        prompt: str,
        model: str,
        response: Dict[str, Any],
        temperature: float = 0.0,
        ttl: int = None
    ):
        """응답 캐싱
        
        Args:
            prompt: 프롬프트
            model: 모델 이름
            response: 캐시할 응답
            temperature: 온도 설정
            ttl: 캐시 유효 시간
        """
        if not Config.CACHE_ENABLED:
            return
        
        # 온도가 0이 아닌 경우 캐시하지 않음
        if temperature > 0:
            return
        
        key = self.generate_cache_key(prompt, model, temperature)
        self._backend.set(key, response, ttl or self._ttl)
    
    def invalidate(self, prompt: str, model: str, temperature: float = 0.0) -> bool:
        """캐시 무효화
        
        Args:
            prompt: 프롬프트
            model: 모델 이름
            temperature: 온도 설정
            
        Returns:
            bool: 무효화 성공 여부
        """
        key = self.generate_cache_key(prompt, model, temperature)
        return self._backend.delete(key)
    
    def clear_all(self):
        """모든 캐시 삭제"""
        self._backend.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회
        
        Returns:
            Dict: 캐시 통계
        """
        return self._backend.get_stats()
