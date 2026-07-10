from typing import Any
import copy
cp = copy.deepcopy
import fractions
frac = fractions.Fraction
import json
import numpy as np
import os
import re
import subprocess

def format_json(obj, indent=0, max_length=100):
    """自定义 JSON 格式化：列表默认压缩到一行，超长时换行缩进。"""
    sp = '  ' * indent
    inner_sp = '  ' * (indent + 1)

    if isinstance(obj, dict):
        if not obj:
            return '{}'
        items = []
        for k, v in obj.items():
            k_str = json.dumps(k, ensure_ascii=False)
            v_str = format_json(v, indent + 1, max_length)
            items.append(f'{inner_sp}{k_str}: {v_str}')
        return '{\n' + ',\n'.join(items) + f'\n{sp}}}'

    elif isinstance(obj, list):
        if not obj:
            return '[]'

        # 先递归格式化每个元素
        item_strs = [format_json(item, indent + 1, max_length) for item in obj]
        # 尝试压缩到一行
        compact = '[' + ', '.join(item_strs) + ']'
        if len(sp + compact) <= max_length:
            return compact

        # 超长则贪心换行
        lines = ['[']
        cur_line = inner_sp
        first = True
        for i, item in enumerate(item_strs):
            sep = '' if first else ' '
            comma = ',' if i < len(item_strs) - 1 else ''
            seg = sep + item + comma
            if not first and len(cur_line + seg) > max_length:
                lines.append(cur_line)
                cur_line = inner_sp + item + comma
            else:
                cur_line += seg
            first = False
        if cur_line.strip():
            lines.append(cur_line)
        lines.append(f'{sp}]')
        return '\n'.join(lines)

    elif isinstance(obj, frac):
        return json.dumps(f'{obj.numerator}/{obj.denominator}', ensure_ascii=False)

    elif isinstance(obj, bool):
        return 'true' if obj else 'false'

    elif isinstance(obj, (int, float)):
        return json.dumps(obj)

    elif obj is None:
        return 'null'

    else:
        return json.dumps(obj, ensure_ascii=False)

def round_up(x):
    return (x + frac(1, 2)) // 1

def custom_decoder(obj):
    if isinstance(obj, str) and ('/' in obj or '.' in obj):
        try:
            return frac(obj)
        except ValueError:
            print(f'无法解析的分数: {obj}')
    elif isinstance(obj, list):  # 递归处理列表中的元素
        return [custom_decoder(item) for item in obj]
    elif isinstance(obj, dict):  # 递归处理字典中的元素
        return {key: custom_decoder(value) for key, value in obj.items()}
    return obj

with open('bpm_data.json', 'r', encoding='utf-8') as f:
    _BUILTIN_BPM = json.load(f, object_hook=custom_decoder)

def merge_bpm(bpm_list: list) -> list:
    merged = []
    for bpm, dur in bpm_list:
        if merged and merged[-1][0] == bpm:
            if dur != -1:
                merged[-1][1] += dur
            else:
                merged[-1][1] = -1
        else:
            merged.append([bpm, dur])
    return merged

def remap_md(md: 'MeasureData', new_meas: frac, bpm_schedule: 'BpmSchedule') -> 'MeasureData':
    new_md = MeasureData(0, new_meas, md.delta_time, True, bpm_schedule)
    new_md.ms = int(new_md)
    new_md.valid = md.valid
    return new_md

class Event:
    """
    Event
    .type: str: 事件类型
    .data: any: 参数
    type对应的data格式
    text: str
    tap: list[int]: [s_ms, 轨道]
    arc: list[any]: [s_ms, e_ms, x_s, x_e, 形状, y_s, y_e, 颜色, 其它, 虚线, [ms]]
    hold: list[int]: [s_ms, e_ms, 轨道]
    timing: list[int, frac, float]: [ms, bpm, 拍数]
    timinggroup: AffParser
    camera: list[any]: [ms, ...]
    scenecontrol: list[any]: [ms, 类型, (可选)持续时间, (可选)执行]
    """
    def __init__(self, type: str, data: Any):
        self.type = type
        self.data = data

    def __len__(self):
        if self.type == 'arc':
            return len(self.data[-1])
        return len(self.data)

class MeasureData:
    def __init__(self, ms: int, measures: frac, delta_time: int = 0, valid: bool = True, bpm_schedule: 'BpmSchedule' = None):
        self.ms = ms # 仅用作排序和缓存的键，不参与计算
        self.measures = measures
        self.delta_time = delta_time
        self.valid = valid
        self.bpm_schedule = bpm_schedule

    @classmethod
    def from_ms(cls, ms: int, bpm_schedule: 'BpmSchedule'):
        """从毫秒时间创建MeasureData实例，使用BPM调度表进行转换。"""
        return bpm_schedule.ms_to_md(ms)
    def __int__(self):
        """将MeasureData实例转换为毫秒时间，使用BPM调度表进行转换。"""
        return self.bpm_schedule.md_to_ms(self)

    def __str__(self):
        return str(int(self))
    
    def __repr__(self):
        return f'{self.ms}, {self.measures // 1}, {self.measures % 1}, {self.delta_time}, {self.valid}'
    
    def __float__(self):
        return float(int(self))

