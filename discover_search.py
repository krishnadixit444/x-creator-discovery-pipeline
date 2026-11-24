import subprocess
import json
import time
import os

OUT_DIR = "/Users/krishna/.gemini/antigravity/scratch/x_creator_partnerships_scraper"
RAW_SEARCH_PATH = os.path.join(OUT_DIR, "raw_search_candidates.json")

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

INSTALL_HOOK_JS = """
(function() {
    window.__capturedUsers = window.__capturedUsers || {};
    window.__capturedTweets = window.__capturedTweets || {};
    window.__searchResponses = window.__searchResponses || 0;
    if (!window.__xhrSearchHookInstalled) {
        window.__xhrSearchHookInstalled = true;
        const origSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send = function() {
            this.addEventListener("load", function() {
                try {
                    if (this.responseURL && this.responseURL.includes("SearchTimeline") && this.status === 200) {
                        window.__searchResponses++;
                        const data = JSON.parse(this.responseText);
                        (function walk(obj) {
                            if (!obj || typeof obj !== "object") return;
                            if (obj.__typename === "User" && (obj.rest_id || obj.id)) {
                                const sn = obj.core?.screen_name || obj.legacy?.screen_name;
                                if (sn) {
                                    const key = sn.toLowerCase();
                                    const followers = obj.relationship_counts?.followers ?? obj.legacy?.followers_count ?? 0;
                                    const existing = window.__capturedUsers[key] || {};
                                    window.__capturedUsers[key] = {
                                        screen_name: sn,
                                        rest_id: obj.rest_id || existing.rest_id || "",
                                        name: obj.core?.name || obj.legacy?.name || existing.name || "",
                                        followers: followers || existing.followers || 0,
                                        location: obj.location?.location ?? obj.legacy?.location ?? existing.location ?? "",
                                        bio: obj.profile_bio?.description ?? obj.legacy?.description ?? existing.bio ?? "",
                                        is_blue_verified: obj.is_blue_verified ?? existing.is_blue_verified ?? false,
                                        sources: Array.from(new Set([...(existing.sources || []), window.__currentQueryLabel || "search"]))
                                    };
                                }
                            }
                            if (obj.__typename === "Tweet" && obj.legacy) {
                                const ur = obj.core?.user_results?.result;
                                const sn = ur?.core?.screen_name || ur?.legacy?.screen_name;
                                const tid = obj.rest_id || obj.legacy.id_str;
                                if (sn && tid) {
                                    const key = sn.toLowerCase();
                                    if (!window.__capturedTweets[key]) window.__capturedTweets[key] = [];
                                    if (window.__capturedTweets[key].length < 5) {
                                        window.__capturedTweets[key].push({
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
    return "HOOK_READY:" + Object.keys(window.__capturedUsers).length;
})()
"""

# Make sure we start on X search page cleanly so search box exists
print("Ensuring Safari tab 1 is on search page...")
safari_nav("https://x.com/search?q=ios%20app&src=typed_query&f=top")
time.sleep(3.5)
print(safari_js(INSTALL_HOOK_JS))

