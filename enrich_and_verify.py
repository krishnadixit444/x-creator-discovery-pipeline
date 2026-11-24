import subprocess
import json
import time
import os
import re
import statistics
from datetime import datetime, timezone
from geo_and_filters import evaluate_location, count_bait_tweets, classify_niche

OUT_DIR = "/Users/krishna/.gemini/antigravity/scratch/x_creator_partnerships_scraper"
ABOUT_CACHE_PATH = os.path.join(OUT_DIR, "about_cache.json")
TWEETS_CACHE_PATH = os.path.join(OUT_DIR, "tweets_cache.json")
USERS_CACHE_PATH = os.path.join(OUT_DIR, "users_cache.json")

FEATS = {
    "rweb_video_screen_enabled": False,
    "rweb_cashtags_enabled": True,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
    "responsive_web_profile_redirect_enabled": True,
    "rweb_tipjar_consumption_enabled": False,
    "verified_phone_label_enabled": True,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "premium_content_api_read_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
    "responsive_web_grok_analyze_post_followups_enabled": True,
    "rweb_cashtags_composer_attachment_enabled": True,
    "responsive_web_jetfuel_frame": True,
    "rweb_sports_post_context_enabled": True,
    "x_elections_post_context_enabled": True,
    "responsive_web_grok_share_attachment_enabled": True,
    "responsive_web_grok_annotations_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "rweb_conversational_replies_downvote_enabled": False,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "content_disclosure_indicator_enabled": True,
    "content_disclosure_ai_generated_indicator_enabled": True,
    "responsive_web_grok_show_grok_translated_post": True,
    "responsive_web_grok_analysis_button_from_backend": True,
    "post_ctas_fetch_enabled": True,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": False,
    "responsive_web_nested_quote_preview_enabled": True,
    "responsive_web_grok_image_annotation_enabled": True,
    "responsive_web_grok_imagine_annotation_enabled": True,
    "responsive_web_made_on_x_label_enabled": False,
    "responsive_web_grok_community_note_auto_translation_is_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
}

QID_USERS_BATCH = "cACg_kWQkzNQ74lcK5rksQ"
QID_ABOUT = "TzOG2twZEfhr9KmClvVVqA"
QID_USER_TWEETS = "D6z-FJI2pKuwEeYYxVIGbg"
QID_FOLLOWING = "eDqlbOS46zda8jDT8dEQ_Q"


def safari_js(js: str) -> str:
    cmd = f'tell application "Safari" to do JavaScript {json.dumps(js)} in tab 1 of window 1'
    p = subprocess.run(['osascript', '-'], input=cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip())
    return p.stdout.strip()


def run_async_safari(js_body: str, result_var: str = "__jobOut", timeout_s: int = 120):
    wrapped = f"""
    (function() {{
        window[{json.dumps(result_var)}] = null;
        (async () => {{
            {js_body}
        }})();
        return "STARTED";
    }})()
    """
    safari_js(wrapped)
    start = time.time()
    while time.time() - start < timeout_s:
        time.sleep(1.0)
        res = safari_js(f"window[{json.dumps(result_var)}] || ''")
        if res:
            return json.loads(res)
    raise TimeoutError(f"Safari job {result_var} timed out after {timeout_s}s")


