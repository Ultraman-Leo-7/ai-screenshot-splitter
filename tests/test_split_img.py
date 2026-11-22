import contextlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageChops
import split_img


ROOT = Path(__file__).resolve().parents[1] / '.test-artifacts'
ROOT.mkdir(exist_ok=True)


class SplitTests(unittest.TestCase):
    def setUp(self):
        import uuid
        self.folder = ROOT / (self._testMethodName + '-' + uuid.uuid4().hex[:8])
        self.folder.mkdir()

    def image(self, name='中文 长截图.png', size=(100, 500), mode='RGB'):
        path = self.folder / name
        with Image.new(mode, size) as img:
            if mode == 'RGB':
                img.putdata([(x % 256, y % 256, (x + y) % 256)
                             for y in range(size[1]) for x in range(size[0])])
            img.save(path)
        return path

    def test_geometry_coverage_and_progress(self):
        for width in (1, 2, 7, 100, 1080):
            for height in (1, 2, 50, 159, 160, 161, 215, 216, 217, 500, 10000):
                for ratios in ((1.6, .12, .35), (1, .99, 0), (.1, 0, .35)):
                    ranges = split_img.plan_slices(width, height, *ratios)
                    self.assertEqual(ranges[0][0], 0)
                    self.assertEqual(ranges[-1][1], height)
                    segment = max(1, int(width * ratios[0]))
                    overlap = min(segment - 1, int(width * ratios[1]))
                    for top, bottom in ranges:
                        self.assertGreater(bottom, top)
                        self.assertLessEqual(bottom, height)
                    for before, after in zip(ranges, ranges[1:]):
                        self.assertGreater(after[0], before[0])
                        self.assertEqual(before[1] - after[0], overlap)

    def test_tail_merge(self):
        self.assertEqual(split_img.plan_slices(100, 210), [(0, 210)])
        self.assertEqual(split_img.plan_slices(100, 500), [(0, 160), (148, 308), (296, 500)])

    def test_lossless_pixels_and_manifest(self):
        path = self.image()
        output = split_img.split_long_image(path)
        manifest = json.loads((output / '切片记录.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifest['slices']), 3)
        with Image.open(path) as original:
            for item in manifest['slices']:
                with Image.open(output / item['file']) as actual:
                    with original.crop((0, item['top'], 100, item['bottom'])) as expected:
                        self.assertEqual(actual.tobytes(), expected.tobytes())

    def test_repeated_run_keeps_old_results_and_source(self):
        path = self.image(size=(30, 70))
        original = path.read_bytes()
        first = split_img.split_long_image(path)
        sentinel = first / '旧文件.txt'
        sentinel.write_text('keep', encoding='utf-8')
        second = split_img.split_long_image(path)
        self.assertNotEqual(first, second)
        self.assertEqual(sentinel.read_text(encoding='utf-8'), 'keep')
        self.assertEqual(path.read_bytes(), original)

    def test_path_quotes(self):
        self.assertEqual(split_img.parse_dragged_paths('& "C:\\one two.png" "D:\\三 四.png"'),
                         ['C:\\one two.png', 'D:\\三 四.png'])
        self.assertEqual(split_img.parse_dragged_paths("& 'C:\\O''Brien 长图.png'"),
                         ["C:\\O'Brien 长图.png"])
        path = self.image()
        self.assertEqual(split_img.parse_dragged_paths(str(path)), [str(path)])
        with self.assertRaises(ValueError):
            split_img.parse_dragged_paths('"C:\\unclosed.png')

    def test_invalid_ratios(self):
        for ratios in ((0, .12, .35), (1, 1, .35), (1, -.1, .35),
                       (1, .1, 1), (float('nan'), .1, .35), (float('inf'), .1, .35)):
            with self.assertRaises(ValueError):
                split_img.plan_slices(100, 500, *ratios)

    def test_transparency(self):
        path = self.folder / 'alpha.png'
        with Image.new('RGBA', (20, 80), (10, 20, 30, 40)) as image:
            image.save(path)
        output = split_img.split_long_image(path)
        with Image.open(output / '001.png') as actual:
            self.assertEqual(actual.mode, 'RGBA')
            self.assertEqual(actual.getpixel((0, 0)), (10, 20, 30, 40))

    def test_cmyk_jpeg(self):
        output = split_img.split_long_image(self.image('CMYK.jpg', (20, 80), 'CMYK'))
        with Image.open(output / '001.png') as actual:
            self.assertEqual(actual.mode, 'RGB')

    def test_exif_rotation(self):
        path = self.folder / 'rotate.jpg'
        with Image.new('RGB', (8, 3), (10, 20, 30)) as image:
            exif = Image.Exif()
            exif[274] = 6
            image.save(path, exif=exif)
        output = split_img.split_long_image(path)
        record = json.loads((output / '切片记录.json').read_text(encoding='utf-8'))
        self.assertEqual(record['oriented_size'], [3, 8])
        with Image.open(output / '001.png') as actual:
            self.assertNotIn(274, actual.getexif())

    def test_corrupt_and_animated_input(self):
        path = self.folder / 'corrupt.png'
        path.write_bytes(b'not an image')
        with self.assertRaises(Exception):
            split_img.split_long_image(path)
        path = self.folder / 'animated.gif'
        with Image.new('RGB', (5, 5), 'red') as first, Image.new('RGB', (5, 5), 'blue') as second:
            first.save(path, save_all=True, append_images=[second])
        with self.assertRaises(ValueError):
            split_img.split_long_image(path)
        self.assertEqual(list(self.folder.glob('*_切片*')), [])

    def test_pixel_protection_remains_enabled(self):
        path = self.image(size=(10, 10))
        with patch.object(Image, 'MAX_IMAGE_PIXELS', 1):
            with self.assertRaises(Image.DecompressionBombError):
                split_img.split_long_image(path)

    def test_cli_continues_on_error_and_returns_failure(self):
        path = self.image(size=(10, 30))
        result = subprocess.run([sys.executable, str(Path(split_img.__file__)),
                                 str(self.folder / 'missing.png'), str(path)],
                                capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertTrue((self.folder / (path.stem + '_切片') / '001.png').is_file())

    def test_interactive_blank_then_image_then_quit(self):
        path = self.image(size=(10, 30))
        with patch('builtins.input', side_effect=['', f'"{path}"', 'q']):
            self.assertEqual(split_img.main([]), 0)
        self.assertTrue((self.folder / (path.stem + '_切片') / '001.png').is_file())


if __name__ == '__main__':
    unittest.main(verbosity=2)
