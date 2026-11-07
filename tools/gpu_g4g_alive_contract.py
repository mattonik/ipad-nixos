#!/usr/bin/env python3
"""Model the observed iOS 8.1 event latch and host-side success promotion."""

STATES = ("APPLE_WAITING", "APPLE_EVENT_0", "APPLE_HOST_ACCEPTED", "FAILED")


def transition(state, event, payload=None):
    """Apply one observed callback/waiter step; no META-start claim is made."""
    if state not in STATES:
        raise ValueError(f"unknown state: {state}")
    if state in ("APPLE_HOST_ACCEPTED", "FAILED"):
        return {"state": state, "payload": payload, "error": None}
    if event == "timeout":
        return {"state": "FAILED", "payload": payload, "error": "timeout"}
    if state == "APPLE_WAITING" and event == "event-0":
        return {"state": "APPLE_EVENT_0", "payload": payload, "error": None}
    if state == "APPLE_EVENT_0" and event == "waiter-promotes-success":
        return {"state": "APPLE_HOST_ACCEPTED", "payload": payload, "error": None}
    return {"state": "FAILED", "payload": payload, "error": "unexpected-event"}


if __name__ == "__main__":
    state = transition("APPLE_WAITING", "event-0", payload=0)
    state = transition(state["state"], "waiter-promotes-success", payload=state["payload"])
    assert state["state"] == "APPLE_HOST_ACCEPTED"
    print("PASS: G4G alive contract is execution-free")
