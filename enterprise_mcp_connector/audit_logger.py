# audit_logger.py
"""
감사 로깅 시스템
Audit Logging System

모든 데이터 접근을 추적 가능하게 기록하고
보안 위반 시 실시간 알림을 제공합니다.
GDPR, HIPAA 등 규정 준수에 필수적입니다.
"""

import json
from datetime import datetime
from typing import Any, Dict
from enum import Enum
from dataclasses import dataclass


class AuditEventType(Enum):
    """감사 이벤트 타입 (Audit Event Types)
    
    - DATA_ACCESS: 데이터 접근
    - DATA_QUERY: 데이터 쿼리
    - SECURITY_VIOLATION: 보안 위반
    - TOOL_EXECUTION: 도구 실행
    """
    DATA_ACCESS = "data_access"
    DATA_QUERY = "data_query"
    SECURITY_VIOLATION = "security_violation"
    TOOL_EXECUTION = "tool_execution"


@dataclass
class AuditLog:
    """감사 로그 엔트리 (Audit Log Entry)
    
    Attributes:
        event_type: 이벤트 타입
        user_id: 사용자 ID
        resource: 접근한 리소스
        action: 수행한 액션
        result: 결과 (success/error/unauthorized)
        timestamp: 타임스탬프
        metadata: 추가 메타데이터
    """
    event_type: AuditEventType
    user_id: str
    resource: str
    action: str
    result: str
    timestamp: datetime
    metadata: Dict[str, Any]

    def to_json(self) -> str:
        """JSON 형식으로 변환
        
        Returns:
            str: JSON 문자열
        """
        return json.dumps({
            "event_type": self.event_type.value,
            "user_id": self.user_id,
            "resource": self.resource,
            "action": self.action,
            "result": self.result,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }, ensure_ascii=False)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 형식으로 변환
        
        Returns:
            Dict: 감사 로그 딕셔너리
        """
        return {
            "event_type": self.event_type.value,
            "user_id": self.user_id,
            "resource": self.resource,
            "action": self.action,
            "result": self.result,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class AuditLogger:
    """감사 로거 - 모든 데이터 접근을 기록
    
    실제 환경에서는 SIEM 시스템(Splunk, ELK 등)으로 전송합니다.
    """

    def __init__(self, log_file: str = "audit.log"):
        """감사 로거 초기화
        
        Args:
            log_file: 로그 파일 경로
        """
        self.log_file = log_file
        self._logs = []  # 메모리 내 로그 저장

    def log(self, audit_log: AuditLog):
        """감사 로그 기록
        
        Args:
            audit_log: 감사 로그 엔트리
        """
        # 메모리에 저장
        self._logs.append(audit_log)
        
        # 파일에 기록
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(audit_log.to_json() + "\n")
        except Exception as e:
            print(f"⚠️ Failed to write audit log: {e}")

        # 실시간 모니터링 (심각한 이벤트는 알림)
        if audit_log.event_type == AuditEventType.SECURITY_VIOLATION:
            self._alert_security_team(audit_log)

    def _alert_security_team(self, log: AuditLog):
        """보안 팀에 알림
        
        실제로는 PagerDuty, Slack, Email 등과 연동합니다.
        
        Args:
            log: 보안 위반 로그
        """
        alert_message = (
            f"🚨 SECURITY ALERT 🚨\n"
            f"User: {log.user_id}\n"
            f"Attempted unauthorized access to: {log.resource}\n"
            f"Action: {log.action}\n"
            f"Time: {log.timestamp.isoformat()}\n"
            f"Metadata: {json.dumps(log.metadata)}"
        )
        print(alert_message)

    def get_logs(self, user_id: str = None, event_type: AuditEventType = None) -> list:
        """로그 조회
        
        Args:
            user_id: 필터링할 사용자 ID (옵션)
            event_type: 필터링할 이벤트 타입 (옵션)
            
        Returns:
            list: 필터링된 감사 로그 목록
        """
        filtered_logs = self._logs
        
        if user_id:
            filtered_logs = [log for log in filtered_logs if log.user_id == user_id]
        
        if event_type:
            filtered_logs = [log for log in filtered_logs if log.event_type == event_type]
        
        return filtered_logs

    def get_summary(self) -> Dict[str, Any]:
        """로그 요약 통계
        
        Returns:
            Dict: 이벤트 타입별 카운트 및 통계
        """
        summary = {
            "total_events": len(self._logs),
            "by_event_type": {},
            "by_user": {},
            "security_violations": 0
        }
        
        for log in self._logs:
            # 이벤트 타입별 카운트
            event_type = log.event_type.value
            summary["by_event_type"][event_type] = summary["by_event_type"].get(event_type, 0) + 1
            
            # 사용자별 카운트
            summary["by_user"][log.user_id] = summary["by_user"].get(log.user_id, 0) + 1
            
            # 보안 위반 카운트
            if log.event_type == AuditEventType.SECURITY_VIOLATION:
                summary["security_violations"] += 1
        
        return summary
