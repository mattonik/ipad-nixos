# Active watchers

Background checks set up for this project. They live outside the repository
(in the Claude desktop app's scheduled tasks, at
`~/.claude/scheduled-tasks/<taskId>/SKILL.md`) and only run while that app is
open, so this file is the in-repo record that they exist and why. Nothing here
changes the build or the device.

| Task ID | Schedule | Watches | Why |
| --- | --- | --- | --- |
| `t1bridge-machine-data-watch` | Mondays ~09:17 local (`17 9 * * 1`, small jitter applied) | [`standardagents/t1bridge`](https://github.com/standardagents/t1bridge) commits, PRs, releases, issues | Whether the "coprocessor regenerates its own provisioning data from Linux" technique lands as a described mechanism. See [j81-touch-id-mesa.md](j81-touch-id-mesa.md). |

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
