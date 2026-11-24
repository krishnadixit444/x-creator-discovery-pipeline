import json
import os
import re
import statistics
from datetime import datetime, timezone
from geo_and_filters import evaluate_location, count_bait_tweets, classify_niche
from enrich_and_verify import (
    OUT_DIR, ABOUT_CACHE_PATH, TWEETS_CACHE_PATH, USERS_CACHE_PATH,
    load_cache, batch_fetch_users, batch_fetch_about, batch_fetch_user_tweets
)

RAW_SEARCH_PATH = os.path.join(OUT_DIR, "raw_search_candidates.json")
SEED_NET_PATH = os.path.join(OUT_DIR, "seed_network_candidates.json")
VERIFIED_OUT_PATH = os.path.join(OUT_DIR, "verified_pool.json")
AUDIT_OUT_PATH = os.path.join(OUT_DIR, "audit_stats.json")

NOW = datetime(2026, 11, 10, 18, 0, 0, tzinfo=timezone.utc)

# Faceless corporate brands / official product accounts / news bots / job boards to exclude
BRAND_OR_BOT_HANDLE_RE = re.compile(
    r"^(apple|google|meta|facebook|microsoft|openai|anthropic|claudeai|github|"
    r"revenuecat|superwall|reactnative|flutterdev|swiftlang|expo|xcode|androiddev|"
    r"triplewhale|motionapp|foreplay|atria|hyros|northbeam|appsflyer|adjust|"
    r"singular|branch|appfigures|sensortower|dataai|mobileaction|"
    r"indiehackers|producthunt|techcrunch|theverge|macrumors|9to5mac|androidpolice|"
    r"soshalsapp|metaforbusiness|tiktokforbusiness|googleads|"
    r"rork|rork_app|starter_story|cognition|higgsfield|higgsfield_ai|payward|vercel|"
    r"openaidevs|claudedevs|letterboxd|openclaw|shipper_now|vibecodeapp|openmarket_xyz|"
    r"usefastlane|arcads_ai|nativescript|appstoretracker|ios_app_builder|bitrig|"
    r"swmansion|dodopayments|hyperframes_|paradevai|streetsforall|bubble|twin_labs|"
    r"lightreelai|svishnevskiy|feedthejim|tobiadonadon_|bkashjosi|herreraevel|"
    r"_kavsoft|stacy_siz|everton_dev|mannybarbas_|lifemaximised|agills|pbteja1998|chronotope|"
    r"ramaswmysridhar|mgorbach|theflutterway|adtechgod|irfansenercom|ikoichi|screenshotfirst|"
    r"caffeineai|seyong|trymirage|fomo|collect|trendtrack_io|meshyai|paybox)$",
    re.IGNORECASE,
)

BRAND_BIO_RE = re.compile(
    r"\b(official\s+(twitter|x|account)\s+(of|for)|customer\s+support|help\s+center|"
    r"status\s+updates|breaking\s+tech\s+news|daily\s+job\s+postings|we\s+are\s+hiring\s+board|"
    r"automated\s+bot|curated\s+bot|newsletter\s+bot)\b",
    re.IGNORECASE,
)


def parse_dt(created_at_str: str):
    if not created_at_str:
        return None
    try:
        return datetime.strptime(created_at_str, "%a %b %d %H:%M:%S %z %Y")
    except Exception:
        return None


def looks_like_individual_or_creator_founder(u: dict) -> bool:
    sn = (u.get("screen_name") or "").lower()
    name = (u.get("name") or "")
    bio = (u.get("bio") or "")
    if BRAND_OR_BOT_HANDLE_RE.match(sn):
        return False
    if BRAND_BIO_RE.search(bio):
        return False
    # Exclude obvious faceless SaaS brands unless bio has founder/creator/personal pronouns ("I ", "my ", "founder", "building", "creator", "strategist", "developer")
    personal_signals = re.search(
        r"\b(i['’]?m|i\s+|my\s+|building|built|founder|co-founder|cofounder|indie|maker|"
        r"developer|engineer|strategist|buyer|specialist|creator|freelancer|consultant|"
        r"husband|wife|dad|mom|father|mother|he/him|she/her|they/them)\b",
        f"{name} {bio}",
        re.IGNORECASE,
    )
    brand_signals = re.search(
        r"\b(inc\.|llc|gmbh|ltd\.|official\s+account|pricing\s+starts|book\s+a\s+demo|"
        r"enterprise\s+platform|trusted\s+by\s+\d+|platform\s+for\s+teams|join\s+thousands\s+of\s+teams)\b",
        bio,
        re.IGNORECASE,
    )
    if brand_signals and not personal_signals:
        return False
    return True


def fmt_k(n: float) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(int(round(n)))


