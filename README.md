**[English](#english) | [中文](#中文)**

---

<a name="english"></a>
## English

# AffParser - Arcaea Chart Parser & Slicing Tool

A Python library for parsing and processing Arcaea `.aff` chart files. Supports chart slicing for practice, speed-changing practice, BPM & rhythm verification, and more.

## Features

- **Chart Event Parsing**: Full support for parsing and exporting tap, hold, arc, timing, camera, scenecontrol, timinggroup events
- **BPM Scheduling**: Manages BPM change segments with precise bidirectional conversion between milliseconds and beat positions (fraction-based arithmetic, no floating-point errors)
- **Chart Slicing**: Select any segment to generate looping practice charts, with automatic handling of timing, scenecontrol events
- **Speed Practice**: Generate 0.8x / 0.9x / 1.0x / 1.1x speed charts
- **Audio Slicing**: Slice audio and apply fade-in/out effects via ffmpeg

## Project Structure

```txt
AffParser/
├── aff_parser.py      # Main parsing library
├── bpm_data.json      # Song BPM data
├── bpm_json.py        # BPM data generation script
└── README.md
```

## Dependencies

- Python 3.11+
- numpy
- ffmpeg (required for audio processing; must be installed and added to PATH)

Install Python dependencies:

```bash
pip install numpy
```

## Quick Start

### Parse a Chart

```python
from aff_parser import AffParser

# Load chart from .aff file
parser = AffParser.from_file('path/to/2.aff', 'Pentiment')

# Get all tap events
taps = parser.get_events_by_type('tap')

# Get all arc events
arcs = parser.get_events_by_type('arc')
```

### Chart Slicing (Practice Mode)

```python
from aff_parser import AffParser

parser = AffParser.from_file('path/to/2.aff', 'Pentiment')

# Slice the segment from 100000ms to 120000ms, with 4 blank measures between repeats, repeated 3 times
sliced = parser.slice_practice(100000, 120000, blank_measures=4, repeat_times=3)
sliced.export_aff('slice.aff')
sliced.export_ogg('base.ogg')
```

### Speed Practice

```python
from aff_parser import AffParser, frac

parser = AffParser.from_file('path/to/2.aff', 'Pentiment')

# Set 0.8x speed
parser.speed_set(frac('0.8'))
parser.export_aff('0.8x.aff')
parser.export_ogg('base_0.8x.ogg')
```

### Batch Speed Practice Chart Generation

```python
from aff_parser import task1

# Generate all 4 speed variants (0.8x, 0.9x, 1.0x, 1.1x)
task1('Pentiment', 'path/to/2.aff')
```

### Speed Practice with Slicing

```python
from aff_parser import task1

# Only slice the 100000ms~120000ms segment, generate 4 speed variants
task1('Pentiment', 'path/to/2.aff', sliceQ=True, start_time=100000, end_time=120000)
```

## Interactive CLI Usage

Run `aff_parser.py` directly and follow the interactive prompts:

```bash
python aff_parser.py
```

The interactive flow is as follows:

1. **Verify BPM?** — Enter `y` to enter BPM verification mode, `n` to enter chart generation mode
2. **Enter song name** — Enter the song name (must have corresponding data in `bpm_data.json`)
3. **Enter AFF file path** — Enter or drag in the full path to the `.aff` chart file

### BPM Verification Mode (y)

Parses the `delta_time` of all rhythm points in the chart and outputs the rhythm offset distribution. Used to verify BPM data accuracy — if the errors are not centered around zero or a significant number fall outside the acceptable range (outside the vertical bars), the BPM data may be incorrect.

Output format example: `...|-3,-2,-1,{0},1,2,3|...`, where braces mark the count of rhythm points with 0ms offset, numbers on both sides represent counts falling at each offset value, and vertical bars indicate the acceptable error range.

### Chart Generation Mode (n)

1. **Slice?** — Enter `y` to slice a segment, `n` to generate full-song speed practice
2. If slicing: **Enter time range (ms-ms)** — e.g., `100000-120000`

A `speed_practice/` or `slice_ms_ms/` folder will be generated in the chart directory, containing:

- `0.ogg` / `0.aff` — 0.8x speed
- `1.ogg` / `1.aff` — 0.9x speed
- `base.ogg` / `2.aff` — 1.0x original speed
- `3.ogg` / `3.aff` — 1.1x speed

## Core Classes

### `BpmSchedule`

Manages the BPM change schedule, responsible for bidirectional conversion between milliseconds and beat positions.

- `ms_to_md(time_ms)` — Convert milliseconds to beat position
- `md_to_ms(md)` — Convert beat position to milliseconds
- `slice(start_meas, end_meas, ...)` — Generate a new BPM schedule for slicing
- `scaled(ratio)` / `i_scaled(ratio)` — Speed change

### `AffParser`

Chart parser, the main entry point class.

- `from_file(file_path, song_name)` — Create a parser from a file
- `slice_practice(start_time, end_time, ...)` — Slice practice mode
- `speed_change(ratio)` / `speed_set(speed)` — Speed change
- `parse_rhythm()` — Extract all rhythm points
- `export_aff(output_url)` — Export .aff file
- `export_ogg(output_url)` — Export .ogg audio

### `MeasureData`

Represents beat position data, including millisecond time, beat count, offset, etc.

### `Event`

Chart event, containing type (tap/arc/hold/timing/camera/scenecontrol/timinggroup) and associated data.

## Adding BPM Data for New Songs

Edit `bpm_data.json`, or create a `bpm_data.json` in the chart folder, using the following format:

```json
{
  "SongName": {
    "max_split": [96],
    "bpm": [[BPM_value, measure_count], ...]
  },
  "SongName1": {
    "max_split": [96],
    "bpm": [[256,1],[255,"1/4"],[254,"0.25"],...,[128,-1]]
  }
}
```

- `max_split`: Measure subdivision precision, default 96. For special cases, refer to Arcana Eden's BPM data, format `[96, [[start_ms, end_ms], subdivision], ...]`
- `bpm`: BPM change list, format `[[BPM, measure_count], ...]`, use `-1` for the last entry to indicate it continues to the end
- Measure counts support fraction/decimal format, e.g., `"1/2"` means half a measure

## Notes

- Depends on song BPM data in `bpm_data.json`; songs not yet included must be added manually
- Audio processing requires ffmpeg installed on the system (`ffmpeg` and `ffprobe` commands must be on PATH)
- Slicing is recommended at rhythm point positions to ensure timing remapping accuracy
- Beat arithmetic uses Python `fractions.Fraction` to guarantee no floating-point precision loss

---

<a name="中文"></a>
## 中文

# AffParser - Arcaea 谱面解析与切片工具

一个用于解析和处理 Arcaea `.aff` 谱面文件的 Python 工具库，支持谱面切片练习、变速练习、BPM 与节奏测试等功能。

## 功能特性

- **谱面事件解析**：完整支持 tap、hold、arc、timing、camera、scenecontrol、timinggroup 等事件的解析与导出
- **BPM 调度**：管理 BPM 变化段，实现毫秒 ↔ 节拍位置的双向精确转换（基于分数运算，无浮点误差）
- **谱面切片**：选取任意段落生成循环练习谱面，自动处理 timing、scenecontrol 等事件
- **变速练习**：支持生成 0.8x / 0.9x / 1.0x / 1.1x 倍速谱面
- **音频切片**：配合 ffmpeg 对音频进行切片、淡入淡出处理

## 项目结构

```txt
AffParser/
├── aff_parser.py      # 主解析库
├── bpm_data.json      # 歌曲 BPM 数据
├── bpm_json.py        # BPM 数据生成脚本
└── README.md
```

## 依赖

- Python 3.11+
- numpy
- ffmpeg（用于音频处理，需安装并加入 PATH）

安装 Python 依赖：

```bash
pip install numpy
```

## 快速开始

### 解析谱面

```python
from aff_parser import AffParser

# 从 .aff 文件加载谱面
parser = AffParser.from_file('path/to/2.aff', 'Pentiment')

# 获取所有 tap 事件
taps = parser.get_events_by_type('tap')

# 获取所有 arc 事件
arcs = parser.get_events_by_type('arc')
```

### 谱面切片（练习模式）

```python
from aff_parser import AffParser

parser = AffParser.from_file('path/to/2.aff', 'Pentiment')

# 切片 100000ms 到 120000ms 的段落，之间间隔 4 小节，重复 3 次
sliced = parser.slice_practice(100000, 120000, blank_measures=4, repeat_times=3)
sliced.export_aff('slice.aff')
sliced.export_ogg('base.ogg')
```

### 变速练习

```python
from aff_parser import AffParser, frac

parser = AffParser.from_file('path/to/2.aff', 'Pentiment')

# 设置 0.8 倍速
parser.speed_set(frac('0.8'))
parser.export_aff('0.8x.aff')
parser.export_ogg('base_0.8x.ogg')
```

### 批量生成变速练习谱

```python
from aff_parser import task1

# 生成全部 4 种倍速（0.8x, 0.9x, 1.0x, 1.1x）
task1('Pentiment', 'path/to/2.aff')
```

### 带切片的变速练习

```python
from aff_parser import task1

# 仅切取 100000ms~120000ms 段落，生成 4 种倍速
task1('Pentiment', 'path/to/2.aff', sliceQ=True, start_time=100000, end_time=120000)
```

## 交互式 CLI 使用

直接运行 `aff_parser.py`，按提示交互操作：

```bash
python aff_parser.py
```

运行后会出现以下交互流程：

1. **验证 BPM？** — 输入 `y` 进入 BPM 验证模式，输入 `n` 进入谱面生成模式
2. **请输入歌曲名** — 输入歌曲名称（需在 `bpm_data.json` 中有对应数据）
3. **请输入 AFF 文件路径** — 输入或拖入 `.aff` 谱面的完整路径

### BPM 验证模式（y）

解析谱面中所有节奏点的 `delta_time`，输出节奏偏移分布。用于验证 BPM 数据的准确性——如果误差不呈中心分布或有一定数量落在允许范围外（竖线外），说明 BPM 数据可能有误。

输出格式示例：`...|-3,-2,-1,{0},1,2,3|...`，其中括号标注偏移 0ms 的节奏数量，两边数字为落在各偏移值的节奏数量，竖线内为误差允许范围。

### 谱面生成模式（n）

1. **是否分段？** — 输入 `y` 进行分段切片，输入 `n` 生成整曲变速练习
2. 若分段：**请输入时间范围(ms-ms)** — 如 `100000-120000`

最终在谱面目录下生成 `speed_practice/` 或 `slice_ms_ms/` 文件夹，包含：

- `0.ogg` / `0.aff` — 0.8x 倍速
- `1.ogg` / `1.aff` — 0.9x 倍速
- `base.ogg` / `2.aff` — 1.0x 原速
- `3.ogg` / `3.aff` — 1.1x 倍速

## 核心类说明

### `BpmSchedule`

管理 BPM 变化调度表，负责毫秒与节拍位置的双向转换。

- `ms_to_md(time_ms)` — 毫秒转节拍位置
- `md_to_ms(md)` — 节拍位置转毫秒
- `slice(start_meas, end_meas, ...)` — 生成切片用的新 BPM 调度
- `scaled(ratio)` / `i_scaled(ratio)` — 变速

### `AffParser`

谱面解析器，核心入口类。

- `from_file(file_path, song_name)` — 从文件创建解析器
- `slice_practice(start_time, end_time, ...)` — 切片练习模式
- `speed_change(ratio)` / `speed_set(speed)` — 变速
- `parse_rhythm()` — 提取所有节奏点
- `export_aff(output_url)` — 导出 .aff 文件
- `export_ogg(output_url)` — 导出 .ogg 音频

### `MeasureData`

表示节拍位置数据，包含毫秒时间、节拍数、偏移量等信息。

### `Event`

谱面事件，包含类型（tap/arc/hold/timing/camera/scenecontrol/timinggroup）和对应数据。

## 添加新歌曲 BPM 数据

编辑 `bpm_data.json`、或在谱面文件夹下创建 `bpm_data.json`，按以下格式添加：

```json
{
  "歌曲名": {
    "max_split": [96],
    "bpm": [[BPM值, 持续小节数], ...]
  },
  "歌曲名1": {
    "max_split": [96],
    "bpm": [[256,1],[255,"1/4"],[254,"0.25"],...,[128,-1]]
  }
}
```

- `max_split`：小节分割精度，默认 96，特殊情况可参考 Arcana Eden 的 BPM 数据，格式 `[96, [[开始毫秒数, 结束毫秒数], 分音], ...]`
- `bpm`：BPM 变化列表，格式 `[[BPM, 小节数], ...]`，最后一个用 `-1` 表示持续到结尾
- 小节数支持分数小数格式，如 `"1/2"` 表示半个小节

## 注意事项

- 依赖 `bpm_data.json` 中的歌曲 BPM 数据，若歌曲未收录需手动添加
- 音频处理需要系统安装 ffmpeg（`ffmpeg` 和 `ffprobe` 命令需在 PATH 中）
- 切片功能建议在节奏点位置切分，以保证 timing 重映射准确性
- 节拍运算使用 Python `fractions.Fraction`，确保无浮点精度损失
