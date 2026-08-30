"""Rendering a plan to SVG.

The brief asks for a rendered plan alongside the JSON. This draws what the
pipeline actually knows: room rectangles at their estimated size, laid out in a
row because no placement has been solved, with each room's interval drawn as a
shaded band around it. Drawing the uncertainty rather than a crisp line is the
point — a plan that looks certain when it is not misrepresents the output.
"""

from __future__ import annotations

MARGIN = 40
GAP = 0.6
PX_PER_M = 42


def render_svg(plan: dict) -> str:
    rooms = plan.get("rooms", [])
    if not rooms:
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="480" height="120">'
                '<text x="20" y="60" font-family="sans-serif" font-size="14">'
                'No rooms reconstructed.</text></svg>')

    boxes = []
    x = 0.0
    for r in rooms:
        w = r["walls"][1]["length"]["value"]
        d = r["walls"][0]["length"]["value"]
        w_hi = r["walls"][1]["length"]["ci_high"]
        d_hi = r["walls"][0]["length"]["ci_high"]
        boxes.append((x, w, d, w_hi, d_hi, r))
        x += max(w, w_hi) + GAP

    total_w = x - GAP
    max_d = max(max(b[2], b[4]) for b in boxes)
    W = int(total_w * PX_PER_M) + 2 * MARGIN
    H = int(max_d * PX_PER_M) + 2 * MARGIN + 70

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}" font-family="ui-sans-serif,system-ui,sans-serif">',
           f'<rect width="{W}" height="{H}" fill="#fbfaf8"/>',
           f'<text x="{MARGIN}" y="26" font-size="15" font-weight="600" fill="#3d3a34">'
           f'{plan["capture"]["capture_id"]} &#183; {plan["capture"]["tier"]} tier</text>',
           f'<text x="{MARGIN}" y="44" font-size="11" fill="#8a8377">'
           f'Rooms drawn at estimated size. Shaded band is the confidence interval. '
           f'Layout is arbitrary: no room placement has been solved.</text>']

    base_y = MARGIN + 30
    for x0, w, d, w_hi, d_hi, r in boxes:
        px = MARGIN + x0 * PX_PER_M
        # Interval band first, so the estimate sits inside it.
        out.append(f'<rect x="{px:.1f}" y="{base_y:.1f}" width="{w_hi * PX_PER_M:.1f}" '
                   f'height="{d_hi * PX_PER_M:.1f}" fill="#e8642e" fill-opacity="0.10" '
                   f'stroke="#e8642e" stroke-opacity="0.25" stroke-dasharray="4 3"/>')
        out.append(f'<rect x="{px:.1f}" y="{base_y:.1f}" width="{w * PX_PER_M:.1f}" '
                   f'height="{d * PX_PER_M:.1f}" fill="#ffffff" fill-opacity="0.7" '
                   f'stroke="#5c564a" stroke-width="1.6"/>')
        ty = base_y + min(d, d_hi) * PX_PER_M + 16
        out.append(f'<text x="{px:.1f}" y="{ty:.1f}" font-size="12" fill="#3d3a34">{r["name"]}</text>')
        out.append(f'<text x="{px:.1f}" y="{ty + 14:.1f}" font-size="10" fill="#8a8377">'
                   f'{d:.2f} &#215; {w:.2f} m</text>')

    out.append('</svg>')
    return "\n".join(out)
