"""Read and sample observed PCM CDS stage profiles using the Python standard library."""

import hashlib
import math
from pathlib import Path
import struct
from typing import Sequence, TypedDict


OBSERVED_VERSIONS = frozenset({104, 105, 112, 113, 114, 115, 129, 131, 132, 134, 135, 136, 137})
DISTANCE_METRES_PER_UNIT = 10.0
HEIGHT_METRES_PER_UNIT = 7.5
PROFILE_SPACING_UNITS = 20.0
EDITOR_SAMPLE_COUNT = 600

ProfilePoint = tuple[float, float]


class Sprint(TypedDict):
    spline_distance_m: float
    type_code: int
    category_code: int
    name_utf8_display: str
    name_bytes_hex: str


class Stage(TypedDict):
    source: str
    sha256: str
    version: int
    name_utf8_display: str
    name_bytes_hex: str
    region_id: int
    spline_length_m: float
    race_length_m: float
    altitude_max_m: float
    altitude_start_m: float
    altitude_finish_m: float
    profile_file_offset: int
    raw_profile_points: list[ProfilePoint]
    profile_points_m: list[ProfilePoint]
    sprints: list[Sprint]


class EditorPoint(TypedDict):
    X: int
    Y: float
    spline_distance_m: float
    altitude_m: float


class EditorProfile(TypedDict):
    X: int
    Y: float
    minimum_height_units: float
    points: list[EditorPoint]


class _Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.position = 0

    def take(self, size: int) -> bytes:
        if size < 0 or size > len(self.data) - self.position:
            raise ValueError(f"Truncated CDS at file offset {self.position:#x}")
        result = self.data[self.position:self.position + size]
        self.position += size
        return result

    def unpack(self, fmt: str) -> tuple:
        return struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))

    def u32(self) -> int:
        return self.unpack("I")[0]

    def string_bytes(self) -> bytes:
        return self.take(self.u32())

    def check_count(self, count: int, minimum_record_size: int) -> None:
        if count > (len(self.data) - self.position) // minimum_record_size:
            raise ValueError(f"Truncated CDS record array at file offset {self.position:#x}")


def _f32(value: float) -> float:
    try:
        result = struct.unpack("<f", struct.pack("<f", value))[0]
    except (OverflowError, struct.error) as error:
        raise ValueError("CDS profile arithmetic exceeds finite float32 range") from error
    if not math.isfinite(result):
        raise ValueError("CDS profile arithmetic requires finite float32 values")
    return result


def _validate_points(points: Sequence[ProfilePoint]) -> None:
    if len(points) < 2:
        raise ValueError("The CDS does not contain enough profile samples")
    if not all(math.isfinite(value) for point in points for value in point):
        raise ValueError("Non-finite CDS profile value")
    if any(a[0] >= b[0] for a, b in zip(points, points[1:])):
        raise ValueError("CDS profile distances are not strictly increasing")


def read_cds(path: str | Path) -> Stage:
    """Read the stage prefix, counted profile, and sprints; ignore later sections.

    Raise ValueError for an unsupported or malformed file, or OSError for a
    file access error. Source name bytes are retained without an encoding guess.
    """
    path = Path(path)
    data = path.read_bytes()
    return read_cds_bytes(data, source=str(path.resolve()))


