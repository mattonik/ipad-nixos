# Framebuffer square check (2026-11-22)

Question: are the breadcrumb squares visible on the panel at all? (None were seen in the successful runs.)

Method: fresh boot of the id bundle, `tools/j81_fb_square_check.py 4` stops the dashboard and writes four
32x32 white squares through /dev/fb0 at the module's geometry (x0 = 8 + 40*(n-1), y0 = height - 40; fb 1536x2048,
stride 6144, 32 bpp, DT node framebuffer@87d0de000). /dev/mem writes to that address fail (outside System RAM): use /dev/fb0.

Result: the user saw four white squares at the bottom-left. So the geometry is on screen and scaling is not the cause.
Likely reason none were seen earlier: the dashboard repaints every 5 s and the runs completed (no hang) long before looking.
Not yet shown: that the module's own ioremap_wc writes at the physical address land in the same scanout memory
(same address as the DT node, so expected). Squares can only be relied on after a hang, with the dashboard frozen.
