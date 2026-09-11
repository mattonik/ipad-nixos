# Active watchers

Background checks set up for this project. They live outside the repository
(in the Claude desktop app's scheduled tasks, at
`~/.claude/scheduled-tasks/<taskId>/SKILL.md`) and only run while that app is
open, so this file is the in-repo record that they exist and why. Nothing here
changes the build or the device.

| Task ID | Schedule | Watches | Why |
| --- | --- | --- | --- |
| `t1bridge-machine-data-watch` | Mondays ~09:17 local (`17 9 * * 1`, small jitter applied) | [`standardagents/t1bridge`](https://github.com/standardagents/t1bridge) commits, PRs, releases, issues | Whether the "coprocessor regenerates its own provisioning data from Linux" technique lands as a described mechanism. See [j81-touch-id-mesa.md](j81-touch-id-mesa.md). |
| `asahi-sep-touchid-watch` | 3rd of the month, ~09:00 local (`0 9 3 * *`) | [Asahi Linux's blog](https://asahilinux.org/blog/) (progress reports, roughly bimonthly) and a quick web search, for real SEP/Touch-ID evidence | A 2026-09 Omarchy announcement claimed Touch-ID-via-Secure-Enclave on M-series Macs but has no repo/commit/writeup behind it and no mention in Asahi's own progress reports. Architecturally closer to J81 than t1bridge (on-die SEP + IOP mailbox, same family), so worth watching Asahi's high-signal channel specifically rather than the marketing announcement. See [j81-touch-id-mesa.md](j81-touch-id-mesa.md)'s 2026-09-12 addendum. |

## On the t1bridge watcher specifically

This is a low-priority research signal, not a blocker for anything on the
roadmap. The analysis in
[`j81-touch-id-mesa.md`](j81-touch-id-mesa.md) concluded that Touch ID on J81
is not a near-term target and that t1bridge's code does not transfer to
A-series. The watcher exists for one narrow reason: if an Apple coprocessor
can be induced to regenerate its own provisioning data without the vendor OS,
that is evidence about how much of Apple's provisioning is genuinely
device-side -- an interesting question for SEP/xART on A-series even though it
is not a Touch ID path.

The watcher is instructed to dismiss routine activity (packaging, Touch Bar
renderers, libfprint bumps) in one line rather than pad a report, and not to
overclaim transferability.

Retire it if the technique lands and turns out to be Apple-firmware-dependent
(the likely outcome), or if it has not appeared after a couple of months.

## On the Asahi/Omarchy SEP watcher specifically

Also a low-priority research signal, not a blocker. Unlike the t1bridge case,
this one starts from an *unverified* claim (no repo, commit, or writeup, and
silence from Asahi's own progress reports as of the check that created this
watcher) -- so most runs should find nothing new to report, and that is the
expected, healthy outcome, not a sign the watcher is useless. It exists
because the underlying architecture (on-die SEP, IOP mailbox) genuinely is
the closer analog to J81, so *if* real evidence ever appears, it is worth
reading in detail rather than dismissed on the T1 template.

Retire it if a real technical result is published and turns out to depend on
M-series-specific SEP firmware/hardware in a way that clearly does not
inform A8X's much older SEP generation (the likely outcome even if the claim
is eventually substantiated), or if nothing has surfaced after a few months.
