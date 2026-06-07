# mojiokoshi

音声ファイルの文字起こし・話者分離パイプライン。

## 方針

- 音声ファイル本体は Git 管理しない。
- Git 管理するのは、スクリプト、設定、README のみ。
- 文字起こし結果や話者分離結果も原則 Git 管理しない。
- 最終的な匿名化済みテキストだけ、必要に応じて手動で管理対象にする。

## 処理フロー

```
MP3 / 音声ファイル
     ↓ 1. ffmpeg で変換
  16kHz モノラル WAV
     ↓ 2. whisper.cpp で文字起こし
  .srt（字幕ファイル）
     ↓ 3. pyannote.audio で話者分離
  .rttm（話者タイムライン）
     ↓ 4. SRT + RTTM を統合
  merged.txt（誰が何を言ったかのテキスト）
```

上記 1〜4 は `scripts/run_pipeline.py` で1コマンドにまとめて実行できる（長尺音声向けのチャンク分割・再開対応つき）。

---

## セットアップ

### 1. 必要なツール

**macOS:**

```bash
brew install ffmpeg uv whisper-cpp
```

**Linux (Ubuntu/Debian):**

```bash
sudo apt install ffmpeg
# uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# whisper-cpp: 公式リポジトリからビルド、またはディストリのパッケージマネージャから
```

### 2. Whisper モデルの準備

任意のディレクトリにモデルをダウンロードする。

```bash
mkdir -p ~/models/whisper
curl -L -o ~/models/whisper/ggml-large-v3-turbo.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin
```

シェルのプロファイル（`~/.zshrc` や `~/.bashrc`）に以下を追記する。

```bash
export WHISPER_MODEL=~/models/whisper/ggml-large-v3-turbo.bin
```

追記後は `source ~/.zshrc`（または該当ファイル）で反映する。

> **注意:** `WHISPER_MODEL` が設定されていない場合、スクリプトはエラーを出力して終了する。
> `--whisper-model PATH` フラグで都度指定することもできる。

### 3. Python 環境の構築

```bash
cd mojiokoshi   # クローンしたディレクトリ

uv sync
source .venv/bin/activate
```

`uv sync` は `pyproject.toml` と `uv.lock` をもとに `.venv` を作成し、依存パッケージを一括インストールする。

> **.venv を作り直す場合:**
> パスが変わったなど `.venv` が壊れた場合は削除して再作成する。
> ```bash
> deactivate 2>/dev/null || true
> rm -rf .venv
> uv sync
> ```

### 4. HuggingFace 認証

```bash
hf auth login
hf auth whoami
```

pyannote のモデルは HuggingFace のライセンスへの同意が必要（初回のみ）。

必要なモデル:

- `pyannote/speaker-diarization-3.1`
- `pyannote/segmentation-3.0`

---

## ワンストップ実行（推奨）: `run_pipeline.py`

長時間の録音（1〜3時間）を変換・分割・文字起こし・話者分離・統合まで一括処理する。

```bash
source .venv/bin/activate

python scripts/run_pipeline.py INPUT.mp3
```

出力は `<入力ファイルのディレクトリ>/pipeline/<ファイル名なし拡張子>/` に作成される。

```text
pipeline/kaiwa20260601/
  kaiwa20260601_16k_mono.wav              # 変換済み音声（ステップ1）
  chunks/chunk_0000.wav (.srt/.rttm/...)  # チャンクごとの中間ファイル
  kaiwa20260601_full.srt                  # 全体の文字起こし（SRT）
  kaiwa20260601_full.rttm                 # 全体の話者分離（RTTM）
  kaiwa20260601_merged.txt                # 中立な統合テキスト（SPEAKER_00 / SPEAKER_01）
```

### なぜチャンク分割するのか

長時間の音声をそのまま処理するとメモリ不足や処理時間の問題が生じる。デフォルトでは20分ごとに60秒のオーバーラップを持つチャンクに分割し、各チャンクを独立して文字起こし・話者分離する。

チャンクをまたぐ話者ラベル（`SPEAKER_00` など）はオーバーラップ区間の一致度で照合し、全体で一貫したラベルに統一される。

