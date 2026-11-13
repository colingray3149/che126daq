# Experimental run archive

All 36 run folders are published here, directly under the repository's top-level
`runs/` directory. Original run numbers and files are preserved; runs are not
renumbered, merged or moved into a miscellaneous/provenance folder.

The complete archive now contains **44,637 CSV sample rows** across runs
**001–036**, with **36 interactive reports**, **36 rendered graph pages** and
**72 PNGs**. The 2026-11-09 run029–033 publication contained **42,610 rows**
across runs **001–033**. The earlier 2026-11-09 run027/028 publication contained **36,798
CSV sample rows** across runs **001–028**, with **28 reports** and **56 PNGs**;
the initial full-archive publication contained **33,538 CSV sample rows** and
**100 original files** across runs **001–026**. Those dated historical
publication counts remain unchanged. Every run includes its raw `data.csv`,
recorded `events.csv` and `notes.md`. Where originally saved, the folder also
includes control configuration, applied-setting acknowledgements and
role/voltage metadata. Each of the 36 folders now opens to a **rendered graph
page** with separate heater/rear PNGs and a full interactive HTML report.

## The three actual tests

These are the original three operator-identified successful tests. **Test 1–3 are
navigation labels, not new run numbers or EXP command names.** Start here for
the first three main experimental results; the other recording IDs below are retained
supporting acquisition history, not additional members of this original three-test set.
The later successful EXP5/run028 is highlighted separately below as the fourth actual test.

| Actual test | Saved run | Identification | Data and logs | Full graphs |
|---|---|---|---|---|
| **Test 1** | **[017](017/)** | Operator's first successful test; 1 mica / 2 basalt-fabric / 1 aluminum layer; probes reversed; actual voltage history unspecified | [Data](017/data.csv) · [Events](017/events.csv) · [Notes](017/notes.md) | [Rendered graphs](017/README.md) · [Interactive](017/report.html) |
| **Test 2** | **[023](023/)** | Successful EXP3 run at operator-reported approximately70V; original65V preset retained | [Data](023/data.csv) · [Events](023/events.csv) · [Notes](023/notes.md) | [Rendered graphs](023/README.md) · [Interactive](023/report.html) |
| **Test 3** | **[026](026/)** | Successful EXP4 staged run;100V preset metadata,700°C final target; operator said it went fine | [Data](026/data.csv) · [Events](026/events.csv) · [Notes](026/notes.md) | [Rendered graphs](026/README.md) · [Interactive](026/report.html) |