class BpmSchedule:
    """
    BPM 调度表，管理 max_split 与 BPM 变化段，负责 毫秒↔节拍位置 双向转换。

    内部数据：
      max_split: [default: frac, [[start_ms: int, end_ms: int], split: frac]]
      bpm_: [[bpm: Fraction, dur: frac], ...] 
      time_: [time_ms: Fraction, ...]  二分查找用
      measure_: [measure: Fraction, ...]  二分查找用
      _cache_ms_to_md: {time_ms: MeasureData}
    """
    def __init__(self, max_split: list, bpm_list: list):
        self.max_split = max_split
        self.bpm = merge_bpm(bpm_list)
        self.length = len(self.bpm)
        self.speed = 1
        self._cache_ms_to_md = {}
        self.time = [0]
        self.measure = [0]
        for bpm, dur in self.bpm:
            if dur == -1:
                break
            time = frac(240, bpm) * dur
            self.time.append(self.time[-1] + time)
            self.measure.append(self.measure[-1] + dur)

    def __len__(self):
        return self.length
    
    def get_max_split_by_ms(self, time_ms: int) -> int:
        ms = self.max_split
        if ms:
            default = ms[0]
            for [start, end], split in ms[1:]:
                if start <= time_ms < end:
                    return split
            return default
        else:
            return 96
    
    def find_segment_by_ms(self, time_ms: int) -> int:
        """二分查找节拍段，返回节拍段索引"""
        time = frac(time_ms, 1000)
        left, right = 0, self.length - 1
        while left < right:
            mid = (left + right) // 2
            if self.time[mid] <= time < self.time[mid + 1]:
                return mid
            elif time < self.time[mid]:
                right = mid - 1
            else:
                left = mid + 1
        return left
    
    def find_segment_by_measure(self, measure: frac) -> int:
        """二分查找节拍段，返回节拍段索引"""
        left, right = 0, self.length - 1
        while left < right:
            mid = (left + right) // 2
            if self.measure[mid] <= measure < self.measure[mid + 1]:
                return mid
            elif measure < self.measure[mid]:
                right = mid - 1
            else:
                left = mid + 1
        return left
    
    def ms_to_md(self, time_ms: int) -> MeasureData:
        if time_ms in self._cache_ms_to_md:
            return self._cache_ms_to_md[time_ms]
        
        max_split = self.get_max_split_by_ms(time_ms)
        segment_idx = self.find_segment_by_ms(time_ms)
        measure_time = frac(240, self.bpm[segment_idx][0])
        pos = frac(round_up((frac(time_ms, 1000) - self.time[segment_idx]) / measure_time * max_split), max_split)
        measure_pos = self.measure[segment_idx] + pos
        if pos == self.bpm[segment_idx][1]:
            pos = 0
            segment_idx += 1
            measure_time = frac(240, self.bpm[segment_idx][0])
        absolute_time = self.time[segment_idx] + measure_time * pos
        delta_time = time_ms - absolute_time * 1000 // 1
        # valid = abs(time_ms - absolute_time * 1000) < 4
        valid = abs(delta_time) <= 3
        md = MeasureData(ms=time_ms, measures=measure_pos, delta_time=delta_time, valid=valid, bpm_schedule=self)
        self._cache_ms_to_md[time_ms] = md
        return md
    
    def measure_to_time(self, measure_pos: frac) -> frac:
        segment_idx = self.find_segment_by_measure(measure_pos)
        measure_time = frac(240, self.bpm[segment_idx][0])
        pos = measure_pos - self.measure[segment_idx]
        time = self.time[segment_idx] + measure_time * pos
        return time
    
    def md_to_ms(self, md: MeasureData) -> int:
        if md.valid:
            return self.measure_to_time(md.measures) * 1000 // 1 + md.delta_time
        else:
            return int(md.ms / self.speed)

    def scaled(self, ratio: frac) -> 'BpmSchedule':
        """返回变速后的新 BpmSchedule（所有 BPM × ratio）"""
        new_bpm = [[bpm * ratio, dur] for bpm, dur in self.bpm]
        bs = BpmSchedule(self.max_split, new_bpm)
        bs.speed = self.speed * ratio
        return bs
    
    def i_scaled(self, ratio: frac):
        """就地变速（所有 BPM × ratio）"""
        for item in self.bpm:
            item[0] *= ratio
        for i in range(self.length):
            self.time[i] /= ratio
        self.speed *= ratio
    
    def slice(self, start_meas: frac, end_meas: frac, blank_measures: int = 0, repeat_times: int = None) -> 'BpmSchedule':
        """返回切片后的新 BpmSchedule（保留 start_time 到 end_time 的部分，前后添加 1 个小节，之间空出 blank_measures 个小节，并重复 repeat_times 次）
        不推荐变速后再切片，因为切片会重新计算节拍位置，可能引入误差，建议先切片后变速。"""
        segment_idx = self.find_segment_by_measure(start_meas)
        segment_jdx = self.find_segment_by_measure(end_meas)
        measure_length = end_meas - start_meas + blank_measures + 2
        start_bpm = self.bpm[segment_idx][0]
        end_bpm = self.bpm[segment_jdx][0]
        start_time = self.measure_to_time(start_meas)
        end_time = self.measure_to_time(end_meas)
        max_time = 150
        if repeat_times == None:
            a = max_time + frac(240, start_bpm) * blank_measures / frac('0.8')
            b = (end_time - start_time + frac(240, start_bpm) * (1 + blank_measures) + frac(240, end_bpm)) / frac('0.8')
            repeat_times = a // b
            print(f'repeat_times: {repeat_times}')
        if segment_idx == segment_jdx:
            new_bpm = [[self.bpm[segment_idx][0], -1]]
        else:
            new_bpm_ = cp(self.bpm[segment_idx:segment_jdx + 1])
            new_bpm_[0][1] = self.measure[segment_idx + 1] - start_meas + 1
            new_bpm_[-1][1] = end_meas - self.measure[segment_jdx] + 1
            new_bpm_.append([new_bpm_[0][0], blank_measures])
            new_bpm = []
            for _ in range(repeat_times):
                new_bpm.extend(cp(new_bpm_))
            new_bpm[-1][1] = -1
            new_bpm = merge_bpm(new_bpm)
        bs = BpmSchedule(self.max_split, new_bpm)
        bs.measure_length = measure_length
        bs.start_bpm = start_bpm
        bs.end_bpm = end_bpm
        return bs, repeat_times
    
    def export_bpm(self, song_name: str, output_path: str):
        """导出BPM文件bpm_data.json（绝对路径）"""
        data = {song_name: {'max_split': self.max_split, 'bpm': self.bpm}}
        json_str = format_json(data)
        output_path = os.path.join(output_path, 'bpm_data.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json_str)

class AffParser:
    """AffParser类，用于解析.aff文件。"""
    def __init__(self, timinggroup: bool = False, noinput: bool = False, parent_parser = None):
        """初始化AffParser实例，设置默认属性值。"""
        self.events = []

        self.timinggroup = timinggroup
        self.noinput = noinput
        self.parent_parser = parent_parser

        self.file_path = None
        self.folder_path = None
        self.file_name = None
        
        self.audio_data = None
        self.sample_rate = None
        self.channels = None
        
        self.song_name = None
        self.audio_offset = None
        self.speed = 1
        self.bpm_schedule = None

    def __len__(self):
        return len(self.events)
    
    @classmethod
    def from_file(cls, file_path: str, song_name: str, parse_ogg: bool = True):
        """从.aff文件路径创建AffParser实例。
        
        参数：
        file_path: str: 谱面aff完整路径
        song_name: str: 歌曲名
        parse_ogg: bool: 是否解析歌曲数据
        
        返回：
        AffParser实例
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件 {file_path} 不存在")
        parser = cls()

        parser.file_path = file_path
        parser.folder_path = os.path.dirname(file_path)
        parser.file_name = os.path.basename(file_path)

        parser.song_name = song_name
        parser.init_bpm()

        if parse_ogg:
            parser.load_ogg()

        parser.parse_event()
        return parser

    @classmethod
    def from_timinggroup(cls, content_list: list[str], noinput: bool = False, parent_parser = None):
        """从timinggroup创建AffParser实例。
        
        参数：
        content_list: list[str]: timinggroup内容列表
        noinput: bool: 是否为timinggroup
        parent_parser: AffParser: timinggroup的主谱面
        """
        parser = cls(timinggroup=True, noinput=noinput, parent_parser=parent_parser)
        parser.bpm_schedule = parent_parser.bpm_schedule
        parser.parse_event(content_list)
        return parser

    def load_aff(self) -> list[str]:
        """加载.aff文件内容。
        
        返回：
        list[str]: .aff文件内容列表
        """
        with open(self.file_path, 'r', encoding='utf-8') as f:
            content_list = f.readlines()
        return content_list
    
    def init_bpm(self):
        """初始化BPM调度表。"""
        data = _BUILTIN_BPM.get(self.song_name)
        if not data:
            url = os.path.join(self.folder_path, 'bpm_data.json')
            try:
                with open(url, 'r', encoding='utf-8') as f:
                    data_ = json.load(f, object_hook=custom_decoder)
                data = data_.get(self.song_name)
            except FileNotFoundError:
                raise FileNotFoundError(f"歌曲 {self.song_name} 的BPM数据未找到")
            if not data:
                raise ValueError(f"歌曲 {self.song_name} 的BPM数据未找到")
        self.bpm_schedule = BpmSchedule(data['max_split'], data['bpm'])
    
    def load_ogg(self):
        """加载歌曲ogg文件（使用 ffmpeg 解码）。"""
        url = os.path.join(self.folder_path, 'base.ogg')
        try:
            # 用 ffprobe 获取音频信息
            probe = subprocess.run(
                ["ffprobe", "-v", "error",
                 "-select_streams", "a:0",
                 "-show_entries", "stream=sample_rate,channels",
                 "-of", "csv=p=0", url],
                capture_output=True, text=True
            )
            sr_str, ch_str = probe.stdout.strip().split(',')
            self.sample_rate = int(sr_str)
            self.channels = int(ch_str)

            # 用 ffmpeg 解码为 raw f32le PCM
            raw = subprocess.run(
                ["ffmpeg", "-v", "error",
                 "-i", url,
                 "-f", "f32le",
                 "-acodec", "pcm_f32le",
                 "-"],
                capture_output=True
            )
            self.audio_data = np.frombuffer(raw.stdout, dtype='float32').copy()
            if self.channels > 1:
                self.audio_data = self.audio_data.reshape(-1, self.channels)
        except (FileNotFoundError, subprocess.CalledProcessError):
            print(f"歌曲 {self.song_name} 的ogg文件未找到或解码失败, 不加载歌曲数据")

    def parse_event(self, content_list: list[str] = None):
        """解析事件行。"""
        in_timinggroup = False
        timinggroup_content = []

        if content_list is None:
            content_list = self.load_aff()

        for line_ in content_list:
            line = line_.strip()
            if not line: continue
            if not in_timinggroup:
                if line[0] == '(':
                    event = self.parse_tap(line)
                elif line.startswith('hold('):
                    event = self.parse_hold(line)
                elif line.startswith('arc('):
                    event = self.parse_arc(line)
                elif line.startswith('timing('):
                    event = self.parse_timing(line)
                elif line.startswith('timinggroup('):
                    in_timinggroup = True
                    noinput_match = bool(re.search(r'noinput', line))
                    continue
                elif line.startswith('camera('):
                    event = self.parse_camera(line)
                elif line.startswith('scenecontrol('):
                    event = self.parse_scenecontrol(line)
                else:
                    if 'AudioOffset:' in line:
                        self.audio_offset = int(line.split(':')[1].strip())
                    event = Event('text', line_)
                self.events.append(event)
            else:
                if line != '};':
                    timinggroup_content.append(line_)
                else:
                    event = self.parse_timinggroup(timinggroup_content, noinput_match)
                    in_timinggroup = False
                    timinggroup_content = []
                    self.events.append(event)

    def parse_tap(self, line: str):
        """解析tap元素"""
        tap_pattern = r'\((\d+),(\d)\)'
        tap_matches = re.search(tap_pattern, line)
        if tap_matches:
            tap_time = MeasureData.from_ms(int(tap_matches.group(1)), self.bpm_schedule)
            tap_track = int(tap_matches.group(2))
            return Event('tap', [tap_time, tap_track])
        else:
            print(f"Invalid tap format: {line}")
            return False

    def parse_arc(self, line: str):
        """解析arc元素"""
        arc_pattern = r'arc\(([^)]+)\)(?:\[([^]]+)\])?'
        arc_matches = re.search(arc_pattern, line)
        if arc_matches:
            arc_args = arc_matches.group(1).split(',')
            arctaps = []
            if arc_matches.group(2) is not None:
                arctaps = arc_matches.group(2).split(',')
            arcdata = [MeasureData.from_ms(int(arc_args[0]), self.bpm_schedule),
                       MeasureData.from_ms(int(arc_args[1]), self.bpm_schedule)]
            arcdata.extend(arc_args[2:])
            arctap_list = []
            arctap_pattern = r'arctap\((\d+)\)'
            for arctap in arctaps:
                time_matches = re.search(arctap_pattern, arctap)
                if time_matches:
                    arctap_list.append(MeasureData.from_ms(int(time_matches.group(1)), self.bpm_schedule))
                else:
                    print('Invalid arctap format:', line, '-', arctap)
                    return False
            arcdata.append(arctap_list)
            return Event('arc', arcdata)
        else:
            print('Invalid arc format:', line)
            return False
    
    def parse_hold(self, line: str):
        """解析hold元素"""
        hold_pattern = r'hold\((\d+),(\d+),(\d)\)'
        hold_matches = re.search(hold_pattern, line)
        if hold_matches:
            hold_start = MeasureData.from_ms(int(hold_matches.group(1)), self.bpm_schedule)
            hold_end = MeasureData.from_ms(int(hold_matches.group(2)), self.bpm_schedule)
            hold_track = int(hold_matches.group(3))
            return Event('hold', [hold_start, hold_end, hold_track])
        else:
            print(f"Invalid hold format: {line}")
            return False
    
    def parse_timing(self, line: str):
        """解析timing元素"""
        timing_pattern = r'timing\((\d+),(-?\d+\.?\d*),(\d+\.?\d*)\)'
        timing_matches = re.search(timing_pattern, line)
        if timing_matches:
            timing_time = MeasureData.from_ms(int(timing_matches.group(1)), self.bpm_schedule)
            timing_bpm = frac(timing_matches.group(2))
            measure_len = frac(timing_matches.group(3))
            return Event('timing', [timing_time, timing_bpm, measure_len])
        else:
            print('Invalid timing format:', line)
            return False
    
    def parse_timinggroup(self, content_list: list[str], noinput: bool = False):
        """解析timinggroup元素"""
        affp = AffParser.from_timinggroup(content_list, noinput=noinput, parent_parser=self)
        return Event('timinggroup', affp)
    
    def parse_camera(self, line: str):
        """解析camera元素"""
        camera_pattern = r'camera\(([^)]+)\)'
        camera_matches = re.search(camera_pattern, line)
        if camera_matches:
            camera_args = camera_matches.group(1).split(',')
            cameradata = [MeasureData.from_ms(int(camera_args[0]), self.bpm_schedule)]
            cameradata.extend(camera_args[1:])
            return Event('camera', cameradata)
        else:
            print('Invalid camera format:', line)
            return False
    
    def parse_scenecontrol(self, line: str):
        """解析scenecontrol（事件控制）元素"""
        scenecontrol_pattern = r'scenecontrol\(([^)]+)\)'
        scenecontrol_matches = re.search(scenecontrol_pattern, line)
        if scenecontrol_matches:
            scenecontrol_args = scenecontrol_matches.group(1).split(',')
            scenecontroldata = [MeasureData.from_ms(int(scenecontrol_args[0]), self.bpm_schedule), scenecontrol_args[1]]
            if len(scenecontrol_args) == 4:
                scenecontroldata += [MeasureData.from_ms(int(float(scenecontrol_args[2])), self.bpm_schedule), scenecontrol_args[3]]
            return Event('scenecontrol', scenecontroldata)
        else:
            print('Invalid scenecontrol format:', line)
            return False
    
    def get_events_by_type(self, type: str) -> list[Event]:
        """根据事件类型获取事件列表。"""
        return [event for event in self.events if event.type == type]
    
    def __str__(self):
        str_ = ''
        for event in self.events:
            if event.type == 'text':
                str_ += event.data
            elif event.type == 'tap':
                str0 = ','.join(map(str, event.data))
                str_ += '(' + str0 + ');\n'
            elif event.type == 'arc':
                str0 = ','.join(map(str, event.data[:-1]))
                str0 = 'arc(' + str0 + ')'
                if event.data[-1]:
                    str1 = ['arctap(' + str(i) + ')' for i in event.data[-1]]
                    str1 = ','.join(str1)
                    str1 = '[' + str1 + ']'
                    str0 += str1
                str_ += str0 + ';\n'
            elif event.type == 'timinggroup':
                str0 = 'timinggroup('
                if event.data.noinput:
                    str0 += 'noinput'
                str0 += '){\n  ' + str(event.data)[:-1].replace('\n', '\n  ') + '\n};\n'
                str_ += str0
            elif event.type == 'timing':
                if self.timinggroup:
                    speed = self.parent_parser.speed
                else:
                    speed = self.speed
                str0 = ','.join((str(event.data[0]),str(float(event.data[1] * speed)),str(float(event.data[2]))))
                str_ += event.type + '(' + str0 + ');\n'
            elif event.type == 'scenecontrol':
                data = event.data.copy()
                if len(data) == 4:
                    data[2] = float(data[2])
                str0 = ','.join(map(str, data))
                str_ += event.type + '(' + str0 + ');\n'
            else: #elif event.type in ('hold', 'camera')
                str0 = ','.join(map(str, event.data))
                str_ += event.type + '(' + str0 + ');\n'
        return str_
    
    def speed_change(self, ratio: frac):
        self.speed *= ratio
        self.bpm_schedule.i_scaled(ratio)
        self.audio_offset /= ratio
        for event in self.events:
            if 'AudioOffset:' in event.data:
                event.data = f'AudioOffset:{int(self.audio_offset)}\n'
                break
    
    def speed_set(self, speed: frac):
        f = speed / self.speed
        self.speed_change(f)
    
    def sort_by_time(self):
        text = [event for event in self.events if event.type == 'text']
        events = [event for event in self.events if event.type != 'text']
        def key(event): 
            if event.type in ('tap', 'camera', 'timing', 'scenecontrol'):
                return (event.data[0].ms, event.data[0].ms)
            elif event.type in ('arc', 'hold'):
                return (event.data[0].ms, event.data[1].ms)
            elif event.type == 'timinggroup':
                event.data.sort_by_time()
                return (float('inf'), float('inf'))
        events.sort(key=key)
        self.events = text + events
    
    def slice_audio(self, start_meas: frac, end_meas: frac, target_bpm: BpmSchedule, blank_measures: int = 0, repeat_times: int = 1) -> tuple[np.ndarray, int, int]:
        """切片音频数据，返回切片后的音频数据和采样率。
        
        参数：
        start_meas: frac: 切片开始节拍位置
        end_meas: frac: 切片结束节拍位置
        target_bpm: BpmSchedule: 目标BPM调度表
        blank_measures: int: 切片间空白节拍数
        repeat_times: int: 切片重复次数
        
        返回：
        tuple[np.ndarray, int, int]: (切片后的音频数据, 采样率, 通道数)
        """
        start_sample_pos = (self.bpm_schedule.measure_to_time(start_meas) + frac(self.audio_offset, 1000)) * self.sample_rate
        end_sample_pos = (self.bpm_schedule.measure_to_time(end_meas) + frac(self.audio_offset, 1000)) * self.sample_rate
        start_sample = frac(240, target_bpm.start_bpm) * self.sample_rate
        end_sample = frac(240, target_bpm.end_bpm) * self.sample_rate
        blank_sample = blank_measures * start_sample
        start_beat = start_sample / 4
        end_beat = end_sample / 4
        sample_length = end_sample_pos - start_sample_pos + start_sample + end_sample + blank_sample

        fade_in_env = 0.5 * (1 - np.cos(np.linspace(0, np.pi, int(start_beat / 2))))
        fade_out_env = 0.5 * (1 + np.cos(np.linspace(0, np.pi, int(end_beat))))
        
        result_audio = []
        audio_length = 0
        for t in range(repeat_times):
            if t == 0:
                audio_ = self.audio_data[int(start_sample_pos - start_sample):int(end_sample_pos + end_sample)].copy()
            else:
                offset = int(sample_length * t - blank_sample) - audio_length
                print(offset)
                audio_ = self.audio_data[int(start_sample_pos - start_sample - blank_sample - offset):int(end_sample_pos + end_sample)].copy()
            audio_length += len(audio_)
            if self.channels > 1:
                audio_[:int(start_beat / 2)] *= fade_in_env[:, np.newaxis]
                audio_[-int(end_beat):] *= fade_out_env[:, np.newaxis]
            else:
                audio_[:int(start_beat / 2)] *= fade_in_env
                audio_[-int(end_beat):] *= fade_out_env
            result_audio.append(audio_)
        return np.concatenate(result_audio), self.sample_rate, self.channels
    def slice_practice(self, start_time: int, end_time: int, blank_measures: int = 0, repeat_times: int = None, parent_parser = None, slice_ogg: bool = True, folder_path: str = None):
        """切片练习模式，返回新的AffParser实例。建议使用在节奏点上的物件的时间
        
        参数：
        start_time: int: 切片开始时间（毫秒）
        end_time: int: 切片结束时间（毫秒）
        blank_measures: int: 切片间空白节拍数
        repeat_times: int: 切片重复次数，若为None，则重复次数将使得总0.8倍速长度不超过150秒
        parent_parser: AffParser: timinggroup的主谱面
        slice_ogg: bool: 是否切片ogg文件
        folder_path: str: 切片保存的文件夹名，默认slice_ms_ms
        """
        if start_time >= end_time:
            raise ValueError("切片开始时间必须小于结束时间")
        
        if not self.timinggroup:
            # 主谱面流程
            self.sort_by_time()
            new_parser = AffParser()

            new_parser.song_name = self.song_name + f'_slice_{start_time}_{end_time}'

            new_parser.folder_path = os.path.join(self.folder_path, f'slice_{start_time}_{end_time}' if folder_path == None else folder_path)
            os.makedirs(new_parser.folder_path, exist_ok=True)

            new_parser.start_meas = self.bpm_schedule.ms_to_md(start_time).measures
            new_parser.end_meas = self.bpm_schedule.ms_to_md(end_time).measures
            start_meas = new_parser.start_meas
            end_meas = new_parser.end_meas

            new_parser.bpm_schedule, repeat_times = self.bpm_schedule.slice(start_meas, end_meas, blank_measures, repeat_times)
            new_parser.bpm_schedule.export_bpm(new_parser.song_name, new_parser.folder_path)
            measure_length = new_parser.bpm_schedule.measure_length
            
            if slice_ogg:
                new_parser.audio_data, new_parser.sample_rate, new_parser.channels = \
                self.slice_audio(start_meas, end_meas, new_parser.bpm_schedule, blank_measures, repeat_times)
            
            new_parser.events = [event for event in self.events if event.type == 'text']
            for event in new_parser.events:
                if 'AudioOffset:' in event.data:
                    event.data = f'AudioOffset:0\n' # 已在音频切片中应用偏移
                    new_parser.audio_offset = 0
                    break
        else:
            new_parser = AffParser(timinggroup=True, noinput=self.noinput, parent_parser=parent_parser)
            new_parser.bpm_schedule = parent_parser.bpm_schedule
            start_meas = parent_parser.start_meas
            end_meas = parent_parser.end_meas
            measure_length = parent_parser.bpm_schedule.measure_length
            
            new_parser.events = [event for event in self.events if event.type == 'text']

        first_timing = True
        last_timing = None
        last_scenecontrol = {'enwidencamera': (None, False), 'enwidenlanes': (None, False), 'hidegroup': (None, False)}
        scenecontrol_status = {'enwidencamera': False, 'enwidenlanes': False, 'hidegroup': False}
        scenecontrol_status_end = {'enwidencamera': False, 'enwidenlanes': False, 'hidegroup': False}
        for event in self.events:
            if event.type in ('tap', 'camera'):
                md = event.data[0]
                meas = md.measures
                if start_meas <= meas <= end_meas:
                    for t in range(repeat_times):
                        new_meas = meas - start_meas + t * measure_length + 1
                        new_md = remap_md(md, new_meas, new_parser.bpm_schedule)
                        new_event = Event(event.type, [new_md] + event.data[1:])
                        new_parser.events.append(new_event)
            elif event.type == 'arc':
                s_md = event.data[0]
                e_md = event.data[1]
                s_meas = s_md.measures
                e_meas = e_md.measures
                if start_meas <= s_meas and e_meas <= end_meas:
                    for t in range(repeat_times):
                        new_s_meas = s_meas - start_meas + t * measure_length + 1
                        new_e_meas = e_meas - start_meas + t * measure_length + 1
                        new_s_md = remap_md(s_md, new_s_meas, new_parser.bpm_schedule)
                        new_e_md = remap_md(e_md, new_e_meas, new_parser.bpm_schedule)
                        data = [new_s_md, new_e_md] + event.data[2:-1]

                        arctap_list = []
                        for arctap_md in event.data[-1]:
                            arctap_meas = arctap_md.measures
                            new_arctap_meas = arctap_meas - start_meas + t * measure_length + 1
                            new_arctap_md = remap_md(arctap_md, new_arctap_meas, new_parser.bpm_schedule)
                            arctap_list.append(new_arctap_md)
                        data.append(arctap_list)
                        new_event = Event('arc', data)
                        new_parser.events.append(new_event)
            elif event.type == 'hold':
                s_md = event.data[0]
                e_md = event.data[1]
                s_meas = s_md.measures
                e_meas = e_md.measures
                if start_meas <= s_meas and e_meas <= end_meas:
                    for t in range(repeat_times):
                        new_s_meas = s_meas - start_meas + t * measure_length + 1
                        new_e_meas = e_meas - start_meas + t * measure_length + 1
                        new_s_md = remap_md(s_md, new_s_meas, new_parser.bpm_schedule)
                        new_e_md = remap_md(e_md, new_e_meas, new_parser.bpm_schedule)
                        new_event = Event('hold', [new_s_md, new_e_md] + event.data[2:])
                        new_parser.events.append(new_event)
            elif event.type == 'timing':
                md = event.data[0]
                meas = md.measures
                if meas < start_meas:
                    if last_timing == None or event.data[0].ms > last_timing.data[0].ms:
                        last_timing = event
                elif start_meas <= meas < end_meas:
                    # 初始 timing
                    if last_timing != None and first_timing:
                        start_bpm = new_parser.bpm_schedule.start_bpm
                        for t in range(repeat_times):
                            meas_start = t * measure_length
                            md_ = MeasureData(0, meas_start, 0, True, new_parser.bpm_schedule)
                            md_.ms = int(md_)
                            event_ = Event('timing', [md_, start_bpm, 4])
                            new_parser.events.append(event_)

                            if start_meas != meas:
                                last_meas = last_timing.data[0].measures
                                timing_bpm = last_timing.data[1]
                                duration = last_timing.data[2] * start_bpm / timing_bpm
                                if duration == 0:
                                    pos = -measure_length
                                else:
                                    pos = (start_meas - last_meas) % duration
                                if pos == 0:
                                    md_ = remap_md(last_timing.data[0], meas_start + 1, new_parser.bpm_schedule)
                                    event_ = Event('timing', [md_] + last_timing.data[1:])
                                    new_parser.events.append(event_)
                                else:
                                    md_ = MeasureData(0, meas_start + 1, 0, True, new_parser.bpm_schedule)
                                    md_.ms = int(md_)
                                    event_ = Event('timing', [md_, start_bpm, 4 * (measure_length - 2)])
                                    new_parser.events.append(event_)
                                    pos = duration - pos
                                    if pos < min(measure_length - 2, meas):
                                        md_ = remap_md(md, meas_start + 1 + pos, new_parser.bpm_schedule)
                                        event_ = Event('timing', [md_] + last_timing.data[1:])
                                        new_parser.events.append(event_)

                        first_timing = False
                    # 重映射 timing
                    for t in range(repeat_times):
                        new_meas = meas - start_meas + t * measure_length + 1
                        new_md = remap_md(md, new_meas, new_parser.bpm_schedule)
                        new_event = Event('timing', [new_md] + event.data[1:])
                        new_parser.events.append(new_event)
            elif event.type == 'timinggroup':
                new_parser.events.append(Event('timinggroup', event.data.slice_practice(start_time, end_time, blank_measures, repeat_times, new_parser)))
            elif event.type == 'scenecontrol':
                md = event.data[0]
                meas = md.measures
                if start_meas <= meas <= end_meas:
                    dur_md = None
                    if len(event) == 4:
                        dur_md = event.data[2]
                        dur_meas = dur_md.measures
                    if dur_md == None or meas + dur_meas <= end_meas:
                        for t in range(repeat_times):
                            new_meas = meas - start_meas + t * measure_length + 1
                            new_md = remap_md(md, new_meas, new_parser.bpm_schedule)
                            new_event = Event('scenecontrol', [new_md] + event.data[1:])
                            new_parser.events.append(new_event)
                    if dur_md:
                        scenecontrol_status_end[event.data[1]] = event.data[-1] == '1'
                elif meas < start_meas and len(event) == 4:
                    if last_scenecontrol[event.data[1]][0] == None or event.data[0].ms > last_scenecontrol[event.data[1]][0].data[0].ms:
                        last_scenecontrol[event.data[1]] = (event, event.data[-1] == '1')
                        scenecontrol_status[event.data[1]] = event.data[-1] == '1'
        for key in scenecontrol_status:
            if scenecontrol_status[key] == scenecontrol_status_end[key]:
                scenecontrol_status[key] = None
        # 初始timing和scenecontrol
        for t in range(repeat_times):
            if first_timing:
                start_bpm = new_parser.bpm_schedule.start_bpm
                meas_start = t * measure_length
                md_ = MeasureData(0, meas_start, 0, True, new_parser.bpm_schedule)
                md_.ms = int(md_)
                event_ = Event('timing', [md_, start_bpm, 4])
                new_parser.events.append(event_)

                last_meas = last_timing.data[0].measures
                timing_bpm = last_timing.data[1]
                duration = last_timing.data[2] * start_bpm / timing_bpm / 4
                if duration == 0:
                    pos = -measure_length
                else:
                    pos = (start_meas - last_meas) % duration
                if pos == 0:
                    md_ = remap_md(last_timing.data[0], meas_start + 1, new_parser.bpm_schedule)
                    event_ = Event('timing', [md_] + last_timing.data[1:])
                    new_parser.events.append(event_)
                else:
                    md_ = MeasureData(0, meas_start + 1, 0, True, new_parser.bpm_schedule)
                    md_.ms = int(md_)
                    event_ = Event('timing', [md_, start_bpm, 4 * (measure_length - 2)])
                    new_parser.events.append(event_)
                    pos = duration - pos
                    if pos < measure_length - 2:
                        md_ = remap_md(md, meas_start + 1 + pos, new_parser.bpm_schedule)
                        event_ = Event('timing', [md_] + last_timing.data[1:])
                        new_parser.events.append(event_)
            
            meas_end = (t + 1) * measure_length - 1 - blank_measures
            md_ = MeasureData(0, meas_end, 0, True, new_parser.bpm_schedule)
            md_.ms = int(md_)
            event_ = Event('timing', [md_, new_parser.bpm_schedule.end_bpm, 4])
            new_parser.events.append(event_)

            meas = t * measure_length
            md = MeasureData(0, meas, 0, True, new_parser.bpm_schedule)
            md.ms = int(md)
            for name, is_active in scenecontrol_status.items():
                if is_active != None and t != 0:
                    signal = '1' if is_active else '0'
                    event = Event('scenecontrol', [md, name, 0., signal])
                    new_parser.events.append(event)
        return new_parser
    
    def parse_rhythm(self) -> list[MeasureData]:
        if not self.timinggroup:
            self.sort_by_time()
        rhythm = []
        last_arc_end = {'0': [None]*3, '1': [None]*3, '2': [None]*3} # 时间距离≥10ms或位置横向距离≥0.1或位置纵向距离>0.01判定蛇头尾未接上
        def not_same_pos(pos1, pos2):
            return (abs(pos1[0].ms - pos2[0].ms) >= 10 or 
                    abs(frac(pos1[1])-frac(pos2[1])) >= frac(1,10) or 
                    abs(frac(pos1[2])-frac(pos2[2])) > frac(1,100))
        for event in self.events:
            if event.type in ('tap', 'hold'):
                rhythm.append(event.data[0])
            elif event.type == 'arc':
                if event.data[9] == 'false':
                    arc_start = [event.data[0],event.data[2],event.data[5]]
                    if last_arc_end[event.data[7]] == [None]*3 or not_same_pos(arc_start, last_arc_end[event.data[7]]):
                        rhythm.append(event.data[0])
                    last_arc_end[event.data[7]] = [event.data[1],event.data[3],event.data[6]]
                rhythm.extend(event.data[-1])
            elif event.type == 'timinggroup':
                rhythm.extend(event.data.parse_rhythm())
        rhythm.sort(key=lambda x: x.ms)
        return rhythm
    
    def export_aff(self, output_url: str):
        """导出AFF文件, output_file为输出文件名（相对路径）"""
        output_file = os.path.join(self.folder_path, output_url)
        folder_path = os.path.dirname(output_file)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(str(self))
        print(f'成功导出AFF文件: {output_file}')

    def export_ogg(self, output_url: str):
        """导出OGG文件, output_file为输出文件名（相对路径）"""
        output_file = os.path.join(self.folder_path, output_url)
        folder_path = os.path.dirname(output_file)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        cmd = ["ffmpeg", "-y", "-hide_banner",
                "-f", "f32le",
                "-ar", str(self.sample_rate),
                "-ac", str(self.channels),
                "-i", "pipe:0",
                "-c:a", "libvorbis", "-q:a", "5",
                output_file]
        if self.speed != 1:
            # 在 pipe:0 之后、-c:a 之前插入音频滤镜（索引 11）
            cmd.insert(11, "-filter:a")
            cmd.insert(12, f"atempo={float(self.speed)}")
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        # 将 numpy 数组转为原始字节（f32le 格式）
        audio_bytes = np.ascontiguousarray(self.audio_data, dtype='float32').tobytes()
        process.communicate(audio_bytes)
    
    def export_timinggroup(self):
        """以普通谱面格式导出所有时间组包括主时间组"""
        events_bak = [event for event in self.events if event.type != 'timinggroup']
        events_text = [event for event in self.events if event.type == 'text']
        events_bak, self.events = self.events, events_bak
        i = 0
        output_file = r'output/00.aff'
        self.export_aff(output_file)
        for tg_event in self.get_events_by_type('timinggroup'):
            i += 1
            self.events = events_text + tg_event.data.get_events_by_type('timing') + [tg_event]
            output_file = r'output/%02d.aff' % i
            self.export_aff(output_file)
        self.events = events_bak
        print(f'成功导出所有时间组，共{i+1}个文件')
    
def task1(song_name: str, url: str, sliceQ: bool = False, start_time: int = None, end_time: int = None, blank_measures: int = 0, repeat_times: int = None):
    parser = AffParser.from_file(url, song_name)

    ratio_idx = {0: frac('0.8'), 1: frac('0.9'), 2: frac('1.0'), 3: frac('1.1')}
    
    sp = 'speed_practice'
    if sliceQ:
        sp = ''
        parser = parser.slice_practice(start_time, end_time, blank_measures, repeat_times)
    for i in range(4):
        if i == 2:
            if sliceQ:
                parser.speed_set(frac(1))
                parser.export_ogg(os.path.join(sp, 'base.ogg'))
                parser.export_aff(os.path.join(sp, '2.aff'))
            else:
                audio_rul = os.path.join(parser.folder_path, 'base.ogg')
                output_url = os.path.join(parser.folder_path, sp, 'base.ogg')
                os.system(f'copy "{audio_rul}" "{output_url}"')
                output_url = os.path.join(parser.folder_path, sp, '2.aff')
                parser.file_path = parser.file_path.replace('/', '\\')
                os.system(f'copy "{parser.file_path}" "{output_url}"')
        else:
            parser.speed_set(ratio_idx[i])
            parser.export_ogg(os.path.join(sp, f'{i}.ogg'))
            parser.export_aff(os.path.join(sp, f'{i}.aff'))

# 使用示例
if __name__ == "__main__":
    bpm_check = input('验证BPM?(y/n): ') == 'y'
    song_name = input('请输入歌曲名: ')
    url = input('请输入AFF文件路径: ')
    if url.startswith("& "): 
        url = url[3:-1]
        url = url.replace("''","'")
    if not bpm_check:
        sms, ems = None, None
        sliceQ = input('是否分段?(y/n): ') == 'y'
        if sliceQ:
            ms_range = input('请输入时间范围(ms-ms): ')
            sms, ems = map(int, ms_range.split('-'))
        task1(song_name, url, sliceQ, sms, ems)
    else:
        parser = AffParser.from_file(url, song_name)
        rhythm = parser.parse_rhythm()
        delta_count = {-3: 0, -2: 0, -1: 0, 0: 0, 1: 0, 2: 0, 3: 0}
        max_ = 52
        max_delta = 3
        min_delta = -3
        for md in rhythm:
            if md.delta_time > max_delta:
                for i in range(md.delta_time - max_delta):
                    delta_count[max_delta + i + 1] =0
                max_delta = md.delta_time
            if md.delta_time < min_delta:
                for i in range(min_delta - md.delta_time):
                    delta_count[min_delta - i - 1] =0
                min_delta = md.delta_time
            delta_count[md.delta_time] += 1
        delta_count = {delta: delta_count[delta] for delta in range(min_delta, max_delta + 1)}
        for delta, value in delta_count.items():
            if delta == -3:
                print('|', end='')
            elif delta == 0:
                print('{', end='')
            elif delta == 1:
                print('}', end='')
            elif delta not in (4, min_delta):
                print(',', end='')
            print(value, end='')
            if delta == 3:
                print('|', end='')
        print()
    input('按回车键退出...')