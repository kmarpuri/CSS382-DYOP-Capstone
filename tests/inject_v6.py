import base64

with open("src/capstone/ui/index.html", "r") as f:
    text = f.read()

# Get the base64 of the two images
with open("/Users/kaustubhsri/.gemini/antigravity-ide/brain/05f1ed5e-f0aa-4e23-8030-7c09b585b8dc/landing_hero_bento_1780374969395.png", "rb") as f:
    bento_b64 = "data:image/png;base64," + base64.b64encode(f.read()).decode("utf-8")

with open("/Users/kaustubhsri/.gemini/antigravity-ide/brain/05f1ed5e-f0aa-4e23-8030-7c09b585b8dc/ai_nodes_1780374987741.png", "rb") as f:
    nodes_b64 = "data:image/png;base64," + base64.b64encode(f.read()).decode("utf-8")

css_start = text.find('/* ── Native Theme Landing Page Styles ──────────────────────────── */')
css_end = text.find('</style>')
body_start = text.find('<div id="landing-page"')
body_end = text.find('<div id="app-container"') + len('<div id="app-container" style="display: none;">')

v6_css = """
  /* ── Native Theme Premium Landing Page Styles ──────────────────────────── */
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

  /* Hero Section */
  .landing-page .hero-section {
    min-height: 85vh;
    padding-top: 15vh;
    justify-content: flex-start;
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
    font-size: clamp(48px, 8vw, 84px);
    font-weight: 800;
    line-height: 1.05;
    letter-spacing: -0.04em;
    margin: 0 0 24px 0;
    color: var(--fg);
  }
  
  .landing-page .hero-sub {
    font-size: clamp(20px, 3vw, 28px);
    font-weight: 500;
    line-height: 1.4;
    color: var(--muted);
    margin: 0 0 48px 0;
    max-width: 700px;
  }

  .landing-page .btn-hero {
    background: var(--accent);
    color: #ffffff;
    font-size: 18px;
    font-weight: 600;
    padding: 16px 36px;
    border-radius: var(--radius-lg);
    border: none;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
    transition: all 200ms ease;
    box-shadow: var(--shadow-md);
  }

  .landing-page .btn-hero:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
    background: var(--accent-hover);
  }

  /* Premium Feature Bento Box */
  .landing-page .bento-section {
    padding: 60px 20px 120px 20px;
    max-width: 1200px;
    width: 100%;
    margin: 0 auto;
  }

  .landing-page .bento-grid {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    grid-auto-rows: minmax(300px, auto);
    gap: 24px;
    width: 100%;
  }

  .landing-page .bento-card {
    background: var(--surface);
    border: 1px solid var(--border-soft);
    border-radius: 32px;
    overflow: hidden;
    position: relative;
    display: flex;
    flex-direction: column;
    box-shadow: var(--shadow-sm);
    text-align: left;
    transition: transform 0.3s ease;
  }
  
  .landing-page .bento-card:hover {
    transform: translateY(-4px);
  }

  .landing-page .bento-large {
    grid-column: span 12;
    min-height: 500px;
  }

  .landing-page .bento-half {
    grid-column: span 6;
  }
  
  @media (max-width: 800px) {
    .landing-page .bento-half {
      grid-column: span 12;
    }
  }

  .landing-page .bento-content {
    padding: 48px;
    position: relative;
    z-index: 2;
  }

  .landing-page .bento-card h3 {
    font-size: clamp(28px, 4vw, 36px);
    font-weight: 700;
    margin: 0 0 16px 0;
    color: var(--fg);
    letter-spacing: -0.02em;
  }

  .landing-page .bento-card p {
    font-size: 19px;
    line-height: 1.5;
    color: var(--muted);
    margin: 0;
    max-width: 400px;
  }

  .landing-page .bento-img {
    position: absolute;
    bottom: 0;
    right: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    z-index: 1;
    opacity: 0.8;
  }
  
  .landing-page .bento-large .bento-img {
    width: 60%;
    height: auto;
    max-height: 90%;
    object-fit: contain;
    right: 5%;
    bottom: -5%;
  }

  /* Floating Bottom Button */
  .landing-page .floating-cta {
    position: fixed;
    bottom: 40px;
    left: 50%;
    transform: translateX(-50%) translateY(100px);
    opacity: 0;
    pointer-events: none;
    transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    z-index: 100;
  }
  
  .landing-page .floating-cta.visible {
    transform: translateX(-50%) translateY(0);
    opacity: 1;
    pointer-events: auto;
  }

  /* Animations */
  .landing-page .observe-me {
    opacity: 0;
    transform: translateY(40px);
    transition: opacity 1s cubic-bezier(0.16, 1, 0.3, 1), transform 1s cubic-bezier(0.16, 1, 0.3, 1);
  }
  
  .landing-page .observe-me.visible {
    opacity: 1;
    transform: translateY(0);
  }
"""

