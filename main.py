"""Cloud Functions (2nd gen) entry point shim.

GCF requires main.py at the source root; the real logic lives in agent/.
"""
from agent.trigger import on_billing_alert  # noqa: F401
