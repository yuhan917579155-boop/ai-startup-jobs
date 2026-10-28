#!/usr/bin/env python3
"""Build the AI-startup job board as a static site from data/jobs.json.

No third-party deps. Output goes to site/dist/ (deploy-ready, NOT deployed:
production deploy needs the user's one-time Vercel login + DNSPod registrar
record change; the new repo goes under the already-connected GitHub account,
so GitHub 02LYH-HUB login is NOT a blocker for this board).

Compliance posture (from NICHE_DECISION.md):
- Each job page shows title/company/location/date + <=280-char summary only.
- Apply always links out to the original posting (url field); full text never
  hosted here.
- Supplementary-source jobs (remoteok/remotive/jobicy) carry a source note.
- Stale/removed postings are dropped by the daily pipeline rerun, not kept.

UI v2 (2026-10-28, user asked for a proper UI before launch):
- Shared stylesheet (light, card-based, responsive, dark-mode aware),
  sticky header with brand mark + nav, hero with stats on the homepage,
  job/company cards, breadcrumbs + big apply button on job pages,
  pricing cards on post-a-job. Emoji-free monogram logo (inline SVG),
  favicon via inline SVG data URI. Inline SVG icons for meta items.
- URLs, sitemap, JSON-LD and page inventory are unchanged from v1.
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
           "viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' "
           "fill='%234f46e5'/%3E%3Ctext x='32' y='44' font-family='Arial' "
           "font-size='34' font-weight='700' fill='white' "
           "text-anchor='middle'%3EA%3C/text%3E%3C/svg%3E")

LOGO_SVG = ('<svg width="30" height="30" viewBox="0 0 64 64" aria-hidden="true">'
            '<rect width="64" height="64" rx="14" fill="#4f46e5"/>'
            '<text x="32" y="44" font-family="Arial" font-size="34" '
            'font-weight="700" fill="#fff" text-anchor="middle">A</text></svg>')

ICON_PIN = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'aria-hidden="true"><path d="M12 21s-7-5.5-7-11a7 7 0 1 1 14 0c0 5.5-7 11-7 11z"/>'
            '<circle cx="12" cy="10" r="2.6"/></svg>')
ICON_CAL = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/>'
            '<path d="M3 10h18M8 3v4M16 3v4"/></svg>')
ICON_TEAM = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
             'aria-hidden="true"><circle cx="9" cy="8" r="3.2"/><path d="M3.5 19c.6-3 2.8-4.5 5.5-4.5S13.9 16 14.5 19"/>'
             '<circle cx="17" cy="9" r="2.4"/><path d="M16 14.7c2.3.2 3.9 1.6 4.4 4.3"/></svg>')
ICON_WIFI = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
             'aria-hidden="true"><path d="M4 10.5a12 12 0 0 1 16 0M6.8 14a8 8 0 0 1 10.4 0"/>'
             '<circle cx="12" cy="17.4" r="1.3" fill="currentColor"/></svg>')
ICON_ARROW = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
              'aria-hidden="true"><path d="M4 12h15M13 6l6 6-6 6"/></svg>')
ICON_SEARCH = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
               'aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.8-3.8"/></svg>')
ICON_CHECK = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" '
              'aria-hidden="true"><path d="M4.5 12.5l5 5L19.5 7"/></svg>')

CSS = """
:root{
--bg:#f5f5f7;--surface:#fff;--ink:#1d1d1f;--muted:#6e6e73;--line:#d2d2d7;
--brand:#0066cc;--brand-btn:#0071e3;--brand-btn-hover:#0077ed;--brand-soft:#eef4fb;
--accent:#008a3d;--accent-soft:#e6f6ec;--gold:#b25309;--gold-soft:#fdf3e3;
--shadow:0 4px 24px rgba(0,0,0,.06);--radius:18px;
--header-bg:rgba(251,251,253,.78)}
@media (prefers-color-scheme:dark){:root{
--bg:#000;--surface:#161617;--ink:#f5f5f7;--muted:#86868b;--line:#424245;
--brand:#2997ff;--brand-btn:#0071e3;--brand-btn-hover:#0077ed;--brand-soft:#12283f;
--accent:#30d158;--accent-soft:#0d2b18;--gold:#ffd60a;--gold-soft:#2c2110;
--shadow:0 4px 24px rgba(0,0,0,.5);--header-bg:rgba(22,22,23,.78)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","SF Pro Display",system-ui,"Helvetica Neue",Arial,sans-serif;
line-height:1.55;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:var(--brand);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1020px;margin:0 auto;padding:0 22px}
.site-header{position:sticky;top:0;z-index:20;background:var(--header-bg);
-webkit-backdrop-filter:saturate(180%) blur(20px);backdrop-filter:saturate(180%) blur(20px);
border-bottom:1px solid var(--line)}
.site-header .wrap{display:flex;align-items:center;gap:14px;height:56px}
.brand{display:flex;align-items:center;gap:9px;font-weight:700;font-size:1.02rem;
color:var(--ink);letter-spacing:-.01em}
.brand:hover{text-decoration:none}
.brand svg{flex:none;border-radius:7px}
.site-nav{margin-left:auto;display:flex;align-items:center;gap:24px}
.site-nav a{color:var(--ink);opacity:.85;font-weight:400;font-size:.86rem}
.site-nav a:hover{opacity:1;text-decoration:none}
.btn{display:inline-flex;align-items:center;gap:7px;background:var(--brand-btn);
color:#fff!important;font-weight:400;padding:9px 17px;border-radius:980px;
font-size:.92rem;border:0}
.btn:hover{background:var(--brand-btn-hover);text-decoration:none}
.btn.sm{padding:6px 13px;font-size:.82rem}
.btn svg{width:15px;height:15px}
main{padding:40px 0 12px}
.hero{text-align:center;padding:34px 0 10px}
.hero h1{font-size:3.1rem;line-height:1.08;font-weight:700;margin:0 0 16px;letter-spacing:-.015em}
.hero h1 .hl{color:var(--brand)}
.hero p.sub{color:var(--muted);font-size:1.28rem;line-height:1.45;max-width:660px;margin:0 auto;font-weight:400}
.stats{display:flex;gap:14px;justify-content:center;flex-wrap:wrap;margin:34px 0 8px}
.stat{background:var(--surface);border-radius:var(--radius);
box-shadow:var(--shadow);padding:18px 24px;min-width:158px}
.stat b{display:block;font-size:1.65rem;font-weight:700;letter-spacing:-.02em}
.stat span{color:var(--muted);font-size:.88rem}
.searchbar{display:flex;align-items:center;gap:10px;background:var(--surface);
border-radius:980px;box-shadow:var(--shadow);
padding:13px 20px;max-width:600px;margin:30px auto 0}
.searchbar svg{width:19px;height:19px;color:var(--muted);flex:none}
.searchbar input{border:0;outline:0;background:transparent;color:var(--ink);
font-size:1rem;width:100%}
h2.section{font-size:1.75rem;font-weight:700;margin:46px 0 6px;letter-spacing:-.015em}
p.section-sub{color:var(--muted);margin:0 0 18px;font-size:1.02rem}
.cards{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:12px}
.job-card{background:var(--surface);border-radius:var(--radius);
box-shadow:var(--shadow);padding:18px 20px;
display:flex;gap:15px;align-items:flex-start}
.avatar{flex:none;width:46px;height:46px;border-radius:12px;color:#fff;
font-weight:700;font-size:1.08rem;display:flex;align-items:center;justify-content:center}
.job-main{min-width:0;flex:1}
.job-title{font-weight:600;font-size:1.05rem;color:var(--ink);letter-spacing:-.01em}
.job-title:hover{color:var(--brand);text-decoration:none}
.meta{display:flex;flex-wrap:wrap;gap:6px 16px;color:var(--muted);
font-size:.9rem;margin-top:3px}
.meta .mi{display:inline-flex;align-items:center;gap:5px}
.meta svg{width:14px;height:14px;flex:none}
.badge{display:inline-flex;align-items:center;gap:4px;font-size:.76rem;font-weight:600;
padding:2px 10px;border-radius:980px}
.badge.remote{background:var(--accent-soft);color:var(--accent)}
.badge.dept{background:var(--brand-soft);color:var(--brand)}
.badge svg{width:12px;height:12px}
.chips{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:10px}
.chip{display:inline-flex;align-items:center;gap:8px;background:var(--surface);
border-radius:980px;padding:8px 15px 8px 10px;
color:var(--ink);font-weight:500;font-size:.93rem;box-shadow:var(--shadow)}
.chip:hover{text-decoration:none}
.chip .avatar{width:27px;height:27px;border-radius:8px;font-size:.82rem}
.chip .n{color:var(--muted);font-weight:400;font-size:.85rem}
.crumbs{color:var(--muted);font-size:.92rem;margin-bottom:18px}
.crumbs a{color:var(--muted)}
.job-head h1{font-size:2.15rem;line-height:1.18;font-weight:700;margin:0 0 10px;letter-spacing:-.015em}
.job-head .meta{font-size:.98rem;margin-bottom:6px}
.apply-box{background:var(--surface);border-radius:var(--radius);
box-shadow:var(--shadow);padding:22px;margin:22px 0}
.apply-box .btn{font-size:1rem;padding:12px 22px}
.summary{font-size:1.06rem;background:var(--surface);
border-radius:var(--radius);box-shadow:var(--shadow);padding:22px;margin:18px 0}
.src-note{color:var(--muted);font-size:.9rem}
.company-head{display:flex;gap:17px;align-items:center;margin-bottom:10px}
.company-head .avatar{width:60px;height:60px;border-radius:15px;font-size:1.45rem}
.company-head h1{margin:0;font-size:2rem;font-weight:700;letter-spacing:-.015em}
.company-head p{margin:2px 0 0;color:var(--muted)}
.pricing{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
gap:18px;margin:22px 0}
.price-card{background:var(--surface);border-radius:var(--radius);
box-shadow:var(--shadow);padding:26px;position:relative}
.price-card.featured{outline:2px solid var(--brand-btn);outline-offset:-2px}
.price-card .tag{position:absolute;top:-11px;left:22px;background:var(--gold-soft);
color:var(--gold);font-size:.74rem;font-weight:700;padding:2px 11px;border-radius:980px;
letter-spacing:.04em}
.price-card h3{margin:0 0 4px;font-size:1.05rem;font-weight:600}
.price-card .amount{font-size:2.1rem;font-weight:700;letter-spacing:-.02em}
.price-card .amount span{font-size:.95rem;color:var(--muted);font-weight:400}
.price-card ul{list-style:none;margin:14px 0 0;padding:0}
.price-card li{display:flex;gap:8px;padding:5px 0;color:var(--muted)}
.price-card li svg{width:16px;height:16px;color:var(--accent);flex:none;margin-top:4px}
.notice{background:var(--gold-soft);border-radius:var(--radius);padding:17px 21px;margin:22px 0}
footer.site-footer{background:var(--bg);border-top:1px solid var(--line);
margin-top:52px;padding:30px 0 36px;color:var(--muted);font-size:.86rem}
footer.site-footer .cols{display:flex;gap:40px;flex-wrap:wrap}
footer.site-footer b{color:var(--ink);display:block;margin-bottom:8px;font-weight:600}
footer.site-footer a{color:var(--muted);display:block;padding:2px 0}
footer.site-footer .fine{margin-top:22px;font-size:.8rem;color:var(--muted)}
@media (max-width:640px){.hero h1{font-size:2.15rem}.hero p.sub{font-size:1.1rem}
.site-nav a.navlink{display:none}.job-head h1{font-size:1.7rem}.stat{min-width:calc(50% - 8px)}
h2.section{font-size:1.45rem}}
"""


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
    return (f'<span class="avatar" style="background:hsl({hue} 55% 46%)" '
            f'aria-hidden="true">{esc(ch)}</span>')


def is_remote(j):
    return str(j.get("remote")).lower() == "true"


def job_card(j):
    badges = ""
    if is_remote(j):
        badges += f'<span class="badge remote">{ICON_WIFI}Remote</span>'
    if j.get("department"):
        badges += f'<span class="badge dept">{esc(j["department"])}</span>'
    date_bit = (f'<span class="mi">{ICON_CAL}{esc(j.get("posted_date", ""))}</span>'
                if j.get("posted_date") else "")
    return (
        f'<li class="job-card">{initial_avatar(j["company"])}<div class="job-main">'
        f'<a class="job-title" href="/jobs/{job_id(j["url"])}.html">{esc(j["title"])}</a>'
        f'<div class="meta"><span class="mi">{esc(j["company"])}</span>'
        f'<span class="mi">{ICON_PIN}{esc(j["location"])}</span>{date_bit}{badges}</div>'
        f"</div></li>"
    )


def company_chip(c, n):
    return (f'<li><a class="chip" href="/companies/{slugify(c)}.html">'
            f'{initial_avatar(c)}{esc(c)}<span class="n">{n}</span></a></li>')


def page(title, body, description="", extra_head=""):
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} | {SITE_NAME}</title>
<meta name="description" content="{esc(description)[:160]}">
<link rel="icon" href="{FAVICON}">
<style>{CSS}</style>{extra_head}
</head><body>
<header class="site-header"><div class="wrap">
<a class="brand" href="/">{LOGO_SVG}{SITE_NAME}</a>
<nav class="site-nav"><a class="navlink" href="/">Jobs</a><a class="navlink" href="/#companies">Companies</a><a class="btn sm" href="/post-a-job.html">Post a job</a></nav>
</div></header>
<main><div class="wrap">{body}</div></main>
<footer class="site-footer"><div class="wrap">
<div class="cols">
<div><b>{SITE_NAME}</b><a href="/">Latest jobs</a><a href="/#companies">Browse companies</a><a href="/post-a-job.html">Post a job</a></div>
<div><b>For employers</b><a href="/post-a-job.html">Pricing &amp; posting</a></div>
<div><b>About the data</b><a href="/#companies">Sources on each job page</a></div>
</div>
<p class="fine">Job summaries only; apply on the employer's site. Listings are refreshed daily from public job boards; expired postings are removed. Data sources are noted on each job page.</p>
</div></footer>
</body></html>
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
    chips = "".join(company_chip(c, len(js)) for c, js in companies_sorted)
    latest = "".join(job_card(j) for j in jobs[:100])
    index_body = f"""<div class="hero">
<h1>Find your role at an <span class="hl">AI startup</span></h1>
<p class="sub">Open roles at the world's leading AI companies, aggregated daily from official career pages. No stale listings: expired postings are removed every day.</p>
<div class="stats">
<div class="stat"><b>{total:,}</b><span>open roles</span></div>
<div class="stat"><b>{len(by_company)}</b><span>AI companies</span></div>
<div class="stat"><b>{remote_n:,}</b><span>remote roles</span></div>
<div class="stat"><b>Daily</b><span>refreshed {today}</span></div>
</div>
<div class="searchbar">{ICON_SEARCH}<input id="q" placeholder="Filter the latest jobs: try 'engineer' or 'San Francisco'" aria-label="Filter latest jobs"></div>
</div>
<h2 class="section">Latest jobs</h2>
<p class="section-sub">The 100 most recent openings. Open a company below for its full list.</p>
<ul class="cards" id="latest">{latest}</ul>
<h2 class="section" id="companies">Browse by company</h2>
<p class="section-sub">Every company on the board, with its open-role count.</p>
<ul class="chips">{chips}</ul>
<script>document.getElementById('q').addEventListener('input',e=>{{const q=e.target.value.toLowerCase();document.querySelectorAll('#latest li').forEach(li=>{{li.style.display=li.textContent.toLowerCase().includes(q)?'':'none'}})}});</script>"""
    (OUT / "index.html").write_text(page("AI Startup Jobs", index_body,
        f"{total:,} open roles at {len(by_company)} AI companies, updated daily."))

    # --- company pages ---
    for company, cjobs in companies_sorted:
        c_remote = sum(1 for j in cjobs if is_remote(j))
        body = (f'<nav class="crumbs"><a href="/">Home</a> / <a href="/#companies">Companies</a> / {esc(company)}</nav>'
                f'<div class="company-head">{initial_avatar(company)}<div>'
                f"<h1>{esc(company)}</h1>"
                f"<p>{len(cjobs)} open roles · {c_remote} remote · updated {today}</p></div></div>"
                f'<ul class="cards">' + "".join(job_card(j) for j in cjobs) + "</ul>")
        (OUT / "companies" / f"{slugify(company)}.html").write_text(
            page(f"{company} jobs", body, f"{len(cjobs)} open roles at {company}."))

    # --- job pages (programmatic SEO: company x role long tail) ---
    for j in jobs:
        jid = job_id(j["url"])
        src = SOURCE_LABEL.get(j.get("source", ""), j.get("source", ""))
        cslug = slugify(j["company"])
        meta_bits = (f'<span class="mi">{ICON_PIN}{esc(j["location"])}</span>'
                     + (f'<span class="mi">{ICON_CAL}Posted {esc(j.get("posted_date", ""))}</span>'
                        if j.get("posted_date") else "")
                     + (f'<span class="mi">{ICON_TEAM}{esc(j["department"])}</span>'
                        if j.get("department") else "")
                     + (f'<span class="badge remote">{ICON_WIFI}Remote</span>' if is_remote(j) else ""))
        summary = esc(j.get("description_summary") or "")
        summary_block = f'<div class="summary">{summary}</div>' if summary else ""
        body = (f'<nav class="crumbs"><a href="/">Home</a> / '
                f'<a href="/companies/{cslug}.html">{esc(j["company"])}</a> / {esc(j["title"])}</nav>'
                f'<div class="job-head"><h1>{esc(j["title"])}</h1>'
                f'<div class="meta">{meta_bits}</div></div>'
                f"{summary_block}"
                f'<div class="apply-box"><a class="btn" href="{esc(j["url"])}" rel="nofollow">Apply on the employer\'s site {ICON_ARROW}</a>'
                f'<p class="src-note">Source: {esc(src)}. Summary only; the full description and application are on the original posting.</p></div>'
                f'<p><a href="/companies/{cslug}.html">More jobs at {esc(j["company"])}</a></p>')
        ld = {
            "@context": "https://schema.org", "@type": "JobPosting",
            "title": j["title"], "hiringOrganization": {"@type": "Organization", "name": j["company"]},
            "jobLocation": {"@type": "Place", "address": j["location"]},
            "datePosted": j.get("posted_date", ""), "url": j["url"],
            "description": (j.get("description_summary") or "")[:280],
        }
        doc = page(f"{j['title']} at {j['company']}", body,
                   f"{j['title']} at {j['company']} ({j['location']}).",
                   extra_head=f'<script type="application/ld+json">{json.dumps(ld)}</script>')
        (OUT / "jobs" / f"{jid}.html").write_text(doc)

    # --- employer posting page (pricing only; no checkout link invented) ---
    check = ICON_CHECK
    post_body = f"""<h2 class="section" style="margin-top:6px">Post a job</h2>
<p class="section-sub">Reach job seekers browsing AI startup roles. One post runs for 30 days on the board and on your company page.</p>
<div class="pricing">
<div class="price-card"><span class="tag">EARLY BIRD</span>
<h3>Early bird</h3><div class="amount">$49 <span>/ post · 30 days</span></div>
<ul>
<li>{check}Listed alongside aggregated AI startup jobs</li>
<li>{check}Linked back to your own application page</li>
<li>{check}Live for the full 30 days</li>
</ul></div>
<div class="price-card featured">
<h3>Standard</h3><div class="amount">$299 <span>/ post · 30 days</span></div>
<ul>
<li>{check}The prevailing rate at established remote job boards</li>
<li>{check}Listed alongside aggregated AI startup jobs</li>
<li>{check}Live for the full 30 days, removed when the posting closes</li>
</ul></div>
</div>
<div class="notice"><strong>Status: paid posting opens at launch.</strong> This page currently carries pricing only: no checkout link or employer contact channel has been published yet, because the payment account and contact details are still to be confirmed at deploy time. The checkout link will be added here once payment is confirmed, before any employer is charged.</div>"""
    (OUT / "post-a-job.html").write_text(page("Post a job", post_body,
        "Post a job at an AI startup: early-bird $49, standard $299 per post for 30 days."))

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
