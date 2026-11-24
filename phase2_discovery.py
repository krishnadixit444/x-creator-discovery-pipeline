import json
import os
import sys
import time
import subprocess
sys.path.insert(0, "/Users/krishna/.gemini/antigravity/scratch/x_creator_partnerships_scraper")

from enrich_and_verify import OUT_DIR, load_cache, USERS_CACHE_PATH, batch_fetch_users
from expand_network import fetch_following_for_seeds
from geo_and_filters import classify_niche, NON_US_EU_TEXT_RE, US_TEXT_RE, EU_TEXT_RE
from run_pipeline import looks_like_individual_or_creator_founder

uc = load_cache(USERS_CACHE_PATH)

# 1. Pick high-signal seeds across all 4 niches (with rest_ids in uc)
SEED_PREFS = [
    # Mobile App Developers (US & EU)
    ("StevenCravotta", "mobile_dev"),
    ("MichaelFilipiuk", "mobile_dev"),
    ("ios_dev_alb", "mobile_dev"),
    ("yasinaktimur", "mobile_dev"),
    ("alex_barashkov", "mobile_dev"),
    ("marcelkargul", "mobile_dev"),
    # App Developers (US & EU)
    ("ErnestoSOFTWARE", "app_dev"),
    ("levelsio", "app_dev"),
    ("jackfriks", "app_dev"),
    ("rileybrown", "app_dev"),
    ("davidondrej1", "app_dev"),
    ("marc_louvion", "app_dev"),
    # Meta Ads Specialists (US & EU)
    ("zackpaid", "meta_ads"),
    ("iamshackelford", "meta_ads"),
    ("social_savannah", "meta_ads"),
    ("herrmanndigital", "meta_ads"),
    ("codyplof", "meta_ads"),
    ("lorenzo_pravata", "meta_ads"),
    ("IstvanicMarin", "meta_ads"),
    ("TaylorHoliday", "meta_ads"),
    # Ads / UA / Creative Strategy Specialists (US & EU)
    ("eric_seufert", "ads_spec"),
    ("DenneyDara", "ads_spec"),
    ("sourfraser", "ads_spec"),
    ("SarahLevinger", "ads_spec"),
    ("TobyWalleruk", "ads_spec"),
    ("ashvinmelwani", "ads_spec"),
]

# Refresh any missing seed users first
missing_seeds = [h for h, _ in SEED_PREFS if h.lower() not in uc]
if missing_seeds:
    uc = batch_fetch_users(missing_seeds, uc)

seeds = []
for h, cat in SEED_PREFS:
    u = uc.get(h.lower())
    if u and u.get("rest_id"):
        seeds.append((u["screen_name"], u["rest_id"], cat))

print(f"Running Following expansion for {len(seeds)} seeds (uses ~{len(seeds)*2} out of 500 quota)...")
net_cands = fetch_following_for_seeds(seeds, pages_per_seed=2)
print("Total unique accounts from seed Following graphs:", len(net_cands))

# 2. Additional targeted SearchTimeline queries focusing on App Developers, European devs/marketers, and Ads Specialists
def safari_js(js: str) -> str:
    cmd = f'tell application "Safari" to do JavaScript {json.dumps(js)} in tab 1 of window 1'
    p = subprocess.run(['osascript', '-'], input=cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip())
    return p.stdout.strip()

def safari_nav(url: str):
    subprocess.run(
        ['osascript', '-e', f'tell application "Safari" to set URL of tab 1 of window 1 to {json.dumps(url)}'],
        check=True
    )

EXTRA_SEARCH_PATH = os.path.join(OUT_DIR, "raw_search_extra.json")

INSTALL_HOOK_JS = """
(function() {
    window.__capturedUsers2 = window.__capturedUsers2 || {};
    window.__capturedTweets2 = window.__capturedTweets2 || {};
    window.__searchResponses2 = window.__searchResponses2 || 0;
    if (!window.__xhrSearchHook2) {
        window.__xhrSearchHook2 = true;
        const origSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send = function() {
            this.addEventListener("load", function() {
                try {
                    if (this.responseURL && this.responseURL.includes("SearchTimeline") && this.status === 200) {
                        window.__searchResponses2++;
                        const data = JSON.parse(this.responseText);
                        (function walk(obj) {
                            if (!obj || typeof obj !== "object") return;
                            if (obj.__typename === "User" && (obj.rest_id || obj.id)) {
                                const sn = obj.core?.screen_name || obj.legacy?.screen_name;
                                if (sn) {
                                    const key = sn.toLowerCase();
                                    const followers = obj.relationship_counts?.followers ?? obj.legacy?.followers_count ?? 0;
                                    const existing = window.__capturedUsers2[key] || {};
                                    window.__capturedUsers2[key] = {
                                        screen_name: sn,
                                        rest_id: obj.rest_id || existing.rest_id || "",
                                        name: obj.core?.name || obj.legacy?.name || existing.name || "",
                                        followers: followers || existing.followers || 0,
                                        location: obj.location?.location ?? obj.legacy?.location ?? existing.location ?? "",
                                        bio: obj.profile_bio?.description ?? obj.legacy?.description ?? existing.bio ?? "",
                                        is_blue_verified: obj.is_blue_verified ?? existing.is_blue_verified ?? false,
                                        sources: Array.from(new Set([...(existing.sources || []), window.__currentQueryLabel2 || "search2"]))
                                    };
                                }
                            }
                            if (obj.__typename === "Tweet" && obj.legacy) {
                                const ur = obj.core?.user_results?.result;
                                const sn = ur?.core?.screen_name || ur?.legacy?.screen_name;
                                const tid = obj.rest_id || obj.legacy.id_str;
                                if (sn && tid) {
                                    const key = sn.toLowerCase();
                                    if (!window.__capturedTweets2[key]) window.__capturedTweets2[key] = [];
                                    if (window.__capturedTweets2[key].length < 5) {
                                        window.__capturedTweets2[key].push({
                                            id: tid,
                                            created_at: obj.legacy.created_at || "",
                                            views: obj.views?.count || "0",
                                            fav: obj.legacy.favorite_count || 0,
                                            text: (obj.legacy.full_text || "").slice(0, 220)
                                        });
                                    }
                                }
                            }
                            for (const k of Object.keys(obj)) walk(obj[k]);
                        })(data);
                    }
                } catch (e) {}
            });
            return origSend.apply(this, arguments);
        };
    }
    return "HOOK2_READY";
})()
"""

