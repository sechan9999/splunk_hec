# data_governance.py
"""
데이터 거버넌스 레이어
Data Governance Layer

데이터 자동 분류, PII 탐지 및 마스킹,
권한 기반 데이터 보호를 제공합니다.
GDPR, CCPA 등의 개인정보 보호 규정 대응.
"""

import re
from typing import Any, Dict
from enum import Enum

try:
    from .security_layer import SecurityContext, AccessLevel
except ImportError:
    from security_layer import SecurityContext, AccessLevel



class DataClassification(Enum):
    """데이터 분류 레벨 (Data Classification Levels)
    
    - PUBLIC: 공개 데이터
    - INTERNAL: 내부 데이터
    - CONFIDENTIAL: 기밀 데이터
    - PII: 개인 식별 정보 (Personally Identifiable Information)
    """
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PII = "pii"


class DataGovernance:
    """데이터 거버넌스 - 데이터 보호 및 변환
    
    자동으로 데이터를 분류하고 권한에 따라 
    적절한 보호 조치를 적용합니다.
    """

    def __init__(self):
        """데이터 거버넌스 초기화
        
        PII 패턴 정의를 설정합니다.
        """
        # PII 패턴 정의 (정규 표현식)
        self.pii_patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
            'phone': r'\b\d{3}-\d{3}-\d{4}\b',
            'credit_card': r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',
            # 한국 주민등록번호 패턴
            'korean_ssn': r'\b\d{6}[- ]?\d{7}\b',
            # 한국 휴대폰 번호 패턴
            'korean_phone': r'\b01[016789]-?\d{3,4}-?\d{4}\b'
        }

        # 민감한 필드 이름
        self.sensitive_fields = [
            'salary', 'ssn', 'social_security', 'medical_history',
            'credit_score', 'password', 'secret', 'private_key'
        ]

        # 민감한 키워드
        self.sensitive_keywords = [
            'salary', 'medical', 'financial', 'confidential',
            'secret', 'private', 'password', 'health'
        ]

    def classify_data(self, data: Dict[str, Any]) -> DataClassification:
        """데이터 자동 분류
        
        Args:
            data: 분류할 데이터 딕셔너리
            
        Returns:
            DataClassification: 데이터 분류 레벨
        """
        data_str = str(data).lower()

        # PII 포함 여부 확인
        for pattern in self.pii_patterns.values():
            if re.search(pattern, str(data)):
                return DataClassification.PII

        # 민감한 키워드 확인
        if any(keyword in data_str for keyword in self.sensitive_keywords):
            return DataClassification.CONFIDENTIAL

        return DataClassification.INTERNAL

    def apply_data_protection(
        self,
        data: Dict[str, Any],
        classification: DataClassification,
        security_context: SecurityContext
    ) -> Dict[str, Any]:
        """접근 권한에 따른 데이터 보호 적용
        
        Args:
            data: 원본 데이터
            classification: 데이터 분류 레벨
            security_context: 보안 컨텍스트
            
        Returns:
            Dict: 보호가 적용된 데이터
        """
        # PII 데이터는 RESTRICTED 권한 필요
        if classification == DataClassification.PII:
            if security_context.access_level != AccessLevel.RESTRICTED:
                return self._mask_pii(data)

        # CONFIDENTIAL 데이터는 CONFIDENTIAL 이상 권한 필요
        if classification == DataClassification.CONFIDENTIAL:
            if security_context.access_level.value < AccessLevel.CONFIDENTIAL.value:
                return self._redact_sensitive_fields(data)

        return data

    def _mask_pii(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """PII 마스킹
        
        개인 식별 정보를 마스킹 처리합니다.
        
        Args:
            data: 원본 데이터
            
        Returns:
            Dict: 마스킹된 데이터
        """
        masked_data = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                # 이메일 마스킹: user@example.com -> u***@example.com
                value = re.sub(
                    self.pii_patterns['email'],
                    lambda m: m.group(0)[0] + '***@' + m.group(0).split('@')[1],
                    value
                )
                
                # SSN 마스킹: 123-45-6789 -> ***-**-****
                value = re.sub(self.pii_patterns['ssn'], '***-**-****', value)
                
                # 전화번호 마스킹
                value = re.sub(self.pii_patterns['phone'], '***-***-****', value)
                
                # 신용카드 마스킹
                value = re.sub(
                    self.pii_patterns['credit_card'],
                    lambda m: '****-****-****-' + m.group(0)[-4:],
                    value
                )
                
                # 한국 주민등록번호 마스킹
                value = re.sub(self.pii_patterns['korean_ssn'], '******-*******', value)
                
                # 한국 휴대폰 번호 마스킹
                value = re.sub(self.pii_patterns['korean_phone'], '010-****-****', value)
                
            elif isinstance(value, dict):
                # 중첩 딕셔너리 재귀 처리
                value = self._mask_pii(value)
                
            masked_data[key] = value
            
        return masked_data

    def _redact_sensitive_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """민감한 필드 제거
        
        Args:
            data: 원본 데이터
            
        Returns:
            Dict: 민감한 필드가 제거된 데이터
        """
        return {
            k: "[REDACTED]" if k.lower() in self.sensitive_fields else v
            for k, v in data.items()
        }

    def detect_pii(self, text: str) -> Dict[str, list]:
        """텍스트에서 PII 탐지
        
        Args:
            text: 검사할 텍스트
            
        Returns:
            Dict: 탐지된 PII 타입별 목록
        """
        detected = {}
        
        for pii_type, pattern in self.pii_patterns.items():
            matches = re.findall(pattern, text)
            if matches:
                detected[pii_type] = matches
                
        return detected
