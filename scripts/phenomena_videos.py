#!/usr/bin/env python3
"""Record sequentially; inspect extracted frames before accepting the inventory."""
import argparse
import json
import shutil
import phenomena as p


def compare_one_av():
    human=p.VIDEOS/'one_av_human.mp4'
    smooth=p.VIDEOS/'one_av_damped.mp4'
    shutil.copy(p.VIDEOS/'phantom_jam.mp4',human)
    shutil.copy(p.VIDEOS/'one_av.mp4',smooth)
    d=p.ROOT/'runs/phenomena/one_av'
    filters="[0:v]trim=duration=25,setpts=PTS-STARTPTS,drawtext=text='All human IDM':x=40:y=140:fontsize=28:fontcolor=white[a];[1:v]trim=duration=25,setpts=PTS-STARTPTS,drawtext=text='One smooth driver':x=40:y=140:fontsize=28:fontcolor=white[b];[a][b]concat=n=2:v=1:a=0[v]"
    p.command(['ffmpeg','-y','-threads','2','-i',human,'-threads','2','-i',smooth,'-filter_complex_threads','2','-filter_threads','2','-filter_complex',filters,'-map','[v]','-c:v','libx264','-threads','2','-preset','veryfast','-crf','20','-pix_fmt','yuv420p',p.VIDEOS/'one_av.mp4'],d/'comparison.log')
    for second,label in [(10,'human'),(35,'smooth')]:
        p.command(['ffmpeg','-y','-threads','2','-ss',str(second),'-i',p.VIDEOS/'one_av.mp4','-frames:v','1','-threads','2',d/(label+'_inspection.png')],d/(label+'_inspection.log'))


def main():
    a=argparse.ArgumentParser();a.add_argument('names',nargs='*');args=a.parse_args()
    for name in args.names or p.SCENARIOS:
        d=p.ROOT/'runs/phenomena'/name;d.mkdir(parents=True,exist_ok=True)
        source=p.ROOT/'runs/phenomena/freeway_fd_n180' if name=='freeway_fd' else d
        if (source/'manifest.json').exists():
            cfg=json.loads((source/'manifest.json').read_text())
            if source!=d:
                for filename in ['net.xml','routes.xml']:
                    shutil.copy(source/filename,d/filename)
                cfg['ring']=True
        else:
            cfg=p.SCENARIOS[name](d)
        p.video(d,cfg,name)
    if not args.names or 'one_av' in args.names:compare_one_av()

if __name__=='__main__':main()
