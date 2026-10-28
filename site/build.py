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
"""
import hashlib
import html
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "jobs.json"
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


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "company"


def job_id(url):
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def esc(s):
    return html.escape(str(s or ""), quote=True)


def job_card(j):
    remote = "Remote" if str(j.get("remote")).lower() == "true" else ""
    badge = f' <span class="badge">{remote}</span>' if remote else ""
    dept = f' · {esc(j["department"])}' if j.get("department") else ""
    return (
        f'<li><a href="/jobs/{job_id(j["url"])}.html">{esc(j["title"])}</a>'
        f"<br><span class=\"meta\">{esc(j['company'])} · {esc(j['location'])}"
        f"{dept} · {esc(j.get('posted_date', ''))}{badge}</span></li>"
    )


def page(title, body, description=""):
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} | {SITE_NAME}</title>
<meta name="description" content="{esc(description)[:160]}">
<style>body{{font-family:system-ui,sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem;line-height:1.6}}a{{color:#0b5fff}}.meta{{color:#555;font-size:.9em}}.badge{{background:#e6f0ff;border-radius:4px;padding:0 .4em;font-size:.85em}}ul{{padding-left:1.2em}}li{{margin:.5em 0}}header{{border-bottom:1px solid #ddd;padding-bottom:1rem}}footer{{border-top:1px solid #ddd;margin-top:2rem;padding-top:1rem;color:#555;font-size:.9em}}</style>
</head><body><header><a href="/">{SITE_NAME}</a> — AI startup jobs, aggregated daily. · <a href="/post-a-job.html">Post a job</a></header>
<main>{body}</main>
<footer>Job summaries only; apply on the employer's site. Listings are refreshed
daily from public job boards; expired postings are removed. Data sources are
noted on each job page.</footer></body></html>
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
    remote_n = sum(1 for j in jobs if str(j.get("remote")).lower() == "true")
    companies_sorted = sorted(by_company.items(), key=lambda kv: -len(kv[1]))

    # --- index ---
    company_links = "".join(
        f'<li><a href="/companies/{slugify(c)}.html">{esc(c)}</a> ({len(js)})</li>'
        for c, js in companies_sorted
    )
    latest = "".join(job_card(j) for j in jobs[:100])
    index_body = f"""<h1>AI Startup Jobs</h1>
<p>{total:,} open roles at {len(by_company)} AI companies. {remote_n:,} marked
remote. Updated {today}. Use your browser's find, or browse by company below.</p>
<p><a href="/post-a-job.html">Hiring at an AI startup? Post a job</a> — early-bird $49, standard $299 per post for 30 days.</p>
<p><label>Filter latest jobs: <input id="q" placeholder="e.g. engineer, San Francisco"></label></p>
<h2>Latest jobs</h2><ul id="latest">{latest}</ul>
<h2>Browse by company</h2><ul>{company_links}</ul>
<script>document.getElementById('q').addEventListener('input',e=>{{const q=e.target.value.toLowerCase();document.querySelectorAll('#latest li').forEach(li=>{{li.style.display=li.textContent.toLowerCase().includes(q)?'':'none'}})}});</script>"""
    (OUT / "index.html").write_text(page("AI Startup Jobs", index_body,
        f"{total:,} open roles at {len(by_company)} AI companies, updated daily."))

    # --- company pages ---
    for company, cjobs in companies_sorted:
        body = f"<h1>{esc(company)} jobs ({len(cjobs)})</h1><ul>" + "".join(
            job_card(j) for j in cjobs) + "</ul>"
        (OUT / "companies" / f"{slugify(company)}.html").write_text(
            page(f"{company} jobs", body, f"{len(cjobs)} open roles at {company}."))

    # --- job pages (programmatic SEO: company x role long tail) ---
    for j in jobs:
        jid = job_id(j["url"])
        src = SOURCE_LABEL.get(j.get("source", ""), j.get("source", ""))
        dept = f"<p>Team: {esc(j['department'])}</p>" if j.get("department") else ""
        remote = "<p>Workplace: Remote</p>" if str(j.get("remote")).lower() == "true" else ""
        summary = esc(j.get("description_summary") or "")
        body = (f"<h1>{esc(j['title'])}</h1>"
                f"<p><strong>{esc(j['company'])}</strong> · {esc(j['location'])} · "
                f"Posted {esc(j.get('posted_date', ''))}</p>{dept}{remote}"
                f"<p>{summary}</p>" if summary else
                f"<h1>{esc(j['title'])}</h1>"
                f"<p><strong>{esc(j['company'])}</strong> · {esc(j['location'])} · "
                f"Posted {esc(j.get('posted_date', ''))}</p>{dept}{remote}")
        body += (f'<p><a href="{esc(j["url"])}" rel="nofollow">Apply on the employer\'s '
                 f'site &rarr;</a></p><p class="meta">Source: {esc(src)}. '
                 f'Summary only; full description and application are on the original posting.</p>')
        ld = {
            "@context": "https://schema.org", "@type": "JobPosting",
            "title": j["title"], "hiringOrganization": {"@type": "Organization", "name": j["company"]},
            "jobLocation": {"@type": "Place", "address": j["location"]},
            "datePosted": j.get("posted_date", ""), "url": j["url"],
            "description": (j.get("description_summary") or "")[:280],
        }
        doc = page(f"{j['title']} at {j['company']}", body,
                   f"{j['title']} at {j['company']} ({j['location']}).")
        doc = doc.replace("</head>", f'<script type="application/ld+json">{json.dumps(ld)}</script></head>')
        (OUT / "jobs" / f"{jid}.html").write_text(doc)

    # --- employer posting page (pricing only; no checkout link invented) ---
    post_body = """<h1>Post a job</h1>
<p>Reach job seekers browsing AI startup roles. One post runs for 30 days on
the board and on your company page.</p>
<h2>Pricing</h2>
<ul>
<li><strong>Early bird — $49</strong> per post, 30 days live.</li>
<li><strong>Standard — $299</strong> per post, 30 days live (the prevailing rate
charged by established remote job boards for a 30-day listing).</li>
</ul>
<h2>What you get</h2>
<ul>
<li>Your role listed alongside aggregated AI startup jobs, with a link back to
your own application page.</li>
<li>Visibility on your company page for the full 30 days.</li>
<li>Removal when the posting closes or expires.</li>
</ul>
<p><strong>Status: paid posting opens at launch.</strong> This page currently
carries pricing only — no checkout link or employer contact channel has been
published yet, because the payment account and contact details are still to be
confirmed at deploy time. The checkout link will be added here once payment is
confirmed, before any employer is charged.</p>"""
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
