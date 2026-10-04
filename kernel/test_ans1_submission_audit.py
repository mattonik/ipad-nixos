#!/usr/bin/env python3
"""Reproduce ANS1 submission-boundary behavior using checked-in C and host stubs.

These are characterization tests of known gaps, not driver correctness tests.
No hardware, block device, firmware or Nix environment is accessed.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PRELUDE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;
typedef uint64_t u64;
typedef uint64_t dma_addr_t;
typedef int blk_status_t;
#define BIT(n) (1U << (n))
#define BLK_STS_OK 0
#define BLK_STS_IOERR 1
#define BLK_STS_TIMEOUT 2
#define ASP_MSG_TYPE 0
#define ASP_MSG_TYPE_SUBMIT 0
#define ASP_SUBMIT_TAG 0
#define ASP_SUBMIT_OP 0
#define ASP_SUBMIT_OP_RING 0
/* Mailbox encoding is outside this test; preserve call/error behavior. */
#define FIELD_PREP(mask,value) ((u64)(value))
#define dma_wmb() ((void)0)
static unsigned warnings, sends, starts;
static int send_result;
#define WARN_ON(x) ((x) ? (++warnings, 1) : 0)
struct asp_cmd_hdr { unsigned char tag; unsigned char rest[47]; };
struct scatterlist { dma_addr_t addr; unsigned len; };
struct asp_iod { struct asp_cmd_hdr cmd; struct scatterlist *sg; int nr_mapped; };
struct apple_asp { void *q; void *rtk; unsigned ep; };
struct asp_queue { struct apple_asp *asp; };
struct request { struct asp_iod *iod; };
struct request_queue { struct asp_queue *queuedata; };
struct blk_mq_hw_ctx { struct request_queue *queue; };
struct blk_mq_queue_data { struct request *rq; };
#define for_each_sg(list,sg,n,i) for ((i)=0,(sg)=(list); (i)<(n); ++(i),++(sg))
#define sg_dma_len(sg) ((sg)->len)
#define sg_dma_address(sg) ((sg)->addr)
static struct apple_asp *queue_to_apple_asp(struct asp_queue *q) { return q->asp; }
static struct asp_iod *blk_mq_rq_to_pdu(struct request *r) { return r->iod; }
/* Request construction and block-layer limits are intentionally not simulated. */
static int asp_setup_cmd(struct asp_queue *q, struct request *r)
{ (void)q; (void)r; return BLK_STS_OK; }
static void blk_mq_start_request(struct request *r) { (void)r; ++starts; }
static int apple_rtkit_send_message(void *rtk, unsigned ep, u64 msg, void *cb, bool atomic)
{ (void)rtk; (void)ep; (void)msg; (void)cb; (void)atomic; ++sends; return send_result; }
'''
TESTS = r'''
/* Extra slot is a sentinel: observe the invalid-tag copy without invoking UB. */
static _Alignas(u32) unsigned char queue[ASP_QUEUE_SIZE + ASP_TAG_SIZE];
static struct apple_asp asp = {.q=queue};
static struct asp_queue aq = {.asp=&asp};
static struct request_queue rq = {.queuedata=&aq};
static struct blk_mq_hw_ctx hctx = {.queue=&rq};
static struct asp_iod iod;
static struct request req = {.iod=&iod};
static struct blk_mq_queue_data bd = {.rq=&req};
static void reset(void)
{ memset(queue,0xcc,sizeof(queue)); memset(&iod,0,sizeof(iod)); warnings=sends=starts=0; send_result=0; }
int main(void)
{
    assert(ASP_CMD_MAX_SECTORS == 4068);
    for (unsigned tag=0; tag<ASP_NUM_TAGS; ++tag) {
        reset(); iod.cmd.tag=tag;
        struct scatterlist sg = {.addr=0x100000, .len=4096};
        iod.sg=&sg; iod.nr_mapped=1;
        assert(apple_asp_queue_rq(&hctx,&bd)==BLK_STS_OK);
        assert(warnings==0 && sends==1 && starts==1);
        assert(*(u32 *)(queue+tag*ASP_TAG_SIZE+ASP_CMD_HDR_SIZE)==0x100);
        assert(queue[ASP_QUEUE_SIZE]==0xcc);
    }
    reset(); struct scatterlist sg = {.addr=0x100000, .len=4068*4096};
    iod.sg=&sg; iod.nr_mapped=1;
    assert(apple_asp_queue_rq(&hctx,&bd)==BLK_STS_OK && warnings==0);
    assert(*(u32 *)(queue+ASP_TAG_SIZE-4)==0x100+4067);
    assert(queue[ASP_TAG_SIZE]==0xcc);

    reset(); sg.len=4069*4096; iod.sg=&sg; iod.nr_mapped=1;
    assert(apple_asp_queue_rq(&hctx,&bd)==BLK_STS_OK);
    assert(warnings==1 && sends==1 && starts==1);
    assert(queue[ASP_TAG_SIZE]==0xcc); /* Bound holds, but submission continues. */

    reset(); sg.len=1; iod.sg=&sg; iod.nr_mapped=1;
    assert(apple_asp_queue_rq(&hctx,&bd)==BLK_STS_OK);
    assert(warnings==1 && sends==1);
    assert(*(u32 *)(queue+ASP_TAG_SIZE-4)==0x100+4067);

    reset(); sg.len=4096; sg.addr=0x100001; iod.sg=&sg; iod.nr_mapped=1;
    assert(apple_asp_queue_rq(&hctx,&bd)==BLK_STS_OK && warnings==0);
    assert(*(u32 *)(queue+ASP_CMD_HDR_SIZE)==0x100); /* Offset discarded. */

    reset(); iod.cmd.tag=ASP_NUM_TAGS;
    assert(apple_asp_queue_rq(&hctx,&bd)==BLK_STS_IOERR);
    assert(warnings==1 && sends==0 && starts==1);
    assert(queue[ASP_QUEUE_SIZE]==ASP_NUM_TAGS); /* Copy precedes guard. */

    reset(); send_result=-ETIMEDOUT;
    assert(apple_asp_queue_rq(&hctx,&bd)==BLK_STS_TIMEOUT && sends==1 && starts==1);
    reset(); send_result=-EIO;
    assert(apple_asp_queue_rq(&hctx,&bd)==BLK_STS_IOERR && sends==1 && starts==1);
    puts("PASS: 16 valid tags, exact SGL capacity, truncated SGL still submitted, short-length underflow, address truncation, late tag guard, send errors");
    puts("Characterization only: synthetic invalid requests do not establish block-layer reachability or hardware behavior");
    return 0;
}
'''


def extract_function(source, name):
    match = re.search(r"^static [^;{}]*\b" + name + r"\([^;{}]*\)\n\{", source, re.M)
    if not match:
        raise ValueError(f"cannot locate {name}")
    # Reviewed functions have no braces inside comments/strings.
    depth = 1
    end = match.end()
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[match.start():end] + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default=os.environ.get("CC", "gcc"))
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    patch = (ROOT / "kernel/patches/0015-ans1-storage-driver-and-core-support.patch").read_text()
    section = patch.split("+++ b/drivers/block/asp.c\n", 1)[1].split("\ndiff --git ", 1)[0]
    source = "\n".join(line[1:] for line in section.splitlines() if line.startswith("+")) + "\n"
    with tempfile.TemporaryDirectory(prefix="ans1-submission-") as directory:
        root = Path(directory)
        target = root / "drivers/block/asp.c"
        target.parent.mkdir(parents=True)
        target.write_text(source)
        subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-d", str(root), "-i",
                        str(ROOT / "kernel/patches/0012-ans1-asp-observation-only.patch")], check=True)
        source = target.read_text()
        constants = []
        for name in ("ASP_TAG_SIZE", "ASP_NUM_TAGS", "ASP_QUEUE_SIZE", "ASP_CMD_HDR_SIZE",
                     "ASP_CMD_MAX_SECTORS", "ASP_LBA_SHIFT", "ASP_LBA_SIZE"):
            constants.append(re.search(r"^#define\s+" + name + r"\b(?:[^\n]*\\\n)*[^\n]*", source, re.M)[0])
        functions = "".join(extract_function(source, name) for name in
                            ("asp_q_cmd_hdr", "asp_q_cmd_data", "apple_asp_submit_cmd",
                             "asp_setup_hw_sgl", "apple_asp_queue_rq"))
        file = root / "audit.c"
        file.write_text(PRELUDE + "\n".join(constants) + "\n" + functions + TESTS)
        executable = root / "audit"
        # The extracted driver compares a signed index against sizeof-derived capacity.
        command = [args.cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                   "-Wno-sign-compare", "-O1", "-g"]
        if args.sanitize:
            command += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        subprocess.run(command + [str(file), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    main()
