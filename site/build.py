#!/usr/bin/env python3
"""Build the AI-startup job board as a static site from data/jobs.json.

No third-party deps. Output goes to site/dist/.

Compliance posture (from NICHE_DECISION.md):
- Each job page shows title/company/location/date + <=280-char summary only.
- Apply always links out to the original posting (url field); full text never
  hosted here.
- Supplementary-source jobs (remoteok/remotive/jobicy) carry a source note.
- Stale/removed postings are dropped by the daily pipeline rerun, not kept.

Design v4 (2026-10-28, direction set by the user across four rounds):
- Editorial / quiet-luxury visual: warm off-white paper (#FAF9F6), ink text,
  serif display type (Fraunces), Inter body, black primary buttons, one
  restrained accent (deep pine #26483A, <5% of any screen).
- Homepage layout for 3-second comprehension: eyebrow, one-line headline,
  search + quick-filter chips, verifiable stat line, text trust band,
  latest roles, company directory, 01/02/03 value columns, dark employer
  band, honest footer with methodology.
- Micro-interactions, restrained and CSS-led: buttons lift 2px on hover,
  cards lift 4px, scroll reveal (0.6s fade + 16px rise, once, grouped
  stagger <=4), nav underline grow, instant form validation states.
  prefers-reduced-motion disables all of it; content is visible without JS.
- Retention P0: quick-filter chips, sticky mobile Apply bar on job pages,
  custom 404 that routes back to search/companies, employer waitlist slot
  and job-alert slots with honest "opens at launch" handling (no fake
  storage: forms validate locally and say alerts open at launch).
- URLs, sitemap, JSON-LD and page inventory are unchanged from v1-v3
  (plus 404.html, which is not in the sitemap).
"""
import hashlib
import html
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "dist"
SITE_NAME = "AI Startup Jobs"
BASE_URL = "https://hajimijob.top"  # target domain; final brand/host confirmed at deploy time

SOURCE_LABEL = {
    "ashby": "company careers page (Ashby board)",
    "greenhouse": "company careers page (Greenhouse board)",
    "remoteok": "Remote OK (aggregated listing)",
    "remotive": "Remotive (aggregated listing)",
    "jobicy": "Jobicy (aggregated listing)",
}

FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
           "viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' "
           "fill='%231a1a1a'/%3E%3Ctext x='32' y='45' font-family='Georgia' "
           "font-size='36' fill='%23faf9f6' "
           "text-anchor='middle'%3EA%3C/text%3E%3C/svg%3E")

LOGO_SVG = ('<svg width="30" height="30" viewBox="0 0 64 64" aria-hidden="true">'
            '<rect width="64" height="64" rx="12" fill="#1a1a1a"/>'
            '<text x="32" y="45" font-family="Georgia" font-size="36" '
            'fill="#faf9f6" text-anchor="middle">A</text></svg>')

ICON_PIN = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'aria-hidden="true"><path d="M12 21s-7-5.5-7-11a7 7 0 1 1 14 0c0 5.5-7 11-7 11z"/>'
            '<circle cx="12" cy="10" r="2.6"/></svg>')
ICON_CAL = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/>'
            '<path d="M3 10h18M8 3v4M16 3v4"/></svg>')
ICON_CHECK = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" '
              'aria-hidden="true"><path d="M4.5 12.5l5 5L19.5 7"/></svg>')
ICON_ARROW = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
              'aria-hidden="true"><path d="M4 12h15M13 6l6 6-6 6"/></svg>')

