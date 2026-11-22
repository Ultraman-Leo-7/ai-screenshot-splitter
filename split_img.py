"""长截图切分：保留原始像素，重叠裁剪，默认输出无损 PNG。"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    print('缺少 Pillow。请运行“长图切分.bat”，或执行 python -m pip install -r requirements.txt。', file=sys.stderr)
    raise SystemExit(2)

HEIGHT_RATIO = 1.6
OVERLAP_RATIO = 0.12
MERGE_TAIL_RATIO = 0.35


def validate_ratios(height_ratio: float, overlap_ratio: float, merge_tail_ratio: float) -> None:
    if not all(math.isfinite(v) for v in (height_ratio, overlap_ratio, merge_tail_ratio)):
        raise ValueError('比例必须是有限数字。')
    if height_ratio <= 0:
        raise ValueError('分段高度比例必须大于 0。')
    if not 0 <= overlap_ratio < height_ratio:
        raise ValueError('重叠比例必须大于等于 0，且小于分段高度比例。')
    if not 0 <= merge_tail_ratio < 1:
        raise ValueError('尾段合并比例必须在 0（含）到 1（不含）之间。')


def plan_slices(width: int, height: int, height_ratio: float = HEIGHT_RATIO,
                overlap_ratio: float = OVERLAP_RATIO,
                merge_tail_ratio: float = MERGE_TAIL_RATIO) -> list[tuple[int, int]]:
    validate_ratios(height_ratio, overlap_ratio, merge_tail_ratio)
    if width <= 0 or height <= 0:
        raise ValueError('图片尺寸必须大于 0。')
    slice_height = max(1, int(width * height_ratio))
    overlap = min(slice_height - 1, int(width * overlap_ratio))
    slices = []
    top = 0
    while top < height:
        bottom = min(top + slice_height, height)
        if height - bottom < slice_height * merge_tail_ratio:
            bottom = height
        slices.append((top, bottom))
        if bottom == height:
            break
        top = bottom - overlap
    return slices


def parse_dragged_paths(raw: str) -> list[str]:
    """只解析路径，不执行终端命令；支持 CMD 双引号及 PowerShell 单引号。"""
    raw = raw.strip()
    if not raw:
        return []
    # 直接粘贴的单个路径即使含空格，也能识别。
    if Path(raw).is_file():
        return [raw]
    paths = []
    i = 0
    while i < len(raw):
        if raw[i].isspace():
            i += 1
            continue
        token = []
        if raw[i] in "\"'":
            quote = raw[i]
            i += 1
            while i < len(raw):
                if raw[i] == quote:
                    if i + 1 < len(raw) and raw[i + 1] == quote:
                        token.append(quote)
                        i += 2
                        continue
                    i += 1
                    break
                token.append(raw[i])
                i += 1
            else:
                raise ValueError('路径引号没有闭合，请重新拖入图片。')
        else:
            while i < len(raw) and not raw[i].isspace():
                token.append(raw[i])
                i += 1
        value = ''.join(token)
        if value and value != '&':
            paths.append(value)
    return paths


def make_output_dir(path: Path, output_root: Path | None) -> Path:
    parent = output_root if output_root is not None else path.parent
    parent.mkdir(parents=True, exist_ok=True)
    sequence = 1
    while True:
        suffix = '' if sequence == 1 else f'_{sequence}'
        candidate = parent / f'{path.stem}_切片{suffix}'
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            sequence += 1


def save_png(crop: Image.Image, destination: Path) -> None:
    if crop.mode in {'1', 'L', 'LA', 'P', 'RGB', 'RGBA', 'I;16'}:
        crop.save(destination, format='PNG')
    else:
        # CMYK JPEG 等模式无法直接存为 PNG。
        with crop.convert('RGB') as converted:
            converted.save(destination, format='PNG')


def split_long_image(file_path: str | Path, *, height_ratio: float = HEIGHT_RATIO,
                     overlap_ratio: float = OVERLAP_RATIO,
                     merge_tail_ratio: float = MERGE_TAIL_RATIO,
                     output_root: Path | None = None) -> Path:
    validate_ratios(height_ratio, overlap_ratio, merge_tail_ratio)
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f'找不到文件：{path}')
    out_dir = None
    try:
        # 保留 Pillow 的默认像素保护，不对所有输入无条件关闭限制。
        with Image.open(path) as source:
            if getattr(source, 'n_frames', 1) > 1:
                raise ValueError('暂不处理动画或多页图片，请先导出需要的单张静态图片。')
            with ImageOps.exif_transpose(source) as img:
                width, height = img.size
                slices = plan_slices(width, height, height_ratio, overlap_ratio, merge_tail_ratio)
                out_dir = make_output_dir(path, output_root)
                records = []
                for index, (top, bottom) in enumerate(slices, start=1):
                    filename = f'{index:03d}.png'
                    with img.crop((0, top, width, bottom)) as crop:
                        save_png(crop, out_dir / filename)
                    records.append({'file': filename, 'top': top, 'bottom': bottom,
                                    'width': width, 'height': bottom - top})
                manifest = {'source': str(path), 'oriented_size': [width, height],
                            'height_ratio': height_ratio, 'overlap_ratio': overlap_ratio,
                            'merge_tail_ratio': merge_tail_ratio, 'slices': records}
                (out_dir / '切片记录.json').write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except Exception:
        if out_dir is not None:
            print(f'[提示] 未完成的输出保留在：{out_dir}；请勿作为完整结果使用。', file=sys.stderr)
        raise
    print(f'[完成] {path.name}：{width} × {height} → {len(slices)} 张 PNG\n       {out_dir}')
    return out_dir


def process_paths(paths: list[str], options: argparse.Namespace) -> int:
    failures = 0
    for path in paths:
        try:
            split_long_image(path, height_ratio=options.height_ratio,
                             overlap_ratio=options.overlap_ratio,
                             merge_tail_ratio=options.merge_tail_ratio,
                             output_root=options.output_dir)
        except Image.DecompressionBombError:
            failures += 1
            print(f'[失败] {path}：像素数超出 Pillow 保护阈值，请先缩小或分段导出原图。', file=sys.stderr)
        except Exception as error:
            failures += 1
            print(f'[失败] {path}：{error}', file=sys.stderr)
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='长截图重叠裁剪；不缩放，默认输出无损 PNG。')
    parser.add_argument('images', nargs='*', help='一张或多张图片，含空格的路径请加引号')
    parser.add_argument('--height-ratio', type=float, default=HEIGHT_RATIO, help='分段高度 / 宽度，默认 1.6')
    parser.add_argument('--overlap-ratio', type=float, default=OVERLAP_RATIO, help='重叠高度 / 宽度，默认 0.12')
    parser.add_argument('--merge-tail-ratio', type=float, default=MERGE_TAIL_RATIO, help='合并尾段阈值，默认 0.35')
    parser.add_argument('--output-dir', type=Path, help='输出父目录，默认与原图同目录')
    options = parser.parse_args(argv)
    try:
        validate_ratios(options.height_ratio, options.overlap_ratio, options.merge_tail_ratio)
    except ValueError as error:
        parser.error(str(error))
    if options.images:
        return int(process_paths(options.images, options) > 0)
    print('把图片拖入窗口后按回车（支持多张）；输入 q 退出。\n每次使用新文件夹保存，原图保持不变。')
    failures = 0
    while True:
        try:
            raw = input('\n拖入图片 > ').strip()
        except EOFError:
            break
        if raw.lower() in {'q', 'quit', 'exit'}:
            break
        if not raw:
            continue
        try:
            paths = parse_dragged_paths(raw)
        except ValueError as error:
            print(f'[提示] {error}')
            continue
        failures += process_paths(paths, options)
    return int(failures > 0)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\n已取消。')
        raise SystemExit(130)
