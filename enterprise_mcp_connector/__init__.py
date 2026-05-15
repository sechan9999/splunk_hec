# __init__.py
"""
Enterprise MCP Connector
==========================

MCP 기반의 엔터프라이즈급 AI 에이전트 커넥터입니다.

주요 기능:
1. 계층적 접근 제어 (RBAC)
2. 자동 PII 탐지 및 마스킹
3. 완전한 감사 추적 (Audit Trail)
4. 데이터 거버넌스 및 분류
5. 실시간 보안 모니터링

사용 예시:
    from enterprise_mcp_connector import (
        SecurityManager, AuditLogger, DataGovernance,
        EnterpriseConnector, create_mcp_tools
    )
    
    # 컴포넌트 초기화
    security_manager = SecurityManager()
    audit_logger = AuditLogger()
    data_governance = DataGovernance()
    
    # 커넥터 생성
    connector = EnterpriseConnector(
        security_manager=security_manager,
        audit_logger=audit_logger,
        data_governance=data_governance
    )
    
    # 사용자 인증 및 컨텍스트 설정
    context = security_manager.authenticate("user_id", "credentials")
    connector.set_context(context)
    
    # MCP 도구 생성
    tools = create_mcp_tools(connector)
"""

from .security_layer import (
    AccessLevel,
    SecurityContext,
    SecurityManager
)

from .audit_logger import (
    AuditEventType,
    AuditLog,
    AuditLogger
)

from .data_governance import (
    DataClassification,
    DataGovernance
)

from .enterprise_connector import EnterpriseConnector

from .mcp_tools import create_mcp_tools

from .agent_orchestrator import (
    setup_agent_components,
    run_secure_ai_agent,
    run_standalone_demo
)

__all__ = [
    # Security
    "AccessLevel",
    "SecurityContext",
    "SecurityManager",
    # Audit
    "AuditEventType",
    "AuditLog",
    "AuditLogger",
    # Governance
    "DataClassification",
    "DataGovernance",
    # Connector
    "EnterpriseConnector",
    # Tools
    "create_mcp_tools",
    # Orchestrator
    "setup_agent_components",
    "run_secure_ai_agent",
    "run_standalone_demo"
]

__version__ = "1.0.0"
