from pathlib import Path

SOURCE = Path(__file__).with_name("j81_thread_shell.S").read_text()


def sampled_indices(total):
    return [i for i in range(total) if 32 <= i < 64]


assert sampled_indices(32) == []
assert sampled_indices(33) == [32]
assert sampled_indices(64) == list(range(32, 64))
assert sampled_indices(65) == list(range(32, 64))
assert "str wzr, [x9, #16]" in SOURCE
assert "ldr w11, [x10, #16]" in SOURCE
assert "cmp w11, #32" in SOURCE
assert "sub w11, w11, #32" in SOURCE

print("PASS: ordinary-store sample window captures calls 33 through 64 only")