CSS = """
:root{
--bg:#faf9f6;--surface:#ffffff;--ink:#1a1a1a;--body:#3e3e3a;--muted:#8a877d;
--line:#e7e4dc;--line-strong:#d8d4c9;--pine:#26483a;--pine-text:#2f5d4a;
--pine-soft:#edf2ee;--gold-bg:#fdf3e3;--gold:#8a5a17;--err:#b3402a;
--serif:"Fraunces",Georgia,"Times New Roman","Songti SC","Noto Serif SC",serif;
--sans:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Noto Sans SC",sans-serif;
--sh-card:0 1px 3px rgba(26,26,26,.04);--sh-card-hover:0 12px 32px rgba(26,26,26,.08);
--sh-btn:0 6px 16px rgba(26,26,26,.18);--ease:cubic-bezier(.22,1,.36,1)}
@media (prefers-color-scheme:dark){:root{
--bg:#131311;--surface:#1c1c1a;--ink:#edeae3;--body:#c9c6bc;--muted:#9c998e;
--line:#2c2c29;--line-strong:#3a3a36;--pine:#8fc7ab;--pine-text:#8fc7ab;
--pine-soft:#1d2b24;--gold-bg:#2c2110;--gold:#e3b959;--err:#e08a75;
--sh-card:0 1px 3px rgba(0,0,0,.4);--sh-card-hover:0 12px 32px rgba(0,0,0,.55);
--sh-btn:0 6px 16px rgba(0,0,0,.5)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--body);font-family:var(--sans);
font-size:16px;line-height:1.65;-webkit-font-smoothing:antialiased}
h1,h2,h3,.serif{font-family:var(--serif);color:var(--ink);font-weight:600}
a{color:var(--pine-text);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1120px;margin:0 auto;padding:0 24px}
@media(min-width:768px){.wrap{padding:0 48px}}
.site-header{position:sticky;top:0;z-index:30;background:var(--bg);
border-bottom:1px solid var(--line)}
.site-header .wrap{display:flex;align-items:center;gap:14px;height:64px}
.brand{display:flex;align-items:center;gap:10px;font-family:var(--serif);
font-weight:700;font-size:1.08rem;color:var(--ink)}
.brand:hover{text-decoration:none}
.brand svg{flex:none}
.site-nav{margin-left:auto;display:flex;align-items:center;gap:28px}
.site-nav a.navlink{color:var(--body);font-size:.94rem;position:relative;padding:4px 0}
.site-nav a.navlink::after{content:"";position:absolute;left:0;bottom:0;height:1px;
width:100%;background:var(--ink);transform:scaleX(0);transform-origin:left;
transition:transform .2s ease}
.site-nav a.navlink:hover{color:var(--ink);text-decoration:none}
.site-nav a.navlink:hover::after{transform:scaleX(1)}
.btn{display:inline-flex;align-items:center;gap:8px;background:var(--ink);
color:var(--bg)!important;font-family:var(--sans);font-weight:600;
padding:12px 24px;border-radius:8px;font-size:.95rem;border:1px solid var(--ink);
cursor:pointer;transition:transform .2s ease,box-shadow .2s ease,background .2s ease}
.btn:hover{transform:translateY(-2px);box-shadow:var(--sh-btn);text-decoration:none}
.btn:active{transform:translateY(0);box-shadow:var(--sh-card);transition-duration:.1s}
.btn:focus-visible,a:focus-visible,input:focus-visible,button:focus-visible{
outline:2px solid var(--pine);outline-offset:2px}
.btn.light{background:var(--bg);color:var(--ink)!important;border-color:var(--bg)}
.btn.sm{padding:9px 16px;font-size:.88rem}
.btn[disabled]{opacity:.55;cursor:default;transform:none;box-shadow:none}
.btn svg{width:15px;height:15px}
main{padding:0 0 8px}
.section{margin-top:104px}
@media(max-width:767px){.section{margin-top:64px}}
h2.section-title{font-size:28px;line-height:1.2;margin:0 0 8px;letter-spacing:-.01em}
p.section-sub{color:var(--muted);margin:0 0 24px}
.eyebrow{font-size:.78rem;font-weight:600;letter-spacing:.22em;color:var(--muted);
text-transform:uppercase;margin:0 0 24px}
.hero{padding:96px 0 0;text-align:left}
.hero h1{font-size:56px;line-height:1.08;letter-spacing:-.02em;margin:0 0 24px;font-weight:600}
.hero p.sub{font-size:1.16rem;line-height:1.55;color:var(--body);max-width:620px;margin:0 0 32px}
.hero p.sub b{color:var(--ink)}
.dataline{color:var(--muted);font-size:.93rem;margin-top:24px}
.dataline b{color:var(--ink);font-weight:600}
.searchrow{display:flex;gap:12px;flex-wrap:wrap;max-width:680px}
.searchbox{flex:1 1 320px;display:flex;align-items:center;background:var(--surface);
border:1px solid var(--line-strong);border-radius:12px;padding:0 18px;height:52px;
transition:border-color .2s ease}
.searchbox:focus-within{border-color:var(--pine)}
.searchbox input{border:0;outline:0;background:transparent;color:var(--ink);
font-size:16px;width:100%;font-family:var(--sans)}
.searchrow .btn{height:52px}
.resultline{color:var(--muted);font-size:.9rem;margin-top:16px;min-height:1.4em}
.zerostate{display:none;background:var(--surface);border:1px solid var(--line);
border-radius:12px;padding:24px;color:var(--muted)}
.zerostate.show{display:block}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.fchip{font-family:var(--sans);font-size:.88rem;font-weight:500;color:var(--body);
background:var(--surface);border:1px solid var(--line-strong);border-radius:980px;
padding:8px 16px;cursor:pointer;min-height:40px;
transition:transform .2s ease,border-color .2s ease,color .2s ease}
.fchip:hover{transform:translateY(-2px);border-color:var(--ink);color:var(--ink)}
.fchip.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.trustband{margin-top:80px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);
padding:32px 0}
.trustband .tb-label{font-size:.76rem;letter-spacing:.22em;color:var(--muted);
text-transform:uppercase;margin:0 0 16px}
.trustband .tb-names{font-family:var(--serif);font-size:1.22rem;color:var(--body);
display:flex;flex-wrap:wrap;gap:12px 34px}
.cards{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:16px}
.job-card{background:var(--surface);border:1px solid var(--line);border-radius:12px;
box-shadow:var(--sh-card);padding:24px;display:flex;gap:16px;align-items:flex-start;
transition:transform .25s ease,box-shadow .25s ease,border-color .25s ease}
.job-card:hover{transform:translateY(-4px);box-shadow:var(--sh-card-hover);
border-color:var(--line-strong)}
.job-card:hover .job-title{color:var(--pine-text)}
.avatar{flex:none;width:44px;height:44px;border-radius:10px;color:#fff;
font-weight:600;font-size:1.02rem;display:flex;align-items:center;justify-content:center;
font-family:var(--serif)}
.job-main{min-width:0;flex:1}
.job-title{font-weight:600;font-size:1.04rem;color:var(--ink);letter-spacing:-.005em;
transition:color .2s ease}
.job-title:hover{text-decoration:none}
.meta{display:flex;flex-wrap:wrap;gap:4px 16px;color:var(--muted);font-size:.9rem;margin-top:4px}
.meta .mi{display:inline-flex;align-items:center;gap:5px}
.meta svg{width:14px;height:14px;flex:none}
.badge{display:inline-flex;align-items:center;font-size:.76rem;font-weight:600;
padding:2px 10px;border-radius:980px}
.badge.remote{background:var(--pine-soft);color:var(--pine-text)}
.badge.dept{background:transparent;border:1px solid var(--line-strong);color:var(--muted)}
.dirlist{list-style:none;margin:0;padding:0;columns:3;column-gap:48px}
.dirlist li{break-inside:avoid;padding:10px 0;border-bottom:1px solid var(--line)}
.dirlist a{color:var(--ink);font-weight:500}
.dirlist .n{color:var(--muted);font-size:.88rem;margin-left:8px}
@media(max-width:900px){.dirlist{columns:2}}
@media(max-width:560px){.dirlist{columns:1}}
.values{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:32px}
.value .num{font-family:var(--serif);font-size:1.3rem;color:var(--pine-text);display:block;margin-bottom:8px}
.value h3{margin:0 0 8px;font-size:1.12rem}
.value p{margin:0;color:var(--muted)}
.darkband{background:#1a1a1a;color:#c9c6bc;border-radius:16px;padding:56px 48px;margin-top:104px}
.darkband h2{color:#faf9f6;font-size:30px;margin:0 0 12px;letter-spacing:-.01em}
.darkband p{margin:0 0 28px;max-width:520px}
.darkband .price-note{color:#e3b959;font-weight:600}
@media(max-width:767px){.darkband{padding:40px 24px;margin-top:64px}}
.alertband{background:var(--surface);border:1px solid var(--line);border-radius:12px;
box-shadow:var(--sh-card);padding:32px;margin-top:24px}
.alertband h3{margin:0 0 6px;font-size:1.2rem}
.alertband p{margin:0 0 18px;color:var(--muted)}
.field{display:flex;gap:12px;flex-wrap:wrap}
.field input{flex:1 1 260px;height:50px;border:1px solid var(--line-strong);
border-radius:8px;padding:0 16px;font-size:16px;background:var(--bg);color:var(--ink);
font-family:var(--sans);transition:border-color .2s ease}
.field input:focus{outline:0;border-color:var(--pine)}
.field.err input{border-color:var(--err)}
.field.ok input{border-color:var(--pine)}
.fmsg{font-size:.88rem;margin-top:10px;min-height:1.3em;color:var(--muted)}
.fmsg.err{color:var(--err)}
.fmsg.ok{color:var(--pine-text)}
.crumbs{color:var(--muted);font-size:.92rem;margin:32px 0 20px}
.crumbs a{color:var(--muted)}
.job-head h1{font-size:40px;line-height:1.15;margin:0 0 12px;letter-spacing:-.015em}
.job-head .meta{font-size:.97rem}
.summary{font-size:1.04rem;background:var(--surface);border:1px solid var(--line);
border-radius:12px;box-shadow:var(--sh-card);padding:24px;margin:24px 0;color:var(--body)}
.apply-box{margin:8px 0 24px}
.apply-box .btn{font-size:1rem;padding:14px 28px}
.src-note{color:var(--muted);font-size:.9rem;margin-top:16px}
.company-head{display:flex;gap:18px;align-items:center;margin-bottom:10px}
.company-head .avatar{width:60px;height:60px;border-radius:12px;font-size:1.5rem}
.company-head h1{margin:0;font-size:34px;letter-spacing:-.015em}
.company-head p{margin:4px 0 0;color:var(--muted)}
.pricing{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px;margin:28px 0}
.price-card{background:var(--surface);border:1px solid var(--line);border-radius:12px;
box-shadow:var(--sh-card);padding:32px;position:relative}
.price-card.featured{border-color:var(--ink)}
.price-card .tag{position:absolute;top:-11px;left:24px;background:var(--gold-bg);
color:var(--gold);font-size:.74rem;font-weight:700;padding:2px 11px;border-radius:980px;
letter-spacing:.05em}
.price-card h3{margin:0 0 6px;font-size:1.05rem}
.price-card .amount{font-family:var(--serif);font-size:2.2rem;font-weight:600;color:var(--ink)}
.price-card .amount span{font-family:var(--sans);font-size:.92rem;color:var(--muted);font-weight:400}
.price-card ul{list-style:none;margin:16px 0 0;padding:0}
.price-card li{display:flex;gap:9px;padding:5px 0;color:var(--muted)}
.price-card li svg{width:16px;height:16px;color:var(--pine-text);flex:none;margin-top:4px}
.notice{background:var(--gold-bg);border-radius:12px;padding:18px 22px;margin:24px 0;color:var(--body)}
.apply-bar{display:none}
@media(max-width:768px){
body.jobpage{padding-bottom:78px}
.apply-bar{display:flex;position:fixed;left:0;right:0;bottom:0;z-index:40;
background:var(--surface);border-top:1px solid var(--line);
padding:12px 16px calc(12px + env(safe-area-inset-bottom));gap:12px;align-items:center}
.apply-bar .t{min-width:0;flex:1;font-size:.88rem;color:var(--ink);font-weight:600;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.apply-bar .btn{padding:11px 18px}
.hero{padding:64px 0 0}
.hero h1{font-size:38px}
.job-head h1{font-size:29px}
.site-nav a.navlink{display:none}
.stat b{font-size:1.4rem}}
footer.site-footer{border-top:1px solid var(--line);margin-top:104px;
padding:40px 0 44px;color:var(--muted);font-size:.9rem}
footer.site-footer .cols{display:flex;gap:48px;flex-wrap:wrap}
footer.site-footer b{color:var(--ink);display:block;margin-bottom:10px;font-weight:600}
footer.site-footer a{color:var(--muted);display:block;padding:3px 0}
footer.site-footer .fine{margin-top:28px;font-size:.85rem;max-width:760px}
.js .reveal{opacity:0;transform:translateY(16px)}
.js .reveal.in{opacity:1;transform:none;transition:opacity .6s var(--ease),transform .6s var(--ease)}
@media (prefers-reduced-motion:reduce){
*,*::before,*::after{transition:none!important;animation:none!important}
.js .reveal{opacity:1;transform:none}}
"""

