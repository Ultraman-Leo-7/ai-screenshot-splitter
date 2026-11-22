# 长图切分 · AI Screenshot Splitter

把长截图按原始分辨率切成多张有重叠的短图，方便上传给支持图片输入的 AI，保留文字和局部细节。

提供 **Windows x64 单文件 EXE**：不需要安装 Python 或 Pillow，切图过程无需联网。

## 下载和使用

从 [Releases 下载最新版](https://github.com/Ultraman-Leo-7/ai-screenshot-splitter/releases/latest)中的 `长图切分.exe`。

1. 双击 EXE，把图片拖进窗口后按回车。支持多张、连续处理，输入 `q` 退出。
2. 也可以把一张或多张图片直接拖到 EXE 图标上，处理结束后按回车关闭窗口。
3. 切片保存在原图旁的 `原文件名_切片` 文件夹，按编号顺序上传其中的 PNG 即可。

重复运行会创建 `_2`、`_3` 等新目录，不改动原图，不覆盖旧结果。只复制 EXE 一个文件也能运行。

## 切片规则

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| 分段高度 | 宽度 × 1.6 | 不缩放原图 |
| 重叠高度 | 宽度 × 0.12 | 保留切口附近上下文，约为常规段高的 7.5% |
| 尾段合并阈值 | 常规段高 × 0.35 | 剩余尾条不足此值时并入当前段 |
| 输出格式 | PNG | 无损保存，保留透明通道 |

例如，1080 × 10000 的长图默认切成 6 张：常规段高 1728，重叠 129，最后一张合并尾条后高 2005 像素。

自动校正 EXIF 方向；CMYK 等无法直接保存为 PNG 的模式转换为 RGB。每批结果包含 `切片记录.json`，记录原图路径、校正方向后的尺寸和各片的起止坐标。只有生成记录并提示“完成”，才表示该张图片全部处理完毕。

重叠裁剪不做 OCR，不能保证切口避开文字。不同 AI 对图片的缩放和视觉 token 分配规则不同，分段有助于保留局部细节，但不能保证特定模型的识别效果或固定 token 预算。

## 命令行参数

```powershell
& ".\长图切分.exe" "D:\图片\长截图.png"
& ".\长图切分.exe" "D:\图片\一.png" "D:\图片\二.jpg"
& ".\长图切分.exe" "D:\图片\长截图.png" --height-ratio 1.8 --overlap-ratio 0.15 --output-dir "D:\图片\结果"
& ".\长图切分.exe" --help
```

`--merge-tail-ratio` 可调整尾段阈值。含空格的路径请加引号。终端交互支持 CMD 双引号、PowerShell 单引号及开头的 `&`，输入只作为路径解析，不执行命令。

EXE 有图片参数且标准输入来自终端时，处理结束等待回车；输入重定向时不暂停。全部成功退出码为 0；有图片失败为 1；参数错误为 2。单张失败后继续处理其他图片。

## 从源码运行

Python 3.11 以上：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe split_img.py
```

Windows 也可双击 `长图切分.bat`，启动文件会创建独立环境并安装依赖，首次配置需要网络。源码依赖 Pillow 13.0.0。

## 构建 EXE

请在 Windows x64 上构建；当前发行版使用 Python 3.14.5、Pillow 13.0.0、PyInstaller 6.22.3。

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe build_exe.py
```

产物为 `dist\长图切分.exe`。输出已存在时脚本停止，可使用 `--output-dir dist-v2` 指定新目录。构建中间文件存入带时间戳的新目录，不执行批量清理。

## 验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

13 项源码测试涵盖坐标覆盖、尾段合并、像素一致性、路径解析、透明通道、EXIF、异常输入等。测试图片和结果保存在被 Git 忽略的 `.test-artifacts` 目录。

发行 EXE 另通过 14 项隔离运行检查：仅复制 EXE 到独立目录、从 PATH 去掉 Python、把 PYTHONHOME/PYTHONPATH 指向不存在的位置，验证启动、多图和多格式处理。未在另一台无 Python 的实体电脑上测试。详见 [EXE验证记录.json](EXE验证记录.json)。

## 支持范围

EXE 面向 Windows 10/11 x64。单文件版启动时会解压内置运行库到系统临时目录，启动可能需要片刻。

保留 Pillow 默认的超大像素保护；异常大的图片可能警告或被拒绝。暂不处理动画、多页图片、文件夹递归及通配符。HEIC 等格式未添加额外解码插件。输出无损 PNG 可能大于原 JPEG 或 WebP。
