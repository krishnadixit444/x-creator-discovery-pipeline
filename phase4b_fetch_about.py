import json
import os
import re
import sys
import time
from collections import Counter
sys.path.insert(0, "/Users/krishna/.gemini/antigravity/scratch/x_creator_partnerships_scraper")

from enrich_and_verify import (
    OUT_DIR, load_cache, save_cache, run_async_safari,
    USERS_CACHE_PATH, ABOUT_CACHE_PATH, TWEETS_CACHE_PATH, QID_ABOUT
)
from geo_and_filters import evaluate_location, classify_niche, NON_US_EU_TEXT_RE, US_TEXT_RE, EU_TEXT_RE
from run_pipeline import evaluate_recent_reach, looks_like_individual_or_creator_founder

ORIGINALS_CACHE_PATH = os.path.join(OUT_DIR, "originals_cache.json")
NON_US_EU_EMOJI_RE = re.compile(r"[🇮🇳🇵🇰🇧🇩🇱🇰🇳🇵🇨🇦🇦🇺🇳🇿🇸🇬🇯🇵🇰🇷🇨🇳🇭🇰🇹🇼🇦🇪🇸🇦🇳🇬🇧🇷🇲🇽🇮🇩🇵🇭🇻🇳🇹🇭]")

with open(os.path.join(OUT_DIR, "raw_search_candidates.json")) as f: raw_u = json.load(f).get("users", {})
with open(os.path.join(OUT_DIR, "meta_list_candidates.json")) as f: meta_u = json.load(f)
with open(os.path.join(OUT_DIR, "seed_network_candidates.json")) as f: net1_u = json.load(f)
net2_u = load_cache(os.path.join(OUT_DIR, "seed_network_candidates2.json"))
net3_u = load_cache(os.path.join(OUT_DIR, "seed_network_candidates3.json"))
net4_u = load_cache(os.path.join(OUT_DIR, "seed_network_candidates4.json"))
net5_u = load_cache(os.path.join(OUT_DIR, "seed_network_candidates5.json"))

uc = load_cache(USERS_CACHE_PATH)
ac = load_cache(ABOUT_CACHE_PATH)
tc = load_cache(TWEETS_CACHE_PATH)
oc = load_cache(ORIGINALS_CACHE_PATH)

merged_u = {}
for src in (raw_u, meta_u, net1_u, net2_u, net3_u, net4_u, net5_u, uc):
    for k, u in src.items():
        kl = k.lower()
        if kl not in merged_u:
            merged_u[kl] = dict(u)
        elif (u.get("followers") or 0) >= (merged_u[kl].get("followers") or 0):
            for fk, fv in u.items():
                if fv not in ("", None, 0, []):
                    merged_u[kl][fk] = fv

merged_tw = {}
for kl, v in tc.items():
    if v.get("tweets"): merged_tw[kl] = v["tweets"]
for kl, v in oc.items():
    if v.get("tweets"): merged_tw[kl] = v["tweets"]

qualifiers = []
seen_rids = set()
for kl, tws in merged_tw.items():
    u = merged_u.get(kl)
    if not u or (u.get("followers") or 0) < 5000 or not looks_like_individual_or_creator_founder(u):
        continue
    rid = u.get("rest_id", "")
    if rid and rid in seen_rids: continue
    if rid: seen_rids.add(rid)
    loc, bio = u.get("location", ""), u.get("bio", "")
    if NON_US_EU_TEXT_RE.search(loc): continue
    ok_r, rsn, m = evaluate_recent_reach(u["screen_name"], u["followers"], tws)
    if not ok_r: continue
    niche = classify_niche(bio, m["tweets_text"])
    if not niche and kl != "jackfriks": continue
    if not niche and kl == "jackfriks": niche = "App Developer"
    qualifiers.append((kl, u, niche, m))

