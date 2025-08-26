#!/bin/sh
set -e

echo "🚀 Checking quickmt-fa-en model..."

# نصب سورس quickmt
pip install ./quickmt

# اگر مدل وجود نداشت، با نوار پیشرفت دانلود کن
if [ ! -d "/app/quickmt-fa-en" ]; then
    echo "⚡ Downloading quickmt-fa-en model with progress bar..."
    pip install huggingface_hub tqdm

    python3 <<'PYCODE'
from huggingface_hub import snapshot_download

print("📥 Downloading quickmt-fa-en |~300~ MB ...")
snapshot_download(
    repo_id="quickmt/quickmt-fa-en",
    local_dir="/app/quickmt-fa-en",
    local_dir_use_symlinks=False,
    resume_download=True
)
print("✅ Model download finished!")
PYCODE
else
    echo "✅ Model already exists, skipping download."
fi

# اجرای FastAPI
exec uvicorn main:app --host 0.0.0.0 --port 8000