### 中断後の再開

各ステップは出力ファイルが既に存在する場合にスキップする。同じコマンドを再実行すれば完了済みのステップは飛ばされ、残りの処理だけが実行される。

### チャンクサイズの変更

```bash
python scripts/run_pipeline.py INPUT.mp3 \
  --chunk-minutes 15 \
  --overlap-seconds 45
```

### 話者名の割り当て

`run_pipeline.py` が生成する `..._merged.txt` は中立なラベル（`SPEAKER_00` / `SPEAKER_01`）を使う。内容を確認して誰がどのラベルかを判断したあと、`merge_srt_rttm.py` で実名を割り当てる（文字起こしや話者分離の再実行は不要）。

```bash
python scripts/merge_srt_rttm.py \
  --srt   .../pipeline/kaiwa20260601/kaiwa20260601_full.srt \
  --rttm  .../pipeline/kaiwa20260601/kaiwa20260601_full.rttm \
  --output .../pipeline/kaiwa20260601/kaiwa20260601_named.txt \
  --speaker-00 M職員 \
  --speaker-01 K職員
```

### オプション一覧

```text
--output-dir DIR        出力ディレクトリ（デフォルト: <入力ディレクトリ>/pipeline/<ファイル名>）
--chunk-minutes N       チャンクの長さ（分）（デフォルト: 20）
--overlap-seconds N     チャンク間のオーバーラップ（秒）（デフォルト: 60）
--num-speakers N        想定話者数（デフォルト: 2）
--whisper-model PATH    ggml モデルのパス（デフォルト: $WHISPER_MODEL）
--diarization-model ID  HuggingFace の pyannote パイプライン名（デフォルト: pyannote/speaker-diarization-3.1）
--device {auto,cuda,mps,cpu}
                        話者分離に使うデバイス（デフォルト: auto — CUDA → MPS → CPU の順で自動検出）
```

---

## 手動ステップごとの実行（参照用・デバッグ用）

`run_pipeline.py` が自動化している各ステップを個別に実行する場合の手順。

### 1. MP3 → 16kHz モノラル WAV

```bash
./scripts/prepare_audio.sh INPUT.mp3
```

出力: `<入力ディレクトリ>/wav/<ファイル名>_16k_mono.wav`

第2引数で出力先を指定することもできる:

```bash
./scripts/prepare_audio.sh INPUT.mp3 OUTPUT.wav
```

### 2. Whisper 文字起こし

```bash
./scripts/transcribe_whisper.sh OUTPUT_16k_mono.wav
```

出力: `.wav.txt` / `.wav.srt` / `.wav.vtt`

### 3. pyannote 話者分離

```bash
source .venv/bin/activate

python scripts/diarize_pyannote.py OUTPUT_16k_mono.wav
```

出力: `.wav.rttm`

長時間かかるため、tmux 内で実行することを推奨する:

```bash
# デタッチ
Ctrl-b d

# 再アタッチ
tmux attach
```

### 4. SRT + RTTM の統合（中立版）

```bash
python scripts/merge_srt_rttm.py \
  --srt    OUTPUT_16k_mono.wav.srt \
  --rttm   OUTPUT_16k_mono.wav.rttm \
  --output merged.txt
```

### 5. 話者名の割り当て

```bash
python scripts/merge_srt_rttm.py \
  --srt    OUTPUT_16k_mono.wav.srt \
  --rttm   OUTPUT_16k_mono.wav.rttm \
  --output named.txt \
  --speaker-00 M職員 \
  --speaker-01 K職員
```

---

## Git 管理ポリシー

管理しないファイル:

```text
*.mp3  *.m4a  *.wav  *.mp4  *.mov
*.txt  *.srt  *.vtt  *.rttm  *.diarization.tsv
data/  output/  tmp/  .venv/  .env  *.token
```

管理するファイル:

```text
README.md  .gitignore  pyproject.toml  uv.lock
scripts/*.sh  scripts/*.py
```

コミット前に必ず確認する:

```bash
git status
git ls-files
```
