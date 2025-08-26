# main.py
import subprocess
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import ctranslate2
import sentencepiece as spm
import ollama
import os, glob, re, time, logging, asyncio, httpx, uuid
from pydantic import BaseModel

logger = logging.getLogger("uvicorn.error")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

MODEL_DIR = "./quickmt-fa-en"
if not os.path.isdir(MODEL_DIR):
    print("⚡ Model not found, running entrypoint.sh to download...")
    subprocess.run(["/bin/sh", "entrypoint.sh"], check=True)


OLLAMA_MODEL = "qwen2.5-coder:1.5b"
OLLAMA_BASE = os.getenv("OLLAMA_BASE", os.getenv("OLLAMA_HOST", "http://ollama:11434"))
OLLAMA_CHAT_PATH = "/v1/chat/completions"
BEAM = 5

translator = None
sp = None

# ---------------- utils ----------------
def find_spm(model_dir):
    files = glob.glob(os.path.join(model_dir, "*.model")) + glob.glob(os.path.join(model_dir, "*.spm"))
    return files[0] if files else None

def load_sp(model_dir):
    sp_path = find_spm(model_dir)
    if sp_path and os.path.isfile(sp_path):
        s = spm.SentencePieceProcessor()
        s.load(sp_path)
        return s
    return None

def encode_text(sp_proc, text):
    if sp_proc is None:
        return text.strip().split()
    return sp_proc.encode(text, out_type=str)

def detokenize_clean(sp_proc, pieces):
    if sp_proc is not None:
        try:
            text = sp_proc.decode_pieces(pieces)
        except Exception:
            try:
                text = sp_proc.decode(sp_proc.encode(" ".join(pieces)))
            except Exception:
                text = " ".join(pieces)
    else:
        text = " ".join(pieces)

    text = text.replace("▁", " ")
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)
    text = re.sub(r"\s+'(\w)", r"'\1", text)
    return text.strip()

# ---------------- translator loader ----------------
def load_translator():
    global translator, sp
    logger.info("🔄 Loading translation model...")
    try:
        translator = ctranslate2.Translator(MODEL_DIR, device="auto")
    except Exception as e:
        logger.warning("Translator init (auto) failed: %s; trying CPU fallback.", e)
        try:
            translator = ctranslate2.Translator(MODEL_DIR, device="cpu")
        except Exception as e2:
            logger.exception("Translator init failed entirely: %s", e2)
            translator = None
            sp = None
            return

    sp = load_sp(MODEL_DIR)
    # warmup
    try:
        if translator:
            for _ in range(1):
                translator.translate_batch([encode_text(sp, "سلام")], beam_size=1)
    except Exception:
        logger.warning("Warmup failed (non-fatal).")
    logger.info("✅ Translator ready. sentencepiece=%s", bool(sp))

async def preload_ollama_model():
    try:
        logger.info(f"🔄 Checking Ollama model: {OLLAMA_MODEL}")
        # try python ollama client first (may raise if unreachable)
        try:
            ollama.show(model=OLLAMA_MODEL)
            logger.info("Ollama model already present (show successful).")
        except Exception:
            logger.info(f"⬇️ Pulling Ollama model via CLI: {OLLAMA_MODEL}")
            # best-effort CLI pull (may not be present in container environment)
            os.system(f"ollama pull {OLLAMA_MODEL}")
    except Exception as e:
        logger.warning("Ollama preload (best-effort) failed: %s", e)
    logger.info("✅ Ollama model ready (or pulled/attempted).")

# ---------------- startup ----------------
@app.on_event("startup")
async def startup_event():
    # load translator (blocking) in a thread to avoid blocking event loop
    await asyncio.to_thread(load_translator)
    # ask Ollama to pull model (best-effort)
    try:
        await preload_ollama_model()
    except Exception as e:
        logger.warning("preload_ollama_model error (ignored): %s", e)
    logger.info("Startup complete. Translator loaded=%s", translator is not None)

# ---------------- routes ----------------
@app.get("/", response_class=HTMLResponse)
async def get_chat(request: Request):
    # if you have templates/chat.html use TemplateResponse; simple demo returns HTML below
    return HTMLResponse(CHAT_HTML)

