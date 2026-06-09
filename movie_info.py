#!/usr/bin/env python3
#!packages/bin/python
# ------------------------------------------------------------------------------

import json
import re
import subprocess
from fractions import Fraction
import argparse
from pathlib import Path

# --------------------------------- CODE ---------------------------------------

def _check_mp4_faststart(pathfile):

    with Path(pathfile).open("rb") as f:
        f.seek(0, 2)
        file_size = f.tell()
        f.seek(0)

        boxes = []
        saw_ftyp = False

        while f.tell() + 8 <= file_size:
            offset = f.tell()
            header = f.read(8)

            if len(header) < 8:
                return {
                    "flag"  : None,
                    "status": "unknown",
                    "reason": "incomplete Box-Header",
                    "file_size": file_size,
                    "boxes": boxes,
                }

            size = int.from_bytes(header[0:4], "big")
            box_type = header[4:8].decode("ascii", errors="replace")
            header_size = 8

            if size == 1:
                large_size_data = f.read(8)
                if len(large_size_data) < 8:
                    return {
                        "flag"  : None,
                        "status": "unknown",
                        "reason": f"Incomplete Large-Size-Header at Box {box_type}",
                        "file_size": file_size,
                        "boxes": boxes,
                    }
                size = int.from_bytes(large_size_data, "big")
                header_size = 16

            elif size == 0:
                size = file_size - offset

            if size < header_size:
                return {
                    "flag"  : None,
                    "status": "unsupported_container",
                    "reason": f"Invalid boxsize at offset {offset}",
                    "file_size": file_size,
                    "boxes": boxes,
                }

            next_offset = offset + size
            if next_offset > file_size:
                return {
                    "flag"  : None,
                    "status": "unsupported_container",
                    "reason": f"Box {box_type} at offset {offset} longer than file",
                    "file_size": file_size,
                    "boxes": boxes,
                }

            box_info = {
                "type": box_type,
                "offset": offset,
                "size": size,
            }

            if box_type == "ftyp":
                saw_ftyp = True

                if size >= 16:
                    major_brand = f.read(4).decode("ascii", errors="replace")
                    minor_version = int.from_bytes(f.read(4), "big")
                    compatible_len = size - header_size - 8
                    compatible_brands = []

                    if compatible_len > 0:
                        compatible_data = f.read(compatible_len)
                        for i in range(0, len(compatible_data) - (len(compatible_data) % 4), 4):
                            compatible_brands.append(
                                compatible_data[i:i + 4].decode("ascii", errors="replace")
                            )

                    box_info["major_brand"] = major_brand
                    box_info["minor_version"] = minor_version
                    box_info["compatible_brands"] = compatible_brands
                else:
                    return {
                        "flag"  : None,
                        "status": "unsupported_container",
                        "reason": "ftyp-Box too small",
                        "file_size": file_size,
                        "boxes": boxes,
                    }

            boxes.append(box_info)

            if offset == 0 and box_type != "ftyp":
                return {
                    "flag"  : None,
                    "status": "unsupported_container",
                    "reason": "File doesn't start with ftyp-Box, not a normal MP4/MOV",
                    "file_size": file_size,
                    "boxes": boxes,
                }

            if box_type == "moov":
                return {
                    "flag"  : True,
                    "status": "faststart_probable",
                    "reason": "moov before mdat",
                    "file_size": file_size,
                    "found_box": box_type,
                    "found_offset": offset,
                    "found_size": size,
                    "boxes": boxes,
                }

            if box_type == "mdat":
                return {
                    "flag"  : False,
                    "status": "not_faststart_probable",
                    "reason": "mdat before moov",
                    "file_size": file_size,
                    "found_box": box_type,
                    "found_offset": offset,
                    "found_size": size,
                    "boxes": boxes,
                }

            f.seek(next_offset)

        if not saw_ftyp:
            return {
                "flag"  : None,
                "status": "unsupported_container",
                "reason": "No ftyp-Box found, perhaps no MP4/MOV",
                "file_size": file_size,
                "boxes": boxes,
            }

    return {
        "flag"  : None,
        "status": "unknown",
        "reason": "Found neither moov nor mdat",
        "file_size": file_size,
        "boxes": boxes,
    }

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

def _run_ffprobe(pathfile, count_frames=False):
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
        pathfile,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

def _parse_fraction(value):
    if not value or value in ("0/0", "N/A"):
        return None
    try:
        return float(Fraction(value))
    except Exception:
        return None

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

def _to_int_or_none(value):
    if value in (None, "N/A"):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

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

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

def _to_bool_from_int(value):
    value = _to_int_or_none(value)
    if value is None:
        return None
    return bool(value)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

def get_media_info(pathfile, use_count_frames_fallback=True, estimate_frames_fallback=True):

    pathfile = str(Path(pathfile).expanduser().resolve())

    data = _run_ffprobe(pathfile, count_frames=False)

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
        counted_data = _run_ffprobe(pathfile, count_frames=True)
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

    return {    "format": 
                {
                    "size": fsize,
                    "duration": duration,
                },
                "video": 
                {
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
                "faststart": _check_mp4_faststart(pathfile)
            }

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read Video-Infos with ffprobe.")
    parser.add_argument("filename", help="path/name video file")
    args = parser.parse_args()
    info = get_media_info(args.filename)
    print(json.dumps(info, indent=2, ensure_ascii=False))
