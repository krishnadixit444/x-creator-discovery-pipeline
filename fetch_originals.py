import json
import os
import re
import sys
import time
sys.path.insert(0, "/Users/krishna/.gemini/antigravity/scratch/x_creator_partnerships_scraper")

from enrich_and_verify import FEATS, OUT_DIR, load_cache, save_cache, run_async_safari, USERS_CACHE_PATH, ABOUT_CACHE_PATH
from geo_and_filters import classify_niche, NON_US_EU_TEXT_RE, BANNED_ABOUT_COUNTRIES, US_TEXT_RE, EU_TEXT_RE
from run_pipeline import looks_like_individual_or_creator_founder

QID_ORIGINALS = "ZFKu1DFS63hgrkLzR3Hsdw"
ORIGINALS_CACHE_PATH = os.path.join(OUT_DIR, "originals_cache.json")

# Load merged raw pools
with open(os.path.join(OUT_DIR, "raw_search_candidates.json")) as f:
    s1 = json.load(f)
raw_u = s1.get("users", {})
raw_tw = s1.get("tweets", {})

with open(os.path.join(OUT_DIR, "meta_list_candidates.json")) as f:
    meta_u = json.load(f)

with open(os.path.join(OUT_DIR, "seed_network_candidates.json")) as f:
    net_u = json.load(f)

uc = load_cache(USERS_CACHE_PATH)
ac = load_cache(ABOUT_CACHE_PATH)
oc = load_cache(ORIGINALS_CACHE_PATH)

merged = {}
for src in (raw_u, meta_u, net_u):
    for k, u in src.items():
        kl = k.lower()
        if kl not in merged or (u.get("followers", 0) > merged[kl].get("followers", 0)):
            merged[kl] = dict(u)
# Merge fresher users_cache
for kl, u in uc.items():
    if kl not in merged or (u.get("followers", 0) >= merged[kl].get("followers", 0)):
        merged[kl] = dict(u)

# Broad relevance regex to capture niche practitioners whose bio mentions apps/ios/mobile/ads/ecom/dtc/growth/building
BROAD_REL_RE = re.compile(
    r"\b(ios|android|swift\w*|flutter|react\s*native|mobile|app\s*store|testflight|"
    r"app|apps|revenuecat|superwall|adapty|paywall|indie\s*(?:hacker|maker|dev)|"
    r"meta\s*ads?|facebook\s*ads?|fb\s*ads|ads|ad\s+creative|creative\s+strateg\w*|"
    r"media\s+buy\w*|paid\s+(?:social|ads|media|acquisition)|user\s+acquisition|"
    r"performance\s+marketing|tiktok\s+ads|applovin|roas|dtc|ecom\w*|mrr|arr|built|building|saas)\b",
    re.IGNORECASE,
)

# Priority shortlist of candidates to inspect via UserOriginalsTimeline (limit ~220 calls)
shortlist = []
for kl, u in merged.items():
    if kl in oc or not u.get("rest_id"):
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

    tw_snip = "\n".join(t.get("text", "") for t in raw_tw.get(kl, []))
    strict_niche = classify_niche(bio, tw_snip)
    broad_hit = bool(BROAD_REL_RE.search(f"{bio}\n{tw_snip}"))
    if not (strict_niche or broad_hit):
        continue

    # Score for prioritization:
    # 1. Explicit US/EU location or already confirmed US/EU in about_cache
    # 2. Strict niche hit (especially Meta Ads Specialist, Ads Specialist, App Developer, Mobile App Developer)
    # 3. Sweet spot follower count (5k - 250k prioritized slightly over 1M celebrities)
    has_geo = 2 if ab else (1 if (US_TEXT_RE.search(f"{loc} {bio}") or EU_TEXT_RE.search(f"{loc} {bio}")) else 0)
    has_strict = 2 if strict_niche in ("Meta Ads Specialist", "Ads Specialist", "App Developer") else (1 if strict_niche else 0)
    sweet_spot = 1 if 5000 <= fc <= 300000 else 0
    shortlist.append((has_geo, has_strict, sweet_spot, min(fc, 250000), kl, u["rest_id"], strict_niche or "broad"))

