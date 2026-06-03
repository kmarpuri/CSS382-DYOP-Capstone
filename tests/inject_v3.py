with open("src/capstone/ui/index.html", "r") as f:
    text = f.read()

css_start = text.find('/* ── Premium Apple Landing Page Styles ──────────────────────────── */')
css_end = text.find('</style>')
body_start = text.find('<div id="landing-page"')
body_end = text.find('<div id="app-container"') + len('<div id="app-container" style="display: none;">')

clean_css = """
  /* ── Clean Landing Page Styles ──────────────────────────── */
  .landing-page {
    font-family: inherit;
    color: var(--fg);
    background: var(--bg);
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
    padding: 0 20px;
  }

  /* Cinematic Hero */
  .landing-page .hero-section {
    min-height: 80vh;
    padding-top: 10vh;
    padding-bottom: 10vh;
  }

  .landing-page .hero-content {
    position: relative;
    z-index: 10;
    display: flex;
    flex-direction: column;
    align-items: center;
    max-width: 900px;
  }

  .landing-page .hero-headline {
    font-size: clamp(40px, 6vw, 72px);
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: -0.03em;
    margin: 0 0 20px 0;
    background: var(--header-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    opacity: 0;
    transform: translateY(30px);
    animation: premiumFadeUp 1s cubic-bezier(0.16, 1, 0.3, 1) forwards 0.2s;
  }

  .landing-page .hero-sub {
    font-size: clamp(20px, 3vw, 26px);
    font-weight: 500;
    line-height: 1.3;
    color: var(--fg-soft);
    margin: 0 0 48px 0;
    opacity: 0;
    transform: translateY(30px);
    animation: premiumFadeUp 1s cubic-bezier(0.16, 1, 0.3, 1) forwards 0.4s;
    max-width: 700px;
  }

  .landing-page .btn-hero {
    background: var(--accent);
    color: #ffffff;
    font-size: 18px;
    font-weight: 600;
    padding: 16px 36px;
    border-radius: 9999px;
    border: none;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
    transition: all 200ms ease;
    opacity: 0;
    transform: translateY(30px);
    animation: premiumFadeUp 1s cubic-bezier(0.16, 1, 0.3, 1) forwards 0.6s;
    box-shadow: var(--shadow-md);
  }

  .landing-page .btn-hero:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
    background: var(--accent-hover);
  }

  .landing-page .btn-hero:active {
    transform: translateY(0);
    box-shadow: var(--shadow-sm);
  }

  /* Feature Sections */
  .landing-page .feature-section {
    padding: 80px 20px 120px 20px;
  }

  .landing-page .feature-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 32px;
    max-width: 1000px;
    width: 100%;
  }

  .landing-page .feature-card {
    background: var(--surface);
    border: 1px solid var(--border-soft);
    border-radius: var(--radius-lg);
    padding: 40px 30px;
    text-align: left;
    display: flex;
    flex-direction: column;
    box-shadow: var(--shadow-sm);
    opacity: 0;
    transform: translateY(40px);
    transition: opacity 0.8s ease, transform 0.8s ease;
  }

  .landing-page .feature-card.visible {
    opacity: 1;
    transform: translateY(0);
  }

  .landing-page .feature-card h3 {
    font-size: 22px;
    font-weight: 600;
    margin: 0 0 16px 0;
    color: var(--fg);
  }

  .landing-page .feature-card p {
    font-size: 16px;
    line-height: 1.5;
    color: var(--muted);
    margin: 0;
  }

  @keyframes premiumFadeUp {
    from { opacity: 0; transform: translateY(30px); }
    to { opacity: 1; transform: translateY(0); }
  }
"""

clean_html = """
<div id="landing-page" class="landing-page">
  <!-- Hero Section -->
  <section class="hero-section">
    <div class="hero-content">
      <h1 class="hero-headline">Course planning.<br>Intelligent and Private.</h1>
      <p class="hero-sub">Drop your transcript. Tell us your schedule preferences. Our local AI builds your perfect path to graduation.</p>
      <button class="btn-hero" onclick="startApp()">Enter Advisor</button>
    </div>
  </section>

  <!-- Feature Grid -->
  <section class="feature-section">
    <div class="feature-grid">
      <div class="feature-card observe-me">
        <h3>Instant Parsing</h3>
        <p>Drop your unofficial UW transcript PDF. We parse every course, transfer credit, and work-in-progress instantly using robust pattern matching.</p>
      </div>
      <div class="feature-card observe-me" style="transition-delay: 100ms;">
        <h3>Absolute Privacy</h3>
        <p>When running in local mode with Ollama, your transcript never leaves your machine. Your data remains strictly yours.</p>
      </div>
      <div class="feature-card observe-me" style="transition-delay: 200ms;">
        <h3>Deep Reasoning</h3>
        <p>Powered by advanced constraint-satisfaction and Llama 3 reasoning. We automatically resolve prerequisites and check the live time schedule.</p>
      </div>
    </div>
  </section>
</div>

<div id="app-container" style="display: none;">
"""

new_text = text[:css_start] + clean_css + "\n" + text[css_end:body_start] + clean_html + "\n" + text[body_end:]

with open("src/capstone/ui/index.html", "w") as f:
    f.write(new_text)

print("Injected Clean Landing Page consistent with theme!")
