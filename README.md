# Persian-Ollama-LLm
Razor-AI — چت محلی با Ollama (فارسی → انگلیسی، آفلاین/بهینه)












⚡ خلاصه (فارسی — اول)

Razor-AI یک لایهٔ واسط است برای بهبود کیفیت تعامل با مدل‌های Ollama برای کاربران فارسی‌زبان. مشکل: بسیاری از مدل‌ها (مخصوصاً مدل‌های کدنویسی) نسبت به ورودی‌های انگلیسی بهتر عمل می‌کنند. راهکار: ورودی فارسی (اختیاری) به‌صورت لوکال با مدل quickmt-fa-en (CTranslate2) ترجمهٔ فارسی → انگلیسی می‌شود، سپس متن انگلیسیِ ترجمه‌شده به Ollama فرستاده می‌شود. بلوک‌های کد (``` ... ```) و inline code دست‌نخورده می‌مانند تا ساختار کد حفظ شود.

این README شامل دستورالعمل‌های کامل برای:

راه‌اندازی با Docker Compose،

دانلود خودکار یا دستی مدل ترجمه،

فعال‌سازی GPU برای Ollama،

راهنمای تغییر مدل Ollama و نکات عملی.

🔍 هدف پروژه

بالا بردن کیفیت پاسخ‌دهیِ مدل‌های Ollama برای ورودی‌های فارسی

حفظ ساختار و کد داخل prompt (مانند fenced code block)

اجرا شدن ترجمه به‌صورت آفلاین و لوکال با CTranslate2 (بدون نیاز به اینترنت بعد از دانلود مدل)

رابط کاربری ساده (FastAPI + SPA) با امکان نمایش ترجمه و پیام مدل

✅ قابلیت‌ها

ترجمهٔ محلی Fa → En با quickmt-fa-en (CTranslate2)

حفظ بلوک‌های کد و inline code

UI زیبا و قابلیت کپی بلوکِ کد

دانلود خودکار مدل ترجمه در entrypoint (در صورت نبود مدل)

پشتیبانی GPU برای Ollama (در صورت موجود بودن سخت‌افزار و تنظیمات میزبان)

امکان تغییر مدل Ollama با ویرایش یک متغیر محیطی (OLLAMA_MODEL)

راهنمای سریع — اجرا با Docker

ساخت ایمیج و بالا آوردن سرویس‌ها:

docker compose build --no-cache
docker compose up -d


مرورگر را باز کن: http://localhost:8000

برای تغییر مدل Ollama، متغیر محیطی OLLAMA_MODEL را ویرایش کن (در docker-compose.yml یا قبل از اجرای کانتینر):

environment:
  - OLLAMA_MODEL=qwen2.5-coder:1.5b


اگر می‌خواهی Ollama را با GPU اجرا کنی، ببین بخش GPU پایین‌تر.

فایل‌های نمونه (قابل کپی)
نمونه docker-compose.yml

در این نمونه Ollama و razor-api در دو سرویس جدا اجرا می‌شوند. اگر می‌خواهی GPU را فعال کنی، راهنمای GPU را ببین.

services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_USE_GPU=1   # در صورت نیاز (روی میزبان نصب GPU لازم است)
    # نکته: برای اجرای با GPU می‌توان از `--gpus all` یا تنظیمات nvidia runtime استفاده کرد.

  razor-api:
    build: .
    container_name: razor-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    depends_on:
      - ollama
    environment:
      - OLLAMA_HOST=http://ollama:11434
      - OLLAMA_MODEL=qwen2.5-coder:1.5b
    volumes:
      - ./app:/app   # برای توسعه: تغییرات لوکال را منعکس می‌کند

volumes:
  ollama_data:

نمونه Dockerfile برای razor-api

(این نمونه دانلود مستقیم مدل داخل image را انجام نمی‌دهد — دانلود در runtime انجام می‌شود تا حجم image زیاد نشود.)

FROM python:3.11-slim

WORKDIR /app
COPY ./app /app
# اگر quickmt repo محلی را داری، آن را هم کپی کن:
COPY ./quickmt /app/quickmt

# نصب وابستگی‌ها
RUN apt-get update && apt-get install -y git curl --no-install-recommends \
  && pip install --no-cache-dir fastapi uvicorn httpx jinja2 python-multipart requests ctranslate2 sentencepiece ollama \
  && pip install --no-cache-dir /app/quickmt || true

