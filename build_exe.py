"""在 Windows 上构建单文件 EXE；构建产物不会覆盖现有文件。"""

import argparse
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description='构建长图切分 Windows x64 单文件版')
    parser.add_argument('--output-dir', type=Path, default=Path('dist'))
    options = parser.parse_args()
    if sys.platform != 'win32' or platform.machine().upper() not in {'AMD64', 'X86_64'}:
        parser.error('请在 Windows x64 环境构建。')
    if sys.version_info < (3, 11):
        parser.error('需要 Python 3.11 或以上版本。')
    root = Path(__file__).resolve().parent
    destination = options.output_dir.resolve()
    if (destination / '长图切分.exe').exists():
        parser.error('输出 EXE 已存在，请使用 --output-dir 指定新的输出目录。')
    build_dir = root / 'build' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    build_dir.mkdir(parents=True)
    env = os.environ.copy()
    env['PYINSTALLER_CONFIG_DIR'] = str(build_dir / 'cache')
    env['PYTHONUTF8'] = '1'
    result = subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--onefile', '--console', '--noupx',
        '--name', '长图切分', '--distpath', str(destination),
        '--workpath', str(build_dir / 'work'), '--specpath', str(build_dir),
        str(root / 'exe_entry.py'),
    ], cwd=root, env=env)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
