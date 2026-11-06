# J81 allocation-class boundary

The decompiled initializer shows a clear boundary after the eight repeated
`param[3]..param[10]` allocations:

1. Eight same-policy objects use flags `0x22`, selector `0x80007`, and each
   receives its own mapped view plus a page-list allocation. These are the
   view-like set extracted by the new tool; only the first four are proven to
   feed the packed firmware registration offsets.
2. Three later `0x22` objects (`param[0x27]`, `[0x29]`, `[0x4d]`) are larger
   variable-size structures. Their mapped views are consumed to build host
   control structures and subfield pointers, not passed through the four-view
   registration call.
3. Two final `0x3ff` objects use flags `0x21` and `0x23`; they are auxiliary
   in/out scratch buffers and are not firmware segment views.

This classification prevents a common adapter mistake: treating every
`0x80007` mapping as one of the four packed firmware views. The safe Linux
plan is therefore four registered firmware views, four additional
view-like/auxiliary allocations that need ownership modeling, three host
structures, and two scratch buffers. No runtime addresses are inferred.
