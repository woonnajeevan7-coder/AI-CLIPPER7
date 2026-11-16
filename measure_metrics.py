import subprocess
import json
import re
from pathlib import Path
from ffmpeg_utils import get_ffmpeg_bin, get_ffprobe_bin

ffmpeg_cmd = str(get_ffmpeg_bin())
ffprobe_cmd = str(get_ffprobe_bin())

clips = [
    ('2-Speaker Podcast (Lex Fridman & Don Lincoln)', 'output_clips/short_1794769829_1.mp4', 'single_face', 'podcast_2speaker'),
    ('Solo Speaker (Steve Jobs Commencement)', 'output_clips/short_1794769848_1.mp4', 'single_face', 'solo_speaker'),
    ('Hindi Video (Ranveer & Prajakta)', 'output_clips/short_1794769855_1.mp4', 'split_screen', 'hindi_video')
]

for name, path_str, layout, tag in clips:
    p = Path(path_str)
    res = subprocess.run([ffprobe_cmd, '-v', 'error', '-show_entries', 'stream=codec_name,codec_type,width,height,pix_fmt,channels,sample_rate', '-show_entries', 'format=duration,size', '-of', 'json', str(p)], capture_output=True, text=True)
    probe = json.loads(res.stdout)
    v = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    a = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
    dur = float(probe['format']['duration'])

    ebur = subprocess.run([ffmpeg_cmd, '-i', str(p), '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True)
    summary_idx = ebur.stderr.rfind('Summary:')
    summary = ebur.stderr[summary_idx:] if summary_idx != -1 else ebur.stderr
    i_val = re.search(r'I:\s+([-\d.]+)\s+LUFS', summary).group(1)
    lra_val = re.search(r'LRA:\s+([-\d.]+)\s+LU', summary).group(1)

    print(f"=== {name} ===")
    print(f"File: {p.name}")
    print(f"Resolution: {v['width']}x{v['height']} | PixFmt: {v['pix_fmt']} | VideoCodec: {v['codec_name']}")
    print(f"AudioCodec: {a['codec_name']} | Channels: {a.get('channels')} | SampleRate: {a.get('sample_rate')}")
    print(f"Duration: {dur:.2f}s")
    print(f"Integrated Loudness: {i_val} LUFS | Target Diff: {float(i_val) - (-14.0):+.2f} LUFS")
    print(f"Loudness Range: {lra_val} LU")
    print(f"Detected Layout: {layout}")
    print(f"Frames: audit_frames/{tag}_clip1_start.jpg, middle.jpg, end.jpg")
    print()
