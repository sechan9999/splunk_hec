# security_layer.py
"""
보안 컨텍스트 및 인증 레이어
Security Context and Authentication Layer

이 모듈은 모든 요청에 대한 보안 정보를 관리하고
사용자 인증 및 세션 관리를 담당합니다.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List
import hashlib
import time
from datetime import datetime


class AccessLevel(Enum):
    """접근 권한 레벨 정의 (Access Level Definition)
    
    계층적 권한 관리:
    - PUBLIC (1): 공개 데이터
    - INTERNAL (2): 내부 데이터
    - CONFIDENTIAL (3): 기밀 데이터
    - RESTRICTED (4): 제한된 데이터 (최고 권한)
    """
    PUBLIC = 1
    INTERNAL = 2
    CONFIDENTIAL = 3
    RESTRICTED = 4


@dataclass
class SecurityContext:
    """보안 컨텍스트 - 모든 요청에 필요한 보안 정보
    
    Attributes:
        user_id: 사용자 고유 식별자
        session_token: 세션 토큰
        access_level: 접근 권한 레벨
        allowed_resources: 접근 가능한 리소스 목록
        timestamp: 세션 생성 시간
    """
    user_id: str
    session_token: str
    access_level: AccessLevel
    allowed_resources: List[str]
    timestamp: float = field(default_factory=time.time)

    def is_valid(self) -> bool:
        """세션 유효성 검증 (예: 1시간)
        
        Returns:
            bool: 세션이 유효한 경우 True
        """
        return (time.time() - self.timestamp) < 3600  # 1시간

    def can_access(self, resource: str, required_level: AccessLevel) -> bool:
        """리소스 접근 권한 확인
        
        Args:
            resource: 접근하려는 리소스 이름
            required_level: 필요한 권한 레벨
            
        Returns:
            bool: 접근이 허용되면 True
        """
        return (
            self.is_valid() and
            resource in self.allowed_resources and
            self.access_level.value >= required_level.value
        )


class SecurityManager:
    """보안 관리자 - 인증 및 권한 검증
    
    사용자 인증, 세션 생성 및 검증을 담당합니다.
    실제 환경에서는 OAuth2, LDAP 등과 연동합니다.
    """

    def __init__(self):
        """보안 관리자 초기화
        
        실제 환경에서는 Redis 등의 세션 저장소를 사용합니다.
        """
        self._sessions = {}

    def authenticate(self, user_id: str, credentials: str) -> Optional[SecurityContext]:
        """사용자 인증 및 세션 생성
        
        Args:
            user_id: 사용자 ID
            credentials: 인증 정보 (비밀번호 해시 등)
            
        Returns:
            SecurityContext: 인증 성공 시 보안 컨텍스트, 실패 시 None
        """
        # 세션 토큰 생성 (실제로는 더 안전한 방법 사용)
        token = hashlib.sha256(
            f"{user_id}{credentials}{time.time()}".encode()
        ).hexdigest()

        # 사용자별 권한 설정 (실제로는 DB에서 조회)
        if user_id.startswith("admin"):
            access_level = AccessLevel.RESTRICTED
            resources = ["customer_data", "financial_data", "compliance_logs"]
        elif user_id.startswith("analyst"):
            access_level = AccessLevel.CONFIDENTIAL
            resources = ["customer_data", "compliance_logs"]
        else:
            access_level = AccessLevel.INTERNAL
            resources = ["customer_data"]

        context = SecurityContext(
            user_id=user_id,
            session_token=token,
            access_level=access_level,
            allowed_resources=resources
        )

        self._sessions[token] = context
        return context

    def validate_session(self, token: str) -> Optional[SecurityContext]:
        """세션 토큰 검증
        
        Args:
            token: 세션 토큰
            
        Returns:
            SecurityContext: 유효한 세션이면 컨텍스트, 아니면 None
        """
        context = self._sessions.get(token)
        if context and context.is_valid():
            return context
        return None

    def revoke_session(self, token: str) -> bool:
        """세션 만료 처리
        
        Args:
            token: 세션 토큰
            
        Returns:
            bool: 세션이 성공적으로 만료되면 True
        """
        if token in self._sessions:
            del self._sessions[token]
            return True
        return False
