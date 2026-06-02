import re

with open("src/capstone/ui/index.html", "r") as f:
    html = f.read()

# 1. Add Apple Landing Page CSS
css_to_add = """
  /* ── Apple Landing Page Styles ──────────────────────────── */
  .landing-page {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", sans-serif;
    color: #1d1d1f;
    background: #ffffff;
    width: 100%;
    overflow-x: hidden;
  }
  
  .landing-page * {
    box-sizing: border-box;
  }

  .landing-page section {
    position: relative;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 80px 20px;
    overflow: hidden;
  }

  /* Full bleed hero */
  .landing-page .hero-section {
    min-height: 100vh;
    background: #f5f5f7;
    justify-content: flex-start;
    padding-top: 15vh;
  }

  .landing-page .hero-headline {
    font-size: clamp(40px, 6vw, 56px);
    font-weight: 600;
    line-height: 1.07;
    letter-spacing: -0.015em;
    margin: 0 0 16px 0;
    opacity: 0;
    transform: translateY(20px);
    animation: fadeUp 1s cubic-bezier(0.16, 1, 0.3, 1) forwards 0.2s;
  }

  .landing-page .hero-sub {
    font-size: clamp(21px, 3vw, 28px);
    font-weight: 400;
    line-height: 1.14;
    letter-spacing: 0.007em;
    color: #1d1d1f;
    margin: 0 0 40px 0;
    opacity: 0;
    transform: translateY(20px);
    animation: fadeUp 1s cubic-bezier(0.16, 1, 0.3, 1) forwards 0.4s;
    max-width: 600px;
  }

  .landing-page .btn-primary {
    background: #0066cc;
    color: #ffffff;
    font-size: 17px;
    font-weight: 400;
    padding: 11px 22px;
    border-radius: 9999px;
    border: none;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
    transition: transform 150ms cubic-bezier(0.4, 0, 0.2, 1);
    opacity: 0;
    transform: translateY(20px);
    animation: fadeUp 1s cubic-bezier(0.16, 1, 0.3, 1) forwards 0.6s;
  }

  .landing-page .btn-primary:active {
    transform: scale(0.95);
  }

  /* Feature Tiles */
  .landing-page .tile-dark {
    background: #272729;
    color: #ffffff;
    min-height: 80vh;
  }
  
  .landing-page .tile-dark .hero-sub {
    color: #f5f5f7;
  }

  .landing-page .tile-light {
    background: #ffffff;
    color: #1d1d1f;
    min-height: 80vh;
  }

  .landing-page .tile-content {
    max-width: 980px;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 24px;
    opacity: 0;
    transform: translateY(40px);
    transition: opacity 1s cubic-bezier(0.16, 1, 0.3, 1), transform 1s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .landing-page .tile-content.visible {
    opacity: 1;
    transform: translateY(0);
  }

  .landing-page .tile-headline {
    font-size: clamp(34px, 5vw, 40px);
    font-weight: 600;
    line-height: 1.1;
    letter-spacing: 0;
    margin: 0;
  }

  /* Gradient Orb for aesthetics */
  .landing-page .orb {
    position: absolute;
    width: 60vw;
    height: 60vw;
    max-width: 800px;
    max-height: 800px;
    border-radius: 50%;
    background: radial-gradient(circle at center, rgba(0,102,204,0.15) 0%, rgba(0,102,204,0) 70%);
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    pointer-events: none;
    z-index: 0;
  }

  .landing-page .hero-mockup {
    margin-top: 60px;
    width: 80%;
    max-width: 800px;
    height: 400px;
    background: rgba(255, 255, 255, 0.8);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 18px;
    box-shadow: 0 20px 40px rgba(0,0,0,0.08);
    border: 1px solid rgba(0,0,0,0.05);
    opacity: 0;
    transform: translateY(40px) perspective(1000px) rotateX(5deg);
    animation: floatUp 1.2s cubic-bezier(0.16, 1, 0.3, 1) forwards 0.8s;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }
  
  .landing-page .hero-mockup img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    opacity: 0.8;
  }

  @keyframes fadeUp {
    to { opacity: 1; transform: translateY(0); }
  }
  
  @keyframes floatUp {
    to { opacity: 1; transform: translateY(0) perspective(1000px) rotateX(0); }
  }
"""

html = html.replace("</style>", css_to_add + "\n</style>")

# 2. Add Landing Page HTML and wrap app
landing_html = """
<div id="landing-page" class="landing-page">
  <!-- Hero Section -->
  <section class="hero-section">
    <div class="orb"></div>
    <h1 class="hero-headline">Your Next Quarter, Planned.</h1>
    <p class="hero-sub">Drop your transcript. Let AI build your perfect schedule.</p>
    <button class="btn-primary" onclick="startApp()">Get Started</button>
    
    <div class="hero-mockup">
      <!-- Abstract mockup of UI -->
      <div style="width: 100%; height: 100%; background: linear-gradient(135deg, #f5f5f7 0%, #ffffff 100%); display: flex; flex-direction: column; gap: 16px; padding: 32px;">
        <div style="width: 40%; height: 24px; background: #e0e0e0; border-radius: 4px;"></div>
        <div style="width: 100%; height: 100px; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);"></div>
        <div style="width: 100%; height: 100px; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);"></div>
      </div>
    </div>
  </section>

  <!-- Feature Tile 1 -->
  <section class="tile-dark">
    <div class="tile-content observe-me">
      <h2 class="tile-headline">Upload Your Transcript.</h2>
      <p class="hero-sub" style="margin-bottom: 0;">We parse your PDF instantly and securely. Nothing leaves your machine in local mode.</p>
    </div>
  </section>

  <!-- Feature Tile 2 -->
  <section class="tile-light">
    <div class="tile-content observe-me">
      <h2 class="tile-headline">AI-Powered Reasoning.</h2>
      <p class="hero-sub" style="margin-bottom: 0;">Powered by Groq Llama 3.3 or local Ollama. We analyze your degree requirements and prerequisites in seconds.</p>
    </div>
  </section>

  <!-- Feature Tile 3 -->
  <section class="tile-dark" style="background: #252527;">
    <div class="tile-content observe-me">
      <h2 class="tile-headline">Schedule-Aware.</h2>
      <p class="hero-sub" style="margin-bottom: 0;">Tell us your time preferences. "Nothing on Fridays." "Afternoons only." We check the time schedule for you.</p>
      <button class="btn-primary" style="margin-top: 32px; opacity: 1; transform: none; animation: none;" onclick="startApp()">Start Planning</button>
    </div>
  </section>
</div>

<div id="app-container" style="display: none;">
"""

html = html.replace("<body>", "<body>\n" + landing_html)
html = html.replace("</body>", "</div>\n</body>")

# 3. Add JS for Observer and App Launch
js_to_add = """
  // ── Landing Page Logic ───────────────────────────────────────
  function startApp() {
    document.getElementById('landing-page').style.display = 'none';
    const appContainer = document.getElementById('app-container');
    appContainer.style.display = 'block';
    appContainer.style.animation = 'fadeUp 0.5s ease forwards';
    window.scrollTo(0, 0);
  }

  document.addEventListener("DOMContentLoaded", () => {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
        }
      });
    }, { threshold: 0.2 });

    document.querySelectorAll('.observe-me').forEach(el => observer.observe(el));
  });
"""

html = html.replace("</script>\n</body>", js_to_add + "\n</script>\n</body>")

with open("src/capstone/ui/index.html", "w") as f:
    f.write(html)
print("Updated index.html")
