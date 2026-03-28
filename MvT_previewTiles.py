#!/usr/bin/env python3
#!packages/bin/python
# ------------------------------------------------------------------------------

import subprocess

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

    def grab_frame_bytes(video_path, ts_sec, width, quality):
        """Pick a single I-Frame at specified point in time, convert to width and quality and return in ram"""
        cmd = [
            "ffmpeg",
            "-loglevel", "error",
            "-skip_frame", "nokey",
            "-ss", format_ts(ts_sec),
            "-i", str(video_path),
            "-vframes", "1",
            "-vf", f"scale={width}:-1",
            "-q:v", str(quality),
            "-f", "image2pipe",
            "-vcodec", "mjpeg",
            "-"
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return result.stdout

    # And now do the work ...

    # Get array of timestamps, one for every tile
    timestamps = gen_ts(video_get_duration( video_path ), cols * rows)

    # Start ffmpeg-process for all the tiles and wait for input via stdin
    proc = subprocess.Popen([
        "ffmpeg",
        "-y",
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "-i", "-",
        "-filter_complex", f"tile={cols}x{rows}",
        "-frames:v", "1",
        out_tile_path
    ], stdin=subprocess.PIPE)

    # Pick one frame after the other and write to ffmpeg-process
    for ts in timestamps:
        print("Tile:",ts)
        img_bytes = grab_frame_bytes(video_path, ts, width, quality)
        proc.stdin.write(img_bytes)

    proc.stdin.close()
    proc.wait()

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
