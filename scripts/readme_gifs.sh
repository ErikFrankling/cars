#!/usr/bin/env bash
# The GIFs in README.md, cut from clips under cars-data/videos (city_videos.sh, intersection_gallery.py, scripts/d8).
# The hero video is videos/readme/berlin_hero.mp4 from city_videos.sh, re-encoded with -crf 27 and uploaded to GitHub.
set -e
cd "$(dirname "$0")/.." || exit 1
G=/home/erikf/projects/personal/cars-data/videos/gallery
O=assets/readme
gif() { # in out start seconds filters fps
  local pal
  pal=$(mktemp --suffix=.png)
  ffmpeg -v error -y -ss "$3" -t "$4" -i "$1" -vf "$5,fps=$6,palettegen=max_colors=128:stats_mode=diff" "$pal"
  ffmpeg -v error -y -ss "$3" -t "$4" -i "$1" -i "$pal" -lavfi "$5,fps=$6[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" -loop 0 "$2"
  rm -f -- "$pal"
}
gif $G/d8/versus_signal.mp4 $O/versus_signal.gif 20 12 "scale=960:-2:flags=lanczos" 12
gif $G/humans/merge_i80_real_vs_sim.mp4 $O/i80_real_vs_sim.gif 4 12 "scale=840:-2:flags=lanczos" 12
gif $G/stockholm-roundabout-0/clip.mp4 $O/stockholm_roundabout.gif 0 12 "crop=1280:720:60:250,scale=640:-2:flags=lanczos" 12
gif $G/nn/ring-wave-removed.mp4 $O/ring_wave.gif 0 60 "setpts=PTS/3,scale=640:-2:flags=lanczos" 10
