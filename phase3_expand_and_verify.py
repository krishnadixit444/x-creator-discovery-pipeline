import json
import os
import re
import sys
import time
from collections import Counter
sys.path.insert(0, "/Users/krishna/.gemini/antigravity/scratch/x_creator_partnerships_scraper")

from enrich_and_verify import (
    FEATS, OUT_DIR, load_cache, save_cache, run_async_safari,
    USERS_CACHE_PATH, ABOUT_CACHE_PATH, TWEETS_CACHE_PATH,
    QID_FOLLOWING, QID_USER_TWEETS, QID_ABOUT,
    batch_fetch_users, batch_fetch_user_tweets
)
from geo_and_filters import classify_niche, NON_US_EU_TEXT_RE, BANNED_ABOUT_COUNTRIES, US_TEXT_RE, EU_TEXT_RE, evaluate_location
from run_pipeline import looks_like_individual_or_creator_founder, evaluate_recent_reach

QID_ORIGINALS = "ZFKu1DFS63hgrkLzR3Hsdw"
ORIGINALS_CACHE_PATH = os.path.join(OUT_DIR, "originals_cache.json")
SEED_NET2_PATH = os.path.join(OUT_DIR, "seed_network_candidates2.json")

uc = load_cache(USERS_CACHE_PATH)
ac = load_cache(ABOUT_CACHE_PATH)
tc = load_cache(TWEETS_CACHE_PATH)
oc = load_cache(ORIGINALS_CACHE_PATH)

# 1. Refresh bonus_handles.json
with open(os.path.join(OUT_DIR, "bonus_handles.json")) as f:
    bonus_handles = json.load(f)
uc = batch_fetch_users(bonus_handles, uc)

# 2. Expand Following (1 page each = 14 calls out of ~445 quota) on verified niche seeds!
SEEDS = [
    ("benradack", "meta_ads"), ("drsnow", "meta_ads"), ("BingHott", "meta_ads"),
    ("itsjahmills", "meta_ads"), ("EcomMame", "meta_ads"), ("SimScaler", "ads_spec"),
    ("irabukht", "meta_ads"), ("AndrewJFaris", "meta_ads"), ("PhilKiel", "meta_ads"),
    ("SebastianRoehl", "app_dev"), ("BrettFromDJ", "app_dev"), ("jakecastilloooo", "app_dev"),
    ("malisauskasLT", "app_dev"), ("PaulSolt", "mobile_dev"), ("Dimillian", "mobile_dev"),
    ("mrousavy", "mobile_dev"), ("LaurenLabeled", "ads_spec"), ("roc" if False else "rokhladnik", "ads_spec")
]

# Merge existing to look up rest_ids
with open(os.path.join(OUT_DIR, "raw_search_candidates.json")) as f: raw_u = json.load(f).get("users", {})
with open(os.path.join(OUT_DIR, "meta_list_candidates.json")) as f: meta_u = json.load(f)
with open(os.path.join(OUT_DIR, "seed_network_candidates.json")) as f: net_u = json.load(f)

def build_merged_u():
    m = {}
    for src in (raw_u, meta_u, net_u, load_cache(SEED_NET2_PATH), uc):
        for k, u in src.items():
            kl = k.lower()
            if kl not in m:
                m[kl] = dict(u)
            else:
                if (u.get("followers") or 0) >= (m[kl].get("followers") or 0):
                    for fk, fv in u.items():
                        if fv not in ("", None, 0, []):
                            m[kl][fk] = fv
    return m

merged_u = build_merged_u()

seed_tuples = []
for h, cat in SEEDS:
    u = merged_u.get(h.lower())
    if u and u.get("rest_id"):
        seed_tuples.append((u["screen_name"], u["rest_id"], cat))

