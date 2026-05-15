# dlp_policy.py
"""
DLP (Data Loss Prevention) Policy Engine
데이터 유출 방지 정책 엔진

에이전트가 외부 툴을 호출하기 전/후에 기밀 정보 포함 여부를 검사합니다.
아웃바운드(외부 전송) 및 인바운드(내부 저장) 검사를 모두 지원합니다.
"""

from typing import Dict, Any, List, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import re
import json
import hashlib


class DLPAction(Enum):
    """DLP 정책 위반 시 조치 (DLP Policy Violation Actions)"""
    ALLOW = "allow"           # 허용
    BLOCK = "block"           # 차단
    MASK = "mask"             # 마스킹 후 허용
    ALERT = "alert"           # 경고 후 허용
    QUARANTINE = "quarantine" # 격리 (검토 대기)
    ENCRYPT = "encrypt"       # 암호화 후 허용


class DataSensitivity(Enum):
    """데이터 민감도 수준 (Data Sensitivity Levels)"""
    PUBLIC = 1           # 공개
    INTERNAL = 2         # 내부용
    CONFIDENTIAL = 3     # 기밀
    RESTRICTED = 4       # 제한적 접근
    TOP_SECRET = 5       # 극비


class TransferDirection(Enum):
    """데이터 전송 방향 (Data Transfer Direction)"""
    INBOUND = "inbound"    # 외부 → 내부 (데이터 수신)
    OUTBOUND = "outbound"  # 내부 → 외부 (데이터 송신)
    INTERNAL = "internal"  # 내부 간 전송


@dataclass
class DLPRule:
    """DLP 규칙 (DLP Rule Definition)"""
    rule_id: str
    name: str
    description: str
    
    # 탐지 조건
    patterns: List[str]              # 정규식 패턴 목록
    keywords: List[str] = field(default_factory=list)  # 키워드 목록
    sensitivity: DataSensitivity = DataSensitivity.CONFIDENTIAL
    
    # 적용 대상
    directions: List[TransferDirection] = field(
        default_factory=lambda: [TransferDirection.OUTBOUND]
    )
    target_tools: List[str] = field(default_factory=list)  # 빈 리스트 = 모든 툴
    
    # 조치
    action: DLPAction = DLPAction.BLOCK
    
    # 예외
    allowed_destinations: List[str] = field(default_factory=list)
    excluded_users: List[str] = field(default_factory=list)
    
    # 메타데이터
    enabled: bool = True
    priority: int = 100  # 낮을수록 높은 우선순위


@dataclass
class DLPViolation:
    """DLP 위반 기록 (DLP Violation Record)"""
    violation_id: str
    rule_id: str
    rule_name: str
    timestamp: datetime
    
    # 위반 상세
    direction: TransferDirection
    tool_name: str
    matched_patterns: List[str]
    matched_keywords: List[str]
    sensitivity: DataSensitivity
    
    # 조치
    action_taken: DLPAction
    data_hash: str  # 원본 데이터의 해시 (감사용)
    
    # 컨텍스트
    user_id: str = ""
    destination: str = ""
    data_preview: str = ""  # 마스킹된 미리보기


@dataclass
class DLPScanResult:
    """DLP 스캔 결과 (DLP Scan Result)"""
    is_clean: bool                    # 위반 없음
    violations: List[DLPViolation]    # 위반 목록
    action: DLPAction                 # 최종 조치
    processed_data: Any               # 처리된 데이터 (마스킹됨)
    scan_time_ms: float               # 스캔 시간


