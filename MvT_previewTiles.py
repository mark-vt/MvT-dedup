#!/usr/bin/env python3
#!packages/bin/python
# ------------------------------------------------------------------------------

import os
import subprocess
from io import BytesIO
from PIL import Image

def MvT_preview_tiles(video_path, cols, rows, width, quality, out_tile_path):

    def video_get_duration(video_path):
        """Length of video in seconds (float) per ffprobe."""
        cmd = [ "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_path) ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        try:
            return float(result.stdout.strip())
        except:
            return None

    def gen_ts(duration, numPics):
        """Create numPics timestamps spread over movie"""
        step = duration / numPics
        offs = step / 2
        return [(i * step + offs) for i in range(numPics)]
    import subprocess

    def format_ts(seconds):
        """Format timestamp to ffmpeg compliant format"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}"

    def grab_frame_bytes(video_path, ts_sec, width):
        """Pick a single I-Frame at specified point in time, convert to width and quality and return in ram"""
        cmd = [
            "ffmpeg",
            "-loglevel", "error",
            "-skip_frame", "nokey",
            "-ss", format_ts(ts_sec),
            "-i", str(video_path),
            "-vframes", "1",
            "-vf", f"scale={width}:-1",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-"
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return result.stdout

    # And now do the work ...

    # Get array of timestamps, one for every tile
    timestamps = gen_ts(video_get_duration( video_path ), cols * rows)

    # Try to grab frames at those timestamps, and store them in a list
    frames = []
    for ts in timestamps:
        try:
            img_bytes = grab_frame_bytes(video_path, ts, width)
            with Image.open(BytesIO(img_bytes)) as frame:
                frames.append(frame.convert("RGB"))
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            print(f"Tile: {ts}: Could not extract tile: {error}")
            break
        else:
            print(f"Tile: {ts}: ok")

    # If no frames were successfully grabbed, return False -> no tile file created
    if not frames:
        return False

    tile_width = max(frame.width for frame in frames)
    tile_height = max(frame.height for frame in frames)
    mosaic = Image.new("RGB", (tile_width * cols, tile_height * rows), "black")
    for index, frame in enumerate(frames):
        mosaic.paste(frame, ((index % cols) * tile_width, (index // cols) * tile_height))

    output_extension = os.path.splitext(out_tile_path)[1].lower()
    if output_extension == ".png":
        mosaic.save(out_tile_path, format="PNG")
    else:
        mosaic.save(out_tile_path, format="JPEG", quality=quality)

    return True

# ---------------------------
# MAIN
# ---------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser( description="Create -c x -r tiles of a video file." )
    parser.add_argument("-i", "--inputfile", required=True, help="Pfad zur Video-Datei")
    parser.add_argument("-o", "--outputfile", required=True, help="Pfad zum finalen Tile")
    #parser.add_argument("-f", "--format", choices=["jpg","png"], default="jpg", help="Dateiformat des Output-Bildes")
    parser.add_argument("-w", "--width", type=int, default=320, help="Breite einzelner Frames (px)")
    parser.add_argument("-c", "--columns", type=int, default=4, help="Anzahl der Spalten im Tile")
    parser.add_argument("-r", "--rows", type=int, default=3, help="Anzahl der Reihen im Tile")
    parser.add_argument("-q", "--quality", type=int, default=4, help="JPEG-Qualität (1=best, 31=schlecht)")
    args = parser.parse_args()

    print("Inputfile:", args.inputfile)
    print("Outputfile:", args.outputfile)
    #print("Format:", args.format)
    print("Width:", args.width)
    print("Columns:", args.columns)
    print("Rows:", args.rows)
    print("Quality:", args.quality)

    MvT_preview_tiles(args.inputfile, args.columns, args.rows, args.width,
                        args.quality, args.outputfile)
