#!/usr/bin/env python3
"""Model the recovered G4G alive handshake without hardware or firmware."""

STATES = ("META_STARTED", "APPLE_EVENT_0", "FIRMWARE_READY", "FAILED")


def transition(state, event, controller_ready=False, payload=None):
    """Return the next state and retained event payload; fail closed."""
    if state not in STATES:
        raise ValueError(f"unknown state: {state}")
    if state in ("FIRMWARE_READY", "FAILED"):
        return {"state": state, "payload": payload, "error": None}
    if event == "timeout":
        return {"state": "FAILED", "payload": payload, "error": "timeout"}
    if state == "META_STARTED" and event == "event-0":
        return {"state": "APPLE_EVENT_0", "payload": payload, "error": None}
    if state == "APPLE_EVENT_0" and event == "controller-ready" and controller_ready:
        return {"state": "FIRMWARE_READY", "payload": payload, "error": None}
    return {"state": "FAILED", "payload": payload, "error": "unexpected-event"}


if __name__ == "__main__":
    state = transition("META_STARTED", "event-0", payload=0)
    state = transition(state["state"], "controller-ready", controller_ready=True,
                       payload=state["payload"])
    assert state["state"] == "FIRMWARE_READY"
    print("PASS: G4G alive contract is execution-free")