shortlist.sort(reverse=True)
print(f"Total uncached broad/strict niche candidates >=5k & non-banned: {len(shortlist)}")
from collections import Counter
print("Top 220 breakdown by initial hint:", Counter(x[6] for x in shortlist[:220]))

targets = [(kl, rid) for _, _, _, _, kl, rid, _ in shortlist[:220]]

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
    let cursor = 0;
    let rl = false;
    async function worker() {{
        while (cursor < batch.length && !rl) {{
            const [h, rid] = batch[cursor++];
            try {{
                const u = "https://x.com/i/api/graphql/{QID_ORIGINALS}/UserOriginalsTimeline?variables=" +
                    encodeURIComponent(JSON.stringify({{
                        userId: rid,
                        count: 20,
                        includePromotedContent: false,
                        withQuickPromoteEligibilityTweetFields: false,
                        withVoice: true
                    }})) +
                    "&features=" + encodeURIComponent(JSON.stringify(feats)) +
                    "&fieldToggles=" + encodeURIComponent(JSON.stringify({{withArticlePlainText: false}}));
                const r = await fetch(u, {{ headers, credentials: "include" }});
                if (r.status === 429) {{
                    rl = true;
                    out[h] = {{ _retry: true, status: 429 }};
                    break;
                }}
                if (r.status === 200) {{
                    const j = await r.json();
                    const inst = j?.data?.user?.result?.timeline?.timeline?.instructions || [];
                    const entries = [];
                    for (const ins of inst) {{
                        if (ins.entries) entries.push(...ins.entries);
                        if (ins.entry) entries.push(ins.entry);
                    }}
                    const tweets = [];
                    for (const ent of entries) {{
                        const isPinned = ent?.content?.clientEventInfo?.component === "pinned_tweets" ||
                                         ent?.content?.itemContent?.socialContext?.contextType === "Pin";
                        const itemContents = [];
                        if (ent?.content?.itemContent) itemContents.push(ent.content.itemContent);
                        if (ent?.content?.items) {{
                            for (const sub of ent.content.items) {{
                                if (sub?.item?.itemContent) itemContents.push(sub.item.itemContent);
                            }}
                        }}
                        for (const ic of itemContents) {{
                            const tr = ic?.tweet_results?.result;
                            if (!tr) continue;
                            const tw = tr.__typename === "TweetWithVisibilityResults" ? tr.tweet : tr;
                            if (!tw?.legacy) continue;
                            const leg = tw.legacy;
                            const fullText = tw.note_tweet?.note_tweet_results?.result?.text || leg.full_text || "";
                            const isRt = Boolean(leg.retweeted_status_result) || fullText.startsWith("RT @");
                            tweets.push({{
                                id: tw.rest_id || leg.id_str || "",
                                created_at: leg.created_at || "",
                                is_pinned: Boolean(isPinned),
                                is_rt: isRt,
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
            await new Promise(r => setTimeout(r, 150));
        }}
    }}
    await Promise.all([worker(), worker(), worker(), worker()]);
    window["__origOut"] = JSON.stringify(out);
    """
    res = run_async_safari(js, "__origOut", timeout_s=90)
    got_rl = False
    for k, v in res.items():
        if v.get("_retry"):
            got_rl = True
        else:
            oc[k] = v
    save_cache(ORIGINALS_CACHE_PATH, oc)
    print(f"  Batch {i//chunk_size + 1}/{(len(targets)-1)//chunk_size + 1} saved (originals_cache: {len(oc)})")
    if got_rl:
        print("  [!] Hit 429 on UserOriginalsTimeline, stopping early!")
        break
print("Finished UserOriginalsTimeline pass! Total cached timelines:", len(oc))
