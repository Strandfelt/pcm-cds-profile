# pcm-cds-profile

`pcm-cds-profile` is a standard-library Python package that reads observed
Pro Cycling Manager `.cds` stage files and exports the sampled elevation
profile as XML or SVG. It does not read process memory, access game archives,
or include game files.

## Install

```powershell
python -m pip install "git+https://github.com/Strandfelt/pcm-cds-profile.git@v0.1.0"
```

Python 3.12 or later is required. The package has no runtime dependencies.

## Python API

```python
from pathlib import Path

from pcm_cds_profile import editor_profile_xml, profile_svg, read_cds

stage = read_cds(Path("stage.cds"))
xml = editor_profile_xml(stage)
svg = profile_svg(stage)

Path("profile.xml").write_text(xml, encoding="utf-8")
Path("profile.svg").write_text(svg, encoding="utf-8")
```

`read_cds(path)` returns stage metadata, raw profile samples, metric profile
samples, and route records. `read_cds_bytes(data, source=...)` parses bytes
from another reader. `editor_profile(stage)` returns the Stage Editor's
600-point full-spline sample. `editor_profile_xml(stage)` serializes that
sample as a `profile` element with its `X` and `Y` attributes and 600 `point`
children. Point `X` values are sample indexes; point `Y` values are heights
shifted by the sampled minimum, not absolute altitudes. This preserves the
observed profile payload and does not create a complete stage project file.

`profile_svg(stage, width=1200, height=360, padding=24)` returns an accessible,
self-contained SVG elevation profile. Its horizontal axis covers the full
spline. The API raises `ValueError` for unsupported or malformed CDS data and
invalid profile or SVG values; file access errors from `read_cds` remain
`OSError` subclasses.

`height_at_units(points, distance)` and `heights_at_units(points, distances)`
use native CDS units. Multiply distance units by 10 for m and height units by
7.5 for m. The Stage Editor lookup uses a half-interval shift, fixed 20-unit
spacing, and float32 arithmetic. The sampler preserves that behavior and its
600-point output.

## Format limits

The parser supports the observed single-object `CTStageData` envelope and
format versions 104, 105, 112, 113, 114, 115, 129, 131, 132, 134, 135, 136,
and 137. These values are observed file versions, not guarantees for all files
from a game release. The reader parses the stage prefix, profile, and route
records only; it does not parse later sections. Unknown versions and
unsupported envelopes are rejected.

Sampling covers the full spline, including roads before the race start and
after the finish. It does not add circuit laps or crop to the race segment.
This is static-file support; it does not establish live telemetry or
RR/ITT/TTT runtime behavior. See the PCM bot's CDS format notes for evidence
and known limits.

## Development

```powershell
python -m unittest discover -s tests -v
```

Tests use synthetic CDS data. No PCM installation or game files are required.