print(f"Expanding Following (1 page each) on {len(seed_tuples)} verified MetaAds/Ads/AppDev seeds...")
net2 = load_cache(SEED_NET2_PATH)
if not net2:
    batch_sz = 9
    for i in range(0, len(seed_tuples), batch_sz):
        b = seed_tuples[i:i + batch_sz]
        js = f"""
        const ct0 = (document.cookie.match(/ct0=([^;]+)/) || [])[1];
        const headers = {{
            "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "x-csrf-token": ct0,
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session"
        }};
        const batch = {json.dumps(b)};
        const feats = {json.dumps(FEATS)};
        const out = {{}};
        for (const [sh, rid, cat] of batch) {{
            try {{
                const u = "https://x.com/i/api/graphql/{QID_FOLLOWING}/Following?variables=" +
                    encodeURIComponent(JSON.stringify({{userId: rid, count: 70, includePromotedContent: false}})) +
                    "&features=" + encodeURIComponent(JSON.stringify(feats));
                const r = await fetch(u, {{headers, credentials: "include"}});
                if (r.status === 200) {{
                    const j = await r.json();
                    const list = [];
                    for (const ins of (j?.data?.user?.result?.timeline?.timeline?.instructions || [])) {{
                        for (const ent of (ins.entries || [])) {{
                            const ur = ent?.content?.itemContent?.user_results?.result;
                            if (ur && (ur.__typename === "User" || ur.rest_id)) {{
                                const sn = ur.core?.screen_name || ur.legacy?.screen_name;
                                if (sn) {{
                                    list.push({{
                                        screen_name: sn,
                                        rest_id: ur.rest_id || "",
                                        name: ur.core?.name || ur.legacy?.name || sn,
                                        followers: ur.relationship_counts?.followers ?? ur.legacy?.followers_count ?? 0,
                                        location: ur.location?.location ?? ur.legacy?.location ?? "",
                                        bio: ur.profile_bio?.description ?? ur.legacy?.description ?? "",
                                        sources: ["follow2:" + sh]
                                    }});
                                }}
                            }}
                        }}
                    }}
                    out[sh] = list;
                }}
            }} catch(e) {{}}
            await new Promise(r => setTimeout(r, 200));
        }}
        window["__net2Out"] = JSON.stringify(out);
        """
        res = run_async_safari(js, "__net2Out", timeout_s=60)
        for sh, lst in res.items():
            for u in lst:
                kl = u["screen_name"].lower()
                if kl not in net2:
                    net2[kl] = u
    save_cache(SEED_NET2_PATH, net2)
print("Total net2 peers collected:", len(net2))

merged_u = build_merged_u()

# 3. Pick top un-inspected niche candidates from the expanded pool!
BROAD_REL_RE = re.compile(
    r"\b(ios|android|swift\w*|flutter|react\s*native|mobile|app\s*store|testflight|"
    r"app|apps|revenuecat|superwall|adapty|paywall|indie\s*(?:hacker|maker|dev)|"
    r"meta\s*ads?|facebook\s*ads?|fb\s*ads|ads|ad\s+creative|creative\s+strateg\w*|"
    r"media\s+buy\w*|paid\s+(?:social|ads|media|acquisition)|user\s+acquisition|"
    r"performance\s+marketing|tiktok\s+ads|applovin|roas|dtc|ecom\w*|mrr)\b",
    re.IGNORECASE,
)

uninspected = []
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
    if NON_US_EU_TEXT_RE.search(loc) or NON_US_EU_TEXT_RE.search(bio):
        continue
    ab = (ac.get(kl, {}).get("account_based_in") or "").lower()
    if ab in BANNED_ABOUT_COUNTRIES:
        continue
    strict_niche = classify_niche(bio, "")
    if not strict_niche and not BROAD_REL_RE.search(bio):
        continue
    has_geo = 2 if ab else (1 if (US_TEXT_RE.search(f"{loc} {bio}") or EU_TEXT_RE.search(f"{loc} {bio}")) else 0)
    # Heavily prioritize explicit strict niche hits in underrepresented niches first
    niche_w = 4 if strict_niche == "Meta Ads Specialist" else (3 if strict_niche in ("Ads Specialist", "App Developer") else (2 if strict_niche else 1))
    uninspected.append((niche_w, has_geo, 1 if fc <= 250000 else 0, min(fc, 200000), kl, u["rest_id"], strict_niche or "broad"))

uninspected.sort(reverse=True)
print(f"Uninspected niche/broad >=5k candidates available: {len(uninspected)}")
print("Top 70 to inspect:", Counter(x[6] for x in uninspected[:70]))

