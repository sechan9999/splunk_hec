"""Kubernetes HPA Pod Autoscaler Module for Unified Ops AX.

Automatically scales Kubernetes agent deployment worker pods (unified-ops-agent-pool)
in response to latency spikes, queue congestion, or anomaly events.
"""

import logging
import os
import subprocess
import time
from typing import Dict, Any, Optional

logger = logging.getLogger("k8s_autoscaler")


class K8sHPAAutoscaler:
    """Kubernetes Deployment Replica & HPA Autoscaler."""

    def __init__(
        self,
        deployment_name: str = "unified-ops-agent-pool",
        namespace: str = "default",
        min_replicas: int = 2,
        max_replicas: int = 10,
        cooldown_sec: int = 300
    ):
        self.deployment_name = deployment_name
        self.namespace = namespace
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.cooldown_sec = cooldown_sec
        self.current_replicas = min_replicas
        self.last_scaled_at: Optional[float] = None
        self.scaling_history: list = []

    def scale_deployment(self, target_replicas: int, reason: str = "latency_spike") -> Dict[str, Any]:
        """Scales deployment worker pod replicas to target count."""
        target_replicas = max(self.min_replicas, min(self.max_replicas, target_replicas))
        previous_replicas = self.current_replicas
        
        if target_replicas == previous_replicas:
            return {
                "scaled": False,
                "reason": f"replicas already at {target_replicas}",
                "current_replicas": self.current_replicas
            }

        # Check cooldown
        if self.last_scaled_at and (time.time() - self.last_scaled_at) < 5:
            return {
                "scaled": False,
                "reason": "cooldown_active",
                "current_replicas": self.current_replicas
            }

        # Attempt live kubectl command if in K8s environment, else simulate
        cmd = f"kubectl scale deployment {self.deployment_name} --replicas={target_replicas} -n {self.namespace}"
        try:
            # Check if kubectl binary exists
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2)
            kubectl_success = res.returncode == 0
        except Exception:
            kubectl_success = False

        self.current_replicas = target_replicas
        self.last_scaled_at = time.time()
        
        event = {
            "timestamp": time.time(),
            "deployment": self.deployment_name,
            "previous_replicas": previous_replicas,
            "new_replicas": target_replicas,
            "reason": reason,
            "kubectl_executed": kubectl_success
        }
        self.scaling_history.append(event)
        logger.warning(
            f"[K8s HPA] Scaling Event: [{self.deployment_name}] "
            f"{previous_replicas} -> {target_replicas} replicas (Reason: {reason})"
        )
        return {
            "scaled": True,
            "deployment": self.deployment_name,
            "previous_replicas": previous_replicas,
            "new_replicas": target_replicas,
            "reason": reason,
            "kubectl_success": kubectl_success
        }

    def trigger_latency_scaleout(self, latency_ms: float) -> Dict[str, Any]:
        """Automatically scales out pod replicas upon detecting latency spike."""
        if latency_ms >= 5000:
            target = 8
        elif latency_ms >= 3000:
            target = 5
        else:
            target = self.min_replicas

        return self.scale_deployment(target, reason=f"latency_spike_{latency_ms:.0f}ms")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "deployment_name": self.deployment_name,
            "namespace": self.namespace,
            "current_replicas": self.current_replicas,
            "min_replicas": self.min_replicas,
            "max_replicas": self.max_replicas,
            "total_scaling_events": len(self.scaling_history),
            "last_event": self.scaling_history[-1] if self.scaling_history else None
        }