# مطمئن شو entrypoint اجراییه
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
CMD ["/app/entrypoint.sh"]

نمونه entrypoint.sh

(این فایل در زمان runtime اجرا می‌شود؛ اگر مدل ترجمه موجود نباشد آن را دانلود می‌کند سپس uvicorn را اجرا می‌کند.)

#!/usr/bin/env sh
set -eu

MODEL_DIR="/app/quickmt-fa-en"

# اگر quickmt محلی داخل اپ هست، نصبش کن (اختیاری)
if [ -d "/app/quickmt" ]; then
  pip install --no-cache-dir /app/quickmt || true
fi

# دانلود مدل ترجمه در صورت عدم وجود یا خالی بودن پوشه
if [ ! -d "${MODEL_DIR}" ] || [ -z "$(ls -A ${MODEL_DIR} 2>/dev/null)" ]; then
  echo "⚡ Downloading quickmt-fa-en (this can take several minutes)..."
  # اگر quickmt-model-download نصب شده باشد:
  quickmt-model-download quickmt/quickmt-fa-en ${MODEL_DIR} || echo "quickmt-model-download failed; continuing"
else
  echo "Model exists, skipping download."
fi

# در نهایت برنامه را اجرا کن
exec uvicorn main:app --host 0.0.0.0 --port 8000


نکته: اگر می‌خواهی دانلود مدل در مرحلهٔ build انجام شود (و داخل image قرار گیرد) — باید دستورات دانلود را داخل Dockerfile اضافه کنی. اما این کار باعث افزایش زمان build و حجم image خواهد شد.

دانلود مدل quickmt-fa-en (دستورات پیشنهادی)

اگر می‌خواهی دستی دانلود کنی یا داخل build این کار انجام شود، این سه فرمان را اجرا کن (فرض بر این است که در پوشهٔ پروژه هستی):

# اگر quickmt repo را نداری:
git clone https://github.com/quickmt/quickmt.git

# نصب package محلی quickmt (برای دسترسی به quickmt-model-download)
pip install ./quickmt/

# دانلود مدل quickmt-fa-en در مسیر ./quickmt-fa-en
quickmt-model-download quickmt/quickmt-fa-en ./quickmt-fa-en


اگر می‌خواهی دانلود را در داخل image انجام دهی، می‌توانی همین سه دستور را در Dockerfile اجرا کنی — اما حجم نهایی image زیاد می‌شود.

نمایش پیشرفت دانلود (تقریبی)

بعضی ابزارها خروجی یک نوار پیشرفت تولید نمی‌کنند یا در لاگ کانتینر به‌صورت خوانا نمایش داده نمی‌شوند. دو راهنما:

مستقیم در میزبان دانلود کن (توصیه): روی ماشین محلی یا سرور، مدل را دانلود کن و پوشهٔ quickmt-fa-en را در volumeٔ ollama یا در پروژه قرار بده تا کانتینر هنگام راه‌اندازی مجبور به دانلود نشود.

اسکریپت progress_downloader.py (نمونه): یک اسکریپت پایتون که فایل‌های مدل را تک‌به‌تک از huggingface یا از لیست فایل‌ها دانلود و اندازهٔ هر فایل را لاگ می‌کند — این خروجی در لاگ کانتینر بهتر نشان داده می‌شود و تقریباً نشان می‌دهد چقدر دانلود شده (تخمینی).

(در صورت خواستت، من progress_downloader.py آماده و برات می‌سازم.)

GPU — فعال‌سازی و یادداشت‌ها

برای استفاده از GPU با Ollama:

روی میزبان، درایور NVIDIA را نصب کن (با نسخه‌ای که کارتت پشتیبانی می‌کند).

nvidia-container-toolkit را نصب کن:

Ubuntu مثال:

distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker


کانتینر Ollama را با GPU اجرا کن:

با docker run:

docker run --gpus all -e OLLAMA_USE_GPU=1 --rm -p 11434:11434 ollama/ollama:latest


یا با Docker Compose: اگر سیستم Docker و Compose توانایی device_requests را دارد، از deploy.resources یا device_requests استفاده کن. در بسیاری از حالات ساده‌تر است تا از docker run --gpus all برای تست اولیه استفاده کنی.

