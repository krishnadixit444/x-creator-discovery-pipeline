import json
import os
import re
import sys
import time
from collections import Counter
sys.path.insert(0, "/Users/krishna/.gemini/antigravity/scratch/x_creator_partnerships_scraper")

from enrich_and_verify import (
    FEATS, OUT_DIR, load_cache, save_cache, run_async_safari,
    USERS_CACHE_PATH, ABOUT_CACHE_PATH, TWEETS_CACHE_PATH
)
from geo_and_filters import classify_niche, NON_US_EU_TEXT_RE, BANNED_ABOUT_COUNTRIES, US_TEXT_RE, EU_TEXT_RE
from run_pipeline import looks_like_individual_or_creator_founder

QID_ORIGINALS = "ZFKu1DFS63hgrkLzR3Hsdw"
ORIGINALS_CACHE_PATH = os.path.join(OUT_DIR, "originals_cache.json")

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

BROAD_REL_RE = re.compile(
    r"\b(ios|android|swift\w*|flutter|react\s*native|mobile|app\s*store|testflight|"
    r"app|apps|revenuecat|superwall|adapty|paywall|indie\s*(?:hacker|maker|dev)|"
    r"meta\s*ads?|facebook\s*ads?|fb\s*ads|ads|ad\s+creative|creative\s+strateg\w*|"
    r"media\s+buy\w*|paid\s+(?:social|ads|media|acquisition)|user\s+acquisition|"
    r"performance\s+marketing|tiktok\s+ads|applovin|roas|dtc|ecom\w*|mrr)\b",
    re.IGNORECASE,
)

# Extra heuristic to prioritize US/EU likely profiles over Asia/unknown when sampling
NON_US_EU_EMOJI_RE = re.compile(r"[🇮🇳🇵🇰🇧🇩🇱🇰🇳🇵🇨🇦🇦🇺🇳🇿🇸🇬🇯🇵🇰🇷🇨🇳🇭🇰🇹🇼🇦🇪🇸🇦🇳🇬🇧🇷🇲🇽🇮🇩🇵🇭🇻🇳🇹🇭]")

shortlist = []
for kl, u in merged_u.items():
    if kl in oc or kl in tc or not u.get("rest_id"):
        continue
    fc = u.get("followers") or 0
    if fc < 5000:
        continue
    if not looks_like_individual_or_creator_founder(u):
        continue
    loc = u.get("location", "")
    bio = u.get("bio", "")
    if NON_US_EU_TEXT_RE.search(loc) or NON_US_EU_TEXT_RE.search(bio) or NON_US_EU_EMOJI_RE.search(f"{loc} {bio}"):
        continue
    ab = (ac.get(kl, {}).get("account_based_in") or "").lower()
    if ab in BANNED_ABOUT_COUNTRIES:
        continue

    strict_niche = classify_niche(bio, "")
    if not strict_niche and not BROAD_REL_RE.search(bio):
        continue

    has_geo = 2 if ab else (1 if (US_TEXT_RE.search(f"{loc} {bio}") or EU_TEXT_RE.search(f"{loc} {bio}")) else 0)
    # Prioritize strong AppDev / AdsSpecialist / MetaAds + explicit US/EU geo so AboutAccountQuery yield is ~95%+
    if strict_niche == "Ads Specialist": nw = 6
    elif strict_niche == "App Developer": nw = 6
    elif strict_niche == "Meta Ads Specialist": nw = 5
    elif strict_niche == "Mobile App Developer": nw = 4
    else: nw = 1
    sweet = 1 if 5000 <= fc <= 250000 else 0
    geo_first = 1 if (has_geo and strict_niche) else (0.5 if strict_niche else 0)
    shortlist.append((geo_first, nw, has_geo, sweet, min(fc, 200000), kl, u["rest_id"], strict_niche or "broad"))

shortlist.sort(reverse=True)
print(f"Total merged users: {len(merged_u)} | Uninspected >=5k niche shortlist: {len(shortlist)}")
print("Top 210 breakdown:", Counter(x[7] for x in shortlist[:210]))

