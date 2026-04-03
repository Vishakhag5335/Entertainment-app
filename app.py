"""
Entertainment Planning Agent — Web UI
Run: python app.py
Opens automatically at http://localhost:5000
"""

import os
import sys
import threading
import webbrowser
from flask import Flask, request, jsonify, Response
from dotenv import load_dotenv
from groq import Groq
from tools import search_movies, search_music

load_dotenv()

app = Flask(__name__)
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ── Agent logic ────────────────────────────────────────────────────────────────

def call_llm(prompt: str) -> str:
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def run_agents(user_input: str) -> dict:
    # Agent 1: Movie Expert
    movie_data = search_movies(user_input)
    movie_result = call_llm(f"""
    You are a Movie Expert. The user asked: "{user_input}"
    Here is the movie data: {movie_data}
    Give a short friendly recommendation with reasons why each movie fits.
    Be brief and to the point. Use bullet points.
    """)

    # Agent 2: Music Expert
    music_data = search_music(user_input)
    music_result = call_llm(f"""
    You are a Music Expert. The user asked: "{user_input}"
    Here is the music data: {music_data}
    Suggest these songs briefly and explain why each fits the mood.
    Be brief and to the point. Use bullet points.
    """)

    # Agent 3: Entertainment Planner
    final_plan = call_llm(f"""
    You are an Entertainment Planner. Combine the following into one clean fun entertainment plan.
    Movies: {movie_result}
    Music: {music_result}
    Format it with:
    - A short welcome line
    - 🎬 Movie Recommendations section
    - 🎵 Music Playlist section
    - A fun closing line
    """)

    return {"movies": movie_result, "music": music_result, "plan": final_plan}


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return Response(HTML, mimetype="text/html")