REVEAL_JS = """<script>
(function(){
var els=document.querySelectorAll('.reveal');
if(!('IntersectionObserver' in window)){els.forEach(function(e){e.classList.add('in')});return}
var io=new IntersectionObserver(function(es){es.forEach(function(en){
if(en.isIntersecting){en.target.classList.add('in');io.unobserve(en.target)}})},{threshold:.12});
els.forEach(function(e){io.observe(e)});
})();
</script>"""

FILTER_JS = """<script>
(function(){
var input=document.getElementById('q'),cards=[].slice.call(document.querySelectorAll('#latest .job-card')),
line=document.getElementById('resultline'),zero=document.getElementById('zerostate'),
chips=[].slice.call(document.querySelectorAll('.fchip')),mode='all';
function catMatch(c){if(mode==='all')return true;if(mode==='remote')return c.dataset.r==='1';
return c.dataset.t.indexOf(mode)>-1}
function apply(){var q=input.value.trim().toLowerCase(),n=0;
cards.forEach(function(c){var ok=catMatch(c)&&(!q||c.dataset.t.indexOf(q)>-1);
c.style.display=ok?'':'none';if(ok)n++});
line.textContent=q||mode!=='all'?('Showing '+n+' of '+cards.length+' latest roles'):'';
zero.classList.toggle('show',n===0)}
input.addEventListener('input',apply);
chips.forEach(function(ch){ch.addEventListener('click',function(){
chips.forEach(function(x){x.classList.remove('on')});ch.classList.add('on');
mode=ch.dataset.mode;apply()})});
})();
</script>"""

