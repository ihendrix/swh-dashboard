import unittest

from swh_utils import decode_filename, extract_extension, timestamp_to_year


class UtilsTests(unittest.TestCase):
    def test_extract_extension(self):
        self.assertEqual(extract_extension(b"src/main.PY"), "py")
        self.assertEqual(extract_extension("archive.tar.gz"), "gz")
        self.assertIsNone(extract_extension("Makefile"))
        self.assertIsNone(extract_extension("name.ext-with-dash"))

    def test_decode_filename(self):
        self.assertEqual(decode_filename(b"hello.py"), "hello.py")
        self.assertEqual(decode_filename(bytearray(b"a.c")), "a.c")

    def test_timestamp_units(self):
        # 2021-01-01T00:00:00Z in seconds, milliseconds, microseconds, nanoseconds.
        self.assertEqual(timestamp_to_year(1609459200), 2021)
        self.assertEqual(timestamp_to_year(1609459200000), 2021)
        self.assertEqual(timestamp_to_year(1609459200000000), 2021)
        self.assertEqual(timestamp_to_year(1609459200000000000), 2021)


if __name__ == "__main__":
    unittest.main()
