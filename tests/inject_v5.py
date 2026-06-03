import re

with open("src/capstone/ui/index.html", "r") as f:
    text = f.read()

css_start_match = re.search(r'/\* ── Apple DESIGN\.md Authentic Styles ──────────────────────────── \*/', text)
css_end = text.find('</style>')
body_start = text.find('<div id="landing-page"')
body_end_match = re.search(r'<div id="app-container"[^>]*>', text)
js_start = text.find('// ── Landing Page Logic ───────────────────────────────────────')
js_end = text.find('</script>', js_start)

if not (css_start_match and body_start != -1 and body_end_match and js_start != -1 and js_end != -1):
    print("Could not find markers")
    exit(1)

css_start = css_start_match.start()
body_end = body_end_match.end()

v5_css = """
  /* ── Native Theme Landing Page Styles ──────────────────────────── */
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

  /* Tall sections to enforce scrolling */
  .landing-page .hero-section {
    min-height: 100vh;
    padding-top: 20vh;
    justify-content: flex-start;
  }

  .landing-page .feature-section {
    min-height: 80vh;
    padding: 80px 20px;
    background: var(--surface);
    border-top: 1px solid var(--border-soft);
  }
  
  .landing-page .feature-section:nth-child(even) {
    background: var(--bg);
  }

  .landing-page .hero-content, .landing-page .feature-content {
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
  }
  
  .landing-page .feature-headline {
    font-size: clamp(32px, 5vw, 48px);
    font-weight: 700;
    line-height: 1.2;
    letter-spacing: -0.02em;
    margin: 0 0 24px 0;
    color: var(--fg);
  }

  .landing-page .hero-sub, .landing-page .feature-sub {
    font-size: clamp(20px, 3vw, 26px);
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

  .landing-page .btn-hero:active {
    transform: translateY(0);
    box-shadow: var(--shadow-sm);
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
    transition: opacity 0.8s cubic-bezier(0.16, 1, 0.3, 1), transform 0.8s cubic-bezier(0.16, 1, 0.3, 1);
  }
  
  .landing-page .observe-me.visible {
    opacity: 1;
    transform: translateY(0);
  }
"""

v5_html = """
<div id="landing-page" class="landing-page">
  <!-- Hero Section -->
  <section class="hero-section" id="hero-top">
    <div class="hero-content">
      <h1 class="hero-headline observe-me" style="transition-delay: 100ms;">Capstone Graduation Scheduler</h1>
      <p class="hero-sub observe-me" style="transition-delay: 200ms;">Drop your transcript. Tell us your schedule preferences. Our local AI builds your perfect path to graduation.</p>
      <button class="btn-hero observe-me" style="transition-delay: 300ms;" onclick="startApp()">Enter Advisor</button>
    </div>
  </section>

  <!-- Feature 1 -->
  <section class="feature-section">
    <div class="feature-content">
      <h2 class="feature-headline observe-me">Instant Transcript Parsing</h2>
      <p class="feature-sub observe-me" style="transition-delay: 100ms;">We instantly parse your unofficial UW transcript PDF. Every completed course, transfer credit, and work-in-progress is extracted securely and instantly using robust pattern matching.</p>
    </div>
  </section>

  <!-- Feature 2 -->
  <section class="feature-section">
    <div class="feature-content">
      <h2 class="feature-headline observe-me">Absolute Privacy via Local LLMs</h2>
      <p class="feature-sub observe-me" style="transition-delay: 100ms;">Your transcript data is sensitive. When running in local mode with Ollama, your transcript never leaves your machine. Your personal academic record remains strictly yours.</p>
    </div>
  </section>
  
  <!-- Feature 3 -->
  <section class="feature-section" style="padding-bottom: 20vh;">
    <div class="feature-content">
      <h2 class="feature-headline observe-me">Deep Reasoning & Constraints</h2>
      <p class="feature-sub observe-me" style="transition-delay: 100ms;">Powered by advanced constraint-satisfaction and Llama 3 reasoning. We automatically resolve prerequisites, respect your target load, and check the live time schedule to guarantee valid plans.</p>
    </div>
  </section>
  
  <!-- Floating Sticky CTA -->
  <div class="floating-cta" id="floating-btn">
    <button class="btn-hero" style="box-shadow: 0 10px 30px rgba(0,0,0,0.2);" onclick="startApp()">Enter Advisor</button>
  </div>
</div>

<div id="app-container" style="display: none;">
"""

v5_js = """
  // ── Landing Page Logic ───────────────────────────────────────
  
  document.addEventListener("DOMContentLoaded", () => {
    // Basic routing
    if (window.location.pathname === '/app') {
      document.getElementById('landing-page').style.display = 'none';
      document.getElementById('app-container').style.display = 'block';
    } else {
      // Intersection Observer for scroll animations
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
          }
        });
      }, { threshold: 0.15 });

      document.querySelectorAll('.observe-me').forEach(el => observer.observe(el));
      
      // Floating button visibility logic based on scrolling past the hero
      const heroObserver = new IntersectionObserver((entries) => {
        const floatingBtn = document.getElementById('floating-btn');
        entries.forEach(entry => {
          // If the hero section is out of view (scrolled past), show the floating button
          if (!entry.isIntersecting) {
            floatingBtn.classList.add('visible');
          } else {
            floatingBtn.classList.remove('visible');
          }
        });
      }, { threshold: 0.1 });
      
      const heroSection = document.getElementById('hero-top');
      if(heroSection) heroObserver.observe(heroSection);
    }
  });

  // Handle browser back/forward buttons seamlessly
  window.addEventListener('popstate', (event) => {
    if (window.location.pathname === '/app') {
      document.getElementById('landing-page').style.display = 'none';
      document.getElementById('app-container').style.display = 'block';
    } else {
      document.getElementById('landing-page').style.display = 'block';
      document.getElementById('app-container').style.display = 'none';
    }
  });

  function startApp() {
    window.history.pushState({}, "", "/app");
    // Native switch without funky fade out transitions that cause black screen bugs
    document.getElementById('landing-page').style.display = 'none';
    document.getElementById('app-container').style.display = 'block';
    window.scrollTo(0, 0);
  }
"""

new_text = text[:css_start] + v5_css + "\n" + text[css_end:body_start] + v5_html + "\n" + text[body_end:js_start] + v5_js + "\n" + text[js_end:]

with open("src/capstone/ui/index.html", "w") as f:
    f.write(new_text)

print("Injected Native Theme Flowing Landing Page!")
