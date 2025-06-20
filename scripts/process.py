#!/usr/bin/env python3
import os, sys, shutil, subprocess, random
def main():
    import ffmpeg
    from yt_dlp import YoutubeDL
    import librosa

    SM = sys.argv[1]
    URL = f"https://www.nicovideo.jp/watch/{SM}"
    WORK = 'tmp'
    OUT = 'output'

    # ディレクトリ準備
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)

    # 動画のみダウンロード
    video_file = os.path.join(WORK, 'video.mp4')
    ydl_video_opts = {
        'format': 'bestvideo[ext=mp4]/bestvideo',
        'outtmpl': video_file,
        'noplaylist': True
    }
    with YoutubeDL(ydl_video_opts) as ydl:
        ydl.download([URL])

    # 音声のみダウンロード
    audio_file = os.path.join(WORK, 'audio.m4a')
    ydl_audio_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio',
        'outtmpl': audio_file,
        'noplaylist': True
    }
    with YoutubeDL(ydl_audio_opts) as ydl:
        ydl.download([URL])

    # ビート検出
    y, sr = librosa.load(audio_file, sr=None)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    probe = ffmpeg.probe(video_file)
    fps = eval([s for s in probe['streams'] if s['codec_type']=='video'][0]['r_frame_rate'])
    beat_frames = [int(b * 512 / librosa.core.hop_length * fps / sr) for b in beats]

    # グリッチ映像生成
    v_in = ffmpeg.input(video_file).video
    a_in = ffmpeg.input(audio_file).audio

    # ベース処理
    drop = random.randint(2,5)
    speed = round(random.uniform(1.5, 3.0), 2)
    v = (v_in
         .filter('select', f"not(mod(n,{drop}))")
         .filter('setpts', f"PTS/{speed}")
         .filter('lutrgb', 'r=negval','g=maxval','b=minval')
    )

    # ビート同期グリッチ
    out_stream = v
    for i, bf in enumerate(beat_frames[:10]):
        seg = v.filter('trim', start_frame=bf, end_frame=bf+3)
        mode = 'lighten' if i % 2 == 0 else 'darken'
        seg = seg.filter('tblend', f'all_mode={mode}').filter('noise','alls','20')
        out_stream = ffmpeg.concat(out_stream, seg, v=1, a=0)

    # 最終マージ
    output_path = os.path.join(OUT, f"{SM}_super_glitch.mp4")
    (ffmpeg.concat(out_stream, a_in, v=1, a=1)
        .output(output_path, vcodec='libx264', acodec='aac', movflags='faststart')
        .overwrite_output()
        .run()
    )
    print("Generated:", output_path)

if __name__ == '__main__':
    main()
