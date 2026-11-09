# ASR and OCR

Speech-to-text with faster-whisper large-v3 and burned-in subtitle OCR with RapidOCR (PP-OCRv6).
**Default host: `ssh vscode`**, even though the skill's general default is `train-1`.
Measured on vscode (2×H20, driver 575) on 2026-11-08 unless noted.

## Pick the source of the text

| Input | Use | Why |
| --- | --- | --- |
| Text subtitle track (`ffprobe` shows subrip/ass/mov_text) | Extract the track; skip ASR and OCR | It is the authored text |
| Single-speaker talk or podcast with clean audio, even with burned-in subtitles | `asr_transcribe.py`, then LLM correction; skip OCR | On a 32 min talk ASR matched OCR at 97.5% and missed only end-card text, in 2 min against 27 min. OCR has its own misreads, so subtitles are not ground truth |
| Burned-in Chinese subtitles on drama or music-heavy audio, foreign-language audio, or verbatim subtitle text needed | `ocr_burned_subs.py` is the dialogue; ASR only supplements | ASR cannot produce Chinese from foreign audio. On a 120 s drama clip ASR dropped whole lines OCR read; that was measured before the ASR config fix and not retested |
| No subtitles, or image-only subtitles (PGS) | `asr_transcribe.py` | Nothing else carries the words |
| Checking dialogue in a generated video | Cut a window at the expected time, `asr_transcribe.py --no-vad`, then listen | VAD swallowed whispered lines (ECHO E3). ASR is corroboration, never acceptance |
| Whole film or series ingest | movieDB pipeline, see below | Handles letterbox detection, masks, audio track choice, resume |

## Environment and paths

| Item | Value |
| --- | --- |
| Env | `source /nfs/envs/moviedb-env.sh`. Do not `pip install` into it |
| Versions | faster-whisper 1.2.1, ctranslate2 4.8.2, rapidocr 3.10.0, onnxruntime-gpu 1.25.1, torch 2.10.0+cu129 |
| Whisper model | `/home/share/user/chenkai/movieDB/model/faster-whisper-large-v3` (`model.bin` 3,087,284,237 bytes); override with `ASR_MODEL` |
| OCR models | Bundled in the env's `rapidocr/models` |
| Host needs | Both `/nfs` and `/home/share`. `tb` has no `/nfs` |

Calling `/nfs/envs/moviedb/bin/python` directly without the env script loses `LD_LIBRARY_PATH`, and ctranslate2 / onnxruntime-gpu then cannot find cuDNN/cuBLAS.

## Choose the device

1. Check the cards and the queue. ComfyUI holds about 52 GB on each vscode card even when idle:
   ```bash
   ssh vscode 'nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv,noheader; for p in 8189 8190; do curl -s -m 5 localhost:$p/queue; echo; done'
   ```
2. **ASR:** if the matching ComfyUI queue is empty and the card has at least 6 GB free, use `--device cuda`. Otherwise use `--device cpu`. An unreachable queue counts as busy.
3. **OCR: CPU, always, on vscode.** Both cards carry ComfyUI. On 2026-10-11 two H200 machines hit driver hangs while onnxruntime-gpu OCR shared cards with vLLM GLM (root cause unproven), so the script has no GPU option.

| Task on vscode | Speed (model load included) | Notes |
| --- | --- | --- |
| ASR, GPU float16 | 19× realtime on a 32 min talk, 45× on a 10 min drama clip | Dense speech is the slow case |
| ASR, CPU int8, 16 threads | 3× realtime on the same talk, 9× on the clip | Same completeness as GPU, so CPU is a slower substitute, not a downgrade |
| OCR, CPU, 8 workers × 4 threads, 3 fps | 3.4–4.6 frames/s | About 1.1–1.5× realtime; the 32 min talk took 27 min |

## Run

Under about a minute, pipe the script over stdin. Nothing needs deploying:

```bash
S=<skill dir>/scripts
ssh vscode 'source /nfs/envs/moviedb-env.sh; python - /path/a.mp4 --device cpu' < $S/asr_transcribe.py
ssh vscode 'source /nfs/envs/moviedb-env.sh; CUDA_VISIBLE_DEVICES=0 python - /path/a.mp4 --device cuda --out /tmp/a.jsonl' < $S/asr_transcribe.py
```

Anything longer goes in tmux with a `ck-` session name and a log file:

```bash
COPYFILE_DISABLE=1 tar cf - -C $S asr_transcribe.py ocr_burned_subs.py | ssh vscode 'mkdir -p /tmp/ck-asr && tar xf - -C /tmp/ck-asr'
ssh vscode "tmux new-session -d -s ck-ocr-x 'source /nfs/envs/moviedb-env.sh; python /tmp/ck-asr/ocr_burned_subs.py /path/a.mp4 --out /tmp/ck-asr/a.jsonl 2>&1 | tee /tmp/ck-asr/a.log; echo RC=\${PIPESTATUS[0]} >> /tmp/ck-asr/a.log'"
```

Treat the job as finished only when the log has an `RC=` line. A failed SSH probe is "unknown", not "done".

