# mojiokoshi

音声ファイルの文字起こし・話者分離パイプライン。

---

## セットアップ（初回のみ）

### ツールのインストール

**macOS:**
```bash
brew install ffmpeg uv whisper-cpp
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt install ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh
# whisper-cpp は公式リポジトリからビルドまたはパッケージマネージャから
```

### Whisper モデルの準備

```bash
mkdir -p ~/models/whisper
curl -L -o ~/models/whisper/ggml-large-v3-turbo.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin
```

`~/.zshrc`（または `~/.bashrc`）に追記して `source` する:

```bash
export WHISPER_MODEL=~/models/whisper/ggml-large-v3-turbo.bin
```

### Python 環境

```bash
cd mojiokoshi
uv sync
```

> `.venv` を作り直す場合: `rm -rf .venv && uv sync`

### HuggingFace 認証

```bash
source .venv/bin/activate
hf auth login
```

pyannote のモデルは HuggingFace 上でライセンスへの同意が必要（初回のみ）:
- `pyannote/speaker-diarization-3.1`
- `pyannote/segmentation-3.0`

---

## 使い方

### パイプライン実行

```bash
source .venv/bin/activate
python scripts/run_pipeline.py INPUT.mp3
```

出力先: `<入力ファイルのディレクトリ>/pipeline/<ファイル名>/`

```text
kaiwa_16k_mono.wav        変換済み音声
chunks/                   チャンクごとの中間ファイル
kaiwa_full.srt            文字起こし（全体）
kaiwa_full.rttm           話者分離（全体）
kaiwa_merged.txt          統合テキスト（SPEAKER_00 / SPEAKER_01）
```

中断した場合は同じコマンドを再実行すれば続きから再開する。

### 話者名の割り当て

`kaiwa_merged.txt` を確認して誰がどのラベルかを判断したあと:

```bash
python scripts/merge_srt_rttm.py \
  --srt    .../kaiwa_full.srt \
  --rttm   .../kaiwa_full.rttm \
  --output .../kaiwa_named.txt \
  --speaker-00 M職員 \
  --speaker-01 K職員
```

### オプション

```text
--output-dir DIR          出力ディレクトリ
--chunk-minutes N         チャンク長（分）[デフォルト: 20]
--overlap-seconds N       チャンク間オーバーラップ（秒）[デフォルト: 60]
--num-speakers N          想定話者数 [デフォルト: 2]
--whisper-model PATH      ggml モデルのパス（$WHISPER_MODEL の上書き）
--diarization-model ID    pyannote パイプライン名 [デフォルト: pyannote/speaker-diarization-3.1]
--device {auto,cuda,mps,cpu}  デバイス [デフォルト: auto]
```

### 手動実行（個別ステップ）

```bash
# 1. 音声変換
./scripts/prepare_audio.sh INPUT.mp3

# 2. 文字起こし
./scripts/transcribe_whisper.sh OUTPUT_16k_mono.wav

# 3. 話者分離（venv 内で）
python scripts/diarize_pyannote.py OUTPUT_16k_mono.wav

# 4. 統合
python scripts/merge_srt_rttm.py \
  --srt OUTPUT_16k_mono.wav.srt \
  --rttm OUTPUT_16k_mono.wav.rttm \
  --output merged.txt
```

---

## Git 管理ポリシー

音声・生成ファイルは管理しない。スクリプト・設定・README のみ管理する。

コミット前に確認:
```bash
git status && git ls-files
```