already_verified = []
need_about = []
for kl, u, niche, m in qualifiers:
    ab = ac.get(kl, {})
    if ab.get("account_based_in"):
        ok_g, reg, geo_ev = evaluate_location(ab, u.get("location", ""), u.get("bio", ""))
        if ok_g:
            e = dict(u)
            e.update({"niche": niche, "reach_metrics": m, "region_label": reg, "location_evidence": geo_ev, "about_info": ab})
            already_verified.append(e)
    else:
        loc, bio = u.get("location", ""), u.get("bio", "")
        if NON_US_EU_TEXT_RE.search(bio) or NON_US_EU_EMOJI_RE.search(f"{loc} {bio}"):
            continue
        has_us_eu = 1 if (US_TEXT_RE.search(f"{loc} {bio}") or EU_TEXT_RE.search(f"{loc} {bio}")) else 0
        # Exclude borderline/ambiguous/off-geo handles from precious Top 50 AboutAccountQuery batch
        if kl in ("solotechdev", "mcflydev", "hieudinh_", "learn2vibecode", "andilosing", "jorgiabays", "ecomrickys", "jakeclaychain", "mustafa01ali", "ricketson_"):
            continue
        # Prioritize Meta Ads, Ads Specialist & App Dev + explicit US/EU geo, ranking by median_views
        nw = 9 if niche in ("Meta Ads Specialist", "Ads Specialist") else (8 if niche == "App Developer" else 5)
        known_eu_us_txt = 1 if (has_us_eu or re.search(r"(£|\bparis\b|\bobvi\b|\blos angeles\b)", f"{bio} {m.get('tweets_text','')}", re.IGNORECASE)) else 0
        need_about.append((nw, known_eu_us_txt, min(m["median_views"], 50000), u["screen_name"], kl))

need_about.sort(reverse=True)
print(f"Already AboutQuery verified & qualifying: {len(already_verified)} | Needs AboutQuery: {len(need_about)}")
print("Already Verified Niches:", Counter(x["niche"] for x in already_verified))
print("Top 50 to fetch AboutQuery for:", Counter(niche for kl, u, niche, m in qualifiers if u["screen_name"] in {x[3] for x in need_about[:50]}))

about_batch = [sn for _, _, _, sn, _ in need_about[:50]]
if about_batch:
    print(f"Fetching fresh AboutAccountQuery for top {len(about_batch)} US/EU likely qualifiers...")
    js_ab = f"""
    const ct0 = (document.cookie.match(/ct0=([^;]+)/) || [])[1];
    const headers = {{
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "x-csrf-token": ct0,
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session"
    }};
    const batch = {json.dumps(about_batch)};
    const out = {{}};
    let cursor = 0, rl = false;
    async function worker() {{
        while (cursor < batch.length && !rl) {{
            const h = batch[cursor++];
            try {{
                const u = "https://x.com/i/api/graphql/{QID_ABOUT}/AboutAccountQuery?variables=" +
                    encodeURIComponent(JSON.stringify({{screenName: h}}));
                const r = await fetch(u, {{headers, credentials: "include"}});
                if (r.status === 429) {{ rl = true; break; }}
                if (r.status === 200) {{
                    const j = await r.json();
                    const ap = j?.data?.user_result_by_screen_name?.result?.about_profile || {{}};
                    out[h.toLowerCase()] = {{
                        account_based_in: ap.account_based_in || "",
                        source: ap.source || "",
                        location_accurate: ap.location_accurate
                    }};
                }}
            }} catch(e) {{}}
            await new Promise(r => setTimeout(r, 140));
        }}
    }}
    await Promise.all([worker(), worker(), worker()]);
    window["__ab4Out"] = JSON.stringify(out);
    """
    res_ab = run_async_safari(js_ab, "__ab4Out", timeout_s=90)
    for k, v in res_ab.items():
        ac[k] = v
    save_cache(ABOUT_CACHE_PATH, ac)
    print(f"Saved {len(res_ab)} new AboutAccountQuery results! Total about_cache: {len(ac)}")

# Rebuild full AboutQuery-verified roster!
final_list = []
for kl, u, niche, m in qualifiers:
    ab = ac.get(kl, {})
    if ab.get("account_based_in"):
        ok_g, reg, geo_ev = evaluate_location(ab, u.get("location", ""), u.get("bio", ""))
        if ok_g:
            e = dict(u)
            e.update({"niche": niche, "reach_metrics": m, "region_label": reg, "location_evidence": geo_ev, "about_info": ab})
            final_list.append(e)

final_list.sort(key=lambda x: (x["reach_metrics"]["median_views"], x["followers"]), reverse=True)
with open(os.path.join(OUT_DIR, "verified_pool_all.json"), "w") as f:
    json.dump(final_list, f, indent=2)

print(f"\n=== FINAL 100% ABOUTQUERY-VERIFIED COUNT: {len(final_list)} ===")
print("Final Niches:", Counter(x["niche"] for x in final_list))
print("Final Regions:", Counter("US" if x["region_label"] == "US" else "Europe" for x in final_list))