def load_cache(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_cache(path: str, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def batch_fetch_users(handles: list, users_cache: dict) -> dict:
    missing = [h for h in handles if h.lower() not in users_cache]
    if not missing:
        return users_cache
    print(f"Fetching fresh profile metadata for {len(missing)} handles via UsersByScreenNames...")
    chunk_size = 40
    for i in range(0, len(missing), chunk_size):
        chunk = missing[i:i + chunk_size]
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
        try {{
            const u = "https://x.com/i/api/graphql/{QID_USERS_BATCH}/UsersByScreenNames?variables=" +
                encodeURIComponent(JSON.stringify({{screen_names: batch}})) +
                "&features=" + encodeURIComponent(JSON.stringify(feats));
            const r = await fetch(u, {{ headers, credentials: "include" }});
            if (r.status === 200) {{
                const j = await r.json();
                for (const item of (j?.data?.users || [])) {{
                    const ur = item?.result;
                    const sn = ur?.core?.screen_name || ur?.legacy?.screen_name;
                    if (sn) {{
                        const bioUrls = (ur?.profile_bio?.entities?.description?.urls || []).map(x => x.expanded_url).filter(Boolean);
                        const siteUrl = (ur?.profile_bio?.entities?.url?.urls || [])[0]?.expanded_url || "";
                        out[sn.toLowerCase()] = {{
                            screen_name: sn,
                            rest_id: ur.rest_id || "",
                            name: ur.core?.name || ur.legacy?.name || sn,
                            followers: ur.relationship_counts?.followers ?? ur.legacy?.followers_count ?? 0,
                            following: ur.relationship_counts?.following ?? ur.legacy?.friends_count ?? 0,
                            tweets_count: ur.tweet_counts?.tweets ?? ur.legacy?.statuses_count ?? 0,
                            location: ur.location?.location ?? ur.legacy?.location ?? "",
                            bio: ur.profile_bio?.description ?? ur.legacy?.description ?? "",
                            website: siteUrl,
                            bio_urls: bioUrls,
                            created_at: ur.core?.created_at || "",
                            is_blue_verified: Boolean(ur.is_blue_verified),
                            prof_category: (ur.professional?.category || []).map(c => c.name).filter(Boolean),
                            prof_type: ur.professional?.professional_type || ""
                        }};
                    }}
                }}
            }} else {{
                out.__http_status = r.status;
            }}
        }} catch (e) {{
            out.__err = String(e);
        }}
        window["__batchUsersOut"] = JSON.stringify(out);
        """
        res = run_async_safari(js, "__batchUsersOut", timeout_s=45)
        if "__http_status" in res:
            print(f"  [!] UsersByScreenNames HTTP {res['__http_status']} on chunk {i//chunk_size + 1}")
        for k, v in res.items():
            if not k.startswith("__"):
                users_cache[k] = v
        save_cache(USERS_CACHE_PATH, users_cache)
        time.sleep(0.4)
    return users_cache


def batch_fetch_about(handles: list, about_cache: dict) -> dict:
    missing = [h for h in handles if h.lower() not in about_cache]
    if not missing:
        return about_cache
    print(f"Fetching AboutAccountQuery location verification for {len(missing)} handles...")
    chunk_size = 60
    for i in range(0, len(missing), chunk_size):
        chunk = missing[i:i + chunk_size]
        js = f"""
        const ct0 = (document.cookie.match(/ct0=([^;]+)/) || [])[1];
        const headers = {{
            "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "x-csrf-token": ct0,
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session"
        }};
        const batch = {json.dumps(chunk)};
        const out = {{}};
        let cursor = 0;
        let rateLimited = false;
        async function worker() {{
            while (cursor < batch.length && !rateLimited) {{
                const h = batch[cursor++];
                try {{
                    const u = "https://x.com/i/api/graphql/{QID_ABOUT}/AboutAccountQuery?variables=" +
                        encodeURIComponent(JSON.stringify({{screenName: h}}));
                    const r = await fetch(u, {{ headers, credentials: "include" }});
                    if (r.status === 429) {{
                        rateLimited = true;
                        out[h.toLowerCase()] = {{ _retry: true, status: 429 }};
                        break;
                    }}
                    if (r.status === 200) {{
                        const j = await r.json();
                        const ap = j?.data?.user_result_by_screen_name?.result?.about_profile || {{}};
                        out[h.toLowerCase()] = {{
                            account_based_in: ap.account_based_in || "",
                            source: ap.source || "",
                            location_accurate: ap.location_accurate
                        }};
                    }} else {{
                        out[h.toLowerCase()] = {{ account_based_in: "", source: "", status: r.status }};
                    }}
                }} catch (e) {{
                    out[h.toLowerCase()] = {{ account_based_in: "", source: "", err: String(e) }};
                }}
                await new Promise(r => setTimeout(r, 150));
            }}
        }}
        await Promise.all([worker(), worker(), worker()]);
        window["__aboutOut"] = JSON.stringify(out);
        """
        res = run_async_safari(js, "__aboutOut", timeout_s=90)
        got_429 = False
        for k, v in res.items():
            if v.get("_retry"):
                got_429 = True
            else:
                about_cache[k] = v
        save_cache(ABOUT_CACHE_PATH, about_cache)
        print(f"  Batch {i//chunk_size + 1}/{(len(missing)-1)//chunk_size + 1} saved (cache total: {len(about_cache)})")
        if got_429:
            print("  [!] Hit 429 on AboutAccountQuery, sleeping 30s...")
            time.sleep(30)
    return about_cache


def batch_fetch_user_tweets(targets: list, tweets_cache: dict) -> dict:
    """
    targets: list of (screen_name_lower, rest_id)
    """
    missing = [(h, rid) for h, rid in targets if h.lower() not in tweets_cache and rid]
    if not missing:
        return tweets_cache
    print(f"Fetching recent public posts via UserTweets for {len(missing)} US/EU candidates...")
    chunk_size = 35
    for i in range(0, len(missing), chunk_size):
        chunk = missing[i:i + chunk_size]
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
        let rateLimited = false;
        async function worker() {{
            while (cursor < batch.length && !rateLimited) {{
                const [h, rid] = batch[cursor++];
                try {{
                    const u = "https://x.com/i/api/graphql/{QID_USER_TWEETS}/UserTweets?variables=" +
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
                        rateLimited = true;
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
                await new Promise(r => setTimeout(r, 180));
            }}
        }}
        await Promise.all([worker(), worker(), worker()]);
        window["__tweetsOut"] = JSON.stringify(out);
        """
        res = run_async_safari(js, "__tweetsOut", timeout_s=100)
        got_429 = False
        for k, v in res.items():
            if v.get("_retry"):
                got_429 = True
            else:
                tweets_cache[k] = v
        save_cache(TWEETS_CACHE_PATH, tweets_cache)
        print(f"  Tweets batch {i//chunk_size + 1}/{(len(missing)-1)//chunk_size + 1} saved (cache total: {len(tweets_cache)})")
        if got_429:
            print("  [!] Hit 429 on UserTweets, sleeping 35s...")
            time.sleep(35)
    return tweets_cache