def read_cds_bytes(data: bytes, *, source: str) -> Stage:
    """Parse CDS bytes from a named source, including a selected PAK member."""
    reader = _Reader(data)
    version, stream_field, type_count = reader.unpack("III")
    if version not in OBSERVED_VERSIONS:
        raise ValueError(f"Unverified CDS version: {version}")
    if stream_field != 1 or type_count != 1:
        raise ValueError("Only the observed single-object CDS envelope is supported")
    if reader.string_bytes() != b"CTStageData":
        raise ValueError("The CDS does not contain the expected CTStageData object")
    if reader.unpack("IIHH") != (1, 1, 0, 0xCEAD):
        raise ValueError("Unexpected CDS object header")

    fields = reader.unpack("I7f")
    name_bytes = reader.string_bytes()
    region_id, _, _ = reader.unpack("iii")
    altitude_start, altitude_finish, _ = reader.unpack("3f")
    reader.take(4)
    if version >= 132:
        reader.take(4)
    reader.take(4)
    if not all(math.isfinite(value) for value in (*fields[1:], altitude_start, altitude_finish)):
        raise ValueError("Non-finite CDS stage field")
    if fields[1] <= 0 or fields[2] <= 0:
        raise ValueError("CDS stage lengths must be positive")

    count = reader.u32()
    profile_offset = reader.position
    reader.check_count(count, struct.calcsize("<ff"))
    raw_points = [reader.unpack("ff") for _ in range(count)]
    _validate_points(raw_points)

    sprints: list[Sprint] = []
    sprint_count = reader.u32()
    reader.check_count(sprint_count, struct.calcsize("<fiiI"))
    for _ in range(sprint_count):
        position, kind, category = reader.unpack("fii")
        sprint_name = reader.string_bytes()
        if not math.isfinite(position):
            raise ValueError("Non-finite CDS sprint position")
        sprints.append({
            "spline_distance_m": position * DISTANCE_METRES_PER_UNIT,
            "type_code": kind,
            "category_code": category,
            "name_utf8_display": sprint_name.decode("utf-8", errors="backslashreplace"),
            "name_bytes_hex": sprint_name.hex(),
        })

    return {
        "source": source,
        "sha256": hashlib.sha256(data).hexdigest(),
        "version": version,
        "name_utf8_display": name_bytes.decode("utf-8", errors="backslashreplace"),
        "name_bytes_hex": name_bytes.hex(),
        "region_id": region_id,
        "spline_length_m": fields[1],
        "race_length_m": fields[2],
        "altitude_max_m": fields[7],
        "altitude_start_m": altitude_start,
        "altitude_finish_m": altitude_finish,
        "profile_file_offset": profile_offset,
        "raw_profile_points": raw_points,
        "profile_points_m": [
            (distance * DISTANCE_METRES_PER_UNIT, height * HEIGHT_METRES_PER_UNIT)
            for distance, height in raw_points
        ],
        "sprints": sprints,
    }


def _height_at_units(points: Sequence[ProfilePoint], distance: float) -> float:
    last = len(points) - 1
    half_spacing = PROFILE_SPACING_UNITS / 2.0
    index = max(0, min(last, math.trunc(_f32(_f32(distance - half_spacing) / PROFILE_SPACING_UNITS))))
    following = min(index + 1, last)
    center = _f32(_f32(_f32(index) + 0.5) * PROFILE_SPACING_UNITS)
    ratio = _f32(_f32(distance - center) / PROFILE_SPACING_UNITS)
    difference = _f32(points[following][1] - points[index][1])
    return _f32(points[index][1] + _f32(ratio * difference))


def height_at_units(points: Sequence[ProfilePoint], distance: float) -> float:
    """Return native height units with the editor's float32 lookup.

    Input pairs and distance use native units, not metres. Stored X values do
    not determine interpolation. The first interval can extrapolate below X=0.
    """
    _validate_points(points)
    if not math.isfinite(distance):
        raise ValueError("Non-finite CDS lookup distance")
    return _height_at_units(points, distance)


def heights_at_units(points: Sequence[ProfilePoint], distances: Sequence[float]) -> list[float]:
    """Return native heights for many native distances; validate the profile once."""
    _validate_points(points)
    if not all(math.isfinite(distance) for distance in distances):
        raise ValueError("Non-finite CDS lookup distance")
    return [_height_at_units(points, distance) for distance in distances]


def editor_profile(stage: Stage) -> EditorProfile:
    """Return the editor's 600-point full-spline export, with SI companions."""
    points = stage["raw_profile_points"]
    _validate_points(points)
    length = _f32(stage["spline_length_m"] / DISTANCE_METRES_PER_UNIT)
    step = _f32(length / (EDITOR_SAMPLE_COUNT - 1))
    if step <= 0:
        raise ValueError("Stage length is too small for float32 profile sampling")
    distance = 0.0
    samples = []
    while distance <= length:
        samples.append((distance, _height_at_units(points, distance)))
        distance = _f32(distance + step)
        if len(samples) > EDITOR_SAMPLE_COUNT + 2:
            raise ValueError("Unexpected editor sampling loop length")
    minimum = min(height for _, height in samples)
    maximum = max(height for _, height in samples)
    while len(samples) < EDITOR_SAMPLE_COUNT:
        samples.append(samples[-1])
    return {
        "X": EDITOR_SAMPLE_COUNT,
        "Y": _f32(maximum - minimum),
        "minimum_height_units": minimum,
        "points": [
            {
                "X": index,
                "Y": _f32(height - minimum),
                "spline_distance_m": distance * DISTANCE_METRES_PER_UNIT,
                "altitude_m": height * HEIGHT_METRES_PER_UNIT,
            }
            for index, (distance, height) in enumerate(samples[:EDITOR_SAMPLE_COUNT])
        ],
    }

