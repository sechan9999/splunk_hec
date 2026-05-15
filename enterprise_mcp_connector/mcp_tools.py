# mcp_tools.py
"""
MCP 스타일 LangChain Tool 래퍼
MCP-Style LangChain Tool Wrapper

LangChain의 @tool 데코레이터와 MCP 패턴을 결합하여
보안이 강화된 도구를 생성합니다.
"""

import json
from typing import Annotated

from pydantic import Field
from langchain_core.tools import tool

from .enterprise_connector import EnterpriseConnector
from .security_layer import AccessLevel


def create_mcp_tools(connector: EnterpriseConnector):
    """MCP 스타일의 LangChain 도구 생성
    
    Args:
        connector: 엔터프라이즈 커넥터
        
    Returns:
        list: LangChain 도구 목록
    """

    @tool
    def get_enterprise_data(
        query: Annotated[str, Field(description="The specific data query for the internal system")],
        resource_type: Annotated[str, Field(description="Type of resource: 'customer_data' or 'compliance_status'")]
    ) -> str:
        """
        기업 내부 데이터베이스에서 정보를 검색하는 MCP 커넥터 도구입니다.
        
        보안 기능:
        - 역할 기반 접근 제어 (RBAC)
        - 자동 PII 마스킹
        - 완전한 감사 추적
        - 데이터 분류 및 보호
        
        Args:
            query: 쿼리 문자열 (고객 ID 또는 시스템 이름)
            resource_type: 리소스 타입 ('customer_data' 또는 'compliance_status')
            
        Returns:
            str: JSON 형식의 결과
        """
        if resource_type == "customer_data":
            result = connector.query_customer(customer_id=query)
        elif resource_type == "compliance_status":
            result = connector.query_compliance(system=query)
        else:
            result = {
                "error": "Unknown resource type",
                "status": "invalid",
                "valid_types": ["customer_data", "compliance_status"]
            }

        return json.dumps(result, indent=2, ensure_ascii=False)

    @tool
    def query_financial_data(
        query: Annotated[str, Field(description="Financial data query parameters")]
    ) -> str:
        """
        재무 데이터 조회 도구 (높은 보안 레벨 필요)
        
        주의: RESTRICTED 권한이 필요합니다.
        
        보안 기능:
        - RESTRICTED 레벨 접근 제어
        - 완전한 감사 추적
        - 민감한 데이터 보호
        
        Args:
            query: 재무 데이터 쿼리
            
        Returns:
            str: JSON 형식의 결과
        """
        result = connector.query_financial(query=query)
        return json.dumps(result, indent=2, ensure_ascii=False)

    @tool
    def check_access_level(
        resource: Annotated[str, Field(description="Resource name to check access for")]
    ) -> str:
        """
        특정 리소스에 대한 현재 사용자의 접근 권한을 확인합니다.
        
        Args:
            resource: 확인할 리소스 이름
            
        Returns:
            str: JSON 형식의 접근 권한 정보
        """
        context = connector._current_context
        
        if not context:
            return json.dumps({
                "error": "No security context",
                "status": "unauthenticated"
            })
        
        # 리소스별 필요 권한 레벨
        resource_levels = {
            "customer_data": AccessLevel.INTERNAL,
            "compliance_logs": AccessLevel.CONFIDENTIAL,
            "financial_data": AccessLevel.RESTRICTED
        }
        
        required_level = resource_levels.get(resource, AccessLevel.INTERNAL)
        has_access = context.can_access(resource, required_level)
        
        result = {
            "user_id": context.user_id,
            "resource": resource,
            "user_access_level": context.access_level.name,
            "required_level": required_level.name,
            "has_access": has_access,
            "allowed_resources": context.allowed_resources
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False)

    return [get_enterprise_data, query_financial_data, check_access_level]