FORM_JS = """<script>
function wireForm(fid){
var f=document.getElementById(fid);if(!f)return;
var wrap=f.querySelector('.field'),inp=f.querySelector('input'),msg=f.querySelector('.fmsg'),
btn=f.querySelector('button');
var emailRe=/^[^\\s@]+@[^\\s@]+\\.[^\\s@]{2,}$/;
inp.addEventListener('input',function(){wrap.classList.remove('err','ok');msg.textContent='';msg.className='fmsg'});
f.addEventListener('submit',function(ev){ev.preventDefault();
var v=inp.value.trim();
if(!emailRe.test(v)){wrap.classList.add('err');wrap.classList.remove('ok');
msg.textContent='Please enter a valid email address.';msg.className='fmsg err';inp.focus();return}
wrap.classList.add('ok');wrap.classList.remove('err');btn.disabled=true;btn.textContent='One moment...';
setTimeout(function(){msg.textContent='Noted \\u2014 alerts and paid posting open at launch, and this is where they will be announced first.';
msg.className='fmsg ok';btn.textContent='Done';},500)});
}
</script>"""


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "company"


def job_id(url):
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def esc(s):
    return html.escape(str(s or ""), quote=True)


def initial_avatar(name):
    ch = next((c for c in (name or "?") if c.isalnum()), "?").upper()
    hue = sum(ord(c) for c in (name or "?")) % 360
    return (f'<span class="avatar" style="background:hsl({hue} 42% 38%)" '
            f'aria-hidden="true">{esc(ch)}</span>')


