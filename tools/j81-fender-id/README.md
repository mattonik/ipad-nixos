# J81 paired Fender and GPU-ID sample

This freestanding arm64 function is a read-only sampling component for an iPadOS diagnostic host with existing Device mappings. Use one invocation on the J81 post-GPC path, as the sole GPU-ID read for that observation. The delivery is a relocatable object. A diagnostic host with the three live mappings is required for a device measurement.

| Argument | Mapping base (physical) | Read |
|---|---:|---|
| page5_base | 0x20e005000 | PMGR +4, bit 30 gates the remaining reads |
| fender_base | 0x201e00000 | Fender +0, full sleep-control word |
| core_base | 0x201000000 | GPU-ID +0x20 |
| result | Separate writable, aligned CPU RAM | One record owned by the caller |

Pass the three **mapped virtual bases**, keeping the original Fender mapping in a dedicated caller variable separate from logging scratch. Use a fresh result owned by this invocation. The function has no logging calls, device stores, loops, or setup side effects. Between the Fender and ID loads it only orders the accesses and checkpoints the raw control and stage in RAM. It samples page 5 once at the gate. An intervening hardware transition remains possible.

## Build and check

From this directory on an Apple Silicon Mac with Xcode and its iPhoneOS SDK:

```sh
./check.sh
xcrun --sdk iphoneos clang -target arm64-apple-ios15.0 -std=c11 -O2 -ffreestanding -fno-stack-protector -Wall -Wextra -Werror -c probe.c -o probe.o
xcrun vtool -show-build probe.o
xcrun nm -g probe.o
xcrun llvm-objdump -d probe.o
```

Check for the IOS platform, symbol _j81_sample_fender_id, the page-5 bit-30 gate, a 32-bit load from Fender +0 and a 32-bit load from core +0x20. The tests use read-only fixture pages, an inaccessible page to check the skip and partial-result paths, and a host object with identical instruction bytes.

## Diagnostic host contract and collection

In a diagnostic target that already owns these mappings, link probe.o or compile probe.c, include probe.h, and call the following once after the GPC poll succeeds and the core map has been established:

```c
j81_sample_fender_id(page5_va, fender_va, core_va, &sample);
```

After return, emit **one** record containing stage, page5, fender and gpu_id in full hexadecimal, using an unambiguous label such as J81_FENDER_ID. Retain the raw OS log row with its OS-assigned boot UUID and timestamp, together with the exact diagnostic build digest and the same-boot GPC poll record. Read the result after the call or through a separately synchronized retained-record mechanism. Formatting or console I/O inside the sampling interval would change the measurement.

| Stage | Valid result fields | Meaning |
|---|---|---|
| 0 | None | Missing mapping on normal return; an interrupted invocation may also leave stage 0 |
| 1 | page5 | On normal return the gate was clear. In a recovered partial record the last completed checkpoint was page 5. |
| 2 | page5, fender | The control checkpoint completed. The ID result is unavailable. |
| 3 | page5, fender, gpu_id | Both reads completed, including when either returned word is zero. |

A stage-3 record with bit 29 clear and ID 0x00070500 would show a clear sample immediately before a successful ID. With bit 29 set, it would establish coexistence. Neither result identifies when the bit changed or what sets it. If the call never returns, ordinary RAM alone does not guarantee a record survives reset. Mark the run incomplete unless the diagnostic host independently recovered a fresh partial record.
