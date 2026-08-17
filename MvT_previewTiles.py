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
    
    def get_image_with_tiles(video_path, duration, cols, rows, width):
        """Extract all requested keyframes and assemble the tiles in one ffmpeg call."""
        
        # Calculate the number of tiles and the time step between them
        num_tiles = cols * rows
        step = duration / num_tiles
        offset = step / 2
        
        # This is a filter for ffmpeg.  Is selects the first keyframe in 
        # each interval centered on a requested timestamp.
        select_expr = ( f"isnan(prev_selected_t)*gte(t\\,{offset})+"
                        f"gt(floor((t-{offset})/{step})\\,"
                        f"floor((prev_selected_t-{offset})/{step}))" ) 

        # Build the ffmpeg command to extract the tiles and assemble them into a single image
        cmd = [
            "ffmpeg",
            "-loglevel", "error",
            "-skip_frame", "nokey",
            "-i", str(video_path),
            "-vf", f"select={select_expr},scale={width}:-1,tile={cols}x{rows}",
            "-vframes", "1",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-"
        ]
        
        #print("ffmpeg command:", " ".join(cmd))
        
        # Run the command and return the output image bytes
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return result.stdout

    def get_first_frame_only(video_path, width):
        """Extract the first video frame as a PNG. Used if no tiles could be extracted."""
        cmd = [
            "ffmpeg",
            "-loglevel", "error",
            "-i", str(video_path),
            "-vf", f"scale={width}:-1",
            "-frames:v", "1",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-"
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return result.stdout

    # Get video duration and validate parameters
    duration = video_get_duration(video_path)
    if duration is None or duration <= 0 or cols <= 0 or rows <= 0 or width <= 0:
        return False

    # Generate the preview tiles or fallback to the first frame if no tiles could be extracted
    try:
        img_bytes = get_image_with_tiles(video_path, duration, cols, rows, width)
        if not img_bytes:
            print("No tiles extracted; showing the first video frame.")
            img_bytes = get_first_frame_only(video_path, width * cols)
        with Image.open(BytesIO(img_bytes)) as frame:
            mosaic = frame.convert("RGB")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Could not extract preview tiles: {error}")
        return False

    if not mosaic:
        return False

    # Store the mosaic image to the specified output path
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
    parser.add_argument("-o", "--outputfile", required=True, help="Pfad zum finalen Tile, .jpg oder .png")
    parser.add_argument("-w", "--width", type=int, default=320, help="Width of single tile (px)")
    parser.add_argument("-c", "--columns", type=int, default=4, help="Number of tiles horizontal")
    parser.add_argument("-r", "--rows", type=int, default=3, help="Number of tiles vertical")
    parser.add_argument("-q", "--quality", type=int, default=60, help="JPEG quality (95=best, 0=worst)")
    args = parser.parse_args()

    print("Inputfile:", args.inputfile)
    print("Outputfile:", args.outputfile)
    print("Width:", args.width)
    print("Columns:", args.columns)
    print("Rows:", args.rows)
    print("Quality:", args.quality)

    MvT_preview_tiles(args.inputfile, args.columns, args.rows, 
                      args.width, args.quality, args.outputfile)
