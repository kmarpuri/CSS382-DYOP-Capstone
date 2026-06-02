import os

with open("src/capstone/ui/index.html", "r") as f:
    text = f.read()

with open("/tmp/hero_b64.txt", "r") as f:
    b64_img = f.read().strip()

css_start = text.find('/* ── Apple Landing Page Styles ──────────────────────────── */')
css_end = text.find('</style>')
body_start = text.find('<div id="landing-page"')
body_end = text.find('<div id="app-container"') + len('<div id="app-container" style="display: none;">')
js_start = text.find('// ── Landing Page Logic ───────────────────────────────────────')
js_end = text.find('</script>', js_start)

premium_css = """
  /* ── Premium Apple Landing Page Styles ──────────────────────────── */
  .landing-page {
    font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Inter", sans-serif;
    color: #1d1d1f;
    background: #000000;
    width: 100%;
    overflow-x: hidden;
    -webkit-font-smoothing: antialiased;
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
    overflow: hidden;
  }

  /* Cinematic Hero */
  .landing-page .hero-section {
    min-height: 100vh;
    background: #000000;
    color: #f5f5f7;
    justify-content: center;
    padding: 0 20px;
    padding-bottom: 10vh;
  }

  .landing-page .hero-bg-image {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 100vw;
    height: 100vh;
    object-fit: cover;
    opacity: 0.5;
    z-index: 0;
    mask-image: radial-gradient(circle, rgba(0,0,0,1) 30%, rgba(0,0,0,0) 80%);
    -webkit-mask-image: radial-gradient(circle, rgba(0,0,0,1) 30%, rgba(0,0,0,0) 80%);
  }

  .landing-page .hero-content {
    position: relative;
    z-index: 10;
    display: flex;
    flex-direction: column;
    align-items: center;
    max-width: 980px;
  }

  .landing-page .hero-headline {
    font-size: clamp(48px, 8vw, 96px);
    font-weight: 700;
    line-height: 1.05;
    letter-spacing: -0.03em;
    margin: 0 0 20px 0;
    background: linear-gradient(180deg, #ffffff 0%, #a0a0a0 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    opacity: 0;
    transform: translateY(30px);
    animation: premiumFadeUp 1.2s cubic-bezier(0.16, 1, 0.3, 1) forwards 0.3s;
  }

  .landing-page .hero-sub {
    font-size: clamp(24px, 4vw, 32px);
    font-weight: 500;
    line-height: 1.15;
    letter-spacing: -0.01em;
    color: #a1a1a6;
    margin: 0 0 48px 0;
    opacity: 0;
    transform: translateY(30px);
    animation: premiumFadeUp 1.2s cubic-bezier(0.16, 1, 0.3, 1) forwards 0.5s;
    max-width: 700px;
  }

  .landing-page .btn-primary {
    background: #ffffff;
    color: #000000;
    font-size: 17px;
    font-weight: 600;
    padding: 14px 28px;
    border-radius: 9999px;
    border: none;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
    transition: all 250ms cubic-bezier(0.4, 0, 0.2, 1);
    opacity: 0;
    transform: translateY(30px);
    animation: premiumFadeUp 1.2s cubic-bezier(0.16, 1, 0.3, 1) forwards 0.7s;
  }

  .landing-page .btn-primary:hover {
    transform: scale(1.03);
    box-shadow: 0 8px 24px rgba(255,255,255,0.15);
  }

  .landing-page .btn-primary:active {
    transform: scale(0.97);
  }

  /* Feature Sections */
  .landing-page .feature-section {
    padding: 120px 20px;
    background: #ffffff;
    color: #1d1d1f;
  }

  .landing-page .feature-section.dark {
    background: #000000;
    color: #f5f5f7;
  }

  .landing-page .feature-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 40px;
    max-width: 1200px;
    width: 100%;
  }

  .landing-page .feature-card {
    background: rgba(245, 245, 247, 1);
    border-radius: 24px;
    padding: 60px 40px;
    text-align: left;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 400px;
    opacity: 0;
    transform: translateY(40px);
    transition: opacity 1s cubic-bezier(0.16, 1, 0.3, 1), transform 1s cubic-bezier(0.16, 1, 0.3, 1);
  }
  
  .landing-page .feature-section.dark .feature-card {
    background: #111113;
  }

  .landing-page .feature-card.visible {
    opacity: 1;
    transform: translateY(0);
  }

  .landing-page .feature-card h3 {
    font-size: 28px;
    font-weight: 600;
    letter-spacing: -0.01em;
    margin: 0 0 16px 0;
  }

  .landing-page .feature-card p {
    font-size: 19px;
    line-height: 1.4;
    font-weight: 400;
    color: #86868b;
    margin: 0;
  }

  /* Deep reasoning section */
  .landing-page .deep-reasoning {
    padding: 160px 20px;
    background: #f5f5f7;
    text-align: center;
  }
  
  .landing-page .deep-reasoning h2 {
    font-size: clamp(40px, 6vw, 64px);
    font-weight: 700;
    letter-spacing: -0.02em;
    max-width: 800px;
    margin: 0 auto 30px auto;
  }

  @keyframes premiumFadeUp {
    from { opacity: 0; transform: translateY(30px); }
    to { opacity: 1; transform: translateY(0); }
  }
"""