توجه: تنظیمات GPU در docker-compose ممکن است بسته به نسخهٔ Docker/Compose متفاوت باشد. اگر مشکلی دیدی، سریع‌ترین راه تستِ GPU این است که Ollama را با docker run --gpus all ... اجرا کنی.

نکاتی دربارهٔ معماری ترجمه و حفظ کد

الگوریتم پیشنهادی برای ترجمهٔ امن:

متن را به بخش‌های fenced code block و متن عادی تقسیم کن (مثلاً با regex دنبال ... باش).

برای قسمت‌های متنِ عادی، inline code (مثل foo()) را با placeholder جایگزین کن.

فقط متنِ طبیعی را (بخش‌هایی که احتمالاً فارسی هستند) به quickmt-fa-en بده و ترجمهٔ انگلیسی بگیر.

جایگزین‌ها را برگردان و مجموعهٔ نهایی را به Ollama بفرست.

اگر نیاز به ترجمهٔ خروجی مدل به فارسی (En→Fa) داشتی، می‌توانی از همان مدل یا از prompt-engineering استفاده کنی.

این رویکرد باعث می‌شود که کدها بدون تغییر باقی بمانند و فقط متن طبیعی ترجمه شود — برای سؤال‌های فنی حیاتی است.

تغییر مدل Ollama

به‌راحتی مقدار OLLAMA_MODEL را عوض کن. مثال:

# در main.py یا environment
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b")


لیست مدل‌های Ollama را در سایت رسمی Ollama ببین و مدل دلخواه را ست کن.

توصیه‌های سیستم‌عامل / نصب‌ها

پیشنهاد من: Ubuntu (آخرین LTS) یا سیستم مبتنی بر Debian برای سرور.

برای توسعه روی ویندوز: از WSL2 با Docker Desktop و GPU passthrough (در صورت نیاز) استفاده کن.

حتماً nvidia-driver و nvidia-container-toolkit را برای GPU نصب کن.

فایل‌های کمکی پیشنهادی که می‌تونم آماده کنم (بگوی تا بسازم)

progress_downloader.py — دانلود فایل به‌صورت تک‌به‌تک با نمایش اندازه‌ها/پیشرفت تقریبی

translate_utils.py — توابع tokenization / detokenize / mask-code-blocks که برای حفظ کیفیت ترجمه استفاده می‌کنی

main.py کامل و هماهنگ شده با entrypoint و مسیر مدل

نسخهٔ README.html تعاملی (اگر می‌خواهی صفحهٔ زیبا برای نمایش در مرورگر هم داشته باشی)

شبکه‌ها / تماس

Twitter/X: @sepy_dev

GitHub: sepehr.ramzany

Instagram: sepehr.ramzany

Email: sepehr.ramzany@gmail.com

License / متن باز

این پروژه برای استفادهٔ شخصی و تحت مجوز متن‌باز منتشر کن (مثلاً MIT). اگر می‌خواهی فایل LICENSE بسازم هم بگو.

🇬🇧 English section (concise summary)
Razor-AI — Local Ollama Chat with high-quality Fa→En translation

Razor-AI improves Persian usability of Ollama models by translating Persian inputs to English using a local offline translator (quickmt-fa-en, CTranslate2). The process preserves fenced code blocks and inline code, sends the translated English prompt to Ollama, and returns the model reply. Deploy with Docker (Ollama + razor-api). Toggle translation per message in UI.

Quick start
git clone https://github.com/your/repo.git
docker compose build --no-cache
docker compose up -d
open http://localhost:8000

Change Ollama model

Set env var OLLAMA_MODEL (e.g. qwen2.5-coder:1.5b) either in docker-compose.yml or on the runtime.

GPU notes

Install NVIDIA drivers + nvidia-container-toolkit on the host. For quick testing:

docker run --gpus all -e OLLAMA_USE_GPU=1 -p 11434:11434 ollama/ollama:latest


Use GPU-aware Compose/deployment if you need production orchestration. Ollama falls back to CPU if no GPU is available.

Model download (recommended)

Prefer downloading models on host and mounting into container, or let entrypoint.sh download quickmt-fa-en at first runtime. Model size: hundreds of MBs — initial download may take several minutes.
