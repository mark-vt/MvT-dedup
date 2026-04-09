#!/usr/bin/env python3
#!packages/bin/python
# ------------------------------------------------------------------------------

import json
import re
import subprocess
from fractions import Fraction


def _run_ffprobe(path, count_frames=False):
    cmd = [
        "ffprobe",
        "-v", "error",
    ]

    if count_frames:
        cmd.append("-count_frames")

    cmd += [
        "-show_entries",
        (
            "stream=index,codec_type,codec_name,width,height,nb_frames,nb_read_frames,"
            "r_frame_rate,avg_frame_rate,bit_rate,sample_rate,sample_fmt,"
            "bits_per_sample,bits_per_raw_sample,channels,channel_layout"
            ":stream_tags=language,title"
            ":stream_disposition=default,forced"
            ":format=duration,size"
        ),
        "-of", "json",
        path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def _parse_fraction(value):
    if not value or value in ("0/0", "N/A"):
        return None
    try:
        return float(Fraction(value))
    except Exception:
        return None


def _to_int_or_none(value):
    if value in (None, "N/A"):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _infer_bits_from_sample_fmt(sample_fmt):
    if not sample_fmt:
        return None

    sample_fmt = sample_fmt.lower()

    explicit_map = {
        "u8": 8,
        "u8p": 8,
        "s16": 16,
        "s16p": 16,
        "s32": 32,
        "s32p": 32,
        "s64": 64,
        "s64p": 64,
        "flt": 32,
        "fltp": 32,
        "dbl": 64,
        "dblp": 64,
    }

    if sample_fmt in explicit_map:
        return explicit_map[sample_fmt]

    match = re.search(r"(\d+)", sample_fmt)
    if match:
        return int(match.group(1))

    return None


def _to_bool_from_int(value):
    value = _to_int_or_none(value)
    if value is None:
        return None
    return bool(value)


def get_media_info(path, use_count_frames_fallback=True, estimate_frames_fallback=True):
    data = _run_ffprobe(path, count_frames=False)

    streams = data.get("streams", [])
    if not streams:
        raise ValueError("Keine Streams gefunden.")

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video_stream is None:
        raise ValueError("Kein Videostream gefunden.")

    format_data = data.get("format", {})

    duration = format_data.get("duration")
    duration = float(duration) if duration not in (None, "N/A") else None
    
    fsize = int(format_data.get("size"))

    r_frame_rate = video_stream.get("r_frame_rate")
    avg_frame_rate = video_stream.get("avg_frame_rate")
    fps = _parse_fraction(avg_frame_rate) or _parse_fraction(r_frame_rate)

    nb_frames = _to_int_or_none(video_stream.get("nb_frames"))
    frame_source = "nb_frames"

    if nb_frames is None and use_count_frames_fallback:
        counted_data = _run_ffprobe(path, count_frames=True)
        counted_streams = counted_data.get("streams", [])
        counted_video_stream = next((s for s in counted_streams if s.get("codec_type") == "video"), None)

        if counted_video_stream:
            nb_read_frames = _to_int_or_none(counted_video_stream.get("nb_read_frames"))
            if nb_read_frames is not None:
                nb_frames = nb_read_frames
                frame_source = "nb_read_frames"

    if nb_frames is None and estimate_frames_fallback and duration is not None and fps is not None:
        nb_frames = round(duration * fps)
        frame_source = "estimated"

    audio_streams = []

    for stream in streams:
        if stream.get("codec_type") != "audio":
            continue

        tags = stream.get("tags", {}) or {}
        disposition = stream.get("disposition", {}) or {}

        sample_fmt = stream.get("sample_fmt")
        bits_per_sample = _to_int_or_none(stream.get("bits_per_sample"))
        bits_per_raw_sample = _to_int_or_none(stream.get("bits_per_raw_sample"))

        inferred_bits_per_sample = None
        effective_bits_per_sample = bits_per_sample

        if not effective_bits_per_sample or effective_bits_per_sample == 0:
            inferred_bits_per_sample = _infer_bits_from_sample_fmt(sample_fmt)
            effective_bits_per_sample = inferred_bits_per_sample

        audio_bit_rate = _to_int_or_none(stream.get("bit_rate"))
        if audio_bit_rate is not None and duration is not None:
            estimated_audio_size_bytes = int(audio_bit_rate * duration / 8)
        else:
            estimated_audio_size_bytes = None
            
        audio_streams.append({
            "index": _to_int_or_none(stream.get("index")),
            "language": tags.get("language"),
            "title": tags.get("title"),
            "codec_name": stream.get("codec_name"),
            "bit_rate": audio_bit_rate,
            "estimated_size_bytes": estimated_audio_size_bytes,
            "sample_rate": _to_int_or_none(stream.get("sample_rate")),
            "sample_fmt": sample_fmt,
            "bits_per_sample": bits_per_sample,
            "bits_per_raw_sample": bits_per_raw_sample,
            "inferred_bits_per_sample": inferred_bits_per_sample,
            "effective_bits_per_sample": effective_bits_per_sample,
            "channels": _to_int_or_none(stream.get("channels")),
            "channel_layout": stream.get("channel_layout"),
            "default": _to_bool_from_int(disposition.get("default")),
            "forced": _to_bool_from_int(disposition.get("forced")),
        })
        
    video_bit_rate = _to_int_or_none(video_stream.get("bit_rate"))
    estimated_video_size_bytes = None
    if video_bit_rate is not None and duration is not None:
        estimated_video_size_bytes = int(video_bit_rate * duration / 8)

    return {
        "format": {
            "size": fsize,
            "duration": duration,
        },
        "video": {
            "width": _to_int_or_none(video_stream.get("width")),
            "height": _to_int_or_none(video_stream.get("height")),
            "codec_name": video_stream.get("codec_name"),
            "bit_rate": _to_int_or_none(video_stream.get("bit_rate")),
            "estimated_size_bytes": estimated_video_size_bytes,
            "r_frame_rate": r_frame_rate,
            "avg_frame_rate": avg_frame_rate,
            "fps": fps,
            "nb_frames": nb_frames,
            "frame_source": frame_source if nb_frames is not None else None,
        },
        "audios": audio_streams,
    }


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Read Video-Infos with ffprobe.")
    parser.add_argument("filename", help="path/name video file")
    args = parser.parse_args()

    video_path = str(Path(args.filename).expanduser().resolve())

    info = get_media_info(video_path)
    print(json.dumps(info, indent=2, ensure_ascii=False))