def evaluate_recent_reach(screen_name: str, followers: int, tweets: list):
    """
    Evaluates chronological non-pinned root original posts for recency, cadence,
    organic views, engagement, and anti-bait quality.
    """
    parsed = []
    for t in tweets:
        if t.get("is_rt") or t.get("is_pinned"):
            continue
        dt = parse_dt(t.get("created_at", ""))
        if not dt:
            continue
        age_days = (NOW - dt).total_seconds() / 86400.0
        t_copy = dict(t)
        t_copy["dt"] = dt
        t_copy["age_days"] = age_days
        parsed.append(t_copy)

    parsed.sort(key=lambda x: x["dt"], reverse=True)

    # Prefer root original posts (non-replies)
    root_posts = [t for t in parsed if not t.get("is_reply")]
    if len(root_posts) < 3:
        return False, "too_few_root_posts", {}

    latest_age = root_posts[0]["age_days"]
    if latest_age > 25:
        return False, f"inactive_latest_{latest_age:.0f}d", {}

    recent_45d = [t for t in root_posts if t["age_days"] <= 45]
    if len(recent_45d) < 3:
        return False, f"low_cadence_45d_{len(recent_45d)}", {}

    # Sample up to latest 12 chronological root posts (within 60d, fallback to latest 8 root posts if sparse)
    sample = [t for t in root_posts if t["age_days"] <= 60][:12]
    if len(sample) < 3:
        sample = root_posts[:6]

    bait_count = count_bait_tweets([t.get("text", "") for t in sample])
    if bait_count >= 3 or (len(sample) > 0 and bait_count / len(sample) >= 0.30):
        return False, f"engagement_bait_{bait_count}/{len(sample)}", {}

    views_list = [t["views"] for t in sample if t["views"] > 0]
    if len(views_list) < 3:
        return False, "insufficient_view_counts", {}

    med_views = statistics.median(views_list)
    avg_views = statistics.mean(views_list)
    avg_likes = statistics.mean(t["fav"] for t in sample)
    avg_replies = statistics.mean(t["rep"] for t in sample)
    avg_reposts = statistics.mean(t["rt"] for t in sample)
    avg_bookmarks = statistics.mean(t["bm"] for t in sample)

    # Healthy organic reach threshold: reject dead feeds & inflated follower mismatch
    if med_views < 1000 and avg_views < 1500:
        return False, f"low_reach_med_{int(med_views)}", {}
    if avg_likes < 8:
        return False, f"low_likes_avg_{avg_likes:.1f}", {}
    if followers >= 50000 and med_views < 1800 and avg_likes < 25:
        return False, f"dead_audience_{followers}_vs_{int(med_views)}v", {}

    # Pick best recent sample post (non-pinned, latest 45d, good views)
    best_sample = max(sample, key=lambda t: (t["views"] + t["fav"] * 20))
    d_min = min(t["dt"] for t in sample).strftime("%b %d")
    d_max = max(t["dt"] for t in sample).strftime("%b %d")
    sample_url = f"https://x.com/{screen_name}/status/{best_sample['id']}"

    eng_rate = ((avg_likes + avg_replies + avg_reposts) / max(1.0, avg_views)) * 100.0
    evidence = (
        f"{len(sample)} orig posts ({d_min}–{d_max}): median {fmt_k(med_views)} views "
        f"(avg {fmt_k(avg_views)}), avg {avg_likes:.0f} likes / {avg_replies:.0f} replies / "
        f"{avg_bookmarks:.0f} bookmarks ({eng_rate:.2f}% ER); sample: {sample_url}"
    )

    metrics = {
        "sample_count": len(sample),
        "posts_45d": len(recent_45d),
        "latest_post_date": root_posts[0]["dt"].strftime("%Y-%m-%d"),
        "median_views": int(round(med_views)),
        "avg_views": int(round(avg_views)),
        "avg_likes": round(avg_likes, 1),
        "avg_replies": round(avg_replies, 1),
        "avg_reposts": round(avg_reposts, 1),
        "avg_bookmarks": round(avg_bookmarks, 1),
        "sample_post_url": sample_url,
        "sample_post_snippet": re.sub(r"\s+", " ", best_sample.get("text", "")).strip()[:120],
        "reach_evidence": evidence,
        "tweets_text": "\n".join(t.get("text", "") for t in sample),
    }
    return True, "OK", metrics


def load_all_raw_candidates() -> dict:
    pool = {}
    if os.path.exists(RAW_SEARCH_PATH):
        with open(RAW_SEARCH_PATH) as f:
            d = json.load(f)
        for k, u in d.get("users", {}).items():
            pool[k.lower()] = u
    if os.path.exists(SEED_NET_PATH):
        with open(SEED_NET_PATH) as f:
            d = json.load(f)
        for k, u in d.items():
            kl = k.lower()
            if kl not in pool:
                pool[kl] = u
            else:
                pool[kl].setdefault("sources", [])
                for s in u.get("sources", []):
                    if s not in pool[kl]["sources"]:
                        pool[kl]["sources"].append(s)
    return pool


