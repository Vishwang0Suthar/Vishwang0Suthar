#!/usr/bin/env python3
"""
Generates a section-heading SVG: lowercase mono label + hairline rule
running to the right edge. This is the only way to put a real typeface
on a heading, since GitHub strips <style> and font-family from markdown.

Usage: python3 generate_heading.py "top languages" heading_top_languages.svg [width]
"""
import base64
import os
import sys

INK = "#1a1a1a"
RULE = "#d8d8d8"


def build(label, width=760):
    font_path = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "heading.woff2")
    with open(font_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    font_size = 15
    char_w = font_size * 0.6
    label = label.lower()
    text_w = len(label) * char_w
    height = 28
    baseline = 18
    rule_y = height / 2
    rule_start = text_w + 14
    esc = label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    return f'''<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
<defs><style>
@font-face {{
  font-family: 'jbm-heading';
  src: url(data:font/woff2;base64,{b64}) format('woff2');
}}
text {{ font-family: 'jbm-heading', monospace; font-size: {font_size}px; fill: {INK}; }}
</style></defs>
<text x="0" y="{baseline}" xml:space="preserve">{esc}</text>
<line x1="{rule_start:.1f}" y1="{rule_y}" x2="{width-2}" y2="{rule_y}" stroke="{RULE}" stroke-width="1"/>
</svg>'''


if __name__ == "__main__":
    label = sys.argv[1]
    out_path = sys.argv[2]
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 760
    with open(out_path, "w") as f:
        f.write(build(label, width))
    print(f"wrote {out_path}")
