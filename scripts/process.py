#!/usr/bin/env python3
import os, sys, shutil, subprocess, random, tempfile
import ffmpeg
from yt_dlp import YoutubeDL
import librosa, numpy as np

SM = sys.argv[1]
URL = f"https://www.nicovideo.jp/watch/{SM}"
WORK = 'tmp'
OUT = 'output'

# ディレクトリ準備
def prepare_dirs():
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(WORK)
    os.makedirs(OUT)

# ダウンロード
def download_assets():
    opts = {'format':'bestvideo[ext=mp4]+bestaudio[ext=m4a]', 'outtmpl':f'{WORK}/asset.%(ext)s'}
    with YoutubeDL(opts) as ydl: ydl.download([URL])
    return f'{WORK}/asset.mp4', f'{WORK}/asset.m4a'

# ビート検出
def detect_beats(audio_path):
    y, sr = librosa.load(audio_path, sr=None)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    info = ffmpeg.probe(audio_path.replace('.m4a','.mp4'))
    fps = eval([s for s in info['streams'] if s['codec_type']=='video'][0]['r_frame_rate'])
    return [int(b*512/librosa.core.hop_length*fps/sr) for b in beats]

# ピクセルソート風フィルタ (ImageMagick + temporary files)
def pixel_sort(frame_img):
    tmp_in = tempfile.mktemp(suffix='.png')
    tmp_out = tempfile.mktemp(suffix='.png')
    frame_img.save(tmp_in)
    # ImageMagick で縦ピクセルソート
    subprocess.run(['convert', tmp_in, '-resize', '1x100%', '+repage', tmp_out])
    return tmp_out

# グリッチ＆同期
def process(video_path, audio_path, beats):
    # 音声入力
    a_in = ffmpeg.input(audio_path)
    # ベース映像
    v = ffmpeg.input(video_path).video

    # 1) ランダムフレームドロップ・カラーチャンネルシフト
    rand_drop = 'not(mod(n\,' + str(random.randint(2,5)) + '))'
    v = v.filter('select', rand_drop)
    v = v.filter('setpts', f'PTS/{random.uniform(1.5,3):.2f}')
    v = v.filter('lutrgb', 'r=negval','g=maxval','b=minval')

    # 2) ピクセルソート風 & ノイズオーバーレイ
    # datamoshテクスチャを挿入するフレームをランダム選択
    glitch_frames = random.sample(range(0, 100), k=10)
    segments = []
    for i, beat in enumerate(beats[:len(glitch_frames)]):
        start = beat
        end = beat+3
        seg = v.filter('trim', start_frame=start, end_frame=end)
        if i % 2 == 0:
            seg = seg.filter('tblend', 'all_mode=lighten')
        else:
            seg = seg.filter('tblend', 'all_mode=darken')
        # ランダムノイズ追加
        seg = seg.filter('noise', 'alls', '20')
        segments.append(seg)
    # 全体合成
    out_stream = v
    for seg in segments:
        out_stream = ffmpeg.concat(out_stream, seg, v=1, a=0)

    # 3) 最終マージ
    out_file = os.path.join(OUT, f"{SM}_super_glitch.mp4")
    (ffmpeg.concat(out_stream, a_in.audio, v=1, a=1)
           .output(out_file, vcodec='libx264', acodec='aac', movflags='faststart')
           .overwrite_output()
           .run()
    )
    print("Generated:", out_file)

# メイン
if __name__ == '__main__':
    prepare_dirs()
    vid, aud = download_assets()
    beats = detect_beats(aud)
    process(vid, aud, beats)
