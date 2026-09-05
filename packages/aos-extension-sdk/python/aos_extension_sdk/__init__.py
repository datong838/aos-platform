"""Isolated extension registration SDK. No implicit data or capability grants."""
from .client import RegistrationContext, serve_registration

__all__ = ["RegistrationContext", "serve_registration"]
