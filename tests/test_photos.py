import tempfile
import unittest
from pathlib import Path
from backend.photos import save_image


class PhotosTest(unittest.TestCase):
    def test_content_address_and_reject_error_page(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = b'\xff\xd8\xff' + b'fixture' * 8 + b'\xff\xd9'
            first = save_image(raw, root)
            self.assertEqual(first, save_image(raw, root))
            self.assertEqual(raw, (root / first).read_bytes())
            self.assertNotEqual(first, save_image(raw[:-2] + b'other\xff\xd9', root))
            for invalid in (b'<html>Service unavailable</html>' * 10, raw[:-2], b''):
                with self.assertRaises(ValueError):
                    save_image(invalid, root)
