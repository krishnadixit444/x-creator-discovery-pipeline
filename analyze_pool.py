import json
import os
import sys
from collections import Counter
sys.path.insert(0, "/Users/krishna/.gemini/antigravity/scratch/x_creator_partnerships_scraper")

from enrich_and_verify import OUT_DIR, load_cache, USERS_CACHE_PATH, ABOUT_CACHE_PATH, TWEETS_CACHE_PATH
from geo_and_filters import evaluate_location, classify_niche, US_TEXT_RE, EU_TEXT_RE, NON_US_EU_TEXT_RE
from run_pipeline import evaluate_recent_reach, looks_like_individual_or_creator_founder

ORIGINALS_CACHE_PATH = os.path.join(OUT_DIR, "originals_cache.json")

with open(os.path.join(OUT_DIR, "raw_search_candidates.json")) as f:
    raw_u = json.load(f).get("users", {})
with open(os.path.join(OUT_DIR, "meta_list_candidates.json")) as f:
    meta_u = json.load(f)
with open(os.path.join(OUT_DIR, "seed_network_candidates.json")) as f:
    net_u = json.load(f)

uc = load_cache(USERS_CACHE_PATH)
ac = load_cache(ABOUT_CACHE_PATH)
tc = load_cache(TWEETS_CACHE_PATH)
oc = load_cache(ORIGINALS_CACHE_PATH)

# Build merged profile dict (latest profile metadata preferred)
merged_u = {}
for src in (raw_u, meta_u, net_u, uc):
    for k, u in src.items():
        kl = k.lower()
        if kl not in merged_u:
            merged_u[kl] = dict(u)
        else:
            # Keep richer fields
            if (u.get("followers") or 0) >= (merged_u[kl].get("followers") or 0):
                for fk, fv in u.items():
                    if fv not in ("", None, 0, []):
                        merged_u[kl][fk] = fv

# Combine tweet caches (prefer oc since it has up to 20 original tweets without RTs!)
merged_tw = {}
for kl, v in tc.items():
    if v.get("tweets"):
        merged_tw[kl] = v["tweets"]
for kl, v in oc.items():
    if v.get("tweets"):
        merged_tw[kl] = v["tweets"]

print(f"Total merged users: {len(merged_u)} | With timelines inspected: {len(merged_tw)} | About cache: {len(ac)}")

verified_with_about = []
verified_loc_needs_about = []
needs_about_no_loc = []
rejected_reasons = Counter()

seen_rids = set()
for kl, tws in merged_tw.items():
    u = merged_u.get(kl)
    if not u:
        continue
    rid = u.get("rest_id", "")
    if rid and rid in seen_rids:
        continue
    if rid:
        seen_rids.add(rid)

    fc = u.get("followers") or 0
    if fc < 5000:
        rejected_reasons["lt_5k"] += 1
        continue
    if not looks_like_individual_or_creator_founder(u):
        rejected_reasons["brand_or_bot"] += 1
        continue
    loc = u.get("location", "")
    bio = u.get("bio", "")
    if NON_US_EU_TEXT_RE.search(loc):
        rejected_reasons["banned_profile_loc"] += 1
        continue

    ok_reach, rsn, metrics = evaluate_recent_reach(u["screen_name"], fc, tws)
    if not ok_reach:
        rejected_reasons[f"reach:{rsn.split('_')[0]}"] += 1
        continue

    niche = classify_niche(bio, metrics.get("tweets_text", ""))
    if not niche:
        rejected_reasons["niche_none"] += 1
        continue

    ab = ac.get(kl, {})
    has_ab = bool(ab.get("account_based_in"))
    ok_geo, reg, geo_ev = evaluate_location(ab, loc, bio)

    entry = dict(u)
    entry["niche"] = niche
    entry["reach_metrics"] = metrics
    entry["region_label"] = reg
    entry["location_evidence"] = geo_ev
    entry["has_about"] = has_ab

    if has_ab and ok_geo:
        verified_with_about.append(entry)
    elif has_ab and not ok_geo:
        rejected_reasons[f"about_geo_reject:{reg}"] += 1
    elif not has_ab and ok_geo:
        # Profile location explicitly US/EU, AboutAccountQuery still pending
        verified_loc_needs_about.append(entry)
    else:
        # Strong creator, AboutAccountQuery needed to determine country
        needs_about_no_loc.append(entry)

print("\nRejection breakdown on inspected timelines:")
for k, v in rejected_reasons.most_common(15):
    print(f"  {k:32s}: {v}")

print(f"\n=== QUALIFYING NICHE+REACH CREATORS SUMMARY ===")
print(f"  1. Fully Verified (AboutQuery + Reach + Niche): {len(verified_with_about)}")
print(f"  2. Explicit US/EU Profile Loc (needs AboutQuery): {len(verified_loc_needs_about)}")
print(f"  3. Strong Creator (needs AboutQuery for geo):     {len(needs_about_no_loc)}")
print(f"  Total candidates passing ALL content/reach checks: {len(verified_with_about) + len(verified_loc_needs_about) + len(needs_about_no_loc)}")

print("Fully Verified Niches:", Counter(x["niche"] for x in verified_with_about))
print("ProfileLoc-Verified Niches:", Counter(x["niche"] for x in verified_loc_needs_about))
print("Unchecked-Loc Niches:", Counter(x["niche"] for x in needs_about_no_loc))

# Save queue sorted by priority for next AboutAccountQuery window!
queue = verified_loc_needs_about + needs_about_no_loc
# Prioritize missing niches (App Developer, Meta Ads Specialist, Ads Specialist) & highest organic reach!
niche_prio = {"Meta Ads Specialist": 4, "Ads Specialist": 3, "App Developer": 2, "Mobile App Developer": 1}
queue.sort(key=lambda x: (1 if x in verified_loc_needs_about else 0, niche_prio.get(x["niche"], 0), x["reach_metrics"]["median_views"]), reverse=True)

with open(os.path.join(OUT_DIR, "about_priority_queue.json"), "w") as f:
    json.dump([x["screen_name"] for x in queue], f, indent=2)
with open(os.path.join(OUT_DIR, "verified_partial.json"), "w") as f:
    json.dump(verified_with_about + verified_loc_needs_about, f, indent=2)
print("Saved about_priority_queue.json with", len(queue), "handles.")
