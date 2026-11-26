# -*- coding: utf-8 -*-
"""Клаузура «Остановка» — подача на формат А3 (420×297 мм), основной масштаб 1:50.
SVG строится в миллиметрах листа, поэтому при печати 100% масштаб точный."""
import math, base64

# ------------------------------------------------------------------ helpers
OUT = []
def add(s): OUT.append(s)

def f(v): return f"{v:.3f}".rstrip('0').rstrip('.')

def catmull(pts, n=24):
    """Сглаживание полилинии сплайном Катмулла–Рома."""
    res = []
    P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i-1], P[i], P[i+1], P[i+2]
        for j in range(n):
            t = j / n
            t2, t3 = t*t, t*t*t
            res.append(tuple(0.5*((2*p1[k]) + (-p0[k]+p2[k])*t + (2*p0[k]-5*p1[k]+4*p2[k]-p3[k])*t2 + (-p0[k]+3*p1[k]-3*p2[k]+p3[k])*t3) for k in range(2)))
    res.append(pts[-1])
    return res

def offset(line, th):
    """Полоса переменной толщины вокруг осевой линии -> контур (left, right)."""
    L, R = [], []
    n = len(line)
    for i in range(n):
        a = line[max(i-1, 0)]; b = line[min(i+1, n-1)]
        dx, dy = b[0]-a[0], b[1]-a[1]
        d = math.hypot(dx, dy) or 1
        nx, ny = -dy/d, dx/d
        t = th(i/(n-1))/2
        L.append((line[i][0]+nx*t, line[i][1]+ny*t))
        R.append((line[i][0]-nx*t, line[i][1]-ny*t))
    return L, R

def smooth(a, b, z):
    t = min(max((z-a)/(b-a), 0), 1)
    return t*t*(3-2*t)

# Волна кровли вдоль остановки (м): подъём по краям, прогиб в середине
def dz(x):
    return 0.18*math.cos(2*math.pi*x/6.0) + 0.10*(x/6.0)

def lift(pts, x):
    d = dz(x)
    return [(y, z + d*smooth(1.6, 2.6, z)) for (y, z) in pts]

# Осевая линия рядового ребра (y – глубина от края платформы, z – высота)
RIB_C = catmull([(1.70, 0.0), (1.67, 0.8), (1.70, 1.75), (1.58, 2.55), (1.15, 2.90), (0.45, 2.86), (-0.12, 2.70)])
RIB_T = lambda t: 0.24 - 0.06*t - 0.06*smooth(0.8, 1, t)
# Передняя стойка торцевых рам (D-образная рама, как в эскизе)
LEG_C = catmull([(0.40, 2.83), (0.17, 2.25), (0.10, 1.30), (0.13, 0.45), (0.10, 0.0)])
LEG_T = lambda t: 0.16 + 0.04*t

def rib_outline(x, end=False):
    c = lift(RIB_C, x)
    L, R = offset(c, RIB_T)
    polys = [L + R[::-1]]
    if end:
        lc = lift(LEG_C, x)
        l2, r2 = offset(lc, LEG_T)
        polys.append(l2 + r2[::-1])
    return polys, c, L, R

def roof_shell(x, th=0.10):
    """Оболочка кровли: от свеса до задней стойки (до z≈2.2), по наружной кромке ребра."""
    c = lift(RIB_C, x)
    L, R = offset(c, RIB_T)
    outer = [p for p in R if p[1] >= 2.15 or p[0] < 1.2]  # R – наружная сторона
    # внутренняя поверхность оболочки
    inner = []
    n = len(outer)
    for i in range(n):
        a = outer[max(i-1, 0)]; b = outer[min(i+1, n-1)]
        dx, dy = b[0]-a[0], b[1]-a[1]; d = math.hypot(dx, dy) or 1
        nx, ny = -dy/d, dx/d
        inner.append((outer[i][0]+nx*th, outer[i][1]+ny*th))
    return outer, inner

class View:
    def __init__(s, ox, oy, k): s.ox, s.oy, s.k = ox, oy, k
    def p(s, u, v): return (s.ox + u*s.k, s.oy - v*s.k)
    def path(s, pts, close=True, **a):
        d = "M" + " L".join(f"{f(s.p(*q)[0])},{f(s.p(*q)[1])}" for q in pts) + (" Z" if close else "")
        add(f'<path d="{d}" {attrs(a)}/>')
    def rect(s, u0, v0, u1, v1, **a):
        xa, ya = s.p(u0, v0); xb, yb = s.p(u1, v1)
        x0, x1, y0, y1 = min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb)
        add(f'<rect x="{f(x0)}" y="{f(y0)}" width="{f(x1-x0)}" height="{f(y1-y0)}" {attrs(a)}/>')
    def line(s, u0, v0, u1, v1, **a):
        x0, y0 = s.p(u0, v0); x1, y1 = s.p(u1, v1)
        add(f'<line x1="{f(x0)}" y1="{f(y0)}" x2="{f(x1)}" y2="{f(y1)}" {attrs(a)}/>')
    def circle(s, u, v, r, **a):
        x, y = s.p(u, v)
        add(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r*s.k)}" {attrs(a)}/>')
    def text(s, u, v, t, **a):
        x, y = s.p(u, v); text(x, y, t, **a)

class FlipView(View):
    def p(s, u, v): return (s.ox + u*s.k, s.oy + v*s.k)

def attrs(a):
    out = []
    for k, v in a.items():
        k = k.replace('_', '-')
        out.append(f'{k}="{v}"')
    return " ".join(out)

def text(x, y, t, size=2.5, anchor="start", weight=400, family="Inter", fill="#2b2622", **a):
    extra = attrs(a)
    add(f'<text x="{f(x)}" y="{f(y)}" font-size="{size}" font-family="{family}" font-weight="{weight}" text-anchor="{anchor}" fill="{fill}" {extra}>{t}</text>')

INK = "#2b2622"
CUT = 0.45; VIS = 0.25; THIN = 0.13; DIM = 0.12
WOOD = "url(#wood)"; WOODF = "#dcae78"; ROOF = "#8f979c"; GLASS = "#d7e8ee"; STEEL = "#4a4f54"
CONC = "url(#conc)"; EARTH = "url(#earth)"

def dim_h(x0, x1, y, label, ext_from=None, size=2.0, tick=1.2):
    """Горизонтальный размер (координаты листа, мм)."""
    add(f'<line x1="{f(x0-1.5)}" y1="{f(y)}" x2="{f(x1+1.5)}" y2="{f(y)}" stroke="{INK}" stroke-width="{DIM}"/>')
    for x in (x0, x1):
        add(f'<line x1="{f(x-tick/2)}" y1="{f(y+tick/2)}" x2="{f(x+tick/2)}" y2="{f(y-tick/2)}" stroke="{INK}" stroke-width="0.3"/>')
        if ext_from is not None:
            add(f'<line x1="{f(x)}" y1="{f(ext_from)}" x2="{f(x)}" y2="{f(y + (1.5 if y > ext_from else -1.5))}" stroke="{INK}" stroke-width="{DIM}"/>')
    text((x0+x1)/2, y-0.8, label, size=size, anchor="middle")

