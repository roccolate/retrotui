"""Window-to-window IPC mediated by the app's EventBus."""

import logging
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

_IPC_ERRORS = (AttributeError, LookupError, OSError, TypeError, ValueError)


@dataclass(frozen=True)
class IPCMessage:
    """A directed message between windows."""

    sender_id: int
    target_id: int  # -1 for broadcast
    channel: str
    payload: object = None


class IPCRouter:
    """Routes messages between windows using the EventBus.

    Windows never hold references to each other.  The router resolves
    targets through the app's window list.
    """

    IPC_TOPIC = "ipc.message"

    def __init__(self, event_bus, window_resolver):
        """
        Parameters
        ----------
        event_bus : EventBus
        window_resolver : callable returning the current window list
        """
        self._bus = event_bus
        self._resolve_windows = window_resolver

    def send(self, sender_id, target_id, channel, payload=None):
        """Send a message to a specific window.  Returns True if delivered."""
        msg = IPCMessage(
            sender_id=sender_id,
            target_id=target_id,
            channel=channel,
            payload=payload,
        )
        for win in self._resolve_windows():
            if getattr(win, "id", None) == target_id:
                handler = getattr(win, "on_ipc_message", None)
                if not callable(handler):
                    return False
                try:
                    handler(msg)
                    return True
                except _IPC_ERRORS:
                    LOGGER.debug("IPC delivery error to window %d", target_id, exc_info=True)
                    return False
        return False

    def broadcast(self, sender_id, channel, payload=None):
        """Broadcast a message to all windows.  Returns delivery count."""
        msg = IPCMessage(
            sender_id=sender_id,
            target_id=-1,
            channel=channel,
            payload=payload,
        )
        count = 0
        for win in self._resolve_windows():
            if getattr(win, "id", None) == sender_id:
                continue
            handler = getattr(win, "on_ipc_message", None)
            if not callable(handler):
                continue
            try:
                handler(msg)
                count += 1
            except _IPC_ERRORS:
                LOGGER.debug(
                    "IPC broadcast error to window %d",
                    getattr(win, "id", "?"),
                    exc_info=True,
                )
        self._bus.publish(self.IPC_TOPIC, data=msg, source=sender_id)
        return count