def run_verification_pass():
    raw_pool = load_all_raw_candidates()
    print(f"Total raw unique candidates loaded: {len(raw_pool)}")

    users_cache = load_cache(USERS_CACHE_PATH)
    about_cache = load_cache(ABOUT_CACHE_PATH)
    tweets_cache = load_cache(TWEETS_CACHE_PATH)

    # Pre-filter out obvious sub-4k handles when follower count already known > 0, refresh all missing or >= 4500
    to_refresh = []
    for k, u in raw_pool.items():
        fc = u.get("followers") or 0
        if fc == 0 or fc >= 4500:
            to_refresh.append(u.get("screen_name") or k)

    print(f"Handles with unknown or >= 4,500 followers to inspect: {len(to_refresh)}")
    users_cache = batch_fetch_users(to_refresh, users_cache)

    # Step 2: Filter >= 5,000 followers & individual creator heuristic & preliminary niche relevance
    stats = {
        "raw_total": len(raw_pool),
        "lt_5k": 0,
        "brand_or_bot": 0,
        "geo_rejected": 0,
        "geo_ambiguous_or_unknown": 0,
        "no_tweets_or_api": 0,
        "niche_mismatch": 0,
        "reach_or_activity_rejected": 0,
        "bait_rejected": 0,
        "passed": 0,
    }

    eligible_5k = []
    seen_rest_ids = set()
    for k in sorted(to_refresh):
        kl = k.lower()
        u = users_cache.get(kl)
        if not u:
            continue
        rid = u.get("rest_id", "")
        if rid and rid in seen_rest_ids:
            continue
        if rid:
            seen_rest_ids.add(rid)

        fc = u.get("followers") or 0
        if fc < 5000:
            stats["lt_5k"] += 1
            continue
        if not looks_like_individual_or_creator_founder(u):
            stats["brand_or_bot"] += 1
            continue
        # Quick pre-check: check if bio OR search tweet hints relevance OR verify after tweets if came from high-signal search
        eligible_5k.append(u)

    print(f"Candidates >= 5,000 followers & personal/creator-led: {len(eligible_5k)}")

    # Step 3: Batch AboutAccountQuery for all >= 5k candidates
    about_cache = batch_fetch_about([u["screen_name"] for u in eligible_5k], about_cache)

    # Filter strictly to US or Europe
    us_eu_candidates = []
    for u in eligible_5k:
        kl = u["screen_name"].lower()
        ab = about_cache.get(kl, {})
        ok_geo, region_label, geo_ev = evaluate_location(ab, u.get("location", ""), u.get("bio", ""))
        if not ok_geo:
            if region_label == "REJECT":
                stats["geo_rejected"] += 1
            else:
                stats["geo_ambiguous_or_unknown"] += 1
            continue
        u_copy = dict(u)
        u_copy["region_label"] = region_label
        u_copy["location_evidence"] = geo_ev
        u_copy["about_info"] = ab
        us_eu_candidates.append(u_copy)

    print(f"Confirmed US or Europe (>= 5k followers): {len(us_eu_candidates)}")

    # Step 4: Batch UserTweets for ALL US/Europe >= 5k candidates
    tweet_targets = [(u["screen_name"].lower(), u["rest_id"]) for u in us_eu_candidates]
    tweets_cache = batch_fetch_user_tweets(tweet_targets, tweets_cache)

    # Step 5: Evaluate niche + recent-post organic reach + engagement-bait filter
    verified = []
    for u in us_eu_candidates:
        kl = u["screen_name"].lower()
        tw_entry = tweets_cache.get(kl, {})
        tweets = tw_entry.get("tweets", [])
        if not tweets:
            stats["no_tweets_or_api"] += 1
            continue

        ok_reach, reason, metrics = evaluate_recent_reach(u["screen_name"], u["followers"], tweets)
        if not ok_reach:
            if reason.startswith("engagement_bait"):
                stats["bait_rejected"] += 1
            else:
                stats["reach_or_activity_rejected"] += 1
            continue

        niche = classify_niche(u.get("bio", ""), metrics.get("tweets_text", ""))
        if not niche:
            stats["niche_mismatch"] += 1
            continue

        u["niche"] = niche
        u["reach_metrics"] = metrics
        verified.append(u)

    stats["passed"] = len(verified)
    verified.sort(key=lambda x: (x["reach_metrics"]["median_views"], x["followers"]), reverse=True)

    with open(VERIFIED_OUT_PATH, "w") as f:
        json.dump(verified, f, indent=2)
    with open(AUDIT_OUT_PATH, "w") as f:
        json.dump(stats, f, indent=2)

    print("\n=== AUDIT STATS ===")
    for sk, sv in stats.items():
        print(f"  {sk:28s}: {sv}")

    from collections import Counter
    print("\n=== VERIFIED BY NICHE ===")
    print(Counter(v["niche"] for v in verified))
    print("\n=== VERIFIED BY REGION ===")
    print(Counter(v["region_label"] for v in verified))


if __name__ == "__main__":
    run_verification_pass()
