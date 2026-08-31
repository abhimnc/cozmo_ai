"""Rendering the plan to SVG.

Draws what the pipeline actually knows, and draws the difference between what is
measured and what is inferred. Room outlines are solid because their dimensions
are measured; the ground they sit on is not, so positions carry a visible note
rather than the crisp authority of a survey drawing. A plan that looked surveyed
when it was arranged would misrepresent the output.
"""

from __future__ import annotations

MARGIN = 56
PX_PER_M = 34

INK = "#3d3a34"
MUTED = "#8a8377"
ROOM = "#ffffff"
WALL = "#5c564a"
ACCENT = "#e8642e"
GROUND = "#fbfaf8"


def render_svg(plan: dict) -> str:
    rooms = plan.get("rooms", [])
    placed = [r for r in rooms if r.get("polygon")]
    if not placed:
        return _fallback(rooms)

    xs = [p[0] for r in placed for p in r["polygon"]]
    ys = [p[1] for r in placed for p in r["polygon"]]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    W = int((maxx - minx) * PX_PER_M) + 2 * MARGIN
    H = int((maxy - miny) * PX_PER_M) + 2 * MARGIN + 76

    def sx(x): return MARGIN + (x - minx) * PX_PER_M
    def sy(y): return MARGIN + 52 + (y - miny) * PX_PER_M

    stitch = plan.get("stitch", {})
    layout = stitch.get("layout", {})
    orphans = set(layout.get("orphan_rooms", []))

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="ui-sans-serif,system-ui,sans-serif">',
        f'<rect width="{W}" height="{H}" fill="{GROUND}"/>',
        f'<text x="{MARGIN}" y="28" font-size="15" font-weight="600" fill="{INK}">'
        f'{plan["capture"]["capture_id"]} &#183; {plan["capture"]["tier"]} tier</text>',
        f'<text x="{MARGIN}" y="46" font-size="11" fill="{MUTED}">'
        f'Room sizes and adjacency are measured. Positions are solved so neighbours touch '
        f'and none overlap &#8212; they are not surveyed.</text>',
    ]

    # Adjacency first, so room outlines sit on top of the links.
    centres = {r["id"]: (sum(p[0] for p in r["polygon"][:4]) / 4,
                         sum(p[1] for p in r["polygon"][:4]) / 4) for r in placed}
    for edge in stitch.get("adjacency", []):
        a, b = centres.get(edge["room_a"]), centres.get(edge["room_b"])
        if not a or not b:
            continue
        conf = edge.get("confidence", 0.5)
        out.append(f'<line x1="{sx(a[0]):.1f}" y1="{sy(a[1]):.1f}" '
                   f'x2="{sx(b[0]):.1f}" y2="{sy(b[1]):.1f}" stroke="{ACCENT}" '
                   f'stroke-width="{1 + 2 * conf:.1f}" stroke-opacity="0.45"/>')

    for r in placed:
        pts = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in r["polygon"])
        dashed = ' stroke-dasharray="5 4"' if r["id"] in orphans else ""
        out.append(f'<polygon points="{pts}" fill="{ROOM}" stroke="{WALL}" '
                   f'stroke-width="1.8"{dashed}/>')
        cx, cy = centres[r["id"]]
        w = r["walls"][1]["length"]["value"]
        d = r["walls"][0]["length"]["value"]
        out.append(f'<text x="{sx(cx):.1f}" y="{sy(cy) - 4:.1f}" font-size="11.5" '
                   f'text-anchor="middle" fill="{INK}">{r["name"]}</text>')
        out.append(f'<text x="{sx(cx):.1f}" y="{sy(cy) + 11:.1f}" font-size="9.5" '
                   f'text-anchor="middle" fill="{MUTED}">{d:.2f} &#215; {w:.2f} m</text>')
        if r["id"] in orphans:
            out.append(f'<text x="{sx(cx):.1f}" y="{sy(cy) + 24:.1f}" font-size="8.5" '
                       f'text-anchor="middle" fill="{ACCENT}">no link recovered</text>')

    fp = stitch.get("footprint_area", {}).get("value")
    ov = stitch.get("room_overlap_area", {}).get("value")
    if fp is not None:
        out.append(f'<text x="{MARGIN}" y="{H - 18}" font-size="10.5" fill="{MUTED}">'
                   f'{len(placed)} rooms &#183; footprint {fp:.1f} m&#178; &#183; '
                   f'overlap {ov:.1f} m&#178; &#183; dashed outline = no adjacency recovered</text>')
    out.append('</svg>')
    return "\n".join(out)


def _fallback(rooms) -> str:
    msg = "No rooms reconstructed." if not rooms else "Rooms reconstructed but not placed."
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="520" height="110">'
            f'<rect width="520" height="110" fill="{GROUND}"/>'
            f'<text x="24" y="60" font-family="ui-sans-serif,system-ui,sans-serif" '
            f'font-size="13" fill="{INK}">{msg}</text></svg>')