@app.route("/plan", methods=["POST"])
def plan():
    data = request.get_json()
    query = (data or {}).get("query", "").strip()
    if not query:
        return jsonify({"error": "Query cannot be empty."}), 400
    try:
        result = run_agents(query)
        return jsonify({"success": True, "query": query, **result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Embedded HTML ──────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>EntertainmentAI</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=DM+Mono:wght@300;400&display=swap" rel="stylesheet"/>
  <style>
    :root {
      --bg:#0a0a0a; --surface:#111; --surface2:#181818;
      --gold:#c8a96e; --gold-dim:#8a6f42; --gold-glow:rgba(200,169,110,.15);
      --text:#e8e0d0; --muted:#6a6258; --border:rgba(200,169,110,.12);
    }
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{background:var(--bg);color:var(--text);font-family:'Cormorant Garamond',Georgia,serif;min-height:100vh;overflow-x:hidden}
    body::before{content:'';position:fixed;inset:0;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.04'/%3E%3C/svg%3E");opacity:.4;pointer-events:none;z-index:999}
    body::after{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 80% 60% at 50% 0%,rgba(200,169,110,.04) 0%,transparent 60%);pointer-events:none;z-index:1}
    .wrap{position:relative;z-index:10;max-width:860px;margin:0 auto;padding:0 2rem 6rem}
    header{padding:4rem 0 2.5rem;text-align:center;animation:fadeDown .8s ease both}
    .logo{display:inline-flex;align-items:center;gap:.5rem;margin-bottom:1.5rem}
    .bar{width:32px;height:1px;background:var(--gold);opacity:.6}
    .logo-txt{font-size:.65rem;letter-spacing:.35em;text-transform:uppercase;color:var(--gold);font-family:'DM Mono',monospace;font-weight:300}
    h1{font-size:clamp(2.8rem,7vw,5rem);font-weight:300;line-height:1.05;color:var(--text)}
    h1 em{font-style:italic;color:var(--gold)}
    .sub{margin-top:1rem;font-size:1.1rem;font-weight:300;color:var(--muted);letter-spacing:.02em}
    .divider{display:flex;align-items:center;gap:1rem;margin:2.5rem 0}
    .divider::before,.divider::after{content:'';flex:1;height:1px;background:var(--border)}
    .divider-ic{color:var(--gold-dim)}
    .search{animation:fadeUp .9s .2s ease both}
    .igroup{display:flex}
    input{flex:1;background:var(--surface);border:1px solid var(--border);border-right:none;color:var(--text);font-family:'Cormorant Garamond',serif;font-size:1.15rem;font-weight:300;padding:1.1rem 1.5rem;outline:none;transition:border-color .3s,box-shadow .3s;letter-spacing:.01em}
    input::placeholder{color:var(--muted);font-style:italic}
    input:focus{border-color:var(--gold-dim);box-shadow:0 0 0 1px var(--gold-dim) inset,0 0 24px var(--gold-glow)}
    btn,button{background:var(--gold);border:1px solid var(--gold);color:#0a0a0a;font-family:'DM Mono',monospace;font-size:.7rem;font-weight:400;letter-spacing:.2em;text-transform:uppercase;padding:1.1rem 1.8rem;cursor:pointer;transition:background .25s,transform .15s;white-space:nowrap}
    button:hover{background:#dbbe85}
    button:active{transform:scale(.98)}
    button:disabled{opacity:.4;cursor:not-allowed}
    .hint{margin-top:.8rem;font-size:.78rem;color:var(--muted);font-family:'DM Mono',monospace;font-weight:300;letter-spacing:.05em}
    .hint strong{color:var(--gold-dim)}
    #loading{display:none;text-align:center;padding:3.5rem 0;animation:fadeUp .5s ease both}
    .reel{display:inline-flex;gap:6px;margin-bottom:1.5rem}
    .hole{width:10px;height:10px;border:1px solid var(--gold);border-radius:50%;animation:pulse 1.2s ease-in-out infinite}
    .hole:nth-child(2){animation-delay:.2s}.hole:nth-child(3){animation-delay:.4s}.hole:nth-child(4){animation-delay:.6s}.hole:nth-child(5){animation-delay:.8s}
    .lbl{display:block;font-size:.7rem;letter-spacing:.3em;text-transform:uppercase;color:var(--gold-dim);font-family:'DM Mono',monospace}
    .steps{margin-top:1.2rem;display:flex;flex-direction:column;gap:.4rem}
    .step{font-size:.85rem;color:var(--muted);font-family:'DM Mono',monospace;font-weight:300;opacity:0;transform:translateX(-8px);transition:opacity .4s,transform .4s}
    .step.active{opacity:1;transform:translateX(0);color:var(--text)}
    .step.done{color:var(--gold-dim);opacity:1;transform:translateX(0)}
    #err{display:none;background:rgba(192,57,43,.08);border:1px solid rgba(192,57,43,.25);padding:1rem 1.5rem;margin-top:1.5rem;font-family:'DM Mono',monospace;font-size:.85rem;color:#e07060;animation:fadeUp .4s ease both}
    #results{display:none;animation:fadeUp .6s ease both}
    .rhead{text-align:center;margin-bottom:2.5rem}
    .rq{font-size:.7rem;letter-spacing:.25em;text-transform:uppercase;color:var(--gold-dim);font-family:'DM Mono',monospace;margin-bottom:.5rem}
    .rt{font-size:2rem;font-weight:300;font-style:italic}
    .tabs{display:flex;border-bottom:1px solid var(--border);margin-bottom:2rem}
    .tab{padding:.8rem 1.5rem;font-family:'DM Mono',monospace;font-size:.68rem;letter-spacing:.2em;text-transform:uppercase;color:var(--muted);cursor:pointer;border-bottom:1px solid transparent;margin-bottom:-1px;transition:color .2s,border-color .2s}
    .tab.active{color:var(--gold);border-bottom-color:var(--gold)}
    .panel{display:none}.panel.active{display:block}
    .card{background:var(--surface);border:1px solid var(--border);padding:2rem 2.5rem;position:relative}
    .card::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--gold-dim),transparent)}
    .card p{font-size:1.05rem;font-weight:300;line-height:1.85;color:var(--text);white-space:pre-wrap}
    .pcard{background:linear-gradient(135deg,var(--surface) 0%,var(--surface2) 100%);border:1px solid var(--border);padding:2.5rem;position:relative;overflow:hidden}
    .pcard::after{content:'✦';position:absolute;top:1.5rem;right:2rem;color:var(--gold-dim);font-size:1.2rem;opacity:.4}
    .pcard p{font-size:1.1rem;font-weight:300;line-height:1.9;white-space:pre-wrap}
    .reset-row{text-align:center;margin-top:3rem}
    .rbtn{background:transparent;border:1px solid var(--border);color:var(--muted);font-family:'DM Mono',monospace;font-size:.65rem;letter-spacing:.2em;padding:.7rem 1.5rem;cursor:pointer;transition:border-color .3s,color .3s}
    .rbtn:hover{border-color:var(--gold-dim);color:var(--gold)}
    footer{text-align:center;padding-top:3rem;font-family:'DM Mono',monospace;font-size:.65rem;letter-spacing:.2em;color:var(--muted);text-transform:uppercase}
    @keyframes fadeDown{from{opacity:0;transform:translateY(-16px)}to{opacity:1;transform:translateY(0)}}
    @keyframes fadeUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
    @keyframes pulse{0%,100%{opacity:.2;transform:scale(.8)}50%{opacity:1;transform:scale(1.1)}}
    @media(max-width:600px){.igroup{flex-direction:column}input{border-right:1px solid var(--border)}button{width:100%}.card,.pcard{padding:1.5rem}}
  </style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="logo"><span class="bar"></span><span class="logo-txt">Entertainment AI</span><span class="bar"></span></div>
    <h1>Your Personal<br><em>Entertainment</em> Planner</h1>
    <p class="sub">Three AI agents &middot; Movies &amp; Music &middot; Curated for you</p>
  </header>
  <div class="divider"><span class="divider-ic">✦</span></div>
  <section class="search">
    <div class="igroup">
      <input type="text" id="q" placeholder="e.g. romantic evening, sci-fi thriller, chill weekend…" autocomplete="off"/>
      <button id="btn" onclick="go()">Plan It</button>
    </div>
    <p class="hint">Powered by <strong>Groq · Llama 3.1 · Serper</strong> &mdash; press Enter or click Plan It</p>
  </section>
  <div id="loading">
    <div class="reel"><div class="hole"></div><div class="hole"></div><div class="hole"></div><div class="hole"></div><div class="hole"></div></div>
    <span class="lbl">Agents at work</span>
    <div class="steps">
      <div class="step" id="s1">🎬 Movie Agent — searching IMDB &amp; Rotten Tomatoes…</div>
      <div class="step" id="s2">🎵 Music Agent — curating the perfect playlist…</div>
      <div class="step" id="s3">📋 Planner Agent — crafting your evening…</div>
    </div>
  </div>
  <div id="err"></div>
  <div id="results">
    <div class="rhead"><div class="rq" id="rq"></div><div class="rt">Your Entertainment Plan</div></div>
    <div class="tabs">
      <div class="tab active" onclick="tab('plan')">Full Plan</div>
      <div class="tab" onclick="tab('movies')">🎬 Movies</div>
      <div class="tab" onclick="tab('music')">🎵 Music</div>
    </div>
    <div id="tp" class="panel active"><div class="pcard"><p id="pt"></p></div></div>
    <div id="tm" class="panel"><div class="card"><p id="mt"></p></div></div>
    <div id="tmu" class="panel"><div class="card"><p id="mus"></p></div></div>
    <div class="reset-row"><button class="rbtn" onclick="reset()">&#8617; Plan Something Else</button></div>
  </div>
  <footer>Built with Flask &middot; Groq &middot; Serper</footer>
</div>
<script>
  const qi=document.getElementById('q'),btn=document.getElementById('btn');
  qi.addEventListener('keydown',e=>{if(e.key==='Enter')go()});
  function animSteps(){
    const s=[300,3200,6500];
    ['s1','s2','s3'].forEach((id,i)=>{
      setTimeout(()=>{
        if(i>0){const p=document.getElementById(['s1','s2','s3'][i-1]);p.classList.add('done');p.classList.remove('active')}
        document.getElementById(id).classList.add('active');
      },s[i]);
    });
  }
  async function go(){
    const q=qi.value.trim();if(!q){qi.focus();return}
    document.getElementById('err').style.display='none';
    document.getElementById('results').style.display='none';
    document.getElementById('loading').style.display='block';
    btn.disabled=true;
    ['s1','s2','s3'].forEach(id=>{const el=document.getElementById(id);el.classList.remove('active','done')});
    animSteps();
    try{
      const r=await fetch('/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:q})});
      const d=await r.json();
      if(!r.ok)throw new Error(d.error||'Something went wrong.');
      ['s1','s2','s3'].forEach(id=>{const el=document.getElementById(id);el.classList.add('done');el.classList.remove('active')});
      await new Promise(res=>setTimeout(res,500));
      document.getElementById('loading').style.display='none';
      document.getElementById('rq').textContent='"'+d.query+'"';
      document.getElementById('pt').textContent=d.plan;
      document.getElementById('mt').textContent=d.movies;
      document.getElementById('mus').textContent=d.music;
      document.getElementById('results').style.display='block';
      document.getElementById('results').scrollIntoView({behavior:'smooth'});
    }catch(e){
      document.getElementById('loading').style.display='none';
      const er=document.getElementById('err');er.style.display='block';er.textContent='⚠ '+e.message;
    }finally{btn.disabled=false}
  }
  function tab(n){
    const tabs=document.querySelectorAll('.tab'),names=['plan','movies','music'];
    tabs.forEach((t,i)=>t.classList.toggle('active',names[i]===n));
    [['tp','plan'],['tm','movies'],['tmu','music']].forEach(([id,nm])=>{
      document.getElementById(id).classList.toggle('active',nm===n);
    });
  }
  function reset(){
    document.getElementById('results').style.display='none';
    document.getElementById('err').style.display='none';
    qi.value='';qi.focus();
    window.scrollTo({top:0,behavior:'smooth'});
  }
</script>
</body>
</html>"""


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = 5000

    # Check for required API keys
    missing = [k for k in ["GROQ_API_KEY", "SERPER_API_KEY"] if not os.getenv(k)]
    if missing:
        print(f"\n⚠  Missing keys in .env: {', '.join(missing)}")
        print("   Add them and restart.\n")
        sys.exit(1)

    # Auto-open browser after a short delay
    def open_browser():
        import time
        time.sleep(1.2)
        webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=open_browser, daemon=True).start()

    print(f"\n🎬 Entertainment Planning Agent")
    print(f"   Running at → http://localhost:{port}")
    print(f"   Press Ctrl+C to quit\n")

    app.run(host="0.0.0.0", port=port, debug=False)