| Script | Output (JSONL) | Key arguments | Final stderr line and exit |
| --- | --- | --- | --- |
| `asr_transcribe.py` | `start end text lang suspect` | `--device cpu\|cuda`, `--lang zh\|en\|ko\|ja\|auto`, `--no-vad`, `--threads` | `ASR_DONE` exit 0, `ASR_SUSPECT` exit 3 |
| `ocr_burned_subs.py` | `start end text score` | `--start --dur --fps --top --workers` | `OCR_DONE` exit 0 |

## LLM correction after ASR

Not yet measured; these rules follow from the error types seen in the ASR/OCR comparison.

- Give the model the video title and description. They carry names and terms ASR cannot infer.
- Ask for typo fixes only: no polishing, no removing spoken fillers, same line count, timestamps unchanged. Check the line count and timestamps afterwards.
- Expect some errors to survive: context cannot settle a sentence about a word choice itself ("用了‘砸’这个字" transcribed as 杂).
- Internal data goes to local models only.

## Pitfalls

- **Keep ASR sequential and without `initial_prompt`.** Both failures below exit 0 and look like normal output.
  - Sequential + `initial_prompt` turned 10 minutes opening with theme music into pure hallucination (161 chars, 42 hits of 请不吝点赞…). Without the prompt: over 600 chars, 0 hits. `condition_on_previous_text=False` did not fix it (529 chars, 6 hits).
  - `BatchedInferencePipeline` lost text silently. On the 32 min talk one 25 s passage vanished (145 chars) after a long VAD segment, at batch 16 and at batch 4. Without the prompt it lost more (640 chars in gaps of 8+). Measured against OCR, sequential mode left only the end-card text uncovered. `s04_asr.py` still uses the batched pipeline, so ASR-only dialogue in movieDB may have holes.
- **The hallucination gate is a heuristic.** It knows listed phrases only, and a legitimate word can trigger the per-line `suspect` hint (…双位数的点赞). On exit 3 do not use the transcript. On exit 0 still spot-check against OCR, the expected text, or by ear.
- **Silence without VAD hallucinates** (Amara.org, 点赞订阅). With VAD a silent file returns 0 lines, which is the correct result.
- **Homophones are not errors** when checking dialogue: 他/她/它 and similar pass; wrong content fails.
- **OCR reads picture text and watermarks.** Raw frames produced Latin noise (`KCON`, `MNY`), and a corner Douyin watermark on the subtitle row was pasted into every line and made different subtitles merge. The script keeps boxes near the centre that contain CJK and drops single-frame lines. A centred logo or an end card (来抖音发现更多创作者) still gets through.
- **OCR misreads and variant characters remain.** Examples: 木知道, 上莱吧, 了→7, and traditional forms 別/沒/換. Normalise those before comparing text.
- **Set thread counts explicitly.** vscode reports 224 cores with a 32-CPU cgroup quota; library defaults oversubscribe. Keep workers × 4 and `--threads` within the quota, and check `/sys/fs/cgroup/cpu.max` on other hosts.
- **Memory limits change.** Check `/sys/fs/cgroup/memory.max` before large runs (256 GiB on 2026-11-08).
- **Never upgrade onnxruntime-gpu past 1.25.1 here.** 1.27+ needs CUDA 13 and silently falls back to CPU on driver 575. `rapidocr` also pulls in CPU `onnxruntime`, which shadows the GPU module.

## Whole film or series (movieDB)

Code is in `/home/share/user/chenkai/movieDB/code` and the manual is `README.md` one level up. The full `run_unit.sh` flow also needs a local GLM service on port 8101 and was built for 8×H200 hosts, so do not start it on vscode by default.

- `BURNIN_OCR=1` runs `s01c_burnin_ocr.py`, which auto-detects letterbox and overlay subtitles.
- `AUDIO_LANG=chi ASR_LANG=zh` selects and transcribes a Mandarin track.

## Coverage of these scripts

Tested with a 1080p Mandarin drama clip, a full 32 min 960×720 Mandarin talk with letterbox subtitles and a Douyin watermark, and generated silence: both ASR devices, the hallucination gate in both directions, and OCR on overlay and letterbox subtitles. On the talk, ASR and OCR text agreed at 97.5% after normalising punctuation. **Not tested:** English/Korean/Japanese, `--lang auto`, 4K sources, noisy multi-speaker audio over full length.

## Not deployed

None of these models are in the shared stores or in the movieDB model directory. Evaluations below come from a 2026-10 paper survey (`movies/docs/survey_20261010/C_perception.md` in `chenkai_airepo`), not local tests. Ask before downloading, and build a separate env instead of changing `/nfs/envs/moviedb`.

| Candidate | Would add |
| --- | --- |
| Qwen3-ASR-1.7B + ForcedAligner | Survey's first choice for Chinese/English/Japanese/Korean, plus aligning existing subtitles to speech |
| FireRedASR2-AED, FireRedVAD | Chinese A/B candidate; speech/singing/music VAD |
| MOSS-Transcribe-Diarize 0.9B | Transcript with anonymous speaker labels |
| SenseVoice-Small | Emotion and audio-event tags |
| WhisperLiveKit streaming API | `Codex/H20_Whisper_中文流式ASR_施工方案_Codex_Astra.md` is a plan, marked as not executed |