print("\nLaunching Phase 2 targeted SearchTimeline queries...")
safari_nav("https://x.com/search?q=consumer%20app&src=typed_query&f=top")
time.sleep(3.5)
safari_js(INSTALL_HOOK_JS)

EXTRA_PLAN = [
    ("app_dev_eu", '("indie app" OR "built an app" OR "launched my app") (london OR berlin OR paris OR amsterdam OR europe OR uk) min_faves:8', ["Top"], 1),
    ("app_dev_us", '("consumer app" OR "app studio" OR "vibecoding") ("ios" OR "mrr" OR "downloads" OR "users") min_faves:15', ["Top"], 2),
    ("app_dev_bio", 'building apps founder', ["People"], 2),
    ("app_dev_indie", 'indie maker apps', ["People"], 2),
    ("mobile_eu", '("ios app" OR "swiftui" OR "react native") (london OR uk OR berlin OR paris OR amsterdam OR europe) min_faves:8', ["Top"], 1),
    ("mobile_android", '("android app" OR "kotlin" OR "flutter") ("play store" OR "mrr" OR "downloads") min_faves:10', ["Top"], 2),
    ("meta_ads_eu", '("meta ads" OR "facebook ads") (uk OR london OR europe OR germany OR netherlands OR spain) min_faves:8', ["Top"], 1),
    ("ads_tiktok", '("tiktok ads" OR "applovin" OR "paid user acquisition") ("mobile app" OR "roas" OR "cpi" OR "cac") min_faves:8', ["Top"], 2),
    ("ads_creative", '("ad creative" OR "static ads" OR "ugc ads") ("meta ads" OR "hook rate" OR "creative testing") min_faves:12', ["Top"], 2),
    ("ads_ua_people", 'user acquisition app', ["People"], 1),
]

for idx, (label, q, tabs, scrolls) in enumerate(EXTRA_PLAN, 1):
    submit_js = f"""
    (function() {{
        window.__currentQueryLabel2 = {json.dumps(label)};
        const input = document.querySelector('input[data-testid="SearchBox_Search_Input"]');
        if (!input) return "NO_INPUT";
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        setter.call(input, {json.dumps(query := q)});
        input.dispatchEvent(new Event("input", {{ bubbles: true }}));
        const form = input.closest("form");
        if (form) form.dispatchEvent(new Event("submit", {{ bubbles: true, cancelable: true }}));
        return "OK";
    }})()
    """
    if safari_js(submit_js) != "OK":
        safari_nav("https://x.com/search?q=apps&src=typed_query&f=top")
        time.sleep(3.5)
        safari_js(INSTALL_HOOK_JS)
        safari_js(submit_js)
    time.sleep(2.4)
    for tname in tabs:
        safari_js(f"""
        (function() {{
            const tabs = Array.from(document.querySelectorAll("a[role=tab], div[role=tab]"));
            const t = tabs.find(x => x.innerText.trim() === {json.dumps(tname)});
            if (t && t.getAttribute("aria-selected") !== "true") t.click();
        }})()
        """)
        time.sleep(2.0)
        for _ in range(scrolls):
            safari_js("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.7)
        safari_js("window.scrollTo(0, 0);")
    cnt = safari_js("Object.keys(window.__capturedUsers2 || {}).length")
    print(f"  [Extra {idx:02d}/{len(EXTRA_PLAN)}] ({label}) -> pool={cnt}")

raw2 = safari_js("JSON.stringify({users: window.__capturedUsers2 || {}, tweets: window.__capturedTweets2 || {}})")
with open(EXTRA_SEARCH_PATH, "w") as f:
    f.write(raw2)

d2 = json.loads(raw2)
print(f"\nPhase 2 complete! Following={len(net_cands)}, ExtraSearch={len(d2['users'])}")
