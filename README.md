# houshasenka-transcript
文字起こしの練習用のレポジトリ

## 方針

- 音声ファイル本体は Git 管理しない。
- Git 管理するのは、スクリプト、設定、README、作業メモのみ。
- 文字起こし結果や話者分離結果も原則 Git 管理しない。
- 最終的な匿名化済みテキストだけ、必要に応じて手動で管理対象にする。

## 想定する処理

1. ffmpeg で音声を分割・整音
2. whisper.cpp で文字起こし
3. pyannote.audio で話者分離
4. Whisper 出力と話者分離結果を統合

---

## Usage

This repository manages scripts for local transcription and speaker diarization.

Audio files, generated WAV files, Whisper outputs, RTTM files, and merged transcripts are not tracked by Git.

## Directory assumptions

The working audio files are stored outside this repository.

Example:

```text
~/pclouddrv/hosh/houshasenka
~/pclouddrv/hosh/houshasenka/20260529
```

The symbolic link `~/pclouddrv` points to pCloud Drive.

## Important path note

If the home/data directory path changes, for example:

```text
/Volumes/macomini-data/Users
```

to:

```text
/Volumes/macomini-data/eUsers
```

the existing `.venv` may contain stale absolute paths.

In that case, recreate the virtual environment instead of trying to repair it.

```bash
cd /Volumes/macomini-data/eUsers/ryo/dev/git/mojiokoshi

deactivate 2>/dev/null || true
rm -rf .venv

uv venv --python 3.12
source .venv/bin/activate
uv pip install pyannote.audio huggingface-hub
```

Confirm:

```bash
which python
python --version
echo "$VIRTUAL_ENV"
hf auth whoami
```

Expected `python` path:

```text
/Volumes/macomini-data/eUsers/ryo/dev/git/mojiokoshi/.venv/bin/python
```

## Initial setup

Install required command-line tools.

```bash
brew install ffmpeg uv whisper-cpp
```

Prepare Whisper model.

Example: `large-v3-turbo`.

```bash
mkdir -p ~/ssd/models/whisper

curl -L -o ~/ssd/models/whisper/ggml-large-v3-turbo.bin \
https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin
```

Create Python environment.

```bash
cd /Volumes/macomini-data/eUsers/ryo/dev/git/mojiokoshi

uv venv --python 3.12
source .venv/bin/activate
uv pip install pyannote.audio huggingface-hub
```

Login to Hugging Face.

```bash
hf auth login
hf auth whoami
```

pyannote models may require accepting the model terms on Hugging Face.

Required or likely required models:

```text
pyannote/speaker-diarization-3.1
pyannote/segmentation-3.0
```

## Workflow for one MP3 file

Example input:

```text
~/pclouddrv/hosh/houshasenka/20260529/kaiwa20260601.mp3
```

### 1. Convert MP3 to 16 kHz mono WAV

```bash
cd /Volumes/macomini-data/eUsers/ryo/dev/git/mojiokoshi

./scripts/prepare_audio.sh \
  ~/pclouddrv/hosh/houshasenka/20260529/kaiwa20260601.mp3
```

This creates:

```text
~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_16k_mono.wav
```

The conversion uses:

```bash
ffmpeg -y \
  -i input.mp3 \
  -ac 1 \
  -ar 16000 \
  -c:a pcm_s16le \
  output_16k_mono.wav
```

This format is safer for Whisper and pyannote than feeding MP3 directly.

### 2. Run Whisper transcription

```bash
./scripts/transcribe_whisper.sh \
  ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_16k_mono.wav
```

This creates files such as:

```text
kaiwa20260601_16k_mono.wav.txt
kaiwa20260601_16k_mono.wav.srt
kaiwa20260601_16k_mono.wav.vtt
```

### 3. Run pyannote speaker diarization

Use the activated venv Python.

```bash
source .venv/bin/activate

python scripts/diarize_pyannote.py \
  ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_16k_mono.wav
```

This creates:

```text
kaiwa20260601_16k_mono.wav.rttm
```

pyannote can be slow. Running this inside tmux is recommended.

Detach from tmux:

```text
Ctrl-b d
```

Reattach:

```bash
tmux attach
```

### 4. Merge Whisper SRT and pyannote RTTM

First create a neutral merged transcript.

```bash
python scripts/merge_srt_rttm.py \
  --srt ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_16k_mono.wav.srt \
  --rttm ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_16k_mono.wav.rttm \
  --output ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_merged.txt
```

Check the result.

```bash
less ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_merged.txt
```

### 5. Assign speaker names

After checking the first few minutes, decide which pyannote speaker corresponds to which person.

If:

```text
SPEAKER_00 = M職員
SPEAKER_01 = K職員
```

run:

```bash
python scripts/merge_srt_rttm.py \
  --srt ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_16k_mono.wav.srt \
  --rttm ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_16k_mono.wav.rttm \
  --output ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_MK.txt \
  --speaker-00 M職員 \
  --speaker-01 K職員
```

If reversed:

```bash
python scripts/merge_srt_rttm.py \
  --srt ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_16k_mono.wav.srt \
  --rttm ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_16k_mono.wav.rttm \
  --output ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_MK.txt \
  --speaker-00 K職員 \
  --speaker-01 M職員
```

## Full example

```bash
cd /Volumes/macomini-data/eUsers/ryo/dev/git/mojiokoshi
source .venv/bin/activate

./scripts/prepare_audio.sh \
  ~/pclouddrv/hosh/houshasenka/20260529/kaiwa20260601.mp3

./scripts/transcribe_whisper.sh \
  ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_16k_mono.wav

python scripts/diarize_pyannote.py \
  ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_16k_mono.wav

python scripts/merge_srt_rttm.py \
  --srt ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_16k_mono.wav.srt \
  --rttm ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_16k_mono.wav.rttm \
  --output ~/pclouddrv/hosh/houshasenka/20260529/wav/kaiwa20260601_merged.txt
```

## Git policy

Do not track raw or generated files.

Not tracked:

```text
*.mp3
*.m4a
*.wav
*.mp4
*.mov
*.txt
*.srt
*.vtt
*.rttm
*.diarization.tsv
data/
output/
tmp/
.venv/
.env
*.token
```

Track only:

```text
README.md
.gitignore
scripts/*.sh
scripts/*.py
```

Before committing, always check:

```bash
git status
git ls-files
```

If sensitive or generated files appear, do not commit them.

Commit scripts and README changes:

```bash
git add README.md .gitignore scripts
git commit -m "Document transcription and diarization workflow"
git push
```


