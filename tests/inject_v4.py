with open("src/capstone/ui/index.html", "r") as f:
    text = f.read()

# We need to find the start of the landing page CSS and the end of the landing page JS.
# Previously I might have messed up the markers if my previous replace removed them.
# Let's search for '<div id="landing-page"' and '</style>'
import re

css_start_match = re.search(r'/\* ── .*?Landing Page Styles ──────────────────────────── \*/', text)
css_end_match = re.search(r'</style>', text[css_start_match.start() if css_start_match else 0:])
if css_start_match and css_end_match:
    css_start = css_start_match.start()
    css_end = css_start_match.start() + css_end_match.start()
else:
    print("Could not find CSS markers")
    exit(1)

body_start = text.find('<div id="landing-page"')
body_end_match = re.search(r'<div id="app-container"[^>]*>', text)
if body_end_match:
    body_end = body_end_match.end()
else:
    print("Could not find body markers")
    exit(1)


apple_css = """
  /* ── Apple DESIGN.md Authentic Styles ──────────────────────────── */
  .landing-page {
    font-family: SF Pro Text, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    color: #1d1d1f;
    background: #ffffff;
    width: 100%;
    overflow-x: hidden;
    -webkit-font-smoothing: antialiased;
  }
  
  .landing-page * {
    box-sizing: border-box;
  }

  /* Full Bleed Tiles */
  .landing-page .product-tile {
    position: relative;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
    text-align: center;
    padding: 80px 20px;
    background: #ffffff;
    color: #1d1d1f;
  }

  .landing-page .product-tile-parchment {
    background: #f5f5f7;
    color: #1d1d1f;
  }

  .landing-page .product-tile-dark {
    background: #272729;
    color: #ffffff;
  }
  
  /* Typography */
  .landing-page .hero-display {
    font-family: SF Pro Display, system-ui, -apple-system, sans-serif;
    font-size: 56px;
    font-weight: 600;
    line-height: 1.07;
    letter-spacing: -0.28px;
    margin: 0 0 8px 0;
  }

  .landing-page .display-lg {
    font-family: SF Pro Display, system-ui, -apple-system, sans-serif;
    font-size: 40px;
    font-weight: 600;
    line-height: 1.1;
    letter-spacing: 0px;
    margin: 0 0 12px 0;
  }

  .landing-page .lead {
    font-size: 28px;
    font-weight: 400;
    line-height: 1.14;
    letter-spacing: 0.196px;
    margin: 0 0 24px 0;
    max-width: 700px;
  }

  .landing-page .body-text {
    font-size: 17px;
    font-weight: 400;
    line-height: 1.47;
    letter-spacing: -0.374px;
    margin: 0 0 16px 0;
    color: #7a7a7a;
  }

  /* Buttons */
  .landing-page .cta-container {
    display: flex;
    gap: 16px;
    justify-content: center;
    align-items: center;
    margin-top: 12px;
  }

  .landing-page .btn-primary {
    background-color: #0066cc;
    color: #ffffff;
    font-size: 17px;
    font-weight: 400;
    padding: 11px 22px;
    border-radius: 9999px;
    border: none;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
    transition: transform 150ms ease;
  }

  .landing-page .btn-primary:active {
    transform: scale(0.95);
  }

  .landing-page .text-link {
    color: #0066cc;
    font-size: 17px;
    font-weight: 400;
    text-decoration: none;
    transition: opacity 150ms ease;
  }
  
  .landing-page .text-link:hover {
    text-decoration: underline;
  }

  .landing-page .text-link-on-dark {
    color: #2997ff;
    font-size: 17px;
    font-weight: 400;
    text-decoration: none;
  }
  
  .landing-page .text-link-on-dark:hover {
    text-decoration: underline;
  }

  /* Animations */
  .landing-page .observe-me {
    opacity: 0;
    transform: translateY(30px);
    transition: opacity 1s cubic-bezier(0.16, 1, 0.3, 1), transform 1s cubic-bezier(0.16, 1, 0.3, 1);
  }
  
  .landing-page .observe-me.visible {
    opacity: 1;
    transform: translateY(0);
  }
"""

apple_html = """
<div id="landing-page" class="landing-page">
  <!-- Top Hero Tile -->
  <section class="product-tile product-tile-parchment">
    <h1 class="hero-display observe-me">Degree Planner Pro.</h1>
    <p class="lead observe-me" style="transition-delay: 100ms;">Brilliantly intelligent. Absolute privacy.</p>
    <div class="cta-container observe-me" style="transition-delay: 200ms;">
      <button class="btn-primary" onclick="startApp()">Enter Advisor</button>
      <a href="#" class="text-link" style="margin-left: 8px;">Learn more &gt;</a>
    </div>
  </section>

  <!-- Dark Product Tile -->
  <section class="product-tile product-tile-dark">
    <h2 class="display-lg observe-me">Deep Reasoning.</h2>
    <p class="lead observe-me" style="transition-delay: 100ms; max-width: 600px;">Powered by advanced constraint-satisfaction and Llama 3. We automatically resolve prerequisites and check the live time schedule.</p>
    <div class="cta-container observe-me" style="transition-delay: 200ms;">
      <button class="btn-primary" onclick="startApp()">Get Started</button>
      <a href="#" class="text-link-on-dark" style="margin-left: 8px;">View technical specs &gt;</a>
    </div>
  </section>

  <!-- Light Utility Tile -->
  <section class="product-tile">
    <h2 class="display-lg observe-me">Instant Parsing.</h2>
    <p class="body-text observe-me" style="transition-delay: 100ms; max-width: 500px; color: #1d1d1f;">Drop your unofficial UW transcript PDF. We parse every course, transfer credit, and work-in-progress instantly using robust pattern matching.</p>
    <div class="cta-container observe-me" style="transition-delay: 200ms;">
      <a href="#" class="text-link">See how it works &gt;</a>
    </div>
  </section>
  
  <!-- Footer Tile -->
  <section class="product-tile product-tile-parchment" style="padding: 64px 20px; align-items: flex-start; text-align: left;">
    <p style="font-size: 12px; color: #7a7a7a; line-height: 1.3;">1. Local execution requires Ollama and Llama 3 models installed.<br>2. Transcripts are never uploaded to any external servers during local mode.</p>
    <div style="width: 100%; height: 1px; background: #e0e0e0; margin: 24px 0;"></div>
    <p style="font-size: 12px; color: #7a7a7a;">Copyright © 2026 Developer Team. All rights reserved.</p>
  </section>
</div>

<div id="app-container" style="display: none;">
"""

new_text = text[:css_start] + apple_css + "\n" + text[css_end:body_start] + apple_html + "\n" + text[body_end:]

with open("src/capstone/ui/index.html", "w") as f:
    f.write(new_text)

print("Injected Apple DESIGN.md Authentic Landing Page!")