# First try remaining UserOriginalsTimeline quota (up to 25), then use fresh UserTweets quota (up to 48)!
orig_batch = [(kl, rid) for _, _, _, _, kl, rid, _ in uninspected[:24]]
tweets_batch = [(kl, rid) for _, _, _, _, kl, rid, _ in uninspected[24:72]]

if orig_batch:
    print(f"Pulling {len(orig_batch)} via remaining UserOriginalsTimeline quota...")
    js_orig = f"""
    const ct0 = (document.cookie.match(/ct0=([^;]+)/) || [])[1];
    const headers = {{
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "x-csrf-token": ct0,
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session"
    }};
    const batch = {json.dumps(orig_batch)};
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
                if (r.status === 429) {{ rl = true; break; }}
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
                }}
            }} catch(e) {{}}
            await new Promise(r => setTimeout(r, 150));
        }}
    }}
    await Promise.all([worker(), worker(), worker()]);
    window["__orig2Out"] = JSON.stringify(out);
    """
    res_o = run_async_safari(js_orig, "__orig2Out", timeout_s=75)
    for k, v in res_o.items():
        oc[k] = v
    save_cache(ORIGINALS_CACHE_PATH, oc)
    print("  UserOriginalsTimeline added:", len(res_o), "| total oc:", len(oc))

# If any left in orig_batch failed due to 429, prepend to tweets_batch up to 48 total
still_missing = [(kl, rid) for kl, rid in (orig_batch + tweets_batch) if kl not in oc and kl not in tc][:48]
if still_missing:
    print(f"Pulling {len(still_missing)} via fresh UserTweets quota...")
    tc = batch_fetch_user_tweets(still_missing, tc)

# 4. Now re-evaluate ALL inspected timelines & pull up to 48 fresh AboutAccountQuery verifications!
merged_tw = {}
for kl, v in tc.items():
    if v.get("tweets"): merged_tw[kl] = v["tweets"]
for kl, v in oc.items():
    if v.get("tweets"): merged_tw[kl] = v["tweets"]

qualifiers = []
for kl, tws in merged_tw.items():
    u = merged_u.get(kl)
    if not u or (u.get("followers") or 0) < 5000 or not looks_like_individual_or_creator_founder(u):
        continue
    if NON_US_EU_TEXT_RE.search(u.get("location", "")):
        continue
    ok_r, rsn, m = evaluate_recent_reach(u["screen_name"], u["followers"], tws)
    if not ok_r: continue
    niche = classify_niche(u.get("bio", ""), m["tweets_text"])
    if not niche: continue
    qualifiers.append((kl, u, niche, m))

print(f"\nTotal timelines inspected: {len(merged_tw)} -> Qualifying reach+niche creators: {len(qualifiers)}")
print("Qualifiers Niche Breakdown:", Counter(q[2] for q in qualifiers))

# Pick top 49 qualifying handles NOT yet in about_cache (prioritize Meta Ads, Ads Specialist, App Dev, Explicit Loc + high reach)
need_about = []
for kl, u, niche, m in qualifiers:
    if kl not in ac:
        has_loc = 1 if (US_TEXT_RE.search(u.get("location","")) or EU_TEXT_RE.search(u.get("location",""))) else 0
        nw = 4 if niche == "Meta Ads Specialist" else (3 if niche == "Ads Specialist" else (2 if niche == "App Developer" else 1))
        need_about.append((has_loc, nw, m["median_views"], u["screen_name"], kl))

need_about.sort(reverse=True)
about_batch = [sn for _, _, _, sn, _ in need_about[:49]]
if about_batch:
    print(f"Fetching fresh AboutAccountQuery for {len(about_batch)} qualifying creators...")
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
    window["__ab2Out"] = JSON.stringify(out);
    """
    res_ab = run_async_safari(js_ab, "__ab2Out", timeout_s=90)
    for k, v in res_ab.items():
        ac[k] = v
    save_cache(ABOUT_CACHE_PATH, ac)
    print(f"Saved {len(res_ab)} new AboutAccountQuery results! Total about_cache: {len(ac)}")

print("PHASE 3 COMPLETE!")
