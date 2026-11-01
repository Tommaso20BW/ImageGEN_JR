"""HEAD TO HEAD: bilancio, ultimi 5 precedenti e forma delle due squadre.

Dati da Transfermarkt (vedi h2h_data.py). Stessa pagina per tutte le maglie e le
coppe UEFA: cambiano sfondo, colori di testi/loghi e logo JR (THEMES).
"""
from graphics.common import DESIGN_H, DESIGN_W, asset_dir, data_uri, esc, font_face, render_html, team_logo

KITS = ('home', 'away', 'third', 'ucl', 'uel', 'conference')
_CANVA = lambda name: data_uri(asset_dir() / 'canva' / name)

# Sfondo, logo JR, colori. acc = colore/texture di "head", 112, etichette e righe.
# veil = colore di fondo in cui sfumano al centro le linee degli sfondi UEFA.
THEMES = {
    'home': dict(bg='bg_home.jpg', jr='jr_black_overlay.png', ink='#111', muted='#555', logo='#111',
                 acc_file='starting_xi_home_number_01.png'),
    'away': dict(bg='bg_away.jpg', jr='jr_white_overlay.png', ink='#fff', muted='rgba(255,255,255,.75)', logo='#fff',
                 acc='#fff', fx='starting_xi_away_fx.png',
                 tint='radial-gradient(ellipse 70% 60% at 50% 45%,rgba(110,20,50,.32),rgba(80,10,35,0))'),
    'third': dict(bg='bg_third.jpg', jr='jr_gold_overlay.png', ink='#fff', muted='rgba(255,255,255,.65)', logo='#d3af49',
                  acc_file='starting_xi_third_number_01.png'),
    'ucl': dict(bg='bg_ucl.jpg', jr='jr_white_overlay.png', ink='#fff', muted='rgba(220,235,255,.75)', logo='#fff',
                acc='linear-gradient(100deg,#28d7c8,#6ec8ff)', veil='2,8,70'),
    'uel': dict(bg='bg_uel.jpg', jr='jr_black_overlay.png', ink='#000', muted='rgba(0,0,0,.65)', logo='#000',
                acc='#000', veil='252,109,6', veil_size='80% 70%', veil_jr=True),
    'conference': dict(bg='bg_conference.jpg', jr='jr_black_overlay.png', ink='#000', muted='rgba(0,0,0,.65)', logo='#000',
                       acc='#000', veil='21,180,24', veil_size='80% 70%', veil_jr=True, v_color='#0a6b1e'),
}
MONTHS = 'GEN FEB MAR APR MAG GIU LUG AGO SET OTT NOV DIC'.split()
ROWS, ROW_H, ROWS_TOP = 5, 100, 605


def _when(iso):
    y, m, d = iso.split('-')
    return f'{int(d)} {MONTHS[int(m) - 1]} {y}'


def _chip(res, th, size=62):
    """V/P/S nei colori classici (verde, grigio, rosso)."""
    bg = {'V': th.get('v_color', '#2fb344'), 'P': '#9a9a9a', 'S': '#e03131'}[res]
    return (f'<div class="dh" style="width:{size}px;height:{size}px;border-radius:50%;background:{bg};color:#fff;flex:none;'
            f'display:flex;align-items:center;justify-content:center;font-size:{size * .66:.0f}px;padding-top:3px">{res}</div>')


def _backdrop(th):
    out = f'<img class="abs" src="{_CANVA(th["bg"])}" style="left:0;top:0;width:{DESIGN_W}px;height:{DESIGN_H}px;object-fit:cover">'
    if 'veil' in th:
        c = th['veil']
        if th.get('veil_jr'):
            out += (f'<div class="abs" style="left:930px;top:-60px;width:220px;height:220px;'
                    f'background:radial-gradient(circle,rgba({c},1) 0,rgba({c},1) 45%,rgba({c},0) 70%)"></div>')
        out += (f'<div class="abs" style="left:0;top:0;width:{DESIGN_W}px;height:{DESIGN_H}px;background:radial-gradient('
                f'ellipse {th.get("veil_size", "66% 60%")} at 50% 50%,rgba({c},1) 0,rgba({c},1) 68%,rgba({c},0) 100%)"></div>')
    if th.get('tint'):
        out += f'<div class="abs" style="left:0;top:0;width:{DESIGN_W}px;height:{DESIGN_H}px;background:{th["tint"]}"></div>'
    if th.get('fx'):
        out += f'<img class="abs" src="{_CANVA(th["fx"])}" style="left:0;top:0;width:{DESIGN_W}px;height:{DESIGN_H}px">'
    return out + f'<img class="abs" src="{_CANVA(th["jr"])}" style="left:0;top:0;width:{DESIGN_W}px;height:{DESIGN_H}px">'