@app.post("/send")
async def send_message(fa_text: str = Form(...)):
    start_time = time.time()

    if translator is None:
        raise HTTPException(status_code=503, detail="Translator not available")

    toks = encode_text(sp, fa_text)
    try:
        out = await asyncio.to_thread(translator.translate_batch, [toks], beam_size=5)
    except RuntimeError as e:
        logger.exception("RuntimeError in translate_batch (send): %s", e)
        # try cpu fallback
        try:
            tr_local = ctranslate2.Translator(MODEL_DIR, device="cpu")
            out = await asyncio.to_thread(tr_local.translate_batch, [toks], beam_size=5)
            globals()['translator'] = tr_local
        except Exception:
            logger.exception("Fallback CPU failed in send.")
            raise HTTPException(status_code=503, detail="Translation failed (CUDA libs missing).")
    except Exception:
        logger.exception("Unexpected translation error (send).")
        raise HTTPException(status_code=500, detail="Internal translation error (send)")

    en_text = detokenize_clean(sp, out[0].hypotheses[0])

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": en_text}]
        )
        ollama_resp = response.get("message", {}).get("content")
    except Exception as e:
        logger.exception("Ollama chat (send) failed: %s", e)
        ollama_resp = str(e)

    duration = time.time() - start_time
    return JSONResponse({
        "fa_text": fa_text,
        "en_text": en_text,
        "ollama_response": ollama_resp,
        "duration_sec": duration
    })

# ---------------- chat API (with translation option) ----------------
CONVERSATIONS: dict[str, list[dict]] = {}

class ChatReq(BaseModel):
    message: str
    session_id: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    use_translation: bool | None = False

@app.post("/api/chat")
async def chat_endpoint(req: Request):
    body = await req.json()
    message = body.get('message')
    session_id = body.get('session_id') or str(uuid.uuid4())
    model = body.get('model') or OLLAMA_MODEL
    system_prompt = body.get('system_prompt')
    use_translation = bool(body.get('use_translation'))

    if not message:
        raise HTTPException(status_code=400, detail='message is required')

    conv = CONVERSATIONS.setdefault(session_id, [])
    if system_prompt:
        conv = [m for m in conv if m.get('role')!='system']
        conv.insert(0, {'role':'system','content':system_prompt,'ts':time.time()})
        CONVERSATIONS[session_id] = conv

    conv.append({'role':'user','content':message,'ts':time.time()})

    translated_en = None
    if use_translation:
        if translator is None:
            raise HTTPException(status_code=503, detail='Translator not available on server')
        tokens = encode_text(sp, message)
        try:
            # IMPORTANT: pass beam_size as keyword so it doesn't become target_prefix
            res = await asyncio.to_thread(translator.translate_batch, [tokens], beam_size=BEAM)
        except RuntimeError as e:
            logger.exception("RuntimeError in translate_batch: %s", e)
            # fallback: try recreate translator with CPU and retry
            try:
                tr_local = ctranslate2.Translator(MODEL_DIR, device="cpu")
                res = await asyncio.to_thread(tr_local.translate_batch, [tokens], beam_size=BEAM)
                globals()['translator'] = tr_local
            except Exception:
                logger.exception("Fallback to CPU failed in chat_endpoint.")
                raise HTTPException(status_code=503, detail="Translation failed (CUDA libs missing).")
        except Exception:
            logger.exception("Unexpected translation error in chat_endpoint.")
            raise HTTPException(status_code=500, detail="Internal translation error")

        out_pieces = res[0].hypotheses[0]
        translated_en = detokenize_clean(sp, out_pieces)

    # Build payload for Ollama; replace last user message with translated EN if present
    messages_payload = []
    for m in conv:
        role = m.get('role')
        content = m.get('content')
        if role == 'user' and content == message and translated_en:
            messages_payload.append({'role':'user','content': translated_en})
        else:
            messages_payload.append({'role': role if role in ('user','assistant','system') else 'user', 'content': content})

    payload = {
        'model': model,
        'messages': messages_payload,
        'temperature': 0.2,
        'max_tokens': 1024,
    }

    headers = {'Content-Type':'application/json'}
    url = OLLAMA_BASE.rstrip('/') + OLLAMA_CHAT_PATH

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.exception("Error contacting Ollama: %s", e)
        raise HTTPException(status_code=502, detail=f'error contacting Ollama: {e}')

    # parse reply
    reply = None
    try:
        choices = data.get('choices')
        if choices and isinstance(choices, list):
            parts = []
            for c in choices:
                msg = c.get('message') or c.get('delta') or {}
                content = msg.get('content') if isinstance(msg, dict) else None
                if content:
                    parts.append(content)
            if parts:
                reply = '\n'.join(parts)
    except Exception:
        reply = None

    if not reply:
        for k in ('result','text','output'):
            if k in data and isinstance(data[k], str):
                reply = data[k]; break

    if not reply:
        reply = str(data)

    conv.append({'role':'assistant','content':reply,'ts':time.time()})
    CONVERSATIONS[session_id] = conv

    return JSONResponse({'reply': reply, 'session_id': session_id, 'translated': translated_en or ''})

