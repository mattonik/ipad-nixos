# J81 allocation lifetime model

`tools/gpu_g4g_allocation_model.py` now represents the recovered initializer
as thirteen allocation classes: four registered firmware views, four
view-like auxiliary objects, three host-control structures, and two scratch
buffers. Every class carries the observed allocate/map/address-view/retain/
release lifecycle, while all runtime addresses remain unresolved.

The model is an adapter checklist, not a loader. It is execution-disabled and
requires mapped/backing address pairs, Linux ownership/cache semantics, DART
IOVA assignment, and release ordering before any firmware operation can be
considered.
