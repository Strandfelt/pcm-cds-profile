import struct
import unittest
from xml.etree import ElementTree

from pcm_cds_profile import (
    editor_profile,
    editor_profile_xml,
    profile_svg,
    read_cds_bytes,
)


def synthetic_cds():
    data = bytearray()

    def pack(fmt, *values):
        data.extend(struct.pack("<" + fmt, *values))

    def string(value):
        pack("I", len(value))
        data.extend(value)

    pack("III", 132, 1, 1)
    string(b"CTStageData")
    pack("IIHH", 1, 1, 0, 0xCEAD)
    pack("I7f", 0, 1000.0, 800.0, 0.0, 0.0, 0.0, 0.0, 225.0)
    string(b"Synthetic")
    pack("iii", 7, 0, 0)
    pack("3f", 75.0, 150.0, 0.0)
    pack("f", 0.0)
    pack("f", 0.0)
    pack("f", 0.0)
    pack("I", 3)
    for point in ((0.0, 10.0), (20.0, 30.0), (40.0, 20.0)):
        pack("ff", *point)
    pack("I", 0)
    return bytes(data)


class ProfileExportTests(unittest.TestCase):
    def setUp(self):
        self.stage = read_cds_bytes(synthetic_cds(), source="synthetic")

    def test_xml_contains_all_editor_profile_values(self):
        profile = editor_profile(self.stage)
        root = ElementTree.fromstring(editor_profile_xml(self.stage))
        self.assertEqual(root.tag, "profile")
        self.assertEqual(root.attrib, {"X": "600", "Y": f'{profile["Y"]:.6f}'})
        points = root.findall("point")
        self.assertEqual(len(points), 600)
        self.assertEqual(
            [(point.get("X"), point.get("Y")) for point in points],
            [(str(point["X"]), f'{point["Y"]:.6f}') for point in profile["points"]],
        )

    def test_svg_is_well_formed_accessible_and_covers_full_spline(self):
        svg = ElementTree.fromstring(profile_svg(self.stage))
        self.assertEqual(svg.attrib["viewBox"], "0 0 1200 360")
        self.assertEqual(svg.attrib["role"], "img")
        self.assertEqual(svg.attrib["aria-label"], "Stage elevation profile")
        namespace = "{http://www.w3.org/2000/svg}"
        self.assertEqual(svg.find(f"{namespace}title").text, "Stage elevation profile")
        path = svg.find(f"{namespace}path")
        self.assertIsNotNone(path)
        self.assertEqual(len(path.attrib["d"].split(" L ")), 600)
        first_x = float(path.attrib["d"].split()[1].split(",")[0])
        last_x = float(path.attrib["d"].split()[-1].split(",")[0])
        self.assertEqual(first_x, 24.0)
        self.assertEqual(last_x, 1176.0)

    def test_svg_handles_flat_profiles_and_rejects_invalid_dimensions(self):
        data = bytearray(synthetic_cds())
        for index in range(3):
            struct.pack_into("<f", data, self.stage["profile_file_offset"] + index * 8 + 4, 10.0)
        flat = read_cds_bytes(bytes(data), source="flat")
        ElementTree.fromstring(profile_svg(flat))
        for options in ({"width": 0}, {"height": -1}, {"padding": 200}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                profile_svg(self.stage, **options)


if __name__ == "__main__":
    unittest.main()
