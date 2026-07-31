"""Event worker — background poller over the outbox."""
import time

from app.db import SessionLocal
from app.domain.models import ASTicket, Customer, Employee
from app.domain.services import open_as_ticket
from app.worker import EventWorker


def test_run_once_drains_outbox_and_fires_agent(session):
    cust = Customer(name="Acme")
    emp = Employee(name="Park", role="production")
    session.add_all([cust, emp])
    session.commit()
    ticket_id = open_as_ticket(session, customer_id=cust.id, summary="전원 부품 고장").id

    worker = EventWorker(SessionLocal)
    result = worker.run_once()

    assert result["triggered"] >= 1
    session.expire_all()
    assert session.get(ASTicket, ticket_id).status == "assigned"  # triage fired via worker
    assert worker.stats["cycles"] == 1
    assert worker.stats["triggered"] >= 1


def test_run_once_is_idempotent(session):
    cust = Customer(name="Acme")
    emp = Employee(name="Park", role="production")
    session.add_all([cust, emp])
    session.commit()
    open_as_ticket(session, customer_id=cust.id, summary="전원 고장")

    worker = EventWorker(SessionLocal)
    worker.run_once()
    assert worker.run_once()["triggered"] == 0  # nothing new to fire on replay


def test_worker_thread_start_and_stop():
    worker = EventWorker(SessionLocal, interval=0.05)
    assert worker.running is False
    worker.start()
    assert worker.running is True
    time.sleep(0.12)  # let it spin a couple cycles on an empty outbox
    worker.stop()
    assert worker.running is False
    assert worker.stats["cycles"] >= 1
