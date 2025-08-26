<!DOCTYPE html>
<html lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Razor-AI Documentation</title>
<style>
  body { font-family: 'Courier New', Courier, monospace; background: #0f1724; color: #e6eef8; margin:0; padding:0;}
  .container { max-width: 1000px; margin:auto; padding:20px; }
  h1, h2, h3 { color:#4f46e5; }
  p { line-height:1.6; }
  .badge { display:inline-block; padding:4px 10px; margin:2px; border-radius:6px; font-size:12px; font-weight:bold; color:white; }
  .badge.python { background:#3776AB; }
  .badge.fastapi { background:#009688; }
  .badge.docker { background:#2496ED; }
  .badge.ollama { background:#999; }
  .section { background:#0b1220; padding:15px; border-radius:12px; margin-bottom:20px; }
  .img-box { text-align:center; margin:20px 0; }
  img { max-width:90%; border-radius:12px; border:2px solid #4f46e5; }
  .config { background:#1e293b; padding:12px; border-radius:12px; margin:10px 0; font-size:14px; }
</style>
</head>
<body>
<div class="container">
  <h1>📘 Razor-AI Documentation</h1>

  <div class="section">
    <h2>🏷️ Badges</h2>
    <span class="badge python">Python 3.12</span>
    <span class="badge fastapi">FastAPI 0.100</span>
    <span class="badge docker">Docker 24.0</span>
    <span class="badge ollama">Ollama latest</span>
    <span class="badge">Status: MVP/Testing</span>
    <span class="badge">License: MIT</span>
  </div>

  <div class="img-box">
    <h2>🖼️ تصاویر پروژه</h2>
    <img src="https://via.placeholder.com/900x400?text=Razor-AI+Project+Overview" alt="Project Overview">
    <img src="https://via.placeholder.com/400x200?text=Translation+Toggle" alt="Translation Option">
  </div>

  <div class="section">
    <h2>⚡ هدف پروژه</h2>
    <p>هدف Razor-AI فراهم کردن بهترین تجربه برای استفاده از مدل‌های Ollama با **ورودی فارسی** است. متن‌ها با مدل <strong>quickmt-fa-en</strong> آفلاین ترجمه می‌شوند و بلوک‌های کد حفظ می‌شوند.</p>
    <ul>
      <li>ترجمه آفلاین Fa → En</li>
      <li>حفظ بلوک‌ها و inline code</li>
      <li>UI زیبا و قابل کپی کردن کد</li>
      <li>پشتیبانی GPU برای Ollama</li>
      <li>تغییر مدل Ollama با متغیر <code>OLLAMA_MODEL</code></li>
    </ul>
  </div>

  <div class="section">
    <h2>⚙️ تنظیمات مهم</h2>
    <p>🔹 <strong>تغییر مدل Ollama:</strong> فقط مقدار زیر را ویرایش کنید:</p>
    <div class="config">
      OLLAMA_MODEL=qwen2.5-coder:1.5b
    </div>
    <p>🔹 <strong>استفاده از GPU:</strong> اگر GPU دارید و می‌خواهید Ollama روی GPU اجرا شود:</p>
    <div class="config">
      docker run --gpus all -e OLLAMA_USE_GPU=1 -p 11434:11434 ollama/ollama:latest
    </div>
    <p>اگر GPU موجود نباشد، Ollama روی CPU fallback می‌کند.</p>
  </div>

  <div class="section">
    <h2>📝 شبکه‌های اجتماعی</h2>
    <p>Twitter/X: <a href="https://twitter.com/sepy_dev" style="color:#4f46e5">@sepy_dev</a></p>
    <p>GitHub: <a href="https://github.com/sepehr.ramzany" style="color:#4f46e5">sepehr.ramzany</a></p>
    <p>Instagram: <a href="https://www.instagram.com/sepehr.ramzany/" style="color:#4f46e5">sepehr.ramzany</a></p>
    <p>Email: <a href="mailto:sepehr.ramzany@gmail.com" style="color:#4f46e5">sepehr.ramzany@gmail.com</a></p>
  </div>

  <div class="section">
    <h2>🇬🇧 English Summary</h2>
    <p>Razor-AI is a local interface to improve Persian input with Ollama models. Persian text is translated offline using <strong>quickmt-fa-en</strong>, code blocks are preserved, then sent to Ollama. Docker + GPU ready.</p>
    <p><strong>Quick Start:</strong> clone repo & docker compose up</p>
    <p><strong>Change Ollama model:</strong> <code>OLLAMA_MODEL=qwen2.5-coder:1.5b</code></p>
    <p><strong>GPU Notes:</strong> Use <code>docker run --gpus all ...</code> for GPU, fallback to CPU if unavailable.</p>
  </div>

</div>
</body>
</html>