Run018 was an intended next recording number, not the completed successful EXP3
test: the documented successful EXP3 closeout belongs to023. These labels follow
the recorded operator assessments, not a new claim that every original target
or hold-duration criterion was met. Source: [experiment log](../docs/experiment-log.md#the-three-actual-tests).

## Successful EXP5 — run028

**[Run028](028/) is the completed EXP5 recording and fourth actual test.** The
operator said it went well. Its event log records measured completion of the
60-second target hold, followed by commanded heat OFF, retained cooldown logging
and a stopped recording. Run027 is the prior supporting recording, not the EXP5
result; both new recordings are preserved without changing their raw bytes.

| Actual test | Saved run | Identification | Original records | Full graphs |
|---|---|---|---|---|
| **Test 4** | **[028](028/)** | Successful EXP5 timed 700°C program; operator said it went well; events record measured60s target completion | [Raw data](028/data.csv) · [Events](028/events.csv) · [Notes](028/notes.md) · [Settings](028/experiment.toml) · [Applied settings](028/experiment-applied.json) · [Metadata](028/run-metadata.json) | [Rendered README](028/README.md) · [Interactive report](028/report.html) |

The new [run028 rendered page](028/README.md) and
[full-history interactive report](028/report.html) match the other run pages.
GitHub's HTML source view does not execute the interactive report; download/open
it locally or open it from a clone. See the [EXP5 closeout](../docs/experiment5.md)
and [current experiment log](../docs/experiment-log.md).

Raw data, event logs, saved settings and folder numbers are unchanged. Graphs
are regenerated derived views; the reports now include the current test labels.

## EXP6 — run036 (actual test 5)

**[Run036](036/) is the completed EXP6 recording and fifth actual test.**
Barrier: **1 layer mica / 2 layers fiberglass heat barrier strip (McMaster 4234N12) / 1 thin aluminum sheet.**
NEXT was sent from HEAT_100 at 18:02:44 UTC; the heater first measured ≥700°C at
249.2 s (18:06:02), peaked at 714.0°C, and the 60-second hold completed at 18:07:02
with heat OFF. The rear side peaked at 80.25°C at 642.0 s during cooldown; the
120°C rear cutoff was not reached. Runs034 and035 (59 and 86 rows) are
room-temperature idle acquisitions before EXP6 START.

| Actual test | Saved run | Barrier | Records | Full graphs |
|---|---|---|---|---|
| **Test 5** | **[036](036/)** | 1 mica / 2 fiberglass strip / 1 aluminum | [Raw data](036/data.csv) · [Events](036/events.csv) · [Notes](036/notes.md) · [Settings](036/experiment.toml) · [Applied settings](036/experiment-applied.json) · [Metadata](036/run-metadata.json) | [Rendered README](036/README.md) · [Interactive report](036/report.html) |

## Latest EXP5 recordings — runs029–033

Runs029–033 add **5,812 sample rows** without changing run028's status as the
completed EXP5 recording and fourth actual test. Run030 recorded **2,215 rows**
and a rear `TC2_LIMIT` trip in `BOOST_FINAL` at **2026-11-09 20:06:42.606 UTC**;
its heater peaked at **483°C** and its rear channel at **139.5°C**. Run033
recorded **1,744 rows** and the same trip at **20:57:57.344 UTC**, with heater
and rear peaks of **679.75°C** and **153.0°C**. Neither run reached 700°C or
completed the timed final hold; neither is labeled a successful EXP5 test.

Runs029, 031 and 032 contain **96**, **1,747** and **10 rows** respectively.
Their retained EXP5/swapped-input/100V metadata describes recording mapping and
manual-preset context, not proof of heating: their own event logs contain no
applied configuration or EXP5 START. Run033's event log also records a normal
NEXT (ID 6) acknowledgement at **20:53:03.506 UTC** after `HOLD_100`; no forced
NEXT action is claimed for the earlier rejected request. See each run's original
events and notes below, plus the [current experiment log](../docs/experiment-log.md).

## Browse runs

Counts below are read from the CSV, not inferred from saved note headers.
A dash in additional records means no separate settings/metadata file was
present; none was fabricated. Every run now has rendered and interactive graphs.

| Run | Sample rows | Raw data | Event log | Run notes | Additional saved records | Graphs |
|---|---:|---|---|---|---|---|
| [001](001/) | 171 | [CSV](001/data.csv) | [Events](001/events.csv) | [Notes](001/notes.md) | — | [Rendered graphs](001/README.md) · [Interactive HTML](001/report.html) |
| [002](002/) | 1 | [CSV](002/data.csv) | [Events](002/events.csv) | [Notes](002/notes.md) | — | [Rendered graphs](002/README.md) · [Interactive HTML](002/report.html) |
| [003](003/) | 352 | [CSV](003/data.csv) | [Events](003/events.csv) | [Notes](003/notes.md) | — | [Rendered graphs](003/README.md) · [Interactive HTML](003/report.html) |
| [004](004/) | 35 | [CSV](004/data.csv) | [Events](004/events.csv) | [Notes](004/notes.md) | — | [Rendered graphs](004/README.md) · [Interactive HTML](004/report.html) |
| [005](005/) | 3,028 | [CSV](005/data.csv) | [Events](005/events.csv) | [Notes](005/notes.md) | — | [Rendered graphs](005/README.md) · [Interactive HTML](005/report.html) |
| [006](006/) | 819 | [CSV](006/data.csv) | [Events](006/events.csv) | [Notes](006/notes.md) | — | [Rendered graphs](006/README.md) · [Interactive HTML](006/report.html) |
| [007](007/) | 602 | [CSV](007/data.csv) | [Events](007/events.csv) | [Notes](007/notes.md) | — | [Rendered graphs](007/README.md) · [Interactive HTML](007/report.html) |
| [008](008/) | 1,912 | [CSV](008/data.csv) | [Events](008/events.csv) | [Notes](008/notes.md) | — | [Rendered graphs](008/README.md) · [Interactive HTML](008/report.html) |
| [009](009/) | 2,464 | [CSV](009/data.csv) | [Events](009/events.csv) | [Notes](009/notes.md) | — | [Rendered graphs](009/README.md) · [Interactive HTML](009/report.html) |
| [010](010/) | 52 | [CSV](010/data.csv) | [Events](010/events.csv) | [Notes](010/notes.md) | — | [Rendered graphs](010/README.md) · [Interactive HTML](010/report.html) |
| [011](011/) | 4,302 | [CSV](011/data.csv) | [Events](011/events.csv) | [Notes](011/notes.md) | — | [Rendered graphs](011/README.md) · [Interactive HTML](011/report.html) |
| [012](012/) | 2,400 | [CSV](012/data.csv) | [Events](012/events.csv) | [Notes](012/notes.md) | — | [Rendered graphs](012/README.md) · [Interactive HTML](012/report.html) |
| [013](013/) | 16 | [CSV](013/data.csv) | [Events](013/events.csv) | [Notes](013/notes.md) | — | [Rendered graphs](013/README.md) · [Interactive HTML](013/report.html) |
| [014](014/) | 2,974 | [CSV](014/data.csv) | [Events](014/events.csv) | [Notes](014/notes.md) | — | [Rendered graphs](014/README.md) · [Interactive HTML](014/report.html) |
| [015](015/) | 2,062 | [CSV](015/data.csv) | [Events](015/events.csv) | [Notes](015/notes.md) | — | [Rendered graphs](015/README.md) · [Interactive HTML](015/report.html) |
| [016](016/) | 737 | [CSV](016/data.csv) | [Events](016/events.csv) | [Notes](016/notes.md) | — | [Rendered graphs](016/README.md) · [Interactive HTML](016/report.html) |
| **[017 — Actual test 1](017/)** | 2,504 | [CSV](017/data.csv) | [Events](017/events.csv) | [Notes](017/notes.md) | [Control config](017/experiment.toml) · [Applied settings](017/experiment-applied.json) | [Rendered graphs](017/README.md) · [Interactive HTML](017/report.html) |
| [018](018/) | 465 | [CSV](018/data.csv) | [Events](018/events.csv) | [Notes](018/notes.md) | [Run metadata](018/run-metadata.json) | [Rendered graphs](018/README.md) · [Interactive HTML](018/report.html) |
| [019](019/) | 2,008 | [CSV](019/data.csv) | [Events](019/events.csv) | [Notes](019/notes.md) | [Control config](019/experiment.toml) · [Applied settings](019/experiment-applied.json) · [Run metadata](019/run-metadata.json) | [Rendered graphs](019/README.md) · [Interactive HTML](019/report.html) |
| [020](020/) | 675 | [CSV](020/data.csv) | [Events](020/events.csv) | [Notes](020/notes.md) | [Run metadata](020/run-metadata.json) | [Rendered graphs](020/README.md) · [Interactive HTML](020/report.html) |
| [021](021/) | 19 | [CSV](021/data.csv) | [Events](021/events.csv) | [Notes](021/notes.md) | [Control config](021/experiment.toml) · [Applied settings](021/experiment-applied.json) · [Run metadata](021/run-metadata.json) | [Rendered graphs](021/README.md) · [Interactive HTML](021/report.html) |
| [022](022/) | 16 | [CSV](022/data.csv) | [Events](022/events.csv) | [Notes](022/notes.md) | [Run metadata](022/run-metadata.json) | [Rendered graphs](022/README.md) · [Interactive HTML](022/report.html) |
| **[023 — Actual test 2](023/)** | 3,313 | [CSV](023/data.csv) | [Events](023/events.csv) | [Notes](023/notes.md) | [Control config](023/experiment.toml) · [Applied settings](023/experiment-applied.json) · [Run metadata](023/run-metadata.json) | [Rendered graphs](023/README.md) · [Interactive HTML](023/report.html) |
| [024](024/) | 8 | [CSV](024/data.csv) | [Events](024/events.csv) | [Notes](024/notes.md) | [Run metadata](024/run-metadata.json) | [Rendered graphs](024/README.md) · [Interactive HTML](024/report.html) |
| [025](025/) | 524 | [CSV](025/data.csv) | [Events](025/events.csv) | [Notes](025/notes.md) | [Run metadata](025/run-metadata.json) | [Rendered graphs](025/README.md) · [Interactive HTML](025/report.html) |
| **[026 — Actual test 3](026/)** | 2,079 | [CSV](026/data.csv) | [Events](026/events.csv) | [Notes](026/notes.md) | [Control config](026/experiment.toml) · [Applied settings](026/experiment-applied.json) · [Run metadata](026/run-metadata.json) | [Rendered graphs](026/README.md) · [Interactive HTML](026/report.html) |
| [027 — Supporting recording](027/) | 1,024 | [CSV](027/data.csv) | [Events](027/events.csv) | [Notes](027/notes.md) | [Run metadata](027/run-metadata.json) | [Rendered graphs](027/README.md) · [Interactive HTML](027/report.html) |
| **[028 — Actual test 4 / successful EXP5](028/)** | 2,236 | [CSV](028/data.csv) | [Events](028/events.csv) | [Notes](028/notes.md) | [Control config](028/experiment.toml) · [Applied settings](028/experiment-applied.json) · [Run metadata](028/run-metadata.json) | [Rendered graphs](028/README.md) · [Interactive HTML](028/report.html) |
| [029 — EXP5-mapped supporting recording](029/) | 96 | [CSV](029/data.csv) | [Events](029/events.csv) | [Notes](029/notes.md) | [Run metadata](029/run-metadata.json) | [Rendered graphs](029/README.md) · [Interactive HTML](029/report.html) |
| [030 — EXP5 rear-cutoff trip](030/) | 2,215 | [CSV](030/data.csv) | [Events](030/events.csv) | [Notes](030/notes.md) | [Control config](030/experiment.toml) · [Applied settings](030/experiment-applied.json) · [Run metadata](030/run-metadata.json) | [Rendered graphs](030/README.md) · [Interactive HTML](030/report.html) |
| [031 — EXP5-mapped supporting recording](031/) | 1,747 | [CSV](031/data.csv) | [Events](031/events.csv) | [Notes](031/notes.md) | [Run metadata](031/run-metadata.json) | [Rendered graphs](031/README.md) · [Interactive HTML](031/report.html) |
| [032 — EXP5-mapped supporting recording](032/) | 10 | [CSV](032/data.csv) | [Events](032/events.csv) | [Notes](032/notes.md) | [Run metadata](032/run-metadata.json) | [Rendered graphs](032/README.md) · [Interactive HTML](032/report.html) |
| [033 — EXP5 rear-cutoff trip](033/) | 1,744 | [CSV](033/data.csv) | [Events](033/events.csv) | [Notes](033/notes.md) | [Control config](033/experiment.toml) · [Applied settings](033/experiment-applied.json) · [Run metadata](033/run-metadata.json) | [Rendered graphs](033/README.md) · [Interactive HTML](033/report.html) |
| [034 — Pre-EXP6 supporting recording](034/) | 59 | [CSV](034/data.csv) | [Events](034/events.csv) | [Notes](034/notes.md) | [Run metadata](034/run-metadata.json) | [Rendered graphs](034/README.md) · [Interactive HTML](034/report.html) |
| [035 — Pre-EXP6 supporting recording](035/) | 86 | [CSV](035/data.csv) | [Events](035/events.csv) | [Notes](035/notes.md) | [Run metadata](035/run-metadata.json) | [Rendered graphs](035/README.md) · [Interactive HTML](035/report.html) |
| **[036 — Actual test 5 / EXP6](036/)** | 1,882 | [CSV](036/data.csv) | [Events](036/events.csv) | [Notes](036/notes.md) | [Control config](036/experiment.toml) · [Applied settings](036/experiment-applied.json) · [Run metadata](036/run-metadata.json) | [Rendered graphs](036/README.md) · [Interactive HTML](036/report.html) |

## Interpretation and historical caveats

- Run numbers identify recordings, not necessarily distinct successful experiments.
  Short runs, restarts, fault-containing runs and unsuccessful attempts are retained.
- Raw channel order is never swapped in the CSV. Consult each run's saved metadata,
  notes and the [legacy mapping annotations](../host/web/run-mappings.json) before
  assigning heater/rear roles; EXP3/4/5 defaults use raw TC2 as heater and raw TC1 as rear.
- **Run006 has stale note metadata:** its original header says `recording` and
  `Samples: 0`, but its CSV contains **819 rows**. The original notes are preserved;
  that historical header is not evidence that acquisition is currently running.
- Missing/invalid readings, zeros, flags and reset epochs are retained. Inclusion
  in this archive does not imply sensor calibration, a valid thermal run or a
  successful outcome. Operator assessments remain separately attributed in logs.
- The72 PNGs render directly on GitHub through each run folder's README. They use
  independent°C axes and the entire saved elapsed-time range. Missing values stay
  gaps; entirely nonfinite channels are explicitly labeled, never plotted as zeros.
- All36 interactive reports are self-contained HTML snapshots. Download/open them
  locally for zoom/hover; GitHub's source view does not execute JavaScript.
  Check the saved snapshot status and source hash rather than assuming a live view.
- Runs are version-controlled but never automatically committed, pushed or deleted
  by the DAQ. Future recordings are no longer hidden by a blanket Git ignore rule.

## Logs and documentation

- [Experiment log](../docs/experiment-log.md): operator outcomes, measured results,
  configuration decisions and run026's cutoff-removal requests/refusals.
- [Activity log](../docs/activity-log.md): implementation, deployment, checks and
  publication history.
- [Run026 detailed notes and refusal record](026/notes.md).
- [Run028 successful EXP5 notes](028/notes.md) and [EXP5 closeout](../docs/experiment5.md).
- [Acquisition and report instructions](../docs/run-notes.md).
- [Experiment control policies](../docs/exp2.md).
- [Quick wiring guide](../WIRING-QUICK.md) and [detailed wiring](../docs/wiring.md).
- [Changelog](../CHANGELOG.md) and [project overview](../README.md).
