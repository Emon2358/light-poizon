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

# ダウンロード (フォールバック対応)
def download_assets():
    # まず bestvideo+bestaudio を試す
    formats = ['bestvideo[ext=mp4]+bestaudio[ext=m4a]', 'best']
    for fmt in formats:
        try:
            opts = {'format': fmt, 'outtmpl': f'{WORK}/asset.%(ext)s'}
            with YoutubeDL(opts) as ydl:
                ydl.download([URL])
            # ファイル名取得
            files = os.listdir(WORK)
            video = next(f for f in files if f.endswith('.mp4'))
            audio = next(f for f in files if f.endswith(('.m4a', '.mp3', '.webm')))
            return os.path.join(WORK, video), os.path.join(WORK, audio)
        except Exception as e:
            print(f"Format {fmt} failed: {e}")
    raise RuntimeError("動画ダウンロードに失敗しました")

# ビート検出
def detect_beats(audio_path):
    y, sr = librosa.load(audio_path, sr=None)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    info = ffmpeg.probe(audio_path.replace(os.path.splitext(audio_path)[1], '.mp4'))
    fps = eval([s for s in info['streams'] if s['codec_type']=='video'][0]['r_frame_rate'])
    return [int(b * 512 / librosa.core.hop_length * fps / sr) for b in beats]

# グリッチ＆同期
def process(video_path, audio_path, beats):
    a_in = ffmpeg.input(audio_path)
    v = ffmpeg.input(video_path).video

    # ランダムフレームドロップ＆カラーチャンネルシフト
    drop = random.randint(2,5)
    v = v.filter('select', f"not(mod(n,{drop}))")
    speed = round(random.uniform(1.5,3.0),2)
    v = v.filter('setpts', f"PTS/{speed}")
    v = v.filter('lutrgb','r=negval','g=maxval','b=minval')

    # ビート同期＆ノイズオーバーレイ
    out = v
    for i, beat in enumerate(beats[:10]):
        seg = v.filter('trim', start_frame=beat, end_frame=beat+3)
        mode = 'lighten' if i%2==0 else 'darken'
        seg = seg.filter('tblend', f'all_mode={mode}').filter('noise','alls','20')
        out = ffmpeg.concat(out, seg, v=1, a=0)

    # 出力
    out_file = os.path.join(OUT, f"{SM}_super_glitch.mp4")
    (ffmpeg.concat(out, a_in.audio, v=1, a=1)
        .output(out_file, vcodec='libx264', acodec='aac', movflags='faststart')
        .overwrite_output().run())
    print("Generated:", out_file)

# メイン
if __name__ == '__main__':
    prepare_dirs()
    vid, aud = download_assets()
    beats = detect_beats(aud)
    process(vid, aud, beats)
