import tempfile
import unittest
import zipfile
from pathlib import Path

import cardscan4linux as scanner


class PanDetectionTests(unittest.TestCase):
    def test_all_formats_and_multiple_pans(self):
        text = ("4222222222222 4111111111111111\t5555-5555-5555-4444 "
                "3782 822463 10005 4000000000000000006")
        self.assertEqual(list(scanner.find_pans(text)), [
            ("visa", "4222222222222"),
            ("visa", "4111111111111111"),
            ("mastercard", "5555555555554444"),
            ("amex", "378282246310005"),
            ("visa", "4000000000000000006"),
        ])

    def test_rejects_bad_range_and_embedded_number(self):
        self.assertEqual(list(scanner.find_pans("5019717010103742")), [])
        self.assertEqual(list(scanner.find_pans("941111111111111119")), [])

    def test_scans_after_line_fifty_and_masks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cards.txt"
            path.write_text("nothing\n" * 60 + "4111111111111111\n", encoding="utf-8")
            findings = scanner.scan_file(path)
            self.assertEqual(findings[0][2], "411111******1111")
            self.assertNotIn("4111111111111111", repr(findings))

    def test_scans_xlsx_zip_members(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cards.xlsx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("xl/sharedStrings.xml", "<t>5555555555554444</t>")
            self.assertEqual(scanner.scan_file(path)[0][1:],
                             ("mastercard", "555555******4444"))

    def test_scan_details_include_line_and_masked_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cards.txt"
            path.write_text("nothing\nCustomer PAN: 4111-1111-1111-1111 active\n",
                            encoding="utf-8")

            source, brand, masked, line_number, sample = scanner.scan_file_details(path)[0]

            self.assertEqual(source, str(path))
            self.assertEqual((brand, masked, line_number),
                             ("visa", "411111******1111", 2))
            self.assertEqual(sample, "Customer PAN: 411111******1111 active")
            self.assertNotIn("4111-1111-1111-1111", sample)


if __name__ == "__main__":
    unittest.main()
