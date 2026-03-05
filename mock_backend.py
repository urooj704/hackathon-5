"""
Lightweight mock backend for FlowForge Support Form.
Runs without PostgreSQL / Redis — all data is in-memory.
"""

import random
import string
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="FlowForge Mock Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory ticket store
tickets: dict = {}


def make_ticket_id():
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"TKT-{suffix}"


# ── Models ──────────────────────────────────────────────────────────────────

class SubmitRequest(BaseModel):
    name: str
    email: str
    subject: str
    category: str = "general"
    priority: str = "medium"
    message: str


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "healthy", "env": "mock", "timestamp": datetime.utcnow().isoformat()}


@app.post("/channels/web-form/submit")
def submit_form(body: SubmitRequest):
    ticket_id = make_ticket_id()
    tickets[ticket_id] = {
        "ticket_id": ticket_id,
        "status": "open",
        "name": body.name,
        "email": body.email,
        "subject": body.subject,
        "category": body.category,
        "priority": body.priority,
        "message": body.message,
        "created_at": datetime.utcnow().isoformat(),
        "messages": [
            {
                "body": body.message,
                "is_from_customer": True,
            },
            {
                "body": (
                    f"Hi {body.name}, thanks for reaching out! "
                    f"We've received your request about \"{body.subject}\". "
                    "Our AI assistant is looking into this and will follow up shortly. "
                    "Your ticket ID is " + ticket_id + "."
                ),
                "is_from_customer": False,
            }
        ],
    }
    # Simulate agent reply after a moment
    tickets[ticket_id]["status"] = "waiting_customer"

    return {"ticket_id": ticket_id, "status": "open", "message": "Request received."}


@app.get("/channels/web-form/ticket/{ticket_id}")
def get_ticket(ticket_id: str):
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