def is_remote(j):
    return str(j.get("remote")).lower() == "true"


def reveal_open(i):
    """Reveal wrapper opening tag; stagger capped at 4 items (240ms)."""
    d = min(i, 4) * 60
    return f'<div class="reveal" style="transition-delay:{d}ms">'


def job_card(j):
    badges = ""
    if is_remote(j):
        badges += '<span class="badge remote">Remote</span>'
    if j.get("department"):
        badges += f'<span class="badge dept">{esc(j["department"])}</span>'
    date_bit = (f'<span class="mi">{ICON_CAL}{esc(j.get("posted_date", ""))}</span>'
                if j.get("posted_date") else "")
    haystack = " ".join([j.get("title", ""), j.get("company", ""), j.get("location", ""),
                         j.get("department", "")]).lower().replace('"', " ")
    return (
        f'<li class="job-card" data-r="{1 if is_remote(j) else 0}" data-t="{esc(haystack)}">'
        f'{initial_avatar(j["company"])}<div class="job-main">'
        f'<a class="job-title" href="/jobs/{job_id(j["url"])}.html">{esc(j["title"])}</a>'
        f'<div class="meta"><span class="mi">{esc(j["company"])}</span>'
        f'<span class="mi">{ICON_PIN}{esc(j["location"])}</span>{date_bit}{badges}</div>'
        f"</div></li>"
    )


def alert_form(fid, heading, text, button="Notify me"):
    return f"""<div class="alertband">
<h3 class="serif">{esc(heading)}</h3><p>{esc(text)}</p>
<form id="{fid}" novalidate><div class="field">
<input type="email" placeholder="you@example.com" aria-label="Email address" autocomplete="email">
<button class="btn" type="submit">{esc(button)}</button></div>
<div class="fmsg" role="status"></div></form></div>"""


