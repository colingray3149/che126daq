# Experimental run archive

All 26 run folders are published here, directly under the repository's top-level
`runs/` directory. Original run numbers and files are preserved; runs are not
renumbered, merged or moved into a miscellaneous/provenance folder.

The initial full-archive publication contains **33,538 CSV sample rows** and
**100 original files** across runs **001–026**. Every run includes its raw
`data.csv`, recorded `events.csv` and `notes.md`. Where originally saved, the
folder also includes control configuration, applied-setting acknowledgements,
role/voltage metadata and an interactive HTML report.

## Browse runs

Counts below are read from the CSV, not inferred from saved note headers.
A dash means that no separate snapshot/report file was present; none was
reconstructed or fabricated. Acquisition configuration is also recorded in notes.

| Run | Sample rows | Raw data | Event log | Run notes | Additional saved records | Graph report |
|---|---:|---|---|---|---|---|
| [001](001/) | 171 | [CSV](001/data.csv) | [Events](001/events.csv) | [Notes](001/notes.md) | — | — |
| [002](002/) | 1 | [CSV](002/data.csv) | [Events](002/events.csv) | [Notes](002/notes.md) | — | — |
| [003](003/) | 352 | [CSV](003/data.csv) | [Events](003/events.csv) | [Notes](003/notes.md) | — | — |
| [004](004/) | 35 | [CSV](004/data.csv) | [Events](004/events.csv) | [Notes](004/notes.md) | — | — |
| [005](005/) | 3,028 | [CSV](005/data.csv) | [Events](005/events.csv) | [Notes](005/notes.md) | — | — |
| [006](006/) | 819 | [CSV](006/data.csv) | [Events](006/events.csv) | [Notes](006/notes.md) | — | — |
| [007](007/) | 602 | [CSV](007/data.csv) | [Events](007/events.csv) | [Notes](007/notes.md) | — | — |
| [008](008/) | 1,912 | [CSV](008/data.csv) | [Events](008/events.csv) | [Notes](008/notes.md) | — | — |
| [009](009/) | 2,464 | [CSV](009/data.csv) | [Events](009/events.csv) | [Notes](009/notes.md) | — | — |
| [010](010/) | 52 | [CSV](010/data.csv) | [Events](010/events.csv) | [Notes](010/notes.md) | — | — |
| [011](011/) | 4,302 | [CSV](011/data.csv) | [Events](011/events.csv) | [Notes](011/notes.md) | — | — |
| [012](012/) | 2,400 | [CSV](012/data.csv) | [Events](012/events.csv) | [Notes](012/notes.md) | — | — |
| [013](013/) | 16 | [CSV](013/data.csv) | [Events](013/events.csv) | [Notes](013/notes.md) | — | — |
| [014](014/) | 2,974 | [CSV](014/data.csv) | [Events](014/events.csv) | [Notes](014/notes.md) | — | — |
| [015](015/) | 2,062 | [CSV](015/data.csv) | [Events](015/events.csv) | [Notes](015/notes.md) | — | — |
| [016](016/) | 737 | [CSV](016/data.csv) | [Events](016/events.csv) | [Notes](016/notes.md) | — | — |
| [017](017/) | 2,504 | [CSV](017/data.csv) | [Events](017/events.csv) | [Notes](017/notes.md) | [Control config](017/experiment.toml) · [Applied settings](017/experiment-applied.json) | [Interactive HTML](017/report.html) |
| [018](018/) | 465 | [CSV](018/data.csv) | [Events](018/events.csv) | [Notes](018/notes.md) | [Run metadata](018/run-metadata.json) | — |
| [019](019/) | 2,008 | [CSV](019/data.csv) | [Events](019/events.csv) | [Notes](019/notes.md) | [Control config](019/experiment.toml) · [Applied settings](019/experiment-applied.json) · [Run metadata](019/run-metadata.json) | — |
| [020](020/) | 675 | [CSV](020/data.csv) | [Events](020/events.csv) | [Notes](020/notes.md) | [Run metadata](020/run-metadata.json) | — |
| [021](021/) | 19 | [CSV](021/data.csv) | [Events](021/events.csv) | [Notes](021/notes.md) | [Control config](021/experiment.toml) · [Applied settings](021/experiment-applied.json) · [Run metadata](021/run-metadata.json) | — |
| [022](022/) | 16 | [CSV](022/data.csv) | [Events](022/events.csv) | [Notes](022/notes.md) | [Run metadata](022/run-metadata.json) | — |
| [023](023/) | 3,313 | [CSV](023/data.csv) | [Events](023/events.csv) | [Notes](023/notes.md) | [Control config](023/experiment.toml) · [Applied settings](023/experiment-applied.json) · [Run metadata](023/run-metadata.json) | [Interactive HTML](023/report.html) |
| [024](024/) | 8 | [CSV](024/data.csv) | [Events](024/events.csv) | [Notes](024/notes.md) | [Run metadata](024/run-metadata.json) | — |
| [025](025/) | 524 | [CSV](025/data.csv) | [Events](025/events.csv) | [Notes](025/notes.md) | [Run metadata](025/run-metadata.json) | — |
| [026](026/) | 2,079 | [CSV](026/data.csv) | [Events](026/events.csv) | [Notes](026/notes.md) | [Control config](026/experiment.toml) · [Applied settings](026/experiment-applied.json) · [Run metadata](026/run-metadata.json) | [Interactive HTML](026/report.html) |

## Interpretation and historical caveats

- Run numbers identify recordings, not necessarily distinct successful experiments.
  Short runs, restarts, fault-containing runs and unsuccessful attempts are retained.
- Raw channel order is never swapped in the CSV. Consult each run's saved metadata,
  notes and the [legacy mapping annotations](../host/web/run-mappings.json) before
  assigning heater/rear roles; EXP3/4 defaults use raw TC2 as heater and raw TC1 as rear.
- **Run006 has stale note metadata:** its original header says `recording` and
  `Samples: 0`, but its CSV contains **819 rows**. The original notes are preserved;
  that historical header is not evidence that acquisition is currently running.
- Missing/invalid readings, zeros, flags and reset epochs are retained. Inclusion
  in this archive does not imply sensor calibration, a valid thermal run or a
  successful outcome. Operator assessments remain separately attributed in logs.
- Interactive reports are self-contained HTML snapshots. Download/open them locally
  (or open from a clone); GitHub's file source view is not an interactive plot viewer.
  Existing reports for017,023,026 are included unchanged. See the report's saved
  snapshot status and source hash, rather than assuming it is a live view.
- Runs are version-controlled but never automatically committed, pushed or deleted
  by the DAQ. Future recordings are no longer hidden by a blanket Git ignore rule.

## Logs and documentation

- [Experiment log](../docs/experiment-log.md): operator outcomes, measured results,
  configuration decisions and run026's cutoff-removal requests/refusals.
- [Activity log](../docs/activity-log.md): implementation, deployment, checks and
  publication history.
- [Run026 detailed notes and refusal record](026/notes.md).
- [Acquisition and report instructions](../docs/run-notes.md).
- [Experiment control policies](../docs/exp2.md).
- [Quick wiring guide](../WIRING-QUICK.md) and [detailed wiring](../docs/wiring.md).
- [Changelog](../CHANGELOG.md) and [project overview](../README.md).