def build_html(*, kit, stats, opponent_name, opponent_id='', **_):
    if kit not in THEMES:
        raise ValueError('Maglia non valida.')
    th = THEMES[kit]
    acc = f'url({_CANVA(th["acc_file"])}) center/100% 100%' if 'acc_file' in th else th['acc']
    juve = data_uri(team_logo('Juventus', '111'))
    opp = data_uri(team_logo(opponent_name, opponent_id))
    lg = lambda u, s: (f'<div style="width:{s}px;height:{s}px;flex:none;background:var(--logo);'
                       f'-webkit-mask:url({u}) center/contain no-repeat"></div>')
    label = lambda txt, y: (f'<div class="abs info acc" style="left:0;top:{y}px;width:{DESIGN_W}px;text-align:center;'
                            f'font-size:26px;letter-spacing:6px;padding-left:6px">{txt}</div>')
    rule = lambda y: f'<div class="abs accbg" style="left:315px;top:{y}px;width:450px;height:2px;opacity:.7"></div>'

    html = (f'<div class="abs al" style="left:0;top:58px;width:{DESIGN_W}px;text-align:center;font-size:156px">head to '
            f'<span class="acc" style="padding-right:24px;margin-right:-24px">head</span></div>'
            + label('BILANCIO', 255)
            + f'<div class="abs" style="left:0;top:305px;width:{DESIGN_W}px;display:flex;justify-content:center;align-items:center;gap:32px">'
            + lg(juve, 96)
            + ''.join(f'<div style="width:170px;text-align:center"><div class="al {"acc" if k == "W" else ""}" '
                      f'style="font-size:112px;padding:0 10px">{stats[k]}</div>'
                      f'<div class="info" style="font-size:19px;color:var(--muted);margin-top:5px">{lab}</div></div>'
                      for k, lab in (('W', 'VITTORIE'), ('D', 'PAREGGI'), ('L', 'VITTORIE')))
            + lg(opp, 96) + '</div>'
            + rule(510) + label('PRECEDENTI', 545))

    matches = stats['matches'][:ROWS]
    top = ROWS_TOP + (ROWS - len(matches)) * ROW_H // 2       # meno di 5 precedenti: righe al centro
    if not matches:
        html += (f'<div class="abs info" style="left:0;top:820px;width:{DESIGN_W}px;text-align:center;font-size:26px;'
                 f'color:var(--muted)">NESSUN PRECEDENTE UFFICIALE</div>')
    for i, m in enumerate(matches):
        y = top + i * ROW_H
        home, away = (juve, opp) if m['juve_home'] else (opp, juve)
        comp = m['competition'].upper()
        html += (f'<div class="abs info" style="left:70px;top:{y + 24}px;width:285px;text-align:right;font-size:22px;'
                 f'color:var(--muted)">{_when(m["date"])}</div>'
                 f'<div class="abs" style="left:377px;top:{y}px;width:326px;display:flex;align-items:center;justify-content:space-between">'
                 f'{lg(home, 68)}<div class="dh" style="font-size:74px">{m["home_goals"]} – {m["away_goals"]}</div>{lg(away, 68)}</div>'
                 f'<div class="abs info" style="left:725px;top:{y + 24}px;width:300px;font-size:{22 if len(comp) <= 17 else 19 if len(comp) <= 20 else 16}px;'
                 f'color:var(--muted);white-space:nowrap">{esc(comp)}</div>')

    html += rule(1125) + label('FORMA', 1160)
    for j, (logo, results) in enumerate(((juve, stats['form']['juve']), (opp, stats['form']['opp']))):
        y = 1215 + j * 86
        html += (f'<div class="abs" style="left:0;top:{y}px;width:{DESIGN_W}px;display:flex;justify-content:center;align-items:center;gap:13px">'
                 + lg(logo, 64) + '<div style="width:14px"></div>' + ''.join(_chip(r, th) for r in results) + '</div>')

    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
{font_face('Allogist', 'AllogistItalic.ttf')}
{font_face('Dharma', 'DharmaGothicEBold.otf')}
{font_face('Info', 'MatchdayInfo.ttf')}
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{--logo:{th['logo']};--muted:{th['muted']}}}
html,body{{width:{DESIGN_W}px;height:{DESIGN_H}px;overflow:hidden;background:#000;color:{th['ink']}}}
.abs{{position:absolute}}
.al{{font-family:Allogist;font-variant-ligatures:none;line-height:1;white-space:nowrap}}
.dh{{font-family:Dharma;line-height:1;white-space:nowrap;letter-spacing:-.5px}}
.info{{font-family:Info;letter-spacing:1px}}
.acc{{background:{acc};-webkit-background-clip:text;background-clip:text;color:transparent}}
.accbg{{background:{acc}}}
</style></head><body>
{_backdrop(th)}
{html}
</body></html>'''


def render(**kwargs):
    return render_html(build_html(**kwargs))
