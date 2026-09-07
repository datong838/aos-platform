"""Isolated extension SDK. No implicit data, tenant, or capability grants."""
from .client import RegistrationContext, serve_registration
from .dispatch import DispatchRef, DispatchWritePort, commit_with_dispatch

__all__ = [
    "DispatchRef",
    "DispatchWritePort",
    "RegistrationContext",
    "commit_with_dispatch",
    "serve_registration",
]
