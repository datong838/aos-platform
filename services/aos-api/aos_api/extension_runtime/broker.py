"""AR1-b registration-only broker; persisted runtime grants arrive in AR1-c."""


class RegistrationBroker:
    def dispatch(self, method: str, payload: dict):
        # Registration never receives data, command, network, or capability ports.
        # This broker must not be reused as the later authorized business broker.
        raise PermissionError("registration phase has no business ports")