def dim_v(y0, y1, x, label, ext_from=None, size=2.0, tick=1.2):
    add(f'<line x1="{f(x)}" y1="{f(min(y0,y1)-1.5)}" x2="{f(x)}" y2="{f(max(y0,y1)+1.5)}" stroke="{INK}" stroke-width="{DIM}"/>')
    for y in (y0, y1):
        add(f'<line x1="{f(x-tick/2)}" y1="{f(y+tick/2)}" x2="{f(x+tick/2)}" y2="{f(y-tick/2)}" stroke="{INK}" stroke-width="0.3"/>')
        if ext_from is not None:
            add(f'<line x1="{f(ext_from)}" y1="{f(y)}" x2="{f(x + (1.5 if x > ext_from else -1.5))}" y2="{f(y)}" stroke="{INK}" stroke-width="{DIM}"/>')
    cx, cy = x-0.8, (y0+y1)/2
    add(f'<text x="{f(cx)}" y="{f(cy)}" font-size="{size}" font-family="Inter" text-anchor="middle" fill="{INK}" transform="rotate(-90 {f(cx)} {f(cy)})">{label}</text>')

def level(x, y, label, side="left"):
    """Отметка уровня ▽ (координаты листа)."""
    s = -1 if side == "left" else 1
    add(f'<path d="M{f(x)},{f(y)} l{f(-1.1)},{f(-1.6)} h2.2 Z" fill="none" stroke="{INK}" stroke-width="0.18"/>')
    add(f'<line x1="{f(x)}" y1="{f(y-1.6)}" x2="{f(x+s*11)}" y2="{f(y-1.6)}" stroke="{INK}" stroke-width="{DIM}"/>')
    text(x + s*(1.6 if s > 0 else 1.6), y-2.2, label, size=1.9, anchor="start" if s > 0 else "end")

def title(x, y, name, scale, w=None):
    text(x, y, name, size=4.2, family="DejaVu Serif", weight=400, letter_spacing="0.15")
    text(x, y+4.2, scale, size=2.4, fill="#7a6e63")
    if w: add(f'<line x1="{f(x)}" y1="{f(y+1.2)}" x2="{f(x+w)}" y2="{f(y+1.2)}" stroke="{INK}" stroke-width="0.2"/>')

def person(v, u, base, h=1.75, fill="#3d3a37", flip=False):
    """Силуэт стоящего человека в ортогональной проекции."""
    k = h/1.75
    pts = [(-0.12,0),(-0.10,0.85),(-0.20,0.88),(-0.22,1.40),(-0.18,1.48),(-0.08,1.50),(-0.08,1.56),
           (0.08,1.56),(0.08,1.50),(0.18,1.48),(0.22,1.40),(0.20,0.88),(0.10,0.85),(0.12,0),(0.02,0),(0,0.8),(-0.02,0)]
    v.path([(u + p[0]*k, base + p[1]*k) for p in pts], fill=fill, stroke="none")
    v.circle(u, base + 1.64*k, 0.1*k, fill=fill)

def sitter(v, u, seat, fill="#3d3a37", facing=1):
    s = facing
    pts = [(0,0),(0.35*s,0),(0.38*s,-0.45),(0.48*s,-0.45),(0.47*s,0.08),(0.05*s,0.12),(0.0,0.62),(-0.12*s,0.62),(-0.16*s,0.05)]
    v.path([(u+p[0], seat+p[1]) for p in pts], fill=fill, stroke="none")
    v.circle(u-0.04*s, seat+0.74, 0.1, fill=fill)

def tree_elev(v, u, base, h=6, r=1.8, op=0.35):
    v.line(u, base, u, base+h*0.55, stroke="#7d6b58", stroke_width=0.35)
    add(f'<g opacity="{op}">')
    for (du, dv, rr) in [(0,h-r,r),(-r*0.6,h-r*1.4,r*0.7),(r*0.6,h-r*1.3,r*0.75),(0,h-r*1.7,r*0.6)]:
        v.circle(u+du, base+dv, rr, fill="#a9b893", stroke="#7f8f6c", stroke_width=0.15)
    add('</g>')

# ------------------------------------------------------------------ document
W, H = 420, 297
sketch_b64 = base64.b64encode(open("sketch.png", "rb").read()).decode()

