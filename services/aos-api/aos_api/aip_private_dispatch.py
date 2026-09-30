"""Durable one-command dispatch shared by private services; no authority decisions."""
from aos_api.aip_network_issuer_attempt import AttemptAlreadyRecorded, AttemptUnknown, AttemptConflict


class DispatchReservationBlocked(ValueError):
    pass


def dispatch_once_or_inquire(command, *, inquiry, reserve, send):
    request = command.inquiry() if inquiry else command
    if not inquiry:
        try:
            reserve()
        except (AttemptAlreadyRecorded, AttemptUnknown):
            request = command.inquiry()
        except AttemptConflict:
            raise
        except Exception:
            raise DispatchReservationBlocked('PRIVATE_DISPATCH_RESERVATION_BLOCKED') from None
    try:
        return send(request)
    except Exception:
        # Durable marker is retained even if connection or partial send failed.
        return {'status': 'unresolved'}
