# datos/ — data sheet

## Sources

All inputs are open data of the Bizkaibus network. Please keep this attribution when you reuse them.

| Data | Format | Where |
|---|---|---|
| Timetable | GTFS | Spanish National Access Point for transport (NAP), dataset 1061, `https://nap.transportes.gob.es/api/Fichero/download/1061` (needs a free API key), mirrored at `https://ctb-gtfs.s3.eu-south-2.amazonaws.com/bizkaibus.zip` |
| Live positions | SIRI Vehicle Monitoring (XML) | `https://ctb-siri.s3.eu-south-2.amazonaws.com/bizkaibus-vehicle-positions.xml`, updated about every 55 s |

The timetable database used by `referencia/evaluar.py` (`bizkaibus.sqlite`, about 45 MB) is the one the Bizkaibus+
app builds from the GTFS every day; its schema is in appendix C of the technical report. A frozen copy will be
published with each data release, together with the captures it matches.

## Learned tables (`tablas/`)

Produced by the daily recalibration from the captures of the live feed. Version: 7 November 2026.

| File | Contents |
|---|---|
| `segment-times.json` | Travel time of each segment between consecutive stops (`"from>to"`), overall (`all`) and by time band (`laborable.punta_manana`, …), with its number of tracks (`n`); `lengthRatios`: ratio actual/timetable by segment length bucket, for segments not learned yet. 470,889 samples |
| `pace-factors.json` | Pace factor *k* (actual / timetable time) by time band, overall (`global`) and by line (`lines`), clamped to 0.6–1.2. 500,000 samples |
| `trip-offsets.json` | Per-trip correction of the timetable layer: by trip (`line\|first stop\|last stop\|departure\|stops`) and day type, one value per third of the route; by line and band; and by band. 531,799 passages |

Line numbers may appear with a leading zero (`0651`) in tables written before 7 November 2026; the code treats `0651`
and `651` as the same line.

## Live feed captures

Snapshots of the SIRI feed every 20 s, in one-hour blocks (Madrid time), archived since 31 October 2026. They will be
published here as monthly releases. Known issues, documented in the technical report:

- From 23:58 to 05:00 the Bizkaibus feed repeats the buses seen before midnight: those entries carry no time of the
  new day and are ignored.
- Some hours are missing when the capture job did not run (GitHub Actions delays or skips scheduled runs).
- The actual passage is reconstructed from the change of next stop between snapshots, so it has a resolution of
  ±30 s (half the interval between snapshots).

## Licence

Data produced here (learned tables, evaluation results): [CC BY 4.0](../LICENSE-CC-BY-4.0.txt). Timetable and feed:
the licence of their publishers.
