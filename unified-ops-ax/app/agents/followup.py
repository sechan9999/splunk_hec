"""Auto Follow-up agent. Drafts a customer-tailored message after delivery,
but NEVER sends it. Sending is an external action, so it is gated behind an
explicit human approval (approve_and_send) — the HITL boundary. The agent
only emits a draft; approval is what produces followup.sent."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway, get_gateway
from app.connectors.notify import build_notifier
from app.domain.models import Customer, FollowUp, Order
from app.events.activity import emit
from app.security.pii import get_cipher


class FollowUpAgent:
    def __init__(self, session: Session, gateway: AIGateway | None = None, notifier=None) -> None:
        self.session = session
        self.gateway = gateway or get_gateway()
        self._notifier = notifier or build_notifier()

    def draft_for_order(self, order_id: str) -> dict:
        order = self.session.get(Order, order_id)
        if order is None:
            raise ValueError(f"order not found: {order_id}")
        customer = self.session.get(Customer, order.customer_id)

        text = self._draft_message(customer, order)
        followup = FollowUp(customer_id=customer.id, channel="email", status="draft", draft=text)
        self.session.add(followup)
        self.session.flush()
        emit(self.session, type="followup.drafted", subject_type="customer", subject_id=customer.id,
             payload={"followup_id": followup.id, "order_id": order.id}, source="agent")
        self.session.commit()

        return {"followup_id": followup.id, "status": followup.status, "draft": text, "requires_approval": True}

    def approve_and_send(self, followup_id: str, *, approver_employee_id: str | None = None) -> dict:
        """Human gate. In production this is where the email/SMS adapter fires;
        the agent can never reach here on its own."""
        followup = self.session.get(FollowUp, followup_id)
        if followup is None:
            raise ValueError(f"followup not found: {followup_id}")
        if followup.status == "sent":
            return {"followup_id": followup.id, "status": "sent", "already": True}

        # Resolve the recipient (PII decrypted) and deliver via the notifier.
        customer = self.session.get(Customer, followup.customer_id)
        cipher = get_cipher()
        to = None
        if customer:
            to = cipher.decrypt(customer.phone) if followup.channel == "sms" else cipher.decrypt(customer.email)

        result = None
        if to:
            result = self._notifier.send(to=to, body=followup.draft or "",
                                         subject="문의 팔로업", channel=followup.channel)

        delivered = bool(result)
        message_id = result.message_id if result else None
        emit(self.session, type="followup.sent", subject_type="customer", subject_id=followup.customer_id,
             payload={"followup_id": followup.id, "delivered": delivered, "message_id": message_id},
             source="app", actor_employee_id=approver_employee_id)
        self.session.commit()
        return {"followup_id": followup.id, "status": "sent", "delivered": delivered, "message_id": message_id}


    @staticmethod
    def list_pending(session: Session) -> list[dict]:
        """List all queued follow-up drafts awaiting human sign-off."""
        drafts = session.query(FollowUp).filter(FollowUp.status == "draft").all()
        return [
            {
                "followup_id": f.id,
                "customer_id": f.customer_id,
                "channel": f.channel,
                "status": f.status,
                "draft": f.draft,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in drafts
        ]

    def _draft_message(self, customer: Customer, order: Order) -> str:
        fallback = (
            f"{customer.name}님, 주문(주문번호 {order.id[:8]})이 잘 전달되었는지 확인차 연락드립니다. "
            f"이용에 불편한 점이나 문의사항이 있으시면 언제든 회신 부탁드립니다. 감사합니다."
        )
        try:
            result = self.gateway.chat([
                {"role": "system", "content": "You draft a short, warm post-delivery follow-up message in Korean. "
                                              "Do not invent facts. Output the message only."},
                {"role": "user", "content": f"Customer: {customer.name}. Order total: {order.total_amount}."},
            ])
            text = result.get("content", "").strip()
            return text or fallback
        except Exception:
            return fallback