# Carefully designed queries across all 4 niches
# Mode: ("label", "query", ["Top", "People"], scrolls_per_tab)
SEARCH_PLAN = [
    # Niche 1: Mobile App Developers
    ("mobile_dev", '"ios app" ("mrr" OR "revenuecat" OR "app store") min_faves:15', ["Top"], 2),
    ("mobile_dev", '"mobile app" ("shipped" OR "launched" OR "mrr" OR "downloads") min_faves:15', ["Top"], 2),
    ("mobile_dev", '("swiftui" OR "react native" OR "expo") ("app" OR "ios") min_faves:20', ["Top"], 2),
    ("mobile_dev", 'ios developer app', ["People"], 2),
    ("mobile_dev", 'mobile app developer', ["People"], 2),
    ("mobile_dev", 'react native swiftui', ["People"], 1),
    ("mobile_dev", '"superwall" OR "revenuecat" ("paywall" OR "ios" OR "mrr") min_faves:10', ["Top"], 2),

    # Niche 2: App Developers
    ("app_dev", '"built an app" OR "building an app" ("users" OR "mrr" OR "downloads") min_faves:20', ["Top"], 2),
    ("app_dev", '"consumer app" ("growth" OR "retention" OR "onboarding" OR "viral") min_faves:15', ["Top"], 2),
    ("app_dev", '"indie app" OR "app studio" ("ios" OR "mobile" OR "revenue") min_faves:10', ["Top"], 2),
    ("app_dev", 'app founder ios', ["People"], 2),
    ("app_dev", 'indie app developer', ["People"], 1),

    # Niche 3: Meta Ads Specialists
    ("meta_ads", '("meta ads" OR "facebook ads") ("roas" OR "cpa" OR "creatives" OR "testing") min_faves:12', ["Top"], 2),
    ("meta_ads", '"meta ads" ("andromeda" OR "creative testing" OR "ad account" OR "cpm") min_faves:10', ["Top"], 2),
    ("meta_ads", 'meta ads specialist', ["People"], 2),
    ("meta_ads", 'facebook ads media buyer', ["People"], 2),
    ("meta_ads", '"meta ads" ("app" OR "installs" OR "subscription" OR "dtc") min_faves:10', ["Top"], 2),

    # Niche 4: Ads / Paid Social / UA / Creative Strategy Specialists
    ("ads_spec", '"creative strategist" ("meta ads" OR "ugc" OR "static ads" OR "hooks") min_faves:10', ["Top"], 2),
    ("ads_spec", 'creative strategist ads', ["People"], 2),
    ("ads_spec", '("user acquisition" OR "paid social") ("mobile app" OR "meta" OR "tiktok ads" OR "applovin") min_faves:8', ["Top"], 2),
    ("ads_spec", 'paid social performance marketing', ["People"], 2),
    ("ads_spec", '("ugc ads" OR "ad creative" OR "video ads") ("ctr" OR "hook rate" OR "roas" OR "scale") min_faves:10', ["Top"], 2),
    ("ads_spec", 'media buyer ecommerce', ["People"], 1),
    ("ads_spec", 'user acquisition mobile', ["People"], 1),
]

def run_query(label, query, tabs, scrolls):
    submit_js = f"""
    (function() {{
        window.__currentQueryLabel = {json.dumps(label)};
        const input = document.querySelector('input[data-testid="SearchBox_Search_Input"]');
        if (!input) return "NO_INPUT";
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        setter.call(input, {json.dumps(query)});
        input.dispatchEvent(new Event("input", {{ bubbles: true }}));
        const form = input.closest("form");
        if (form) form.dispatchEvent(new Event("submit", {{ bubbles: true, cancelable: true }}));
        return "OK";
    }})()
    """
    status = safari_js(submit_js)
    if status != "OK":
        print(f"  [!] Search input missing on {label}, reloading search page...")
        safari_nav("https://x.com/search?q=apps&src=typed_query&f=top")
        time.sleep(3.5)
        safari_js(INSTALL_HOOK_JS)
        status = safari_js(submit_js)
    time.sleep(2.4)

    for tab_name in tabs:
        click_tab_js = f"""
        (function() {{
            const tabs = Array.from(document.querySelectorAll("a[role=tab], div[role=tab]"));
            const target = tabs.find(t => t.innerText.trim() === {json.dumps(tab_name)});
            if (target) {{
                const selected = target.getAttribute("aria-selected");
                if (selected !== "true") {{
                    target.click();
                    return "CLICKED_" + {json.dumps(tab_name)};
                }}
                return "ALREADY_" + {json.dumps(tab_name)};
            }}
            return "NO_TAB_" + {json.dumps(tab_name)};
        }})()
        """
        res = safari_js(click_tab_js)
        if res.startswith("CLICKED_"):
            time.sleep(2.2)

        for s in range(scrolls):
            safari_js("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.8)
        safari_js("window.scrollTo(0, 0);")
        time.sleep(0.4)

for idx, (label, q, tabs, scrolls) in enumerate(SEARCH_PLAN, 1):
    try:
        run_query(label, q, tabs, scrolls)
        cnt = safari_js("Object.keys(window.__capturedUsers || {}).length + '|' + (window.__searchResponses || 0)")
        print(f"[{idx:02d}/{len(SEARCH_PLAN)}] ({label}) -> pool|reqs = {cnt} | q={q[:55]}")
    except Exception as e:
        print(f"[{idx:02d}] ERROR on {q}: {e}")

raw_data = safari_js("JSON.stringify({users: window.__capturedUsers || {}, tweets: window.__capturedTweets || {}, responses: window.__searchResponses || 0})")
with open(RAW_SEARCH_PATH, "w") as f:
    f.write(raw_data)

parsed = json.loads(raw_data)
u_count = len(parsed["users"])
gte5k = sum(1 for u in parsed["users"].values() if (u.get("followers") or 0) >= 5000)
print(f"\nSaved {u_count} unique users ({gte5k} with >= 5,000 followers) from {parsed['responses']} SearchTimeline responses to {RAW_SEARCH_PATH}")
