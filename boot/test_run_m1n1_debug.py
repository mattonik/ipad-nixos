from pathlib import Path

text = Path(__file__).with_name("run_m1n1_debug.sh").read_text()
assert "--pongo-shell" in text
assert "--override-pongo" in text
assert "load_m1n1.py" in text
assert "m1n1-linux.bin" in text
assert "sudo" in text
print("run_m1n1_debug contract passed")
