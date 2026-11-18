from audit_gpu_store_export import summarize

prefix = "B0 D0:00000000>00000000 A0:00000000>00000000 M00000001 O"
row = "P1T1:00000000/80000000:00020320=0000030f;"
bridge = row.replace("/80000000", "/00000000")
result = summarize([prefix + "00000020 " + row] * 17)
assert result["sample_full"] and result["staged_minus_printed"] == 15
assert result["region0_gfx_word_values"] == {"0000030f": 17}
result = summarize([prefix + "00000001 " + bridge + "?;", prefix + "00000001 " + row])
assert (result["ordinary_rows_in_text"], result["other_rows"], result["unready_rows"]) == (1, 1, 1)
for bad in ([], [prefix + "00000113 "], [prefix + "00000000 " + row],
            [prefix + "00000001 " + row[:-1]], [prefix + "00000001 ", prefix + "00000002 "]):
    try:
        summarize(bad)
    except ValueError:
        continue
    raise AssertionError("accepted inconsistent export")
print("PASS: store-export accounting")
