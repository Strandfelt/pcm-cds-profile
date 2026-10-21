"""Export sampled CDS profiles as XML or SVG."""

from math import isfinite
from xml.etree import ElementTree

from pcm_cds_profile.cds import Stage, editor_profile

_SVG_NAMESPACE = "http://www.w3.org/2000/svg"
ElementTree.register_namespace("", _SVG_NAMESPACE)


def _number(value: float) -> str:
    return format(value, ".6f")


def editor_profile_xml(stage: Stage) -> str:
    """Return the sampled 600-point profile as an XML ``profile`` element.

    X and Y values follow the observed Stage Editor profile representation:
    X is a sample index and Y is height relative to the sampled minimum.
    """
    sampled = editor_profile(stage)
    root = ElementTree.Element("profile", {
        "X": str(sampled["X"]),
        "Y": _number(sampled["Y"]),
    })
    for point in sampled["points"]:
        ElementTree.SubElement(root, "point", {
            "X": str(point["X"]),
            "Y": _number(point["Y"]),
        })
    return ElementTree.tostring(root, encoding="unicode", short_empty_elements=True)


def profile_svg(
    stage: Stage,
    *,
    width: int = 1200,
    height: int = 360,
    padding: int = 24,
) -> str:
    """Return a self-contained SVG elevation profile sampled over the full spline."""
    if any(not isinstance(value, int) or isinstance(value, bool) for value in (width, height, padding)):
        raise ValueError("SVG width, height, and padding must be integers")
    if width <= 0 or height <= 0 or padding < 0 or 2 * padding >= min(width, height):
        raise ValueError("SVG dimensions and padding do not leave a drawable area")

    points = editor_profile(stage)["points"]
    distances = [point["spline_distance_m"] for point in points]
    altitudes = [point["altitude_m"] for point in points]
    if not all(isfinite(value) for value in (*distances, *altitudes)):
        raise ValueError("SVG profile values must be finite")

    distance_min, distance_max = distances[0], distances[-1]
    altitude_min, altitude_max = min(altitudes), max(altitudes)
    distance_range = distance_max - distance_min
    altitude_range = altitude_max - altitude_min
    if distance_range <= 0:
        raise ValueError("SVG profile distance range must be positive")
    drawable_width = width - 2 * padding
    drawable_height = height - 2 * padding

    coordinates = []
    for distance, altitude in zip(distances, altitudes):
        x = padding + (distance - distance_min) * drawable_width / distance_range
        if altitude_range:
            y = padding + (altitude_max - altitude) * drawable_height / altitude_range
        else:
            y = padding + drawable_height / 2
        coordinates.append(f"{_number(x)},{_number(y)}")

    root = ElementTree.Element(f"{{{_SVG_NAMESPACE}}}svg", {
        "viewBox": f"0 0 {width} {height}",
        "width": str(width),
        "height": str(height),
        "role": "img",
        "aria-label": "Stage elevation profile",
    })
    title = ElementTree.SubElement(root, f"{{{_SVG_NAMESPACE}}}title")
    title.text = "Stage elevation profile"
    ElementTree.SubElement(root, f"{{{_SVG_NAMESPACE}}}path", {
        "d": "M " + " L ".join(coordinates),
        "fill": "none",
        "stroke": "#2864dc",
        "stroke-width": "2",
        "vector-effect": "non-scaling-stroke",
    })
    return ElementTree.tostring(root, encoding="unicode", short_empty_elements=True)