def page(title, body, description="", extra_head="", body_class="", scripts=""):
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} | {SITE_NAME}</title>
<meta name="description" content="{esc(description)[:160]}">
<link rel="icon" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script>document.documentElement.classList.add('js')</script>
<style>{CSS}</style>{extra_head}
</head><body class="{body_class}">
<header class="site-header"><div class="wrap">
<a class="brand" href="/">{LOGO_SVG}{SITE_NAME}</a>
<nav class="site-nav"><a class="navlink" href="/#latest">Jobs</a><a class="navlink" href="/#companies">Companies</a><a class="btn sm" href="/post-a-job.html">Post a job</a></nav>
</div></header>
<main><div class="wrap">{body}</div></main>
<footer class="site-footer"><div class="wrap">
<div class="cols">
<div><b>{SITE_NAME}</b><a href="/#latest">Latest jobs</a><a href="/#companies">Browse companies</a><a href="/post-a-job.html">Post a job</a></div>
<div><b>For employers</b><a href="/post-a-job.html">Pricing &amp; posting</a></div>
<div><b>How it works</b><a href="/#how">Data &amp; methodology</a></div>
</div>
<p class="fine" id="how">Methodology: listings are synced daily from the official recruiting systems (Ashby and Greenhouse) used by the companies themselves, plus attributed listings from Remote OK, Remotive and Jobicy. Only a short summary is shown here; applications always happen on the employer's own site. Postings that close are removed at the next sync.</p>
</div></footer>
{scripts}</body></html>
"""


def main():
    jobs = []
    for _shard in sorted((ROOT / "data").glob("jobs-*.json")):
        jobs.extend(json.loads(_shard.read_text()))
    jobs.sort(key=lambda j: (j.get("posted_date") or "", j.get("title") or ""), reverse=True)
    by_company = defaultdict(list)
    for j in jobs:
        by_company[j["company"]].append(j)

    if OUT.exists():
        import shutil
        shutil.rmtree(OUT)
    (OUT / "companies").mkdir(parents=True)
    (OUT / "jobs").mkdir(parents=True)

    today = date.today().isoformat()
    total = len(jobs)
    remote_n = sum(1 for j in jobs if is_remote(j))
    companies_sorted = sorted(by_company.items(), key=lambda kv: -len(kv[1]))

    # --- index ---
    top_names = [c for c, _ in companies_sorted[:8]]
    trust = "".join(f"<span>{esc(c)}</span>" for c in top_names)
    latest_cards = "".join(job_card(j) for j in jobs[:20])
    dir_items = "".join(
        f'<li><a href="/companies/{slugify(c)}.html">{esc(c)}</a>'
        f'<span class="n">{len(js)} roles</span></li>'
        for c, js in companies_sorted)
    index_body = f"""<div class="hero">