targets = [(kl, rid) for _, _, _, _, _, kl, rid, _ in shortlist[:210]]

chunk_size = 35
for i in range(0, len(targets), chunk_size):
    chunk = targets[i:i + chunk_size]
    js = f"""
    const ct0 = (document.cookie.match(/ct0=([^;]+)/) || [])[1];
    const headers = {{
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "x-csrf-token": ct0,
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session"
    }};
    const batch = {json.dumps(chunk)};
    const feats = {json.dumps(FEATS)};
    const out = {{}};
    let cursor = 0, rl = false;
    async function worker() {{
        while (cursor < batch.length && !rl) {{
            const [h, rid] = batch[cursor++];
            try {{
                const u = "https://x.com/i/api/graphql/{QID_ORIGINALS}/UserOriginalsTimeline?variables=" +
                    encodeURIComponent(JSON.stringify({{userId: rid, count: 20, includePromotedContent: false, withQuickPromoteEligibilityTweetFields: false, withVoice: true}})) +
                    "&features=" + encodeURIComponent(JSON.stringify(feats)) +
                    "&fieldToggles=" + encodeURIComponent(JSON.stringify({{withArticlePlainText: false}}));
                const r = await fetch(u, {{headers, credentials: "include"}});
                if (r.status === 429) {{ rl = true; out[h] = {{ _retry: true }}; break; }}
                if (r.status === 200) {{
                    const j = await r.json();
                    const tweets = [];
                    for (const ins of (j?.data?.user?.result?.timeline?.timeline?.instructions || [])) {{
                        const ents = ins.entries || (ins.entry ? [ins.entry] : []);
                        for (const ent of ents) {{
                            const isPinned = ent?.content?.clientEventInfo?.component === "pinned_tweets" || ent?.content?.itemContent?.socialContext?.contextType === "Pin";
                            const tr = ent?.content?.itemContent?.tweet_results?.result;
                            const tw = tr?.__typename === "TweetWithVisibilityResults" ? tr.tweet : tr;
                            if (!tw?.legacy) continue;
                            const leg = tw.legacy;
                            const fullText = tw.note_tweet?.note_tweet_results?.result?.text || leg.full_text || "";
                            tweets.push({{
                                id: tw.rest_id || leg.id_str || "",
                                created_at: leg.created_at || "",
                                is_pinned: Boolean(isPinned),
                                is_rt: Boolean(leg.retweeted_status_result) || fullText.startsWith("RT @"),
                                is_reply: Boolean(leg.in_reply_to_status_id_str),
                                views: parseInt(tw.views?.count || "0", 10) || 0,
                                fav: leg.favorite_count || 0,
                                rt: leg.retweet_count || 0,
                                rep: leg.reply_count || 0,
                                bm: leg.bookmark_count || 0,
                                text: fullText.slice(0, 320)
                            }});
                        }}
                    }}
                    out[h] = {{ tweets }};
                }} else {{
                    out[h] = {{ tweets: [], status: r.status }};
                }}
            }} catch (e) {{
                out[h] = {{ tweets: [], err: String(e) }};
            }}
            await new Promise(r => setTimeout(r, 140));
        }}
    }}
    await Promise.all([worker(), worker(), worker(), worker()]);
    window["__orig4Out"] = JSON.stringify(out);
    """
    res = run_async_safari(js, "__orig4Out", timeout_s=90)
    got_rl = False
    for k, v in res.items():
        if v.get("_retry"):
            got_rl = True
        else:
            oc[k] = v
    save_cache(ORIGINALS_CACHE_PATH, oc)
    print(f"  Batch {i//chunk_size + 1}/{(len(targets)-1)//chunk_size + 1} saved (originals_cache: {len(oc)})")
    if got_rl:
        print("  [!] Hit 429 on UserOriginalsTimeline, stopping!")
        break
print("Phase 4a complete! Total originals_cache:", len(oc))
