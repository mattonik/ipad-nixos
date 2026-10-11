#!/usr/bin/env python3
"""Check touch-diag.c's SPI frame constants against the capture analyzer."""
from pathlib import Path
import re
import unittest

import analyze_touch_capture as capture

SOURCE = Path(__file__).with_name("touch-diag.c").read_text()


def frame(name):
    match = re.search(rf"{name}\[\d+\] = \{{([^}}]*)\}}", SOURCE)
    assert match, name
    return bytes(int(x, 0) for x in re.findall(r"0x[0-9a-fA-F]+|\b\d+\b", match.group(1)))


class FrameTests(unittest.TestCase):
    def test_wake(self):
        data = frame("F_WAKE")
        self.assertEqual(len(data), 16)
        self.assertEqual(capture.summarize((data, None))["kind"], "n1_wake_command")

    def test_atn_short_and_long(self):
        self.assertEqual(capture.summarize((frame("F_ATN_SHORT"), None))["kind"],
                         "legacy_short_ack_query")
        self.assertEqual(capture.summarize((frame("F_ATN_LONG"), None))["kind"],
                         "legacy_long_response_query")

    def test_dummy_is_atn_followed_by_seven_filler_words(self):
        data = frame("F_DUMMY")
        self.assertEqual(data, bytes.fromhex("1aa1") + bytes.fromhex("18e1") * 7)

    def test_no_write_or_firmware_frames_in_source(self):
        for opcode in ("0x1e, 0x33", "0x1d, 0x53", "0x1c, 0x73"):
            self.assertNotIn(opcode, SOURCE)

    def test_defaults_are_apples_decoded_mode_2(self):
        self.assertIn("g_spi_mode = 2", SOURCE)
        self.assertNotIn("g_spi_mode = 3", SOURCE)
        self.assertIn("g_spi_hz = 1984000", SOURCE)

    def test_explicit_overrides_still_parsed_and_range_checked(self):
        self.assertIn('"--spi-mode"', SOURCE)
        self.assertIn("g_spi_mode = strtoul(argv[i + 1]", SOURCE)
        self.assertIn('"--spi-hz"', SOURCE)
        self.assertIn("g_spi_mode > 3", SOURCE)

    def test_spi_check_is_not_described_as_read_only(self):
        header = SOURCE.split("*/", 1)[0]
        block = header.split("touch-diag spi-check", 1)[1].split("touch-diag run", 1)[0]
        self.assertIn("NOT read-only", block)
        self.assertIn("NO SPI frame", block)
        self.assertNotIn("read-only handshake", SOURCE)


class DisplaySyncPinmuxTests(unittest.TestCase):
    """Source-level contract for the opt-in GPIO55 pinmux experiment."""

    def test_masks_and_word_math_match_the_decode(self):
        self.assertIn("#define PINMUX_MASK 0x260u", SOURCE)
        self.assertIn("#define PINMUX_PERIPH1 0x220u", SOURCE)
        self.assertIn("#define PINMUX_PERIPH_FIELD 0x60u", SOURCE)
        # Model of the exact word the tool computes, from the recorded baseline.
        saved = 0x00072A82
        self.assertEqual(saved & 0x60, 0, "baseline is PERIPH=0")
        want = (saved & ~0x260) | 0x220
        self.assertEqual((want >> 5) & 3, 1)
        self.assertEqual(want & 0x260, 0x220)
        # Only bits inside the 0x260 mask may change.
        self.assertEqual(saved & ~0x260, want & ~0x260)
        # A pin already in a peripheral function must be refused.
        self.assertNotEqual(0x00072623 & 0x60, 0)

    def test_both_acknowledgements_and_spi_device_required(self):
        self.assertIn('"--display-sync-pinmux"', SOURCE)
        self.assertIn('"--approve-display-sync-pinmux"', SOURCE)
        self.assertIn("ds_flag != ds_approve", SOURCE)
        self.assertIn("--display-sync-pinmux requires --spi-dev", SOURCE)
        # Still behind the existing execute + PMU-write acknowledgement.
        run_branch = SOURCE.split('if (!strcmp(cmd, "run"))', 1)[1]
        self.assertLess(run_branch.index("--execute"), run_branch.index("ds_flag != ds_approve"))

    def test_refuses_a_pin_that_is_already_muxed(self):
        self.assertIn("if (saved & PINMUX_PERIPH_FIELD)", SOURCE)
        self.assertIn("already muxed to a peripheral", SOURCE)

    def test_exact_saved_word_is_restored_and_verified_before_rail_cleanup(self):
        unwind = SOURCE.split("static void unwind(void)", 1)[1].split("static int status", 1)[0]
        self.assertIn("g_gpio_w[GPIO_DISPLAY_SYNC] = g_st.ds_saved", unwind)
        self.assertIn("RESTORE MISMATCH", unwind)
        # Reset is asserted first, then the pin word, then rails and clock.
        order = [unwind.index(m) for m in ("asserting reset", "g_st.ds_saved", "GPIO95 low",
                                           "restoring LDO14", "disabling touch clock")]
        self.assertEqual(order, sorted(order))
        # The state flag is set before the write so every later exit restores it.
        self.assertLess(SOURCE.index("g_st.ds_changed = 1;"),
                        SOURCE.index("g_gpio_w[GPIO_DISPLAY_SYNC] = want"))

    def test_status_path_and_normal_run_keep_gpio_read_only(self):
        self.assertIn("open_pmu() || open_mem(0, 0)", SOURCE)
        self.assertIn("open_mem(1, g_ds_pinmux)", SOURCE)
        self.assertIn("if (gpio_writable)", SOURCE)
        # The only GPIO writes are through g_gpio_w; the read mapping is PROT_READ only.
        self.assertIn("MAP_SHARED, g_mem, GPIO_BASE);\n\tif (p == MAP_FAILED) {\n\t\tperror(\"mmap gpio\");", SOURCE)
        self.assertNotRegex(SOURCE, r"g_gpio\[[^\]]*\]\s*=[^=]")

    def test_no_new_frames_or_levels_were_added(self):
        for name in ("F_DUMMY", "F_WAKE", "F_ATN_SHORT", "F_ATN_LONG"):
            self.assertIn(name, SOURCE)
        self.assertEqual(len(re.findall(r"static const uint8_t F_", SOURCE)), 5)  # 4 handshake frames + the 2-byte wake 19 c1 of --apple-order
        self.assertIn("NOT a\n *                       GPIO-high write", SOURCE)


if __name__ == "__main__":
    unittest.main()
