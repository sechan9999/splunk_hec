# advanced_masking.py
"""
Advanced Dynamic Masking with Presidio
고급 동적 마스킹 - Microsoft Presidio 연동

컨텍스트를 유지하면서 민감 데이터만 치환하는 고급 마스킹 시스템
Presidio를 사용하여 40+ 개인정보 유형을 탐지하고 안전하게 마스킹합니다.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import re
import hashlib


class EntityType(Enum):
    """탐지 가능한 개인정보 유형 (Detectable PII Entity Types)"""
    # 개인 식별 정보
    PERSON = "PERSON"
    EMAIL_ADDRESS = "EMAIL_ADDRESS"
    PHONE_NUMBER = "PHONE_NUMBER"
    
    # 금융 정보
    CREDIT_CARD = "CREDIT_CARD"
    IBAN_CODE = "IBAN_CODE"
    CRYPTO_WALLET = "CRYPTO"
    
    # 정부 발급 ID
    SSN = "US_SSN"  # 미국 사회보장번호
    PASSPORT = "US_PASSPORT"
    DRIVER_LICENSE = "US_DRIVER_LICENSE"
    KR_RRN = "KR_RRN"  # 한국 주민등록번호
    
    # 의료 정보
    MEDICAL_LICENSE = "MEDICAL_LICENSE"
    HEALTH_RECORD = "NRP"  # National Registration Number
    
    # 위치 정보
    LOCATION = "LOCATION"
    IP_ADDRESS = "IP_ADDRESS"
    
    # 날짜/시간
    DATE_TIME = "DATE_TIME"
    
    # 기타
    URL = "URL"
    DOMAIN_NAME = "DOMAIN_NAME"


@dataclass
class DetectedEntity:
    """탐지된 개체 정보 (Detected Entity Info)"""
    entity_type: EntityType
    text: str
    start: int
    end: int
    score: float  # 0.0 ~ 1.0 신뢰도
    context: str = ""  # 주변 컨텍스트


@dataclass
class MaskingConfig:
    """마스킹 설정 (Masking Configuration)"""
    # 마스킹 방식
    use_hash: bool = False  # True면 해시, False면 마스크 문자
    mask_char: str = "*"
    preserve_length: bool = True
    preserve_format: bool = True  # 예: 이메일은 ***@***.com 형태 유지
    
    # 컨텍스트 보존
    show_entity_type: bool = True  # [EMAIL] 같은 태그 표시
    keep_partial: int = 0  # 앞/뒤 몇 글자 유지 (예: 2면 "Jo***oe")
    
    # 고급 옵션
    consistent_replacement: bool = True  # 같은 값은 같은 마스크로
    audit_trail: bool = True  # 마스킹 이력 기록


class PresidioWrapper:
    """Presidio 래퍼 (Presidio Wrapper)
    
    Microsoft Presidio 라이브러리가 설치되어 있으면 사용하고,
    없으면 내장 탐지기로 폴백합니다.
    """
    
    def __init__(self):
        self._presidio_available = False
        self._analyzer = None
        self._anonymizer = None
        
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine
            
            self._analyzer = AnalyzerEngine()
            self._anonymizer = AnonymizerEngine()
            self._presidio_available = True
            print("✓ Presidio engine initialized successfully")
        except ImportError:
            print("⚠️ Presidio not installed. Using built-in detector.")
            print("   Install with: pip install presidio-analyzer presidio-anonymizer")
    
    @property
    def is_available(self) -> bool:
        return self._presidio_available
    
    def analyze(self, text: str, language: str = "en") -> List[DetectedEntity]:
        """텍스트 분석하여 개인정보 탐지"""
        if self._presidio_available:
            return self._analyze_with_presidio(text, language)
        return self._analyze_builtin(text)
    
    def _analyze_with_presidio(self, text: str, language: str) -> List[DetectedEntity]:
        """Presidio를 사용한 분석"""
        results = self._analyzer.analyze(text=text, language=language)
        
        entities = []
        for result in results:
            try:
                entity_type = EntityType(result.entity_type)
            except ValueError:
                entity_type = EntityType.PERSON  # 기본값
            
            entities.append(DetectedEntity(
                entity_type=entity_type,
                text=text[result.start:result.end],
                start=result.start,
                end=result.end,
                score=result.score,
                context=text[max(0, result.start-20):min(len(text), result.end+20)]
            ))
        
        return entities
    
    def _analyze_builtin(self, text: str) -> List[DetectedEntity]:
        """내장 패턴 매칭 분석"""
        entities = []
        
        # 패턴 정의
        patterns = {
            EntityType.EMAIL_ADDRESS: r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            EntityType.PHONE_NUMBER: r'\b\d{2,3}[-.\s]?\d{3,4}[-.\s]?\d{4}\b',
            EntityType.CREDIT_CARD: r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            EntityType.SSN: r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
            EntityType.KR_RRN: r'\b\d{6}[-\s]?\d{7}\b',
            EntityType.IP_ADDRESS: r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            EntityType.URL: r'https?://[^\s]+',
        }
        
        for entity_type, pattern in patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append(DetectedEntity(
                    entity_type=entity_type,
                    text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    score=0.85,  # 패턴 매칭 기반이므로 고정 점수
                    context=text[max(0, match.start()-20):min(len(text), match.end()+20)]
                ))
        
        return entities


class AdvancedMaskingEngine:
    """고급 마스킹 엔진 (Advanced Masking Engine)
    
    컨텍스트를 보존하면서 민감 데이터를 안전하게 마스킹합니다.
    """
    
    def __init__(self, config: MaskingConfig = None):
        self.config = config or MaskingConfig()
        self.presidio = PresidioWrapper()
        self._replacement_map: Dict[str, str] = {}  # 일관된 치환을 위한 맵
        self._masking_log: List[Dict] = []
    
    def mask(
        self,
        text: str,
        entity_types: List[EntityType] = None,
        min_score: float = 0.5
    ) -> Tuple[str, List[DetectedEntity]]:
        """텍스트 마스킹
        
        Args:
            text: 마스킹할 텍스트
            entity_types: 마스킹할 개체 유형 (None이면 전체)
            min_score: 최소 신뢰도 임계값
            
        Returns:
            Tuple[str, List[DetectedEntity]]: (마스킹된 텍스트, 탐지된 개체 목록)
        """
        # 1. 개인정보 탐지
        detected = self.presidio.analyze(text)
        
        # 2. 필터링
        if entity_types:
            detected = [e for e in detected if e.entity_type in entity_types]
        detected = [e for e in detected if e.score >= min_score]
        
        # 3. 위치 역순 정렬 (뒤에서부터 치환해야 인덱스가 안 꼬임)
        detected_sorted = sorted(detected, key=lambda x: x.start, reverse=True)
        
        # 4. 마스킹 적용
        masked_text = text
        for entity in detected_sorted:
            replacement = self._get_replacement(entity)
            masked_text = (
                masked_text[:entity.start] + 
                replacement + 
                masked_text[entity.end:]
            )
            
            # 감사 로그
            if self.config.audit_trail:
                self._masking_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "entity_type": entity.entity_type.value,
                    "original_length": len(entity.text),
                    "replacement": replacement,
                    "score": entity.score
                })
        
        return masked_text, detected
    
    def _get_replacement(self, entity: DetectedEntity) -> str:
        """마스킹 치환값 생성"""
        original = entity.text
        
        # 일관된 치환 모드
        if self.config.consistent_replacement and original in self._replacement_map:
            return self._replacement_map[original]
        
        # 해시 모드
        if self.config.use_hash:
            hash_val = hashlib.sha256(original.encode()).hexdigest()[:8]
            replacement = f"[{entity.entity_type.value}:{hash_val}]"
        
        # 포맷 보존 모드
        elif self.config.preserve_format:
            replacement = self._format_preserving_mask(original, entity.entity_type)
        
        # 길이 보존 모드
        elif self.config.preserve_length:
            replacement = self.config.mask_char * len(original)
        
        # 기본 모드
        else:
            if self.config.show_entity_type:
                replacement = f"[{entity.entity_type.value}]"
            else:
                replacement = self.config.mask_char * 5
        
        # 일관된 치환을 위해 저장
        if self.config.consistent_replacement:
            self._replacement_map[original] = replacement
        
        return replacement
    
    def _format_preserving_mask(self, original: str, entity_type: EntityType) -> str:
        """포맷을 보존하는 마스킹"""
        mask = self.config.mask_char
        keep = self.config.keep_partial
        
        if entity_type == EntityType.EMAIL_ADDRESS:
            # john.doe@example.com → j***@e***.com
            if "@" in original:
                local, domain = original.split("@", 1)
                masked_local = local[0] + mask * 3 if local else mask * 4
                if "." in domain:
                    parts = domain.rsplit(".", 1)
                    masked_domain = parts[0][0] + mask * 3 + "." + parts[1]
                else:
                    masked_domain = mask * 4
                return f"{masked_local}@{masked_domain}"
        
        elif entity_type == EntityType.PHONE_NUMBER:
            # 010-1234-5678 → 010-****-5678
            digits = re.sub(r'\D', '', original)
            if len(digits) >= 10:
                return digits[:3] + "-" + mask * 4 + "-" + digits[-4:]
        
        elif entity_type == EntityType.CREDIT_CARD:
            # 1234-5678-9012-3456 → ****-****-****-3456
            digits = re.sub(r'\D', '', original)
            if len(digits) >= 16:
                return mask * 4 + "-" + mask * 4 + "-" + mask * 4 + "-" + digits[-4:]
        
        elif entity_type == EntityType.SSN or entity_type == EntityType.KR_RRN:
            # 123-45-6789 → ***-**-6789
            digits = re.sub(r'\D', '', original)
            return mask * (len(digits) - 4) + digits[-4:]
        
        elif entity_type == EntityType.IP_ADDRESS:
            # 192.168.1.100 → 192.168.***.***
            parts = original.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.{mask * 3}.{mask * 3}"
        
        # 기본: 앞뒤 일부 보존
        if keep > 0 and len(original) > keep * 2:
            return original[:keep] + mask * (len(original) - keep * 2) + original[-keep:]
        
        return mask * len(original)
    
    def get_masking_log(self) -> List[Dict]:
        """마스킹 이력 반환"""
        return self._masking_log.copy()
    
    def clear_log(self):
        """마스킹 이력 초기화"""
        self._masking_log.clear()
        self._replacement_map.clear()


class ContextAwareMasker:
    """컨텍스트 인식 마스커 (Context-Aware Masker)
    
    문맥을 분석하여 더 정확한 마스킹을 수행합니다.
    예: "John의 이메일은 john@email.com입니다" 
    → "고객의 이메일은 [EMAIL]입니다"
    """
    
    def __init__(self):
        self.engine = AdvancedMaskingEngine(MaskingConfig(
            show_entity_type=True,
            preserve_format=True,
            consistent_replacement=True
        ))
        
        # 컨텍스트 패턴
        self._context_patterns = {
            "name_intro": r"(제 이름은|my name is|이름:)\s*",
            "email_intro": r"(이메일:|email:|메일 주소:)\s*",
            "phone_intro": r"(전화번호:|phone:|연락처:)\s*",
        }
    
    def mask_with_context(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """컨텍스트를 분석하여 마스킹
        
        Returns:
            Tuple[str, Dict]: (마스킹된 텍스트, 분석 결과)
        """
        # 1. 기본 마스킹
        masked_text, entities = self.engine.mask(text)
        
        # 2. 컨텍스트 분석 및 정제
        analysis = {
            "original_length": len(text),
            "masked_length": len(masked_text),
            "entities_found": len(entities),
            "entity_summary": {},
            "risk_level": "LOW"
        }
        
        # 엔티티 요약
        for entity in entities:
            type_name = entity.entity_type.value
            if type_name not in analysis["entity_summary"]:
                analysis["entity_summary"][type_name] = 0
            analysis["entity_summary"][type_name] += 1
        
        # 위험도 평가
        high_risk_types = [EntityType.CREDIT_CARD, EntityType.SSN, EntityType.KR_RRN]
        med_risk_types = [EntityType.EMAIL_ADDRESS, EntityType.PHONE_NUMBER]
        
        for entity in entities:
            if entity.entity_type in high_risk_types:
                analysis["risk_level"] = "HIGH"
                break
            elif entity.entity_type in med_risk_types:
                if analysis["risk_level"] != "HIGH":
                    analysis["risk_level"] = "MEDIUM"
        
        return masked_text, analysis


# === 테스트 ===
def test_advanced_masking():
    """고급 마스킹 테스트"""
    print("=" * 60)
    print("🔐 Advanced Dynamic Masking Test")
    print("=" * 60)
    
    masker = ContextAwareMasker()
    
    test_cases = [
        "Contact John Doe at john.doe@example.com or 010-1234-5678",
        "My SSN is 123-45-6789 and credit card is 4532-1234-5678-9012",
        "서버 IP는 192.168.1.100이고, 주민번호는 901234-1234567입니다.",
        "Please send the documents to support@company.co.kr",
    ]
    
    for i, text in enumerate(test_cases, 1):
        print(f"\n📝 Test Case {i}:")
        print(f"   Original: {text}")
        masked, analysis = masker.mask_with_context(text)
        print(f"   Masked:   {masked}")
        print(f"   Risk: {analysis['risk_level']} | Entities: {analysis['entity_summary']}")
    
    print("\n" + "=" * 60)
    print("✅ Advanced Masking Test Complete!")


if __name__ == "__main__":
    test_advanced_masking()