<p class="eyebrow">AI Startup Job Board — Updated Daily</p>
<h1>Every AI job. One board.</h1>
<p class="sub"><b>{total:,}</b> open roles at <b>{len(by_company)} AI companies</b>, pulled from their official career pages and refreshed every day. Expired postings are removed, not left to rot.</p>
<div class="searchrow">
<label class="searchbox"><input id="q" placeholder="Search the latest roles — try 'engineer' or 'remote'" aria-label="Search latest roles"></label>
<a class="btn" href="#latest">Browse jobs</a>
</div>
<div class="chips" role="group" aria-label="Quick filters">
<button class="fchip on" data-mode="all">All</button>
<button class="fchip" data-mode="remote">Remote</button>
<button class="fchip" data-mode="engineer">Engineering</button>
<button class="fchip" data-mode="product">Product</button>
<button class="fchip" data-mode="design">Design</button>
<button class="fchip" data-mode="research">Research</button>
</div>
<p class="resultline" id="resultline"></p>
</div>
<div class="trustband"><p class="tb-label">Roles from teams at</p><div class="tb-names">{trust}</div></div>
<div class="section" id="latest">
<h2 class="section-title">Latest roles</h2>
<p class="section-sub">The 20 most recent openings across all companies. Pick a company below for its full list.</p>
<ul class="cards" id="latest-list">{latest_cards}</ul>
<div class="zerostate" id="zerostate">No roles in the latest 20 match that filter. Try a different term, or browse the full company lists below.</div>
{alert_form("alertForm", "New AI roles, once a week", "One short email with the week's most interesting new openings. No spam, unsubscribe anytime.", "Get job alerts")}
</div>
<div class="section" id="companies">
<h2 class="section-title">Browse by company</h2>
<p class="section-sub">Every company on the board, with its current open-role count.</p>
<ul class="dirlist">{dir_items}</ul>
</div>
<div class="section">
<h2 class="section-title">Why this board</h2>
<p class="section-sub"></p>
<div class="values">
<div class="value"><span class="num">01</span><h3>Only AI companies</h3><p>From the labs everyone knows to startups that closed a round last month — the roles big boards bury.</p></div>
<div class="value"><span class="num">02</span><h3>Refreshed daily</h3><p>Synced from official career pages every day. When a posting closes, it disappears here too.</p></div>
<div class="value"><span class="num">03</span><h3>Straight to the source</h3><p>A short summary here, then one click to the official application page. No accounts, no resume uploads.</p></div>
</div>
</div>
<div class="darkband">
<h2>Hiring at an AI startup?</h2>
<p>Put your role in front of people who came here specifically for AI jobs. Launch pricing starts at <span class="price-note">$49 early bird</span> per post for 30 days.</p>
<a class="btn light" href="/post-a-job.html">Post a job</a>
</div>"""
    (OUT / "index.html").write_text(page("AI Startup Jobs", index_body,
        f"{total:,} open roles at {len(by_company)} AI companies, updated daily.",
        scripts=FORM_JS + FILTER_JS + REVEAL_JS + '<script>wireForm("alertForm")</script>'))

    # --- company pages ---
    for company, cjobs in companies_sorted:
        c_remote = sum(1 for j in cjobs if is_remote(j))
        card_list = "".join(
            f"{reveal_open(i % 8)}<ul class=\"cards\" style=\"margin-bottom:16px\">{job_card(j)}</ul></div>"
            for i, j in enumerate(cjobs))
        body = (f'<nav class="crumbs"><a href="/">Home</a> / <a href="/#companies">Companies</a> / {esc(company)}</nav>'
                f'<div class="company-head">{initial_avatar(company)}<div>'
                f"<h1>{esc(company)}</h1>"
                f"<p>{len(cjobs)} open roles · {c_remote} remote · updated {today}</p></div></div>"
                f'<div style="margin-top:24px">{card_list}</div>')
        (OUT / "companies" / f"{slugify(company)}.html").write_text(
            page(f"{company} jobs", body, f"{len(cjobs)} open roles at {company}.",
                 scripts=REVEAL_JS))

    # --- job pages ---
    for j in jobs:
        jid = job_id(j["url"])
        src = SOURCE_LABEL.get(j.get("source", ""), j.get("source", ""))
        cslug = slugify(j["company"])
        meta_bits = (f'<span class="mi">{ICON_PIN}{esc(j["location"])}</span>'
                     + (f'<span class="mi">{ICON_CAL}Posted {esc(j.get("posted_date", ""))}</span>'
                        if j.get("posted_date") else "")
                     + (f'<span class="mi">{esc(j["department"])}</span>' if j.get("department") else "")
                     + ('<span class="badge remote">Remote</span>' if is_remote(j) else ""))
        summary = esc(j.get("description_summary") or "")
        summary_block = f'<div class="summary">{summary}</div>' if summary else ""
        # Supplementary aggregator sources (Remote OK / Remotive / Jobicy) require
        # a named credit + hyperlink back on the page where their data is used,
        # and their apply URL points at the aggregator's own job page, not the
        # employer's site — so both the button label and the source note differ.
        SUPP_NAME = {"remoteok": "Remote OK", "remotive": "Remotive", "jobicy": "Jobicy"}
        if j.get("source", "") in SUPP_NAME:
            supp = SUPP_NAME[j["source"]]
            apply_btn = (f'<a class="btn apply-btn" href="{esc(j["url"])}" rel="nofollow" '
                         f'target="_blank">Apply via {supp} {ICON_ARROW}</a>')
            src_note = (f'<p class="src-note">Source: <a href="{esc(j["url"])}">{supp}</a> '
                        f'(aggregated listing). Summary only; the full description and application are on the original posting.</p>')
        else:
            apply_btn = (f'<a class="btn apply-btn" href="{esc(j["url"])}" rel="nofollow" '
                         f'target="_blank">Apply on the employer\'s site {ICON_ARROW}</a>')
            src_note = (f'<p class="src-note">Source: {esc(src)}. Summary only; the full description and application are on the original posting.</p>')
        body = (f'<nav class="crumbs"><a href="/">Home</a> / '
                f'<a href="/companies/{cslug}.html">{esc(j["company"])}</a> / {esc(j["title"])}</nav>'
                f'<div class="job-head"><h1>{esc(j["title"])}</h1>'
                f'<div class="meta">{meta_bits}</div></div>'
                f"{summary_block}"
                f'<div class="apply-box">{apply_btn}'
                f'{src_note}</div>'
                + alert_form("alertForm", "Similar roles, weekly",
                             f"Get new {esc(j['company'])} and similar AI roles in one short weekly email.", "Get job alerts")
                + f'<p style="margin-top:24px"><a href="/companies/{cslug}.html">More jobs at {esc(j["company"])}</a></p>'
                + f'<div class="apply-bar"><span class="t">{esc(j["title"])} · {esc(j["company"])}</span>'
                  f'<a class="btn apply-btn" href="{esc(j["url"])}" rel="nofollow" target="_blank">Apply</a></div>')
        ld = {
            "@context": "https://schema.org", "@type": "JobPosting",
            "title": j["title"], "hiringOrganization": {"@type": "Organization", "name": j["company"]},
            "jobLocation": {"@type": "Place", "address": j["location"]},
            "datePosted": j.get("posted_date", ""), "url": j["url"],
            "description": (j.get("description_summary") or "")[:280],
        }
        apply_js = """<script>