@app.post('/api/clear')
async def clear_conv(req: Request):
    body = await req.json()
    session_id = body.get('session_id')
    if session_id and session_id in CONVERSATIONS:
        CONVERSATIONS.pop(session_id, None)
    return JSONResponse({'ok': True})

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "translator": translator is not None}
# ---------------- UI HTML (Markdown + code highlighting, with RTL & copy) ----------------
CHAT_HTML = r"""<!doctype html>
<html lang="fa">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>چت با qwen2.5-coder + ترجمه (Fa→En)</title>

  <!-- JetBrains Mono -->
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&display=swap" rel="stylesheet">
  <!-- highlight.js CSS -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/github.min.css">

  <style>
    :root{
      --bg:#0f1724;
      --card:#0b1220;
      --accent:#4f46e5;
      --text:#e6eef8;
      --muted:#94a3b8;
      --code-bg:#fff6e6;
      --code-text:#1f2937;
      --bubble-user:linear-gradient(90deg,#0ea5a9,#06b6d4);
      --bubble-assistant:rgba(255,255,255,0.03);
      --btn-accent:#06b6d4;
      --translated-bg: rgba(255,255,255,0.06);
      --translated-border: rgba(255,255,255,0.04);
    }

    html,body{height:100%}
    body{
      font-family:'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, "Roboto Mono", "Courier New", monospace;
      background:linear-gradient(180deg,#071022 0%, #071822 100%);
      color:var(--text);
      padding:18px;
      margin:0;
      -webkit-font-smoothing:antialiased;
      -moz-osx-font-smoothing:grayscale;
    }

    .app{max-width:980px;margin:0 auto;background:var(--card);border-radius:12px;padding:18px;box-shadow:0 10px 40px rgba(2,6,23,.6);display:flex;flex-direction:column;gap:12px;min-height:80vh}
    header{display:flex;align-items:center;gap:12px}
    h1{margin:0;font-size:20px;font-weight:700}
    .meta{font-size:12px;color:var(--muted)}

    .controls{display:flex;gap:8px;margin-top:6px;align-items:center;flex-wrap:wrap}
    .select,input,textarea{background:#071021;border:1px solid rgba(255,255,255,0.04);color:var(--text);padding:8px;border-radius:8px}
    .select{padding:6px 10px}
    .system input{min-width:280px}

    .btn{display:inline-flex;align-items:center;gap:8px;cursor:pointer;border:0;padding:8px 12px;border-radius:10px;font-weight:600;font-size:13px;box-shadow:0 6px 14px rgba(2,6,23,0.5);transition:transform .08s ease;user-select:none;color:#041018;background:var(--btn-accent)}
    .btn.secondary{ background: transparent; color: var(--muted); border:1px solid rgba(255,255,255,0.04); box-shadow:none }

    .messages{margin-top:6px;flex:1;overflow:auto;padding:12px;background:rgba(255,255,255,0.02);border-radius:10px;display:flex;flex-direction:column;gap:10px}
    .msg{padding:10px 14px;border-radius:12px;margin-bottom:0;max-width:82%;line-height:1.45;word-break:break-word;position:relative}
    .msg.user{align-self:flex-end;background:var(--bubble-user);color:#002d2d;border-bottom-right-radius:4px}
    .msg.assistant{align-self:flex-start;background:var(--bubble-assistant);color:var(--text);border-bottom-left-radius:4px}

    .msg .md{ color: var(--text); font-size:14px; white-space:pre-wrap }
    .msg.user .md{ color: #012; } /* user bubble text darker */
    .msg.assistant .md{ color: #e6eef8; } /* assistant text lighter */

    .md p{ margin:0 0 8px 0; }
    .md h1, .md h2, .md h3 { color: var(--text); margin:6px 0; }
    .md code{ background: rgba(255,255,255,0.03); padding:2px 6px; border-radius:6px; font-family:inherit; color:inherit; font-size:13px }

    .md pre{ background: var(--code-bg); color: var(--code-text); padding:12px; border-radius:8px; overflow:auto; margin:8px 0; border:1px solid rgba(0,0,0,0.06); box-shadow: inset 0 -2px 0 rgba(0,0,0,0.02); position:relative }
    .md pre code{ background: transparent; padding:0; color:var(--code-text); font-size:13px; line-height:1.4; display:block }

    /* translated box under user message */
    .translated{
      display:block;
      margin-top:8px;
      padding:8px 10px;
      background:var(--translated-bg);
      border:1px solid var(--translated-border);
      border-radius:8px;
      color:var(--text);
      font-size:13px;
      direction:ltr; /* translations usually en, keep ltr, we'll detect later */
      text-align:left;
      white-space:pre-wrap;
    }

    /* copy button inside pre (top-right) */
    .copy-btn{
      position:absolute;
      top:8px;
      right:8px;
      background:rgba(0,0,0,0.08);
      border-radius:6px;
      padding:6px;
      font-size:12px;
      color:var(--code-text);
      cursor:pointer;
      border:1px solid rgba(0,0,0,0.04);
      display:flex;
      align-items:center;
      gap:6px;
    }
    .copy-btn:active{ transform:translateY(1px) }
    .copy-btn .copied{
      display:none;
      font-size:12px;
      color:green;
      margin-left:6px;
    }

    /* small responsive tweaks */
    @media (max-width:720px){
      .app{padding:12px}
      .controls{gap:6px}
      .system input{min-width:160px}
      .messages{height:58vh}
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div style="width:56px;height:56px;border-radius:12px;background:linear-gradient(135deg,#1e293b,#0ea5a9);display:flex;align-items:center;justify-content:center;font-weight:700">QW</div>
      <div>
        <h1>چت با qwen2.5-coder</h1>
        <div class="meta">سرور Ollama: <code>""" + OLLAMA_BASE + """</code> · ترجمه محلی: <code>quickmt-fa-en</code></div>
      </div>
    </header>

    <div class="controls">
      <label class="small">مدل
        <select id="model" class="select small">
          <option value="qwen2.5-coder:1.5b">qwen2.5-coder:1.5b</option>
          <option value="qwen2.5-coder:0.5b">qwen2.5-coder:0.5b</option>
          <option value="qwen2.5-coder:3b">qwen2.5-coder:3b</option>
        </select>
      </label>

      <label class="small system">System:
        <input id="system_prompt" placeholder="مثلاً: You are a helpful coding assistant." />
      </label>

      <label class="small" style="display:flex;align-items:center;gap:6px">
        <input type="checkbox" id="use_translation" /> ترجمه (FA → EN)
      </label>

      <button id="clear" class="btn secondary small">پاک کردن چت</button>
    </div>

    <div id="messages" class="messages" aria-live="polite"></div>

    <form id="form" autocomplete="off">
      <textarea id="prompt" placeholder="پیام خود را تایپ کنید..."></textarea>
      <button type="submit" class="btn">ارسال</button>
    </form>
  </div>

<!-- Libraries -->
<script src="https://cdn.jsdelivr.net/npm/markdown-it@13.0.1/dist/markdown-it.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>

<script>
  const md = window.markdownit({
    html: false,
    linkify: true,
    typographer: true,
    highlight: function (str, lang) {
      try {
        if (lang && hljs.getLanguage(lang)) {
          return hljs.highlight(str, { language: lang }).value;
        }
        return hljs.highlightAuto(str).value;
      } catch (__) {
        return '';
      }
    }
  });

  const messagesEl = document.getElementById('messages');
  const form = document.getElementById('form');
  const promptEl = document.getElementById('prompt');
  const modelEl = document.getElementById('model');
  const systemEl = document.getElementById('system_prompt');
  const clearBtn = document.getElementById('clear');
  const transBox = document.getElementById('use_translation');

  let sessionId = localStorage.getItem('ollama_session_id');
  if(!sessionId){ sessionId = crypto.randomUUID(); localStorage.setItem('ollama_session_id', sessionId); }

  // detect if text contains RTL (Persian/Arabic) characters
  function isRTL(text){
    return /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]/.test(text);
  }

  function renderMarkdown(text){
    return md.render(text || '');
  }

  // add copy button to code blocks
  function addCopyButtons(container){
    container.querySelectorAll('pre').forEach(pre => {
      // avoid adding twice
      if (pre.querySelector('.copy-btn')) return;
      const btn = document.createElement('button');
      btn.className = 'copy-btn';
      btn.type = 'button';
      btn.innerHTML = '<span class="label">کپی</span><span class="copied">✓</span>';
      // copy action
      btn.addEventListener('click', async (e) => {
        try {
          const codeEl = pre.querySelector('code');
          if(!codeEl) return;
          const text = codeEl.innerText;
          await navigator.clipboard.writeText(text);
          const copied = btn.querySelector('.copied');
          const label = btn.querySelector('.label');
          label.style.display = 'none';
          copied.style.display = 'inline';
          setTimeout(()=>{ copied.style.display='none'; label.style.display='inline'; }, 1400);
        }catch(err){
          console.warn('copy failed', err);
        }
      });
      // position button inside pre
      pre.style.position = 'relative';
      pre.appendChild(btn);
    });
  }

  function addMessage(role, text, extraHtml=''){
    const div = document.createElement('div');
    div.className = 'msg ' + (role==='user' ? 'user' : 'assistant');

    // if text is RTL (persian) set dir
    if (isRTL(text)) {
      // wrap with a RTL container: use markdown render but set dir on wrapper
      const rendered = renderMarkdown(text);
      div.innerHTML = `<div class="md" dir="rtl" style="text-align:right">${rendered}</div>${extraHtml}<div class="meta">${role}</div>`;
    } else {
      const rendered = renderMarkdown(text);
      div.innerHTML = `<div class="md">${rendered}</div>${extraHtml}<div class="meta">${role}</div>`;
    }

    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    // highlight code and add copy buttons
    div.querySelectorAll('pre code').forEach((el) => hljs.highlightElement(el));
    addCopyButtons(div);
  }

  // show translated box separately (under last user message)
  function showTranslatedUnderLastUser(translated){
    if(!translated) return;
    const lastUser = messagesEl.querySelector('.msg.user:last-of-type');
    if(!lastUser) return;
    // create translated element
    const transEl = document.createElement('div');
    transEl.className = 'translated';
    // if translated contains RTL letters -> mark RTL (rare, translation is EN)
    if(isRTL(translated)){
      transEl.setAttribute('dir','rtl');
      transEl.style.textAlign = 'right';
      transEl.innerHTML = renderMarkdown(translated);
    } else {
      transEl.setAttribute('dir','ltr');
      transEl.style.textAlign = 'left';
      // render inline markdown to avoid full-blocks inside the translated box
      transEl.innerHTML = md.renderInline(translated);
    }
    lastUser.querySelector('.md').appendChild(transEl);
  }

  form.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const text = promptEl.value.trim();
    if(!text) return;
    addMessage('user', text);
    promptEl.value = '';

    const payload = {message:text, session_id: sessionId, model: modelEl.value, system_prompt: systemEl.value, use_translation: transBox.checked};

    // typing placeholder
    const typing = document.createElement('div');
    typing.className='msg assistant';
    typing.id='typing';
    typing.innerHTML = `<div class="md">در حال تایپ...</div><div class="meta">assistant</div>`;
    messagesEl.appendChild(typing);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    try{
      const res = await fetch('/api/chat', {method:'POST',headers:{'content-type':'application/json'}, body: JSON.stringify(payload)});
      if(!res.ok){ throw new Error('server error ' + res.status); }
      const data = await res.json();
      document.getElementById('typing')?.remove();

      // show translated under last user
      if(data.translated && data.translated.length){
        showTranslatedUnderLastUser(data.translated);
      }

      addMessage('assistant', data.reply || '<no-reply>');
    }catch(err){
      document.getElementById('typing')?.remove();
      addMessage('assistant', 'خطا: ' + String(err.message || err));
    }
  });

  clearBtn.addEventListener('click', async ()=>{
    await fetch('/api/clear', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({session_id: sessionId})});
    messagesEl.innerHTML = '';
  });

  // Enter to send, Shift+Enter newline
  promptEl.addEventListener('keydown', (e)=>{
    if(e.key === 'Enter' && !e.shiftKey){
      e.preventDefault();
      form.requestSubmit();
    }
  });
</script>
</body>
</html>"""


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='0.0.0.0', port=8000, reload=False)