v6_html = f"""
<div id="landing-page" class="landing-page">
  <!-- Hero Section -->
  <section class="hero-section" id="hero-top">
    <div class="hero-content">
      <h1 class="hero-headline observe-me" style="transition-delay: 100ms;">Capstone Graduation Scheduler.</h1>
      <p class="hero-sub observe-me" style="transition-delay: 200ms;">Drop your transcript. Tell us your schedule preferences. Our local AI builds your perfect path to graduation.</p>
      <button class="btn-hero observe-me" style="transition-delay: 300ms;" onclick="startApp()">Enter Advisor</button>
    </div>
  </section>

  <!-- Premium Bento Grid Section -->
  <section class="bento-section">
    <div class="bento-grid">
      
      <!-- Large Feature -->
      <div class="bento-card bento-large observe-me">
        <div class="bento-content">
          <h3>Intelligent UI.</h3>
          <p>An intuitive interface that transforms academic planning into a visual experience. Drag, drop, and optimize your schedule natively.</p>
        </div>
        <img src="{bento_b64}" class="bento-img" alt="Bento UI" style="mask-image: linear-gradient(to right, transparent, black 40%); -webkit-mask-image: linear-gradient(to right, transparent, black 40%);"/>
      </div>
      
      <!-- Half Feature 1 -->
      <div class="bento-card bento-half observe-me" style="transition-delay: 100ms;">
        <div class="bento-content">
          <h3>Absolute Privacy.</h3>
          <p>Powered entirely by local Llama 3 models through Ollama. Your unofficial UW transcript never leaves your machine. Period.</p>
        </div>
      </div>
      
      <!-- Half Feature 2 -->
      <div class="bento-card bento-half observe-me" style="transition-delay: 200ms;">
        <div class="bento-content">
          <h3 style="color: #fff;">Deep Reasoning.</h3>
          <p style="color: rgba(255,255,255,0.7);">Advanced constraint-satisfaction algorithms automatically resolve prerequisites and check the live time schedule to guarantee valid plans.</p>
        </div>
        <img src="{nodes_b64}" class="bento-img" alt="AI Nodes" style="width: 100%; object-fit: cover; z-index: 0; mask-image: linear-gradient(to bottom, transparent, black 80%); -webkit-mask-image: linear-gradient(to top, transparent, black 80%);"/>
      </div>

    </div>
  </section>
  
  <!-- Footer Tile -->
  <section style="padding: 64px 20px; max-width: 1200px; margin: 0 auto; align-items: flex-start; text-align: left; border-top: 1px solid var(--border-soft);">
    <p style="font-size: 12px; color: var(--muted); line-height: 1.3;">1. Local execution requires Ollama and Llama 3 models installed.<br>2. Transcripts are never uploaded to any external servers during local mode.</p>
    <div style="width: 100%; height: 1px; background: var(--border-soft); margin: 24px 0;"></div>
    <p style="font-size: 12px; color: var(--muted);">Copyright © 2026 Developer Team. All rights reserved.</p>
  </section>

  <!-- Floating Sticky CTA -->
  <div class="floating-cta" id="floating-btn">
    <button class="btn-hero" style="box-shadow: 0 10px 40px rgba(0,0,0,0.3);" onclick="startApp()">Enter Advisor</button>
  </div>
</div>

<div id="app-container" style="display: none;">
"""

new_text = text[:css_start] + v6_css + "\n" + text[css_end:body_start] + v6_html + "\n" + text[body_end:]

with open("src/capstone/ui/index.html", "w") as f:
    f.write(new_text)

print("Injected Premium Bento Landing Page!")