class DLPPolicyEngine:
    """DLP 정책 엔진 (DLP Policy Engine)
    
    데이터 유출 방지 정책을 관리하고 실행합니다.
    """
    
    def __init__(self):
        self._rules: Dict[str, DLPRule] = {}
        self._violations: List[DLPViolation] = []
        self._violation_count = 0
        
        # 기본 규칙 로드
        self._load_default_rules()
    
    def _load_default_rules(self):
        """기본 DLP 규칙 로드"""
        default_rules = [
            DLPRule(
                rule_id="DLP-001",
                name="Credit Card Detection",
                description="Detects credit card numbers in outbound data",
                patterns=[
                    r'\b(?:\d{4}[-\s]?){3}\d{4}\b',  # 신용카드 번호
                    r'\b\d{16}\b',  # 연속 16자리
                ],
                keywords=["credit card", "card number", "카드번호"],
                sensitivity=DataSensitivity.RESTRICTED,
                action=DLPAction.BLOCK
            ),
            DLPRule(
                rule_id="DLP-002",
                name="SSN Detection",
                description="Detects Social Security Numbers",
                patterns=[
                    r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',  # US SSN
                    r'\b\d{6}[-\s]?\d{7}\b',  # 한국 주민번호
                ],
                keywords=["ssn", "social security", "주민등록번호", "주민번호"],
                sensitivity=DataSensitivity.TOP_SECRET,
                action=DLPAction.BLOCK
            ),
            DLPRule(
                rule_id="DLP-003",
                name="API Key Detection",
                description="Detects exposed API keys and secrets",
                patterns=[
                    r'(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[=:]\s*["\']?[\w\-]{20,}["\']?',
                    r'(?i)bearer\s+[\w\-\.]+',
                    r'sk-[a-zA-Z0-9]{20,}',  # OpenAI 형식
                    r'ghp_[a-zA-Z0-9]{36}',  # GitHub 토큰
                ],
                keywords=["api_key", "secret_key", "bearer token"],
                sensitivity=DataSensitivity.TOP_SECRET,
                action=DLPAction.BLOCK
            ),
            DLPRule(
                rule_id="DLP-004",
                name="Email PII Detection",
                description="Detects email addresses in sensitive context",
                patterns=[
                    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                ],
                keywords=["email", "이메일", "메일주소"],
                sensitivity=DataSensitivity.CONFIDENTIAL,
                action=DLPAction.MASK
            ),
            DLPRule(
                rule_id="DLP-005",
                name="Internal IP Detection",
                description="Prevents leaking internal network information",
                patterns=[
                    r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3})\b',  # 10.x.x.x
                    r'\b(?:172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b',  # 172.16-31.x.x
                    r'\b(?:192\.168\.\d{1,3}\.\d{1,3})\b',  # 192.168.x.x
                ],
                keywords=["internal ip", "server ip", "서버 주소"],
                sensitivity=DataSensitivity.CONFIDENTIAL,
                action=DLPAction.MASK
            ),
            DLPRule(
                rule_id="DLP-006",
                name="Source Code Detection",
                description="Prevents leaking proprietary source code",
                patterns=[
                    r'(?i)(?:def|class|function|public|private)\s+\w+\s*\(',
                    r'(?i)import\s+(?:from\s+)?[\w\.]+',
                ],
                keywords=["source code", "proprietary", "confidential code"],
                sensitivity=DataSensitivity.RESTRICTED,
                action=DLPAction.ALERT,
                target_tools=["web_search", "email_send", "file_upload"]
            ),
            DLPRule(
                rule_id="DLP-007",
                name="Financial Data Detection",
                description="Detects financial reports and numbers",
                patterns=[
                    r'(?i)(revenue|profit|loss|budget|salary)\s*[:=]\s*\$?[\d,]+',
                    r'\$[\d,]+(?:\.\d{2})?',
                ],
                keywords=["financial report", "quarterly results", "revenue", "매출", "연봉"],
                sensitivity=DataSensitivity.RESTRICTED,
                action=DLPAction.ALERT
            ),
            DLPRule(
                rule_id="DLP-008",
                name="Medical Data Detection (HIPAA)",
                description="Detects protected health information",
                patterns=[
                    r'(?i)(diagnosis|patient|medical\s*record|prescription)\s*[:=]',
                    r'(?i)ICD-?\d{1,2}[-\.]?\w+',  # ICD 코드
                ],
                keywords=["patient", "diagnosis", "medical record", "HIPAA", "진단", "처방"],
                sensitivity=DataSensitivity.TOP_SECRET,
                action=DLPAction.BLOCK
            ),
        ]
        
        for rule in default_rules:
            self.add_rule(rule)
    
    def add_rule(self, rule: DLPRule):
        """규칙 추가"""
        self._rules[rule.rule_id] = rule
    
    def remove_rule(self, rule_id: str) -> bool:
        """규칙 제거"""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False
    
    def get_rules(self) -> List[DLPRule]:
        """모든 규칙 조회"""
        return sorted(self._rules.values(), key=lambda r: r.priority)
    
    def scan(
        self,
        data: Any,
        direction: TransferDirection,
        tool_name: str = "",
        user_id: str = "",
        destination: str = ""
    ) -> DLPScanResult:
        """데이터 DLP 스캔
        
        Args:
            data: 스캔할 데이터
            direction: 전송 방향
            tool_name: 호출 대상 툴 이름
            user_id: 사용자 ID
            destination: 목적지
            
        Returns:
            DLPScanResult: 스캔 결과
        """
        import time
        start_time = time.time()
        
        # 데이터를 문자열로 변환
        if isinstance(data, dict):
            text = json.dumps(data, ensure_ascii=False)
        elif isinstance(data, (list, tuple)):
            text = json.dumps(data, ensure_ascii=False)
        else:
            text = str(data)
        
        violations = []
        processed_data = data
        
        # 우선순위 순으로 규칙 검사
        for rule in self.get_rules():
            if not rule.enabled:
                continue
            
            # 방향 필터
            if direction not in rule.directions:
                continue
            
            # 툴 필터
            if rule.target_tools and tool_name not in rule.target_tools:
                continue
            
            # 사용자 제외
            if user_id in rule.excluded_users:
                continue
            
            # 목적지 허용
            if destination and destination in rule.allowed_destinations:
                continue
            
            # 패턴 매칭
            matched_patterns = []
            for pattern in rule.patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    matched_patterns.append(pattern)
            
            # 키워드 매칭
            matched_keywords = []
            text_lower = text.lower()
            for keyword in rule.keywords:
                if keyword.lower() in text_lower:
                    matched_keywords.append(keyword)
            
            # 위반 감지
            if matched_patterns or matched_keywords:
                self._violation_count += 1
                violation = DLPViolation(
                    violation_id=f"VIO-{self._violation_count:06d}",
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    timestamp=datetime.now(),
                    direction=direction,
                    tool_name=tool_name,
                    matched_patterns=matched_patterns,
                    matched_keywords=matched_keywords,
                    sensitivity=rule.sensitivity,
                    action_taken=rule.action,
                    data_hash=hashlib.sha256(text.encode()).hexdigest()[:16],
                    user_id=user_id,
                    destination=destination,
                    data_preview=text[:100] + "..." if len(text) > 100 else text
                )
                violations.append(violation)
                self._violations.append(violation)
        
        # 최종 조치 결정 (가장 엄격한 것 적용)
        action_priority = {
            DLPAction.BLOCK: 0,
            DLPAction.QUARANTINE: 1,
            DLPAction.ENCRYPT: 2,
            DLPAction.MASK: 3,
            DLPAction.ALERT: 4,
            DLPAction.ALLOW: 5,
        }
        
        if violations:
            final_action = min(
                [v.action_taken for v in violations],
                key=lambda a: action_priority[a]
            )
            
            # 마스킹 조치 시 데이터 처리
            if final_action == DLPAction.MASK:
                processed_data = self._mask_sensitive_data(data, violations)
        else:
            final_action = DLPAction.ALLOW
        
        scan_time = (time.time() - start_time) * 1000
        
        return DLPScanResult(
            is_clean=len(violations) == 0,
            violations=violations,
            action=final_action,
            processed_data=processed_data,
            scan_time_ms=scan_time
        )
    
    def _mask_sensitive_data(self, data: Any, violations: List[DLPViolation]) -> Any:
        """민감 데이터 마스킹"""
        if isinstance(data, str):
            masked = data
            for violation in violations:
                for pattern in violation.matched_patterns:
                    masked = re.sub(pattern, "[REDACTED]", masked, flags=re.IGNORECASE)
            return masked
        elif isinstance(data, dict):
            return {k: self._mask_sensitive_data(v, violations) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._mask_sensitive_data(item, violations) for item in data]
        return data
    
    def get_violation_history(
        self,
        limit: int = 100,
        rule_id: str = None,
        user_id: str = None
    ) -> List[DLPViolation]:
        """위반 이력 조회"""
        filtered = self._violations
        
        if rule_id:
            filtered = [v for v in filtered if v.rule_id == rule_id]
        if user_id:
            filtered = [v for v in filtered if v.user_id == user_id]
        
        return filtered[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """DLP 통계"""
        if not self._violations:
            return {"total_violations": 0, "message": "No violations recorded"}
        
        by_rule = {}
        by_action = {}
        by_sensitivity = {}
        
        for v in self._violations:
            by_rule[v.rule_name] = by_rule.get(v.rule_name, 0) + 1
            by_action[v.action_taken.value] = by_action.get(v.action_taken.value, 0) + 1
            by_sensitivity[v.sensitivity.value] = by_sensitivity.get(v.sensitivity.value, 0) + 1
        
        return {
            "total_violations": len(self._violations),
            "by_rule": by_rule,
            "by_action": by_action,
            "by_sensitivity": by_sensitivity,
            "blocked_count": by_action.get("block", 0),
            "masked_count": by_action.get("mask", 0),
        }


class DLPInterceptor:
    """DLP 인터셉터 (DLP Interceptor)
    
    에이전트 툴 호출을 가로채서 DLP 검사를 수행합니다.
    """
    
    def __init__(self, engine: DLPPolicyEngine = None):
        self.engine = engine or DLPPolicyEngine()
    
    def intercept_outbound(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        user_id: str = "",
        destination: str = ""
    ) -> Tuple[bool, DLPScanResult, Dict[str, Any]]:
        """아웃바운드 호출 가로채기
        
        Args:
            tool_name: 호출할 툴 이름
            tool_args: 툴 인자
            user_id: 사용자 ID
            destination: 목적지
            
        Returns:
            Tuple[bool, DLPScanResult, Dict]: (허용 여부, 스캔 결과, 처리된 인자)
        """
        result = self.engine.scan(
            data=tool_args,
            direction=TransferDirection.OUTBOUND,
            tool_name=tool_name,
            user_id=user_id,
            destination=destination
        )
        
        if result.action == DLPAction.BLOCK:
            return False, result, {}
        elif result.action == DLPAction.QUARANTINE:
            return False, result, {}
        else:
            return True, result, result.processed_data
    
    def intercept_inbound(
        self,
        tool_name: str,
        response_data: Any,
        user_id: str = ""
    ) -> Tuple[bool, DLPScanResult, Any]:
        """인바운드 응답 가로채기
        
        Args:
            tool_name: 툴 이름
            response_data: 응답 데이터
            user_id: 사용자 ID
            
        Returns:
            Tuple[bool, DLPScanResult, Any]: (허용 여부, 스캔 결과, 처리된 데이터)
        """
        result = self.engine.scan(
            data=response_data,
            direction=TransferDirection.INBOUND,
            tool_name=tool_name,
            user_id=user_id
        )
        
        # 인바운드는 보통 마스킹만 적용
        return True, result, result.processed_data


def wrap_tool_with_dlp(
    tool_func: Callable,
    tool_name: str,
    interceptor: DLPInterceptor = None
) -> Callable:
    """DLP 래퍼로 툴 감싸기
    
    Args:
        tool_func: 원본 툴 함수
        tool_name: 툴 이름
        interceptor: DLP 인터셉터
        
    Returns:
        Callable: DLP가 적용된 툴 함수
    """
    if interceptor is None:
        interceptor = DLPInterceptor()
    
    def wrapped_tool(*args, **kwargs):
        # 1. 아웃바운드 검사
        allowed, result, processed_args = interceptor.intercept_outbound(
            tool_name=tool_name,
            tool_args=kwargs
        )
        
        if not allowed:
            return {
                "error": "DLP Policy Violation",
                "action": result.action.value,
                "violations": [
                    {"rule": v.rule_name, "sensitivity": v.sensitivity.value}
                    for v in result.violations
                ]
            }
        
        # 경고 로깅
        if result.action == DLPAction.ALERT and result.violations:
            print(f"⚠️ DLP Alert: {len(result.violations)} potential issues detected")
        
        # 2. 원본 툴 실행 (처리된 인자로)
        if isinstance(processed_args, dict):
            response = tool_func(*args, **processed_args)
        else:
            response = tool_func(*args, **kwargs)
        
        # 3. 인바운드 검사
        _, inbound_result, processed_response = interceptor.intercept_inbound(
            tool_name=tool_name,
            response_data=response
        )
        
        return processed_response
    
    return wrapped_tool


# === 테스트 ===
def test_dlp_policy():
    """DLP 정책 테스트"""
    print("=" * 60)
    print("🛡️ DLP Policy Engine Test")
    print("=" * 60)
    
    engine = DLPPolicyEngine()
    interceptor = DLPInterceptor(engine)
    
    # 테스트 케이스
    test_cases = [
        {
            "name": "Credit Card Leak",
            "tool": "email_send",
            "data": {"body": "Send payment to 4532-1234-5678-9012"}
        },
        {
            "name": "API Key Exposure",
            "tool": "web_search",
            "data": {"query": "search for api_key=sk-1234567890abcdefghijklmnop"}
        },
        {
            "name": "Safe Query",
            "tool": "search_db",
            "data": {"query": "SELECT name FROM customers"}
        },
        {
            "name": "Internal IP Leak",
            "tool": "log_external",
            "data": {"message": "Server at 192.168.1.100 is down"}
        },
        {
            "name": "Medical Data Leak",
            "tool": "file_upload",
            "data": {"content": "Patient diagnosis: ICD-10 J06.9 Acute URTI"}
        },
    ]
    
    for case in test_cases:
        print(f"\n📝 Test: {case['name']}")
        print(f"   Tool: {case['tool']}")
        
        allowed, result, _ = interceptor.intercept_outbound(
            tool_name=case["tool"],
            tool_args=case["data"]
        )
        
        if allowed:
            status = "✅ ALLOWED"
            if result.violations:
                status += f" (with {len(result.violations)} alerts)"
        else:
            status = f"🚫 BLOCKED ({result.action.value})"
        
        print(f"   Status: {status}")
        
        if result.violations:
            for v in result.violations:
                print(f"   → Violation: {v.rule_name} ({v.sensitivity.value})")
    
    # 통계 출력
    print("\n" + "=" * 60)
    print("📊 DLP Statistics")
    print("=" * 60)
    stats = engine.get_statistics()
    print(f"   Total Violations: {stats['total_violations']}")
    print(f"   Blocked: {stats.get('blocked_count', 0)}")
    print(f"   Masked: {stats.get('masked_count', 0)}")
    
    print("\n✅ DLP Policy Test Complete!")


if __name__ == "__main__":
    test_dlp_policy()