premium_html = f"""
<div id="landing-page" class="landing-page">
  <!-- Hero Section -->
  <section class="hero-section">
    <img src="{b64_img}" alt="Abstract 3D Glass Orb" class="hero-bg-image" />
    <div class="hero-content">
      <h1 class="hero-headline">Course planning.<br>Brilliantly intelligent.</h1>
      <p class="hero-sub">Drop your transcript. Tell us your schedule preferences. Our local AI builds your perfect path to graduation.</p>
      <button class="btn-primary" onclick="startApp()">Enter Advisor</button>
    </div>
  </section>

  <!-- Feature Grid -->
  <section class="feature-section">
    <div class="feature-grid">
      <div class="feature-card observe-me">
        <div>
          <h3>Instant Parsing.</h3>
          <p>Drop your unofficial UW transcript PDF. We parse every course, transfer credit, and work-in-progress instantly using robust pattern matching.</p>
        </div>
      </div>
      <div class="feature-card observe-me" style="transition-delay: 150ms;">
        <div>
          <h3>Absolute Privacy.</h3>
          <p>When running in local mode with Ollama, your transcript never leaves your machine. Your data remains strictly yours.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Deep Reasoning Section -->
  <section class="deep-reasoning">
    <h2 class="observe-me">Understands your degree. Explores the schedule.</h2>
    <p class="hero-sub observe-me" style="margin: 0 auto 60px auto; color: #86868b;">Powered by advanced constraint-satisfaction and Llama 3 reasoning. We automatically resolve prerequisites, check the live time schedule, and recommend only courses that fit your load.</p>
    <button class="btn-primary observe-me" style="background: #1d1d1f; color: #fff;" onclick="startApp()">Get Started Now</button>
  </section>
</div>

<div id="app-container" style="display: none;">
"""

premium_js = """
  // ── Landing Page Logic ───────────────────────────────────────
  
  // Initialize routing
  document.addEventListener("DOMContentLoaded", () => {
    // If the user loads /app directly, skip the landing page
    if (window.location.pathname === '/app') {
      document.getElementById('landing-page').style.display = 'none';
      document.getElementById('app-container').style.display = 'block';
    } else {
      // Set up intersection observers for scroll animations
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
          }
        });
      }, { threshold: 0.15 });

      document.querySelectorAll('.observe-me').forEach(el => observer.observe(el));
    }
  });

  // Handle browser back/forward buttons
  window.addEventListener('popstate', (event) => {
    if (window.location.pathname === '/app') {
      document.getElementById('landing-page').style.display = 'none';
      document.getElementById('app-container').style.display = 'block';
      window.scrollTo(0, 0);
    } else {
      document.getElementById('landing-page').style.display = 'block';
      document.getElementById('app-container').style.display = 'none';
    }
  });

  function startApp() {
    // Push state so back button works!
    window.history.pushState({}, "", "/app");
    
    const landing = document.getElementById('landing-page');
    const appContainer = document.getElementById('app-container');
    
    // Smooth transition
    landing.style.opacity = '0';
    landing.style.transition = 'opacity 0.4s ease';
    
    setTimeout(() => {
      landing.style.display = 'none';
      appContainer.style.display = 'block';
      appContainer.style.animation = 'premiumFadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards';
      window.scrollTo(0, 0);
    }, 400);
  }
"""

new_text = text[:css_start] + premium_css + "\n" + text[css_end:body_start] + premium_html + "\n" + text[body_end:js_start] + premium_js + "\n" + text[js_end:]

with open("src/capstone/ui/index.html", "w") as f:
    f.write(new_text)

print("Injected Premium Apple Landing Page!")
