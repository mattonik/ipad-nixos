import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gpu_g4g_alive_contract import transition


def main():
    event = transition("APPLE_WAITING", "event-0", payload=0x1234)
    assert event == {"state": "APPLE_EVENT_0", "payload": 0x1234, "error": None}
    ready = transition(event["state"], "waiter-promotes-success", payload=event["payload"])
    assert ready["state"] == "APPLE_HOST_ACCEPTED"
    assert ready["payload"] == 0x1234
    assert transition("APPLE_WAITING", "event-1")["error"] == "unexpected-event"
    assert transition("APPLE_EVENT_0", "controller-ready")["state"] == "FAILED"
    assert transition("APPLE_EVENT_0", "timeout")["error"] == "timeout"
    print("PASS: G4G alive contract fails closed")


if __name__ == "__main__":
    main()
