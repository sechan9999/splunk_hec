# main.py
"""
MCP 기반 엔터프라이즈 AI 에이전트 커넥터
MCP-Based Enterprise AI Agent Connector

주요 기능:
1. 계층적 접근 제어 (RBAC)
2. 자동 PII 탐지 및 마스킹
3. 완전한 감사 추적 (Audit Trail)
4. 데이터 거버넌스 및 분류
5. 실시간 보안 모니터링
"""

import argparse
import asyncio
import sys
import os

# Add parent directory to path for direct execution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from security_layer import SecurityManager, AccessLevel
from audit_logger import AuditLogger
from data_governance import DataGovernance
from enterprise_connector import EnterpriseConnector


def setup_components():
    """컴포넌트 설정
    
    Returns:
        tuple: (connector, security_manager, audit_logger, data_governance)
    """
    security_manager = SecurityManager()
    audit_logger = AuditLogger(log_file="enterprise_audit.log")
    data_governance = DataGovernance()
    
    connector = EnterpriseConnector(
        security_manager=security_manager,
        audit_logger=audit_logger,
        data_governance=data_governance
    )
    
    return connector, security_manager, audit_logger, data_governance


def run_standalone_demo():
    """스탠드얼론 데모 실행 (비동기 없이)
    
    API 키 없이 로컬에서 테스트할 때 사용합니다.
    """
    print("""
🔐 MCP Enterprise Connector - Standalone Demo
================================================
""")
    
    # 컴포넌트 설정
    connector, security_manager, audit_logger, data_governance = setup_components()
    
    # 다양한 사용자 시나리오 테스트
    test_users = [
        ("admin_user", "admin_credentials"),
        ("analyst_user", "analyst_credentials"),
        ("regular_user", "regular_credentials")
    ]
    
    for user_id, credentials in test_users:
        print(f"\n{'='*60}")
        print(f"Testing with user: {user_id}")
        print(f"{'='*60}")
        
        # 사용자 인증
        context = security_manager.authenticate(user_id, credentials)
        if not context:
            print(f"❌ Authentication failed for {user_id}")
            continue
        
        connector.set_context(context)
        
        print(f"✅ Authenticated!")
        print(f"   Access Level: {context.access_level.name}")
        print(f"   Allowed Resources: {context.allowed_resources}")
        
        # 테스트 쿼리 실행
        print("\n📊 Customer Data Query:")
        result = connector.query_customer("CUST-001")
        print(f"   Status: {result['status']}")
        if "data" in result:
            print(f"   Data: {result['data']}")
        
        print("\n📊 Compliance Query:")
        result = connector.query_compliance("security_system")
        print(f"   Status: {result['status']}")
        if "error" in result:
            print(f"   Note: {result.get('error', 'N/A')}")
        
        print("\n📊 Financial Data Query:")
        result = connector.query_financial("quarterly_revenue")
        print(f"   Status: {result['status']}")
        if "error" in result:
            print(f"   Note: {result.get('error', 'N/A')}")
    
    # 감사 로그 요약
    print("\n" + "="*60)
    print("📋 AUDIT LOG SUMMARY")
    print("="*60)
    
    summary = audit_logger.get_summary()
    print(f"Total Events: {summary['total_events']}")
    print(f"By Event Type: {summary['by_event_type']}")
    print(f"Security Violations: {summary['security_violations']}")
    print(f"\n✅ Audit log saved to: {audit_logger.log_file}")


def test_data_governance():
    """데이터 거버넌스 테스트"""
    print("""
🛡️ Data Governance Test
========================
""")
    
    data_governance = DataGovernance()
    
    # PII 탐지 테스트
    test_data = {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "123-456-7890",
        "ssn": "123-45-6789",
        "status": "active"
    }
    
    print("📝 Original Data:")
    for key, value in test_data.items():
        print(f"   {key}: {value}")
    
    print("\n🔍 PII Detection:")
    pii_found = data_governance.detect_pii(str(test_data))
    for pii_type, matches in pii_found.items():
        print(f"   {pii_type}: {matches}")
    
    print("\n🔒 Masked Data (for non-admin users):")
    masked = data_governance._mask_pii(test_data)
    for key, value in masked.items():
        print(f"   {key}: {value}")


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(
        description="MCP Enterprise AI Agent Connector"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run standalone demo without LLM"
    )
    parser.add_argument(
        "--test-governance",
        action="store_true",
        help="Test data governance features"
    )
    
    args = parser.parse_args()
    
    print("""
🔐 MCP Enterprise Connector Initialized
========================================

Security Features:
✓ Role-Based Access Control (RBAC)
✓ PII Detection & Masking
✓ Audit Logging & Compliance
✓ Data Classification & Governance
✓ Real-time Security Monitoring
""")
    
    if args.test_governance:
        test_data_governance()
    elif args.demo:
        print("Starting standalone demo mode...\n")
        run_standalone_demo()
    else:
        print("Use --demo for standalone demo or --test-governance for governance test")
        print("\nExample usage:")
        print("  python main.py --demo")
        print("  python main.py --test-governance")


if __name__ == "__main__":
    main()
