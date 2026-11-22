"""独立 EXE 入口；复用已经验证的切片程序。"""

import sys

from split_img import main


def run() -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    try:
        result = main()
    except SystemExit as error:
        result = error.code if isinstance(error.code, int) else 1
    except KeyboardInterrupt:
        print('\n已取消。')
        return 130
    # 拖到 EXE 图标上会新开窗口；等待回车，方便查看结果及错误。
    # 重定向输入的自动化调用不暂停；无参数交互模式自行等待输入。
    if len(sys.argv) > 1 and sys.stdin.isatty() and not any(
            item in {'-h', '--help'} for item in sys.argv[1:]):
        try:
            input('\n处理结束，按回车关闭窗口…')
        except (EOFError, KeyboardInterrupt):
            pass
    return result


if __name__ == '__main__':
    raise SystemExit(run())
