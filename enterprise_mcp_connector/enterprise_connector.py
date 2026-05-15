# enterprise_connector.py
"""
MCP 스타일 엔터프라이즈 커넥터
MCP-Style Enterprise Connector

보안 레이어를 갖춘 도구로, 모든 데이터 접근의 
중앙 제어 포인트 역할을 합니다.

6단계 보안 프로세스:
인증 → 권한 확인 → 실행 → 분류 → 보호 → 로깅
"""

from typing import Optional, Dict, Any
from datetime import datetime

try:
    from .security_layer import SecurityManager, SecurityContext, AccessLevel
    from .audit_logger import AuditLogger, AuditLog, AuditEventType
    from .data_governance import DataGovernance, DataClassification
except ImportError:
    from security_layer import SecurityManager, SecurityContext, AccessLevel
    from audit_logger import AuditLogger, AuditLog, AuditEventType
    from data_governance import DataGovernance, DataClassification



class EnterpriseConnector:
    """MCP 기반 엔터프라이즈 커넥터 - 보안 레이어를 갖춘 도구
    
    모든 데이터 접근의 중앙 제어 포인트로, 
    거버넌스를 적용한 쿼리 실행을 담당합니다.
    """

    def __init__(
        self,
        security_manager: SecurityManager,
        audit_logger: AuditLogger,
        data_governance: DataGovernance
    ):
        """엔터프라이즈 커넥터 초기화
        
        Args:
            security_manager: 보안 관리자
            audit_logger: 감사 로거
            data_governance: 데이터 거버넌스
        """
        self.security_manager = security_manager
        self.audit_logger = audit_logger
        self.data_governance = data_governance
        self._current_context: Optional[SecurityContext] = None

    def set_context(self, security_context: SecurityContext):
        """현재 요청의 보안 컨텍스트 설정
        
        Args:
            security_context: 보안 컨텍스트
        """
        self._current_context = security_context

    def _execute_with_governance(
        self,
        resource: str,
        required_level: AccessLevel,
        query_func: callable,
        query_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """거버넌스를 적용한 쿼리 실행
        
        6단계 보안 프로세스를 적용하여 쿼리를 안전하게 실행합니다.
        
        Args:
            resource: 리소스 이름
            required_level: 필요한 권한 레벨
            query_func: 실행할 쿼리 함수
            query_params: 쿼리 파라미터
            
        Returns:
            Dict: 실행 결과 (data, status, classification 포함)
        """
        # 1. 보안 컨텍스트 검증
        if not self._current_context:
            return {
                "error": "No security context provided",
                "status": "unauthorized"
            }

        # 2. 접근 권한 확인
        if not self._current_context.can_access(resource, required_level):
            # 감사 로그: 보안 위반
            self.audit_logger.log(AuditLog(
                event_type=AuditEventType.SECURITY_VIOLATION,
                user_id=self._current_context.user_id,
                resource=resource,
                action="access_denied",
                result="unauthorized",
                timestamp=datetime.now(),
                metadata={"required_level": required_level.name}
            ))
            return {
                "error": "Access denied",
                "status": "forbidden"
            }

        try:
            # 3. 데이터 쿼리 실행
            raw_data = query_func(**query_params)

            # 4. 데이터 분류
            classification = self.data_governance.classify_data(raw_data)

            # 5. 데이터 보호 적용
            protected_data = self.data_governance.apply_data_protection(
                raw_data,
                classification,
                self._current_context
            )

            # 6. 감사 로그: 성공
            self.audit_logger.log(AuditLog(
                event_type=AuditEventType.DATA_ACCESS,
                user_id=self._current_context.user_id,
                resource=resource,
                action="query_executed",
                result="success",
                timestamp=datetime.now(),
                metadata={
                    "query_params": query_params,
                    "classification": classification.value
                }
            ))

            return {
                "data": protected_data,
                "status": "success",
                "classification": classification.value
            }

        except Exception as e:
            # 감사 로그: 실패
            self.audit_logger.log(AuditLog(
                event_type=AuditEventType.DATA_ACCESS,
                user_id=self._current_context.user_id,
                resource=resource,
                action="query_executed",
                result="error",
                timestamp=datetime.now(),
                metadata={"error": str(e)}
            ))
            return {
                "error": str(e),
                "status": "error"
            }

    # === 실제 도구 정의 ===

    def get_customer_data(self, customer_id: str) -> Dict[str, Any]:
        """고객 데이터 조회 (내부 구현)
        
        실제로는 데이터베이스 쿼리를 수행합니다.
        
        Args:
            customer_id: 고객 ID
            
        Returns:
            Dict: 고객 데이터
        """
        # 시뮬레이션 데이터 (실제로는 DB에서 조회)
        return {
            "customer_id": customer_id,
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "123-456-7890",
            "status": "active",
            "tier": "premium"
        }

    def get_compliance_status(self, system: str) -> Dict[str, Any]:
        """컴플라이언스 상태 조회
        
        Args:
            system: 시스템 이름
            
        Returns:
            Dict: 컴플라이언스 상태
        """
        return {
            "system": system,
            "compliance_checks": {
                "data_encryption": "passed",
                "access_control": "passed",
                "audit_logging": "passed"
            },
            "last_audit": "2025-02-01"
        }

    def get_financial_data(self, query: str) -> Dict[str, Any]:
        """재무 데이터 조회
        
        높은 보안 레벨이 필요합니다.
        
        Args:
            query: 쿼리 문자열
            
        Returns:
            Dict: 재무 데이터
        """
        return {
            "query": query,
            "revenue": 1500000,
            "expenses": 1200000,
            "profit": 300000,
            "quarter": "Q4 2025"
        }

    # === 거버넌스가 적용된 공개 API ===

    def query_customer(self, customer_id: str) -> Dict[str, Any]:
        """고객 데이터 조회 (거버넌스 적용)
        
        Args:
            customer_id: 고객 ID
            
        Returns:
            Dict: 보호된 고객 데이터
        """
        return self._execute_with_governance(
            resource="customer_data",
            required_level=AccessLevel.INTERNAL,
            query_func=self.get_customer_data,
            query_params={"customer_id": customer_id}
        )

    def query_compliance(self, system: str) -> Dict[str, Any]:
        """컴플라이언스 상태 조회 (거버넌스 적용)
        
        Args:
            system: 시스템 이름
            
        Returns:
            Dict: 컴플라이언스 상태
        """
        return self._execute_with_governance(
            resource="compliance_logs",
            required_level=AccessLevel.CONFIDENTIAL,
            query_func=self.get_compliance_status,
            query_params={"system": system}
        )

    def query_financial(self, query: str) -> Dict[str, Any]:
        """재무 데이터 조회 (거버넌스 적용)
        
        RESTRICTED 권한이 필요합니다.
        
        Args:
            query: 쿼리 문자열
            
        Returns:
            Dict: 재무 데이터
        """
        return self._execute_with_governance(
            resource="financial_data",
            required_level=AccessLevel.RESTRICTED,
            query_func=self.get_financial_data,
            query_params={"query": query}
        )
