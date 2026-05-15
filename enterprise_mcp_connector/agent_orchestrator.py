# agent_orchestrator.py
"""
에이전트 오케스트레이션 (최종 통합)
Agent Orchestration (Final Integration)

보안이 강화된 MCP 기반 AI 에이전트를 실행합니다.
완전한 엔드-투-엔드 보안 플로우를 제공합니다.
"""

import asyncio
from typing import Optional

from .security_layer import SecurityManager
from .audit_logger import AuditLogger
from .data_governance import DataGovernance
from .enterprise_connector import EnterpriseConnector
from .mcp_tools import create_mcp_tools


def setup_agent_components():
    """에이전트 컴포넌트 설정
    
    Returns:
        tuple: (connector, security_manager, audit_logger, data_governance)
    """
    # 1. 보안 컴포넌트 초기화
    security_manager = SecurityManager()
    audit_logger = AuditLogger(log_file="enterprise_audit.log")
    data_governance = DataGovernance()

    # 2. 엔터프라이즈 커넥터 생성
    connector = EnterpriseConnector(
        security_manager=security_manager,
        audit_logger=audit_logger,
        data_governance=data_governance
    )
    
    return connector, security_manager, audit_logger, data_governance


async def run_secure_ai_agent():
    """보안이 강화된 MCP 기반 AI 에이전트 실행
    
    이 함수는 실제 LLM(OpenAI, Anthropic 등)과 연동됩니다.
    API 키가 필요합니다.
    """
    # 컴포넌트 설정
    connector, security_manager, audit_logger, data_governance = setup_agent_components()

    # 3. 사용자 인증 (실제로는 SSO, OAuth2 등)
    security_context = security_manager.authenticate(
        user_id="data_scientist_001",
        credentials="secure_password_hash"
    )

    if not security_context:
        print("❌ Authentication failed")
        return

    # 4. 보안 컨텍스트 설정
    connector.set_context(security_context)

    print(f"✅ Authenticated as: {security_context.user_id}")
    print(f"   Access Level: {security_context.access_level.name}")
    print(f"   Allowed Resources: {security_context.allowed_resources}\n")

    # 5. MCP 도구 생성
    tools = create_mcp_tools(connector)

    try:
        # 6. LLM 및 에이전트 설정
        from langchain_openai import ChatOpenAI
        from langchain.agents import AgentExecutor, create_openai_functions_agent
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
        
        llm = ChatOpenAI(model="gpt-4-turbo", temperature=0)

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a secure AI Staff Engineer specializing in enterprise data integration.

SECURITY GUIDELINES:
- Always respect access control policies
- Handle PII data with care
- Report any security violations
- All actions are audited

Available resources depend on user's access level.
Use the provided tools to safely access enterprise data."""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_openai_functions_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True
        )

        # 7. 다양한 시나리오 테스트
        test_queries = [
            "고객 ID 'CUST-12345'의 데이터를 조회해줘.",
            "현재 시스템의 컴플라이언스 상태를 확인해줘.",
            "재무 데이터에 접근해서 수익 정보를 가져와줘."  # 권한 부족 시나리오
        ]

        for i, query in enumerate(test_queries, 1):
            print(f"\n{'='*80}")
            print(f"Query {i}: {query}")
            print(f"{'='*80}\n")
            
            try:
                response = await agent_executor.ainvoke({
                    "input": query,
                    "chat_history": []
                })
                print(f"\n✅ Response: {response['output']}\n")
            except Exception as e:
                print(f"\n❌ Error: {str(e)}\n")

    except ImportError as e:
        print(f"⚠️ LangChain OpenAI not available: {e}")
        print("Running in demo mode without LLM...")
        await run_demo_mode(connector, tools)

    # 8. 감사 로그 요약
    print("\n" + "="*80)
    print("AUDIT LOG SUMMARY")
    print("="*80)
    
    summary = audit_logger.get_summary()
    print(f"Total Events: {summary['total_events']}")
    print(f"By Event Type: {summary['by_event_type']}")
    print(f"Security Violations: {summary['security_violations']}")
    print(f"Check '{audit_logger.log_file}' for complete audit trail")


async def run_demo_mode(connector: EnterpriseConnector, tools: list):
    """데모 모드 실행 (LLM 없이)
    
    Args:
        connector: 엔터프라이즈 커넥터
        tools: MCP 도구 목록
    """
    print("\n" + "="*80)
    print("DEMO MODE - Testing MCP Tools Directly")
    print("="*80 + "\n")

    # 1. 고객 데이터 조회 테스트
    print("📊 Test 1: Query Customer Data")
    result = connector.query_customer("CUST-12345")
    print(f"Result: {result}\n")

    # 2. 컴플라이언스 상태 확인 테스트
    print("📊 Test 2: Check Compliance Status")
    result = connector.query_compliance("main_system")
    print(f"Result: {result}\n")

    # 3. 재무 데이터 조회 테스트 (권한 부족 예상)
    print("📊 Test 3: Query Financial Data (may fail due to permissions)")
    result = connector.query_financial("Q4 revenue")
    print(f"Result: {result}\n")


def run_standalone_demo():
    """스탠드얼론 데모 실행 (비동기 없이)
    
    API 키 없이 로컬에서 테스트할 때 사용합니다.
    """
    print("""
🔐 MCP Enterprise Connector - Standalone Demo
================================================
""")
    
    # 컴포넌트 설정
    connector, security_manager, audit_logger, data_governance = setup_agent_components()
    
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
        
        print("\n📊 Financial Data Query:")
        result = connector.query_financial("quarterly_revenue")
        print(f"   Status: {result['status']}")
        if "error" in result:
            print(f"   Error: {result['error']}")
    
    # 감사 로그 요약
    print("\n" + "="*60)
    print("📋 AUDIT LOG SUMMARY")
    print("="*60)
    
    summary = audit_logger.get_summary()
    print(f"Total Events: {summary['total_events']}")
    print(f"By Event Type: {summary['by_event_type']}")
    print(f"Security Violations: {summary['security_violations']}")
    print(f"\n✅ Audit log saved to: {audit_logger.log_file}")


if __name__ == "__main__":
    asyncio.run(run_secure_ai_agent())
