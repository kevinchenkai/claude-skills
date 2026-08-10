#!/usr/bin/env python3
"""验证 H3 输出：像素有效性 + 音频有效性 + 清晰度/运动量客观指标。

usage: h3_verify.py <mp4> [<mp4> ...]
"""
import sys
import av
import numpy as np


def lap_var(gray):
    """Laplacian 方差 — 清晰度代理，越高越锐利。"""
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    g = gray
    out = (g[:-2, 1:-1] * k[0, 1] + g[1:-1, :-2] * k[1, 0] +
           g[1:-1, 1:-1] * k[1, 1] + g[1:-1, 2:] * k[1, 2] + g[2:, 1:-1] * k[2, 1])
    return float(out.var())


def analyze(path):
    r = {"path": path.split("/")[-1]}
    try:
        c = av.open(path)
    except Exception as e:
        return {**r, "ERROR": str(e)}
    r["streams"] = [s.type for s in c.streams]
    vs = c.streams.video[0]
    r["size"] = f"{vs.codec_context.width}x{vs.codec_context.height}"
    r["fps"] = round(float(vs.average_rate), 2)

    n = 0
    blank = 0
    means = []
    sharp = []
    motion = []
    prev = None
    for i, f in enumerate(c.decode(video=0)):
        a = f.to_ndarray(format="rgb24").astype(np.float32)
        means.append(a.mean())
        if a.std() < 1.0:
            blank += 1
        if i % 8 == 0:  # 抽样算重指标
            g = a.mean(axis=2)
            gs = g[::2, ::2]
            sharp.append(lap_var(gs))
            if prev is not None:
                motion.append(float(np.abs(gs - prev).mean()))
            prev = gs
        n += 1
    r["frames"] = n
    r["blank"] = blank
    r["dur_s"] = round(n / float(vs.average_rate), 2)
    r["mean_min_max"] = f"{min(means):.1f}/{max(means):.1f}"
    r["sharpness"] = round(float(np.mean(sharp)), 1)
    r["motion"] = round(float(np.mean(motion)), 3) if motion else None

    # audio
    try:
        c2 = av.open(path)
        if c2.streams.audio:
            a0 = c2.streams.audio[0]
            buf = [fr.to_ndarray().astype(np.float32).ravel() for fr in c2.decode(audio=0)]
            x = np.concatenate(buf)
            ch = a0.codec_context.channels
            sr = a0.codec_context.sample_rate
            r["audio"] = (f"{sr}Hz/{ch}ch "
                          f"rms={np.sqrt((x**2).mean()):.3f} "
                          f"nan={bool(np.isnan(x).any())} "
                          f"dur={len(x)/sr/ch:.2f}s")
            # --- 音频内容特征（用于判断音频是否随提示词变化 / 是否含人声）---
            m = x[:len(x) // ch * ch].reshape(-1, ch).mean(axis=1)  # 下混单声道
            n = 1 << 14
            hop = n // 2
            frames_ = [m[i:i + n] * np.hanning(n) for i in range(0, max(1, len(m) - n), hop)]
            if frames_:
                S = np.abs(np.fft.rfft(np.stack(frames_), axis=1)) + 1e-9
                freqs = np.fft.rfftfreq(n, 1.0 / sr)
                psd = S.mean(axis=0)
                centroid = float((freqs * psd).sum() / psd.sum())
                # 人声基频/共振峰主要能量在 85-3000 Hz；风声/低频轰鸣偏低频
                band = lambda lo, hi: float(psd[(freqs >= lo) & (freqs < hi)].sum() / psd.sum())
                # 帧级能量起伏：语音/音效有明显包络变化，稳态噪声则平坦
                env = np.sqrt((np.stack(frames_) ** 2).mean(axis=1))
                flux = float(env.std() / (env.mean() + 1e-9))
                r["audio_feat"] = (f"centroid={centroid:.0f}Hz "
                                   f"lo(<300)={band(0,300):.2f} "
                                   f"mid(300-3k)={band(300,3000):.2f} "
                                   f"hi(>3k)={band(3000, sr/2):.2f} "
                                   f"env_var={flux:.2f}")
        else:
            r["audio"] = "NONE"
    except Exception as e:
        r["audio"] = f"ERR {e}"
    return r


if __name__ == "__main__":
    rows = [analyze(p) for p in sys.argv[1:]]
    keys = ["path", "frames", "blank", "dur_s", "size", "sharpness", "motion", "mean_min_max", "audio"]
    for r in rows:
        if "ERROR" in r:
            print(f"{r['path']}: ERROR {r['ERROR']}")
            continue
        print(" | ".join(f"{k}={r.get(k)}" for k in keys))
        if r.get("audio_feat"):
            print(f"    audio_feat: {r['audio_feat']}")
