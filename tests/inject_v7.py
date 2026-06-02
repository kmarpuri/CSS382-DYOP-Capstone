import os

with open("src/capstone/ui/index.html", "r") as f:
    text = f.read()

css_start = text.find('/* ── Native Theme Premium Landing Page Styles ──────────────────────────── */')
if css_start == -1:
    css_start = text.find('/* ── Native Theme Landing Page Styles ──────────────────────────── */')
    
css_end = text.find('</style>')
body_start = text.find('<div id="landing-page"')
body_end = text.find('<div id="app-container"') + len('<div id="app-container" style="display: none;">')

v7_css = """
  /* ── Native Theme Expanded Landing Page Styles ──────────────────────────── */
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
    min-height: 90vh;
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

  /* Step-by-Step Section */
  .landing-page .steps-section {
    padding: 100px 20px;
    background: var(--surface);
    border-top: 1px solid var(--border-soft);
    border-bottom: 1px solid var(--border-soft);
    width: 100%;
  }
  
  .landing-page .steps-container {
    max-width: 1000px;
    width: 100%;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 60px;
    text-align: left;
  }
  
  .landing-page .step-row {
    display: flex;
    align-items: center;
    gap: 40px;
  }
  
  .landing-page .step-number {
    font-size: 80px;
    font-weight: 800;
    color: var(--border);
    line-height: 1;
    min-width: 80px;
    text-align: right;
  }
  
  .landing-page .step-text h3 {
    font-size: 28px;
    font-weight: 700;
    margin: 0 0 12px 0;
    color: var(--fg);
  }
  
  .landing-page .step-text p {
    font-size: 18px;
    line-height: 1.5;
    color: var(--muted);
    margin: 0;
  }

  @media (max-width: 700px) {
    .landing-page .step-row {
      flex-direction: column;
      text-align: center;
      gap: 16px;
    }
    .landing-page .step-number {
      text-align: center;
    }
  }

  /* Premium Feature Bento Box */
  .landing-page .bento-section {
    padding: 120px 20px;
    max-width: 1200px;
    width: 100%;
    margin: 0 auto;
  }
  
  .landing-page .section-title {
    font-size: 40px;
    font-weight: 800;
    letter-spacing: -0.03em;
    margin: 0 0 60px 0;
    color: var(--fg);
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
    padding: 48px;
  }
  
  .landing-page .bento-card:hover {
    transform: translateY(-4px);
  }

  .landing-page .bento-large {
    grid-column: span 12;
    min-height: 400px;
  }

  .landing-page .bento-half {
    grid-column: span 6;
  }
  
  @media (max-width: 800px) {
    .landing-page .bento-half {
      grid-column: span 12;
    }
  }

  .landing-page .bento-card h3 {
    font-size: clamp(28px, 4vw, 36px);
    font-weight: 700;
    margin: 0 0 16px 0;
    color: var(--fg);
    letter-spacing: -0.02em;
  }

  .landing-page .bento-card p {
    font-size: 18px;
    line-height: 1.6;
    color: var(--muted);
    margin: 0 0 16px 0;
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

v7_html = """
<div id="landing-page" class="landing-page">
  <!-- Hero Section -->
  <section class="hero-section" id="hero-top">
    <div class="hero-content">
      <h1 class="hero-headline observe-me" style="transition-delay: 100ms;">Capstone Graduation Scheduler.</h1>
      <p class="hero-sub observe-me" style="transition-delay: 200ms;">Drop your unofficial UW transcript. Tell us your major and credit preferences. Our local AI mathematically guarantees your fastest path to graduation.</p>
      <button class="btn-hero observe-me" style="transition-delay: 300ms;" onclick="startApp()">Enter Advisor</button>
    </div>
  </section>

  <!-- How it Works Section -->
  <section class="steps-section">
    <h2 class="section-title observe-me">How it works.</h2>
    <div class="steps-container">
      
      <div class="step-row observe-me">
        <div class="step-number">1</div>
        <div class="step-text">
          <h3>Export your UW Transcript</h3>
          <p>Log in to MyPlan or the UW Registrar and download your unofficial transcript as a PDF. The formatting doesn't need to be perfect—our parser handles everything from standard exports to print-to-PDFs.</p>
        </div>
      </div>
      
      <div class="step-row observe-me">
        <div class="step-number">2</div>
        <div class="step-text">
          <h3>Set your academic preferences</h3>
          <p>Drop the PDF into our tool, select your intended major (e.g., Computer Science & Software Engineering), and specify your preferred credit load per quarter. You are entirely in control of how aggressively you want to schedule.</p>
        </div>
      </div>
      
      <div class="step-row observe-me">
        <div class="step-number">3</div>
        <div class="step-text">
          <h3>Receive your optimized schedule</h3>
          <p>Hit generate. Within seconds, the system cross-references your completed credits against the university degree requirements and live time schedule, automatically resolving all prerequisites to output a conflict-free quarterly plan.</p>
        </div>
      </div>

    </div>
  </section>

  <!-- Premium Bento Grid Section -->
  <section class="bento-section">
    <h2 class="section-title observe-me">Designed for precision.</h2>
    <div class="bento-grid">
      
      <!-- Large Feature -->
      <div class="bento-card bento-large observe-me">
        <h3>Intelligent Natural Language Processing.</h3>
        <p>Transcripts are notoriously unstructured. Transfer credits, withdrawn classes, and work-in-progress courses all break standard parsers. We leverage local Llama 3 models specifically fine-tuned for structured extraction to robustly parse the exact text of your PDF with zero data loss.</p>
        <p>This means whether you transferred from Bellevue College or took a gap year, the system understands your academic history precisely as a human advisor would, ensuring your final plan is mathematically sound.</p>
      </div>
      
      <!-- Half Feature 1 -->
      <div class="bento-card bento-half observe-me" style="transition-delay: 100ms;">
        <h3>Absolute Privacy.</h3>
        <p>Your academic record is highly sensitive personal data. By utilizing Ollama to run lightweight Llama 3 instances entirely on your local machine, your transcript is never uploaded to an external API or cloud server. The entire reasoning pipeline executes offline.</p>
      </div>
      
      <!-- Half Feature 2 -->
      <div class="bento-card bento-half observe-me" style="transition-delay: 200ms;">
        <h3>Prerequisite Resolution.</h3>
        <p>The scheduler uses an advanced constraint-satisfaction algorithm. It maps out the directed acyclic graph (DAG) of UW prerequisites and ensures you are never scheduled for a class unless its prerequisites have been fulfilled in a prior quarter.</p>
      </div>
      
      <!-- Half Feature 3 -->
      <div class="bento-card bento-half observe-me" style="transition-delay: 100ms;">
        <h3>Live Time Schedule.</h3>
        <p>A degree plan is useless if the classes aren't actually offered. The tool automatically cross-references its recommendations against the live UW Time Schedule to guarantee the courses plotted for Autumn or Winter are definitively available.</p>
      </div>
      
      <!-- Half Feature 4 -->
      <div class="bento-card bento-half observe-me" style="transition-delay: 200ms;">
        <h3>Interactive Control.</h3>
        <p>Don't like the AI's suggestion? The interface is completely drag-and-drop. Move a class to the next quarter and the system will instantly flag any broken prerequisites or credit limits, acting as a guardrail while you customize your path.</p>
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

new_text = text[:css_start] + v7_css + "\n" + text[css_end:body_start] + v7_html + "\n" + text[body_end:]

with open("src/capstone/ui/index.html", "w") as f:
    f.write(new_text)

print("Injected Expanded Native Theme Landing Page!")
