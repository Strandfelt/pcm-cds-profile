# pcm-cds-profile

`pcm-cds-profile` is a Python package for reading Pro Cycling Manager `.cds`
stage files and exporting elevation profiles as XML or SVG.

## Install

```powershell
python -m pip install "git+https://github.com/Strandfelt/pcm-cds-profile.git@v0.1.0"
```

Python 3.12 or later is required.

## Usage

```python
from pathlib import Path

from pcm_cds_profile import editor_profile_xml, profile_svg, read_cds

stage = read_cds(Path("stage.cds"))
Path("profile.xml").write_text(editor_profile_xml(stage), encoding="utf-8")
Path("profile.svg").write_text(profile_svg(stage), encoding="utf-8")
```

`read_cds(path)` reads stage metadata, elevation samples, and route records.
Use `read_cds_bytes(data, source=...)` to parse bytes. `editor_profile_xml`
exports the Stage Editor's 600-point profile as XML. `profile_svg` creates an
accessible elevation profile.

## Development

```powershell
python -m unittest discover -s tests -v
```
