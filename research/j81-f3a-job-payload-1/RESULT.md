# Research request 32 result: the empty compute job's payload bytes (J81, for J1)

Sources:
- **Mesa's Imagination driver** (Orchard's public fork `OrchardLinux/mesa`): `csbgen/rogue/cdm.xml`, `csbgen/rogue/cr.xml`, `vulkan/pds/pvr_pds.c`, `pvr_rogue_pds_encode.h`/`pvr_rogue_pds_defs.h`, `pvr_arch_job_context.c`;
- **Orchard's kernel** (`OrchardLinux/linux` `059fadee`): `pvr_apple.c`, `pvr_apple.h`, `pvr_apple_layout.h`, `pvr_apple_chip.h`, `pvr_apple_s8003.c`;
- the 19H394 kext and the decoded firmware.

All of it was read on GitHub; nothing was downloaded or run. Tags: **source** (Mesa, public), **orchard**, **code**, **fwdis**, **inferred**. Words are quoted from the public sources; there is no Apple binary content.

## Short answer

- **The control stream for an empty job is one word, `0x80000000`** (CDMCTRL STREAM_TERMINATE: block type 2 in bits 31:30). It is 4 bytes, the base is 32-bit aligned, and it goes at a page start (Mesa's 64-byte guard rule). Orchard's kernel writes exactly this word (t1).
- **The PDS program is a single HALT, `0xd3000000`,** not Mesa's fence-terminate program. Orchard's kernel uses one HALT "for the terminate and context PDS programs". The encoding checks against Mesa's `pvr_pds_inst_encode_halt` (SP opcode `0xd` << 28, HALT 6 << 23).

  Mesa's fence-terminate program (a barrier, an optional software barrier, then DOUTC) depends on device features and isn't needed for an empty job (t1).
- **The descriptor words decode as CR_CDM_*_PDS1** (t2):
  - `0x00a00004` = unified_size 5, data_size 2;
  - `0x00900004` = unified_size 4, data_size 2;
  - all other fields 0.

  These are Apple's values, not Mesa's: Mesa's terminate PDS1 sets seq_dep, common_shared and fence. On 19H394 user space supplies the word, so J1 uses the A8-family `0x00900004` first (inferred).

  By the record layout, `+0x21c`/`+0x224` feed CDM_CONTEXT_PDS0/PDS1. The firmware's write of RGX `0x4b0` reads W `+0x224`. `+0x23c`/`+0x244` then match CDM_TERMINATE_PDS/PDS1 (inferred).
- **Mirror Orchard's VM layout in slot 1** (t3, t4):
  - a zeroed page at VA 0;
  - an 8 KiB data page at **VA `0x200000`**, with the stream at `+0` and the HALT at `+0x1000`;
  - the hardware objects.

  Point the record's stream base and both "terminate" fields at `0x200000`. Point every PDS program field (code | data << 32) at the HALT, `0x201000`.

## Q1: the control stream (t1)

The stream is the single word `0x80000000` at the start of the page. The base register field covers bits 39:2.

## Q2: the PDS program (t1, t4)

Use the HALT (`0xd3000000`), with code and data both at `0x201000`. The PDS address fields are 28 bits (31:4), so an address fits in 32 bits. Either it is relative to the PDS exec base (Orchard: "the firmware's PDS and USC code bases are the code heaps' bases"; PDS heap at `0x2a_0000_0000`), or a low absolute VA. Orchard's own HALT sits at `0x201000` and is named in every compute job. If J1 faults there, J1d uses offset 0 from the heap base instead.

## Q3: the descriptor words (t2) and record fields (t3)

Each field is listed with Orchard's semantics (`pvr_apple.h`):
- `terminate` = the address of the stream's terminate word;
- `tail` is 16-byte aligned;
- `pds_*` = code | data << 32;
- `state[4]` = context buffers, 0 for an empty job.

## Q4: placement (t4)

- **VA 0:** a zeroed page. Orchard maps it because fragment jobs write there; iPadOS keeps it mapped.
- **VA `0x200000`:** the data page.
- **The hardware objects** at `0x8_00000000`.
- **Flags:** plain (valid | SLC bypass, no protect).

Nothing else is needed for a job with no dispatch (inferred).

## Q5: cross-check (t5)

Every Orchard A9 compute job carries this terminate stream and HALT: the kernel maps the data page into every VM and Mesa names it. A job with no kernel at all isn't shown in their public code. The boots are J1 with the values above, then J1b (`0x00a00004`), then J1d (the relative PDS address).

## Not resolved

- Whether 19H394's PDS addresses are exec-base-relative or absolute (J1 against J1d).
- The exact descriptor value 19H394's user driver uses.
- The firmware's TERMINATE_PDS register writes, which weren't located in the decode.

## Files

- `t1-payload-words.tsv`: Q1/Q2, the payload words with byte offsets.
- `t2-descriptors.tsv`: Q3, the field decode of the two descriptor words and which register each feeds.
- `t3-record-fields.tsv`: Q3, the record fields for an empty job.
- `t4-placement.tsv`: Q4, slot 1's VA layout and the PDS address convention.
- `t5-next-boots.tsv`: Q5, the ranked boots and the Orchard cross-check.
- `SHA256SUMS`.