document.querySelectorAll('.apply-btn').forEach(function(b){b.addEventListener('click',function(){
var old=b.innerHTML;b.innerHTML='Opening\\u2026';setTimeout(function(){b.innerHTML=old},2500)})});
</script>"""
        doc = page(f"{j['title']} at {j['company']}", body,
                   f"{j['title']} at {j['company']} ({j['location']}).",
                   extra_head=f'<script type="application/ld+json">{json.dumps(ld)}</script>',
                   body_class="jobpage",
                   scripts=FORM_JS + '<script>wireForm("alertForm")</script>' + apply_js)
        (OUT / "jobs" / f"{jid}.html").write_text(doc)

    # --- employer posting page (pricing; waitlist slot — payment not yet confirmed) ---
    post_body = f"""<div style="padding-top:56px">
<p class="eyebrow">For Employers</p>
<h2 class="section-title" style="font-size:34px">Post a job</h2>
<p class="section-sub" style="max-width:560px">Reach job seekers browsing AI startup roles. One post runs for 30 days on the board and on your company page.</p>
<div class="pricing">
<div class="price-card"><span class="tag">EARLY BIRD</span>
<h3>Early bird</h3><div class="amount">$49 <span>/ post · 30 days</span></div>
<ul>
<li>{ICON_CHECK}Listed alongside aggregated AI startup jobs</li>
<li>{ICON_CHECK}Linked back to your own application page</li>
<li>{ICON_CHECK}Live for the full 30 days</li>
</ul></div>
<div class="price-card featured">
<h3>Standard</h3><div class="amount">$299 <span>/ post · 30 days</span></div>
<ul>
<li>{ICON_CHECK}The prevailing rate at established remote job boards</li>
<li>{ICON_CHECK}Listed alongside aggregated AI startup jobs</li>
<li>{ICON_CHECK}Live for the full 30 days, removed when the posting closes</li>
</ul></div>
</div>
<div class="notice"><strong>Paid posting opens at launch.</strong> Pricing is final, but no checkout link is published yet: the payment account is being confirmed, and no employer will be charged before it is. Leave an email below to be notified the moment posting opens.</div>
{alert_form("waitlistForm", "Be first to post", "One email when paid posting opens — early-bird pricing is reserved for the waitlist.", "Join the waitlist")}
</div>"""
    (OUT / "post-a-job.html").write_text(page("Post a job", post_body,
        "Post a job at an AI startup: early-bird $49, standard $299 per post for 30 days.",
        scripts=FORM_JS + '<script>wireForm("waitlistForm")</script>'))

    # --- 404 (not in sitemap; Vercel serves /404.html for unknown paths) ---
    popular = "".join(
        f'<li><a href="/companies/{slugify(c)}.html">{esc(c)}</a>'
        f'<span class="n">{len(js)} roles</span></li>'
        for c, js in companies_sorted[:9])
    nf_body = f"""<div style="padding-top:88px;max-width:640px">
<p class="eyebrow">404</p>
<h1 class="serif" style="font-size:40px;line-height:1.15;margin:0 0 16px">This role has closed.</h1>
<p style="color:var(--muted);margin:0 0 32px">Postings here are refreshed daily, and this one is gone — it may have been filled. The same company may have newer roles:</p>
<ul class="dirlist" style="columns:1">{popular}</ul>
<p style="margin-top:32px"><a class="btn" href="/">Browse the latest roles</a></p>
</div>"""
    (OUT / "404.html").write_text(page("Page not found", nf_body,
        "This posting is no longer available. Browse current AI startup roles."))

    # --- sitemap + robots ---
    urls = ["", "/post-a-job.html"] + [f"/companies/{slugify(c)}.html" for c, _ in companies_sorted] + \
           [f"/jobs/{job_id(j['url'])}.html" for j in jobs]
    sm = ('<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
          "".join(f"<url><loc>{BASE_URL}{u if u else '/'}</loc></url>\n" for u in urls) +
          "</urlset>\n")
    (OUT / "sitemap.xml").write_text(sm)
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: "
                                   f"{BASE_URL}/sitemap.xml\n")

    print(f"jobs={total} companies={len(by_company)} remote={remote_n} "
          f"pages={len(urls)} out={OUT}")
    print("largest company pages:", [(c, len(js)) for c, js in companies_sorted[:3]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