add(f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">
<defs>
 <pattern id="wood" patternUnits="userSpaceOnUse" width="3" height="1.2">
  <rect width="3" height="1.2" fill="{WOODF}"/>
  <path d="M0,0.4 C1,0.25 2,0.55 3,0.4" stroke="#b9854e" stroke-width="0.12" fill="none"/>
 </pattern>
 <pattern id="woodcut" patternUnits="userSpaceOnUse" width="1.2" height="1.2" patternTransform="rotate(45)">
  <rect width="1.2" height="1.2" fill="{WOODF}"/><line x1="0" y1="0" x2="0" y2="1.2" stroke="#8a5a2b" stroke-width="0.15"/>
 </pattern>
 <pattern id="conc" patternUnits="userSpaceOnUse" width="2.4" height="2.4">
  <rect width="2.4" height="2.4" fill="#e4e0da"/><circle cx="0.6" cy="0.7" r="0.18" fill="#8c867e"/><circle cx="1.7" cy="1.6" r="0.12" fill="#8c867e"/>
  <path d="M1.5,0.3 l0.35,0.2 l-0.3,0.15z" fill="none" stroke="#8c867e" stroke-width="0.08"/>
 </pattern>
 <pattern id="earth" patternUnits="userSpaceOnUse" width="3" height="3" patternTransform="rotate(45)">
  <line x1="0" y1="0" x2="0" y2="3" stroke="#6e655b" stroke-width="0.12"/>
 </pattern>
 <pattern id="gravel" patternUnits="userSpaceOnUse" width="2" height="2">
  <rect width="2" height="2" fill="#efebe5"/><circle cx="0.5" cy="0.5" r="0.3" fill="none" stroke="#8c867e" stroke-width="0.08"/><circle cx="1.5" cy="1.3" r="0.25" fill="none" stroke="#8c867e" stroke-width="0.08"/>
 </pattern>
 <pattern id="tiles" patternUnits="userSpaceOnUse" width="6" height="3">
  <rect width="6" height="3" fill="#ebe6df"/><path d="M0,0 H6 M0,1.5 H6 M0,0 V1.5 M3,1.5 V3" stroke="#cfc7bc" stroke-width="0.1"/>
 </pattern>
 <pattern id="tiles200" patternUnits="userSpaceOnUse" width="1.5" height="0.75">
  <rect width="1.5" height="0.75" fill="#ebe6df"/><path d="M0,0 H1.5 M0,0 V0.375 M0.75,0.375 V0.75 M0,0.375 H1.5" stroke="#d6cfc5" stroke-width="0.05"/>
 </pattern>
 <pattern id="grass" patternUnits="userSpaceOnUse" width="2.2" height="2.2">
  <rect width="2.2" height="2.2" fill="#dfe5d2"/><path d="M0.4,1.2 l0.15,-0.35 M0.6,1.2 l-0.05,-0.4 M1.5,2 l0.12,-0.3 M1.7,2 l-0.06,-0.32" stroke="#93a37c" stroke-width="0.07"/>
 </pattern>
 <pattern id="tactile" patternUnits="userSpaceOnUse" width="1" height="1">
  <rect width="1" height="1" fill="#f0d98a"/><circle cx="0.5" cy="0.5" r="0.22" fill="#c9a640"/>
 </pattern>
 <pattern id="seam" patternUnits="userSpaceOnUse" width="1.6" height="4">
  <rect width="1.6" height="4" fill="{ROOF}"/><line x1="0.8" y1="0" x2="0.8" y2="4" stroke="#6d757a" stroke-width="0.12"/>
 </pattern>
 <filter id="paper"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="3"/><feColorMatrix values="0 0 0 0 0.45  0 0 0 0 0.40  0 0 0 0 0.33  0 0 0 0.05 0"/></filter>
 <clipPath id="skclip"><rect x="326" y="14" width="86" height="53" rx="0"/></clipPath>
</defs>
<rect width="{W}" height="{H}" fill="#faf7f1"/>

<rect x="20" y="5" width="395" height="287" fill="none" stroke="{INK}" stroke-width="0.5"/>
''')

# ================================================================== ЗАГОЛОВОК
text(26, 24, "ОСТАНОВКА", size=13, family="DejaVu Serif", letter_spacing="1.2")
text(26.5, 32, "павильон «Волна» · остановочный пункт общественного транспорта", size=3.0, family="DejaVu Serif", font_style="italic", fill="#6b5f54")
add(f'<line x1="26.5" y1="35.5" x2="150" y2="35.5" stroke="{INK}" stroke-width="0.25"/>')
desc = ["Клаузура. Навес образован пятью гнутоклеёными деревянными",
        "рёбрами переменного сечения; волнообразная кровля повторяет",
        "движение потока, торцевые D-образные рамы придают жёсткость.",
        "Задняя стенка — закалённое стекло, скамья вдоль всей стены."]
for i, l in enumerate(desc):
    text(26.5, 40.5 + i*3.6, l, size=2.45, fill="#4a423b")

# ================================================================== ГЕНПЛАН 1:200
gx0, gy0 = 26, 60
title(gx0, gy0+3, "ГЕНЕРАЛЬНЫЙ ПЛАН", "М 1:200", 62)
gv = View(gx0 + 12*5 + 4, gy0 + 7 + 7*5 + 4, 5)   # мир x∈[-12.8,15], y∈[-9,7]
U0, U1, V0, V1 = -12.8, 13.4, -8.6, 7.0
add(f'<clipPath id="gp"><rect x="{f(gv.p(U0,V1)[0])}" y="{f(gv.p(U0,V1)[1])}" width="{f((U1-U0)*5)}" height="{f((V1-V0)*5)}"/></clipPath><g clip-path="url(#gp)">')
gv.rect(U0, V0, U1, V1, fill="url(#grass)")
gv.rect(U0, -8.6, U1, -0.6, fill="#c9c6c1")                   # проезжая часть
gv.rect(U0, -9.6, U1, -8.0, fill="url(#tiles200)", stroke=INK, stroke_width=0.18)  # противоположный тротуар
gv.rect(U0, -0.6, U1, 3.0, fill="url(#tiles200)")              # тротуар/платформа
gv.line(U0, -0.6, U1, -0.6, stroke=INK, stroke_width=0.35)
gv.line(U0, 3.0, U1, 3.0, stroke=INK, stroke_width=0.2)
gv.line(U0, -8.0, U1, -8.0, stroke=INK, stroke_width=0.35)
gv.line(U0, -4.3, U1, -4.3, stroke="#ffffff", stroke_width=0.35, stroke_dasharray="3 2")
# разметка 1.17 – жёлтая зигзаг-линия зоны остановки
zz = [(-9 + i*1.0, -1.0 if i % 2 else -1.9) for i in range(0, 21)]
gv.path(zz, close=False, fill="none", stroke="#e3b81c", stroke_width=0.3)
# пешеходный переход
for i in range(5):
    gv.rect(9.6 + i*0.8, -8.0, 10.0 + i*0.8, -0.6, fill="#ffffff")
# тактильная полоса вдоль бордюра
gv.rect(-9, -0.6, 9, -0.1, fill="#f0d98a")
# автобус
gv.rect(-8.0, -3.75, 4.0, -1.25, fill="#ffffff", stroke=INK, stroke_width=0.2, rx=0.4)
gv.rect(-7.6, -3.45, 3.5, -1.55, fill="none", stroke="#9a948d", stroke_width=0.12)
gv.text(-2, -2.75, "автобус", size=1.8, anchor="middle", fill="#6b645d")
# пешеходная дорожка в парк
gv.path([(8.2, 3.0), (8.6, 4.8), (10.5, 6.2), (13, 7.2), (15.5, 7.2), (12.8, 5.4), (10.2, 4.0), (9.8, 3.0)], fill="url(#tiles200)", stroke=INK, stroke_width=0.15)
# деревья
for (u, v, r) in [(-11, 5.2, 1.7), (-7.5, 5.8, 2.0), (-4, 5.0, 1.6), (-0.8, 5.6, 1.9), (3.2, 5.3, 1.7), (6.3, 5.9, 1.8), (12.6, 3.6, 1.3), (-12, -9.2, 1.4), (4, -9.3, 1.3)]:
    gv.circle(u+0.25, v-0.25, r, fill="#9aa68a", opacity=0.35)
    gv.circle(u, v, r, fill="#b7c39f", stroke="#6f7f5c", stroke_width=0.18)
    gv.circle(u, v, 0.15, fill="#6f7f5c")
# кусты за павильоном
for (u, v) in [(-0.6, 3.6), (0.4, 3.9), (1.5, 3.55), (4.6, 3.7), (5.6, 3.95), (6.6, 3.6)]:
    gv.circle(u, v, 0.6, fill="#c3ceab", stroke="#7f8f6c", stroke_width=0.12)
# павильон — кровля в плане
roof_pl = [(0, -0.22), (6.0, -0.22), (6.0, 1.92), (0, 1.92)]
gv.path(roof_pl, fill="#cfa06a", stroke=INK, stroke_width=0.4)
for xr in (0.3, 1.65, 3.0, 4.35, 5.7):
    gv.line(xr, -0.22, xr, 1.92, stroke="#8a5a2b", stroke_width=0.15)
# знак остановки, урна
gv.circle(-1.0, -0.3, 0.18, fill=INK)
gv.circle(6.6, 1.4, 0.25, fill="none", stroke=INK, stroke_width=0.15)
add('</g>')
gv.rect(U0, V0, U1, V1, fill="none", stroke=INK, stroke_width=0.25)
# подписи генплана
def gl(u, v, t, **a): gv.text(u, v, t, size=1.9, fill="#3d3732", **a)
gl(-12.3, -6.5, "проезжая часть")
gl(9.6, -0.15, "тротуар", anchor="end")
gl(-12.3, 6.0, "газон, сквер", )
gl(9.3, -7.6, "пешеходный переход", anchor="end")
# выноска на павильон
gv.line(3.0, 0.85, 7.6, 2.4, stroke=INK, stroke_width=0.12)
gl(7.7, 2.15, "остановочный павильон")
gl(-1.2, 0.9, "знак «А»", anchor="end")
gv.line(-1.0, -0.3, -1.1, 0.6, stroke=INK, stroke_width=0.1)
# север
nx, ny = gv.p(11.6, 5.6)
add(f'<g transform="translate({f(nx)},{f(ny)})"><circle r="3.2" fill="#faf7f1" stroke="{INK}" stroke-width="0.2"/><path d="M0,-2.8 L1,1.6 L0,0.8 L-1,1.6 Z" fill="{INK}"/><text y="-3.8" font-size="2" text-anchor="middle" font-family="Inter" fill="{INK}">С</text></g>')

# ================================================================== ФАСАД 1:50
k = 20
fv = View(192, 92, k)      # x –> вправо, z –> вверх, ±0.000 на y=92
title(186, 17, "ФАСАД", "М 1:50", 30)
# фон: деревья
add('<g opacity="0.55">')
tree_elev(fv, -0.4, 0, 4.0, 1.0, 0.5); tree_elev(fv, 3.6, 0, 4.3, 1.2, 0.45); tree_elev(fv, 6.2, 0, 3.9, 0.9, 0.5)
add('</g>')
# земля
fv.rect(-1.0, -0.18, 6.6, 0, fill="url(#tiles)", stroke="none")
fv.line(-1.0, 0, 6.6, 0, stroke=INK, stroke_width=CUT)
fv.line(-1.0, -0.18, 6.6, -0.18, stroke=INK, stroke_width=THIN)
# задняя стенка – стекло между рёбрами
ribs_x = [0.3, 1.65, 3.0, 4.35, 5.7]
for i in range(4):
    a, b = ribs_x[i]+0.09, ribs_x[i+1]-0.09
    top = 2.30 + dz((a+b)/2)*0.35
    if i == 3:   # информационный стенд
        fv.rect(a, 0.1, b, top, fill=GLASS, stroke=INK, stroke_width=THIN)
        fv.rect(a+0.12, 0.95, b-0.12, 2.0, fill="#f4f1ea", stroke=INK, stroke_width=0.18)
        fv.text((a+b)/2, 1.86, "РАСПИСАНИЕ", size=1.4, anchor="middle", weight=600)
        for j in range(9):
            fv.line(a+0.22, 1.72-j*0.08, a+0.22+(0.7 if j % 3 else 0.9), 1.72-j*0.08, stroke="#8b847c", stroke_width=0.12)
        fv.rect(a+0.95+0.15, 1.0, b-0.22, 1.72, fill="#cfdccf", stroke="#8b847c", stroke_width=0.1)
        fv.text(a+1.08+0.08, 1.33, "схема", size=1.2, fill="#5d6a5d")
    else:
        fv.rect(a, 0.1, b, top, fill=GLASS, stroke=INK, stroke_width=THIN)
    # блики стекла
    fv.line(a+0.25, 0.7, a+0.75, 1.6, stroke="#ffffff", stroke_width=0.5)
    fv.line(a+0.45, 0.7, a+0.85, 1.4, stroke="#ffffff", stroke_width=0.25)
    for zz_ in (0.25, top-0.15):  # точечные крепления
        fv.circle(a+0.08, zz_, 0.025, fill=STEEL); fv.circle(b-0.08, zz_, 0.025, fill=STEEL)
# скамья
fv.rect(1.85, 0.40, 5.55, 0.47, fill=WOOD, stroke=INK, stroke_width=VIS)
fv.rect(1.85, 0.55, 5.55, 0.62, fill=WOOD, stroke=INK, stroke_width=THIN)
fv.rect(1.85, 0.72, 5.55, 0.79, fill=WOOD, stroke=INK, stroke_width=THIN)
for xb in (2.0, 3.7, 5.4):
    fv.rect(xb-0.03, 0, xb+0.03, 0.40, fill=STEEL)
# кашпо с растениями
fv.rect(0.42, 0, 1.55, 0.45, fill=WOOD, stroke=INK, stroke_width=VIS)
for j, xp in enumerate([0.5, 0.65, 0.8, 0.95, 1.1, 1.25, 1.4]):
    h = 0.35 + 0.25*math.sin(j*1.7)**2
    fv.path([(xp, 0.45), (xp-0.12, 0.45+h), (xp+0.02, 0.45+h*0.6), (xp+0.14, 0.45+h*0.9), (xp+0.08, 0.45)], fill="#93a67a", stroke="#5e6e4b", stroke_width=0.1)
# рёбра (в фасаде видны торцом – вертикальные полосы)
def rib_under(x):
    c = lift(RIB_C, x); L, R = offset(c, RIB_T)
    return min(p[1] for p in L if p[0] < 1.3)
for i, x in enumerate(ribs_x):
    w = 0.10 if i in (0, 4) else 0.08
    top = rib_under(x)
    fv.rect(x-w, 0, x+w, top+0.05, fill=WOOD, stroke=INK, stroke_width=VIS)
# передние стойки торцевых рам (D-рамы) – видны в фасаде целиком по ширине
for x, s in ((0.3, -1), (5.7, 1)):
    zlb = rib_under(x)
    pts = [(x - 0.10, 0), (x + 0.10, 0), (x+0.10, zlb), (x-0.10, zlb)]
    # изгиб стойки: на фасаде показываем силуэт с выносом наружу
    leg = [(x+s*0.0-0.11, 0), (x+0.11, 0), (x+0.11+s*0.06, 0.9), (x+0.11+s*0.12, 1.9), (x+0.11+s*0.05, zlb+0.05),
           (x-0.11+s*0.05, zlb+0.05), (x-0.11+s*0.12, 1.9), (x-0.11+s*0.06, 0.9)]
    fv.path(leg, fill=WOOD, stroke=INK, stroke_width=CUT*0.8)
# кровля – подшивка, лобовая кромка, верхняя плоскость
xs = [i/60*6 for i in range(61)]
def z_lip_top(x):
    c = lift(RIB_C, x); L, R = offset(c, RIB_T); return R[-1][1] + 0.02
def z_lip_bot(x):
    c = lift(RIB_C, x); L, R = offset(c, RIB_T); return L[-1][1] - 0.02
def z_top(x):
    c = lift(RIB_C, x); L, R = offset(c, RIB_T); return max(p[1] for p in R)
def z_soffit(x):
    c = lift(RIB_C, x); L, R = offset(c, RIB_T); return max(p[1] for p in L if p[0] < 1.4)
roof_up = [(x, z_top(x)) for x in xs]
lip_t = [(x, z_lip_top(x)) for x in xs]
lip_b = [(x, z_lip_bot(x)) for x in xs]
soff = [(x, z_soffit(x)) for x in xs]
fv.path(soff + lip_b[::-1], fill="#e9c695", stroke=INK, stroke_width=THIN)           # подшивка из рейки
for j in range(1, 4):
    t = j/4
    fv.path([(x, z_lip_bot(x)+(z_soffit(x)-z_lip_bot(x))*t) for x in xs], close=False, fill="none", stroke="#b9854e", stroke_width=0.12)
fv.path(roof_up + lip_t[::-1], fill="url(#seam)", stroke=INK, stroke_width=VIS)        # фальцевая кровля
fv.path(lip_t + lip_b[::-1], fill=WOOD, stroke=INK, stroke_width=CUT)                 # лобовая доска
fv.path(roof_up, close=False, fill="none", stroke=INK, stroke_width=CUT)
# люди
sitter(fv, 2.75, 0.47, facing=1)
person(fv, 4.95, 0, 1.70)
# знак остановки
fv.line(-0.55, 0, -0.55, 2.6, stroke=STEEL, stroke_width=0.5)
fv.rect(-0.83, 2.6, -0.27, 3.16, fill="#ffffff", stroke=STEEL, stroke_width=0.3)
fv.text(-0.55, 2.8, "A", size=4.5, anchor="middle", weight=700, fill="#2f6fae")
# размеры
yb = fv.p(0, -0.18)[1]
for i in range(4):
    dim_h(fv.p(ribs_x[i], 0)[0], fv.p(ribs_x[i+1], 0)[0], yb + 5, "1350", ext_from=yb+1, size=1.9)
dim_h(fv.p(0, 0)[0], fv.p(0.3, 0)[0], yb+5, "", ext_from=yb+1)
dim_h(fv.p(5.7, 0)[0], fv.p(6, 0)[0], yb+5, "", ext_from=yb+1)
text(fv.p(0.15, 0)[0], yb+3.4, "300", size=1.6, anchor="middle"); text(fv.p(5.85, 0)[0], yb+3.4, "300", size=1.6, anchor="middle")
dim_h(fv.p(0, 0)[0], fv.p(6, 0)[0], yb + 10, "6000", ext_from=yb+1, size=2.1)
# оси
for i, x in enumerate(ribs_x):
    px, py = fv.p(x, 0)
    add(f'<line x1="{f(px)}" y1="{f(yb+10)}" x2="{f(px)}" y2="{f(yb+13)}" stroke="{INK}" stroke-width="{DIM}"/>')
    add(f'<circle cx="{f(px)}" cy="{f(yb+15.2)}" r="2.2" fill="#faf7f1" stroke="{INK}" stroke-width="0.2"/>')
    text(px, yb+16, str(i+1), size=2.2, anchor="middle")
# отметки
lx = fv.p(-1.05, 0)[0]
level(lx, fv.p(0, 0)[1], "±0.000", "left")
level(lx, fv.p(0, 0.47)[1], "+0.470", "left")
level(lx, fv.p(0, z_lip_bot(6))[1], f"+{z_lip_bot(0):.3f}", "left")
level(lx, fv.p(0, z_top(0))[1], f"+{z_top(0):.3f}", "left")
level(fv.p(6.25, 0)[0], fv.p(0, z_top(6))[1], f"+{z_top(6):.3f}", "right")

# ================================================================== ЭСКИЗ (перспектива автора)
add(f'<rect x="326" y="14" width="86" height="53" fill="#ffffff" stroke="{INK}" stroke-width="0.2"/>')
add(f'<image x="326" y="14" width="86" height="53" preserveAspectRatio="xMidYMid slice" clip-path="url(#skclip)" style="mix-blend-mode:multiply" xlink:href="data:image/png;base64,{sketch_b64}"/>')
text(326, 74, "ЭСКИЗ-ИДЕЯ", size=3.2, family="DejaVu Serif", letter_spacing="0.15")
text(326, 78, "перспектива, карандаш (клаузура)", size=2.2, fill="#7a6e63")
# формообразование: эскизные пиктограммы
fx, fy = 362, 88
for j in range(3):
    ox = fx + j*16
    add(f'<path d="M{ox},{fy+3} C{ox+3},{fy-2 - j} {ox+7},{fy+4+j} {ox+12},{fy-1}" fill="none" stroke="{INK}" stroke-width="{0.25+0.12*j}"/>')
    if j < 2: text(ox+13.5, fy+1.8, "→", size=2.4)
text(fx, fy+6.5, "волна → ребро → павильон", size=1.9, fill="#7a6e63")

# ================================================================== ВИД СБОКУ 1:50
sv = View(194+3*20 - 0.2*20, 196, k)    # y (глубина) –> вправо, дорога слева
sv = View(214, 196, k)
title(186, 116, "ВИД СБОКУ", "М 1:50", 40)
add('<g opacity="0.35">'); tree_elev(sv, 3.2, 0, 4.0, 0.9, 0.5); add('</g>')
sv.rect(-1.1, -0.18, 3.0, 0, fill="url(#tiles)")
sv.rect(-1.15, -0.18, -0.6, -0.02, fill="#c9c6c1")
sv.line(-1.15, -0.18, -0.6, -0.18, stroke=INK, stroke_width=THIN)
sv.path([(-0.6, -0.18), (-0.6, 0), (3.0, 0)], close=False, fill="none", stroke=INK, stroke_width=CUT)
# дальняя торцевая рама (выше по волне) – тонкой линией
far = rib_outline(5.7, True)[0]
for poly in far: sv.path(poly, fill="#efe3d2", stroke=INK, stroke_width=THIN)
# боковое стекло внутри дальней рамы
sv.path([(0.32, 0.1), (1.55, 0.1), (1.55, 2.2), (0.5, 2.35), (0.28, 1.5)], fill=GLASS, stroke=INK, stroke_width=THIN, opacity=0.9)
sv.line(0.6, 0.6, 1.1, 1.6, stroke="#ffffff", stroke_width=0.5)
# скамья (торец), кашпо
sv.rect(1.12, 0.40, 1.60, 0.47, fill=WOOD, stroke=INK, stroke_width=VIS)
sv.path([(1.58, 0.50), (1.64, 0.50), (1.70, 0.86), (1.64, 0.86)], fill=WOOD, stroke=INK, stroke_width=VIS)
sv.path([(1.2, 0), (1.25, 0.40), (1.5, 0.40), (1.55, 0.0)], close=False, fill="none", stroke=STEEL, stroke_width=0.6)
sv.rect(1.10, 0, 1.62, 0.45, fill=WOOD, stroke=INK, stroke_width=VIS)
for j in range(5):
    sv.path([(1.15+j*0.1, 0.45), (1.1+j*0.1, 0.8+0.1*(j % 2)), (1.2+j*0.1, 0.45)], fill="#93a67a", stroke="#5e6e4b", stroke_width=0.1)
# ближняя торцевая рама
near, cN, Ln, Rn = rib_outline(0.3, True)
for poly in near: sv.path(poly, fill=WOOD, stroke=INK, stroke_width=CUT)
# ламели клеёного бруса – линии вдоль ребра
for t in (0.33, 0.66):
    sv.path([(Ln[i][0]*(1-t)+Rn[i][0]*t, Ln[i][1]*(1-t)+Rn[i][1]*t) for i in range(len(Ln))], close=False, fill="none", stroke="#a4703c", stroke_width=0.1)
# торец кровли (свес 300 мм перед рамой)
o, inn = roof_shell(0.0)
sv.path(o + inn[::-1], fill="url(#seam)", stroke=INK, stroke_width=VIS)
# стальные опорные башмаки
for yb_ in (1.70, 0.10):
    sv.rect(yb_-0.16, 0, yb_+0.16, 0.08, fill=STEEL)
person(sv, -0.25, 0, 1.75)
# размеры вида сбоку
ys = sv.p(0, -0.18)[1]
ymin = min(p[0] for p in o); ymax = max(max(p[0] for p in poly) for poly in near)
dim_h(sv.p(0.10, 0)[0], sv.p(1.70, 0)[0], ys+5, "1600", ext_from=ys+1, size=1.9)
dim_h(sv.p(ymin, 0)[0], sv.p(ymax, 0)[0], ys+10, f"{round((ymax-ymin)*1000/10)*10}", ext_from=ys+1, size=2.0)
for x_, n_ in ((0.10, "А"), (1.70, "Б")):
    px = sv.p(x_, 0)[0]
    add(f'<circle cx="{f(px)}" cy="{f(ys+15.2)}" r="2.2" fill="#faf7f1" stroke="{INK}" stroke-width="0.2"/>')
    text(px, ys+16, n_, size=2.1, anchor="middle")
ztop0 = max(p[1] for p in o)
dim_v(sv.p(0, 0)[1], sv.p(0, ztop0)[1], sv.p(2.75, 0)[0], f"{round(ztop0*1000/10)*10}", ext_from=sv.p(2.0, 0)[0], size=1.9)

# ================================================================== РАЗРЕЗ 1-1 1:50
xv = View(305, 196, k)
XS = 2.33
title(285, 116, "РАЗРЕЗ 1–1", "М 1:50", 46)
# вид за плоскостью разреза: ребро по оси 3 (x=3.0 – сечение проходит в пролёте рядом)
beyond = rib_outline(3.0, False)[0]
for poly in beyond: xv.path(poly, fill="#efe3d2", stroke=INK, stroke_width=THIN)
far2 = rib_outline(5.7, True)[0]
xv.path(far2[1], fill="#f3eadf", stroke=INK, stroke_width=THIN)
# грунт и конструкция покрытия (в разрезе)
xv.rect(-0.9, -0.75, 2.6, -0.32, fill=EARTH)
xv.rect(-0.6, -0.32, 2.6, -0.12, fill="url(#gravel)", stroke=INK, stroke_width=THIN)    # щебень
xv.rect(-0.6, -0.12, 2.6, -0.08, fill="#d8d2c8", stroke=INK, stroke_width=THIN)          # пескоцемент
xv.rect(-0.6, -0.08, 2.6, 0.0, fill="#cbc4ba", stroke=INK, stroke_width=VIS)             # плитка
xv.rect(-0.75, -0.40, -0.6, 0.0, fill=CONC, stroke=INK, stroke_width=VIS)                 # бордюр
xv.rect(-1.3, -0.40, -0.75, -0.18, fill="#bdb9b4", stroke=INK, stroke_width=THIN)         # асфальт
xv.rect(1.45, -0.75, 1.95, -0.08, fill=CONC, stroke=INK, stroke_width=CUT)                # ленточный ростверк
xv.line(-1.3, 0, -0.6, 0, stroke="none")
# стекло (в разрезе)
o3, i3 = roof_shell(XS)
zg = min(p[1] for p in i3 if p[0] > 1.5)
xv.rect(1.68, 0.06, 1.72, 2.22, fill="#9fc3d0", stroke=INK, stroke_width=0.2)
xv.rect(1.63, 0.0, 1.77, 0.08, fill=STEEL)    # опорный профиль
# скамья (в разрезе)
xv.rect(1.12, 0.40, 1.60, 0.47, fill="url(#woodcut)", stroke=INK, stroke_width=CUT)
xv.path([(1.56, 0.50), (1.62, 0.50), (1.67, 0.86), (1.61, 0.86)], fill="url(#woodcut)", stroke=INK, stroke_width=CUT)
xv.path([(1.2, 0), (1.25, 0.40), (1.55, 0.40), (1.58, 0.47), (1.62, 0.9)], close=False, fill="none", stroke=STEEL, stroke_width=0.5)
# кровля (в разрезе): фальцевая сталь + обрешётка + рейка подшивки
xv.path(o3 + i3[::-1], fill="#d4b083", stroke=INK, stroke_width=CUT)
xv.path(o3, close=False, fill="none", stroke=STEEL, stroke_width=0.45)
xv.path(i3, close=False, fill="none", stroke="#8a5a2b", stroke_width=0.3)
# люди
sitter(xv, 1.32, 0.47, facing=-1)
person(xv, 0.45, 0, 1.75, fill="#55504b")
# выноски (номера материалов)
def callout(v, u, w, n, tu, tw):
    a = v.p(u, w); b = v.p(tu, tw)
    add(f'<line x1="{f(a[0])}" y1="{f(a[1])}" x2="{f(b[0])}" y2="{f(b[1])}" stroke="{INK}" stroke-width="0.12"/>')
    add(f'<circle cx="{f(a[0])}" cy="{f(a[1])}" r="0.35" fill="{INK}"/>')
    add(f'<circle cx="{f(b[0])}" cy="{f(b[1])}" r="1.7" fill="#faf7f1" stroke="{INK}" stroke-width="0.2"/>')
    text(b[0], b[1]+0.7, str(n), size=1.9, anchor="middle", weight=600)
callout(xv, 2.0, 2.45, 1, 2.6, 2.1)
callout(xv, 0.9, 3.0 + dz(XS)*0.95 - 0.03, 2, 0.6, 3.45)
callout(xv, 0.3, 2.66 + dz(XS) * 0.7, 3, -0.4, 2.2)
callout(xv, 1.70, 1.6, 4, 2.45, 1.45)
callout(xv, 1.35, 0.44, 5, 2.45, 0.75)
callout(xv, 1.70, -0.4, 6, 2.45, -0.45)
callout(xv, 0.7, -0.04, 7, 0.4, -0.6)
callout(xv, 1.70, 0.04, 8, 2.45, 0.2)
# размеры разреза
dim_v(xv.p(0, 0)[1], xv.p(0, 0.47)[1], xv.p(-1.0, 0)[0], "470", ext_from=xv.p(1.1, 0)[0])
zl = min(p[1] for p in i3 if p[0] < 0.2)
dim_v(xv.p(0, 0.47)[1], xv.p(0, zl)[1], xv.p(-1.0, 0)[0], f"{round((zl-0.47)*100)*10}", ext_from=xv.p(-0.2, 0)[0])
ztop3 = max(p[1] for p in o3)
dim_v(xv.p(0, 0)[1], xv.p(0, ztop3)[1], xv.p(-1.5, 0)[0], f"{round(ztop3*100)*10}", ext_from=xv.p(1.2, 0)[0])
level(xv.p(-0.7, 0)[0]+0.3, xv.p(0, -0.18)[1], "−0.180", "left")

# ================================================================== ПЛАН 1:50
pv = FlipView(56, 215, k)  # x –> вправо, y (к дороге) –> вниз
def P(x, y): return (x, -y)   # y=0 — передний край, растёт вверх на листе (назад)
title(26, 166, "ПЛАН", "М 1:50  (на отм. +1.000)", 44)
pv.rect(-0.9, 0.6, 6.6, -2.15, fill="url(#tiles)")
pv.rect(-0.9, 0.6, 6.6, 0.1, fill="url(#tactile)")
pv.line(-0.9, 0.6, 6.6, 0.6, stroke=INK, stroke_width=CUT)   # бордюр
pv.rect(-0.9, 1.1, 6.6, 0.6, fill="#c9c6c1")
pv.line(-0.9, 1.1, 6.6, 1.1, stroke="#e3b81c", stroke_width=0.3, stroke_dasharray="2 1.2")
pv.text(-0.8, 1.0, "проезжая часть", size=1.7, anchor="start", fill="#5a544e")
pv.text(-0.9, 0.42, "тактильная плитка", size=1.6, fill="#6b5a2a")
# кровля над плоскостью сечения (пунктир)
pv.rect(0, 0.22, 6.0, -1.92, fill="none", stroke=INK, stroke_width=0.18, stroke_dasharray="1.6 0.8")
# стекло задней стены
for i in range(4):
    a, b = ribs_x[i]+0.1, ribs_x[i+1]-0.1
    pv.rect(a, -1.68, b, -1.72, fill="#9fc3d0", stroke=INK, stroke_width=0.15)
# боковое стекло у оси 5
pv.rect(5.66, -0.32, 5.74, -1.58, fill="#9fc3d0", stroke=INK, stroke_width=0.15)
# скамья
pv.rect(1.85, -1.12, 5.55, -1.62, fill=WOOD, stroke=INK, stroke_width=VIS)
for j in range(1, 6): pv.line(1.85, -1.12-j*0.083, 5.55, -1.12-j*0.083, stroke="#a4703c", stroke_width=0.1)
# кашпо
pv.rect(0.42, -1.1, 1.55, -1.62, fill=WOOD, stroke=INK, stroke_width=VIS)
for (u, w) in [(0.65, -1.3), (0.95, -1.42), (1.3, -1.3), (0.8, -1.5), (1.2, -1.5)]:
    pv.circle(u, w, 0.13, fill="#93a67a", stroke="#5e6e4b", stroke_width=0.1)
# рёбра в сечении на +1.000
for i, x in enumerate(ribs_x):
    w = 0.10 if i in (0, 4) else 0.08
    pv.rect(x-w, -1.54, x+w, -1.86, fill="url(#woodcut)", stroke=INK, stroke_width=CUT)
    if i in (0, 4):
        pv.rect(x-w, -0.02, x+w, -0.22, fill="url(#woodcut)", stroke=INK, stroke_width=CUT)
# урна, знак
pv.circle(6.3, -1.2, 0.2, fill="#ffffff", stroke=INK, stroke_width=VIS)
pv.circle(-0.6, 0.0, 0.05, fill=INK); pv.rect(-0.85, 0.06, -0.35, -0.06, fill="none", stroke=INK, stroke_width=0.2)
# секущая 1-1
sx = 2.33
for w0, w1 in ((0.95, 0.65), (-2.05, -2.35)):
    pv.line(sx, w0, sx, w1, stroke=INK, stroke_width=0.6)
for w in (0.95, -2.35):
    a = pv.p(sx, w)
    add(f'<path d="M{f(a[0])},{f(a[1])} h3.2 m-1,-0.6 l1,0.6 l-1,0.6" fill="none" stroke="{INK}" stroke-width="0.3"/>')
    text(a[0]+1.6, a[1]+(-1.0 if w < 0 else 2.6), "1", size=2.4, anchor="middle", weight=600)
# оси и размеры плана
yb = pv.p(0, 1.1)[1]
for i in range(4):
    dim_h(pv.p(ribs_x[i], 0)[0], pv.p(ribs_x[i+1], 0)[0], yb+4.5, "1350", ext_from=yb+0.5, size=1.9)
dim_h(pv.p(0, 0)[0], pv.p(6, 0)[0], yb+9, "6000", ext_from=yb+0.5, size=2.0)
for i, x in enumerate(ribs_x):
    px = pv.p(x, 0)[0]
    add(f'<line x1="{f(px)}" y1="{f(pv.p(0,-2.3)[1])}" x2="{f(px)}" y2="{f(yb+9)}" stroke="{INK}" stroke-width="0.1" stroke-dasharray="4 0.8 0.6 0.8"/>')
    add(f'<circle cx="{f(px)}" cy="{f(yb+13)}" r="2.2" fill="#faf7f1" stroke="{INK}" stroke-width="0.2"/>')
    text(px, yb+13.8, str(i+1), size=2.2, anchor="middle")
xl = pv.p(-0.9, 0)[0]
dim_v(pv.p(0, -0.1)[1], pv.p(0, -1.70)[1], xl-3, "1600", ext_from=pv.p(-0.1, 0)[0], size=1.9)
dim_v(pv.p(0, 0.22)[1], pv.p(0, -1.92)[1], xl-7.5, "2140", ext_from=pv.p(-0.1, 0)[0], size=1.9)
for w, n_ in ((-0.1, "А"), (-1.70, "Б")):
    py = pv.p(0, w)[1]
    add(f'<circle cx="{f(xl-12)}" cy="{f(py)}" r="2.2" fill="#faf7f1" stroke="{INK}" stroke-width="0.2"/>')
    text(xl-12, py+0.8, n_, size=2.1, anchor="middle")
# площадь
pv.text(3.7, -0.75, "навес  S = 12.8 м²", size=1.9, anchor="middle", fill="#5a544e")

# ================================================================== МАТЕРИАЛЫ / ЭКСПЛИКАЦИЯ
mx, my = 196, 224
title(mx, my, "МАТЕРИАЛЫ И КОНСТРУКЦИИ", "экспликация к разрезу 1–1", 90)
mats = [
    ("wood",   "Рёбра-рамы: клеёная древесина лиственницы,", "гнутоклеёный брус 160–200 мм, масло-воск"),
    ("seam",   "Кровля: фальцевая сталь с полимерным", "покрытием, цвет «графит», по обрешётке"),
    ("slats",  "Подшивка: рейка из термодерева 40×20 мм", "с шагом 10 мм по нижней плоскости"),
    ("glass",  "Стекло закалённое триплекс 10 мм", "на точечных креплениях (спайдеры)"),
    ("wood2",  "Скамья: брусок ясеня (термо) на", "стальном каркасе, порошковая окраска"),
    ("conc",   "Ленточный ростверк: монолитный", "бетон В25 по щебёночной подготовке"),
    ("tiles",  "Покрытие платформы: бетонная плитка", "60 мм, тактильная полоса у бордюра"),
    ("steel",  "Опорные башмаки и профили: сталь", "оцинкованная, анкеры в ростверк"),
]
for i, (pat, l1, l2) in enumerate(mats):
    col, row = i // 4, i % 4
    x = mx + col*108; y = my + 10 + row*12.2
    cx, cy = x+5.5, y+2.5
    fills = {"wood": "url(#wood)", "seam": "url(#seam)", "slats": "#e9c695", "glass": GLASS, "wood2": "#c48b55",
             "conc": "url(#conc)", "tiles": "url(#tiles)", "steel": STEEL}
    add(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="5.2" fill="{fills[pat]}" stroke="{INK}" stroke-width="0.25"/>')
    if pat == "glass":
        add(f'<line x1="{f(cx-2.5)}" y1="{f(cy+1.5)}" x2="{f(cx+0.5)}" y2="{f(cy-2.5)}" stroke="#fff" stroke-width="0.7"/>')
    if pat == "slats":
        for j in range(-4, 5):
            add(f'<line x1="{f(cx-4.8)}" y1="{f(cy+j*1.1)}" x2="{f(cx+4.8)}" y2="{f(cy+j*1.1)}" stroke="#a4703c" stroke-width="0.2"/>')
        add(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="5.2" fill="none" stroke="#faf7f1" stroke-width="0.6"/><circle cx="{f(cx)}" cy="{f(cy)}" r="5.5" fill="none" stroke="{INK}" stroke-width="0.25"/>')
    add(f'<circle cx="{f(x+13)}" cy="{f(y+1.2)}" r="1.7" fill="#faf7f1" stroke="{INK}" stroke-width="0.2"/>')
    text(x+13, y+1.9, str(i+1), size=1.9, anchor="middle", weight=600)
    text(x+16, y+1.9, l1, size=2.35)
    text(x+16, y+5.2, l2, size=2.1, fill="#6b5f54")

# ================================================================== МАСШТАБНЫЕ ЛИНЕЙКИ И ТЭП
def scalebar(x, y, k, meters, step, label):
    for i in range(int(meters/step)):
        add(f'<rect x="{f(x+i*step*k)}" y="{f(y)}" width="{f(step*k)}" height="1.2" fill="{INK if i % 2 == 0 else "#faf7f1"}" stroke="{INK}" stroke-width="0.15"/>')
    for i in range(int(meters/step)+1):
        if (i*step) % (1 if step < 1 else step) == 0:
            text(x+i*step*k, y+3.6, f"{i*step:g}", size=1.7, anchor="middle")
    text(x+meters*k+2, y+1.3, "м", size=1.8)
    text(x, y-1.3, label, size=1.9, fill="#6b5f54")
scalebar(26, 156, 5, 10, 2, "М 1:200")
scalebar(100, 156, 20, 3, 0.5, "М 1:50")

tep = [("Длина павильона", "6,00 м"), ("Глубина (по кровле)", "2,14 м"), ("Высота в верхней точке", "3,25 м"),
       ("Площадь под навесом", "12,8 м²"), ("Посадочных мест", "6"), ("Шаг рёбер-рам", "1,35 м")]
text(26, 285.5, "  ·  ".join(f"{a} — {b}" for a, b in tep[:3]), size=2.0, fill="#4a423b")
text(26, 289, "  ·  ".join(f"{a} — {b}" for a, b in tep[3:]), size=2.0, fill="#4a423b")

# штамп
add(f'<rect x="355" y="281" width="60" height="11" fill="none" stroke="{INK}" stroke-width="0.35"/>')
add(f'<line x1="355" y1="286.5" x2="415" y2="286.5" stroke="{INK}" stroke-width="0.15"/><line x1="392" y1="281" x2="392" y2="292" stroke="{INK}" stroke-width="0.15"/>')
text(357, 285, "Клаузура «Остановка»", size=2.1)
text(357, 290.5, "Выполнил(а):", size=2.0, fill="#6b5f54")
text(394, 285, "Лист А3", size=2.0); text(394, 290.5, "М 1:50, 1:200", size=1.9)

add('</svg>')
open("ostanovka_A3.svg", "w", encoding="utf-8").write("\n".join(OUT))
print("ok")
