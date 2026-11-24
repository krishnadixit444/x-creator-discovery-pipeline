import json
import os
import time
from enrich_and_verify import FEATS, QID_FOLLOWING, run_async_safari, OUT_DIR

SEED_OUT_PATH = os.path.join(OUT_DIR, "seed_network_candidates.json")


def fetch_following_for_seeds(seeds: list, pages_per_seed: int = 2) -> dict:
    """
    seeds: list of (screen_name, rest_id, seed_niche)
    Fetches 1..pages_per_seed pages (~50-70 accounts per page) of Following for each seed.
    """
    print(f"Expanding Following graphs for {len(seeds)} niche seeds ({pages_per_seed} pages each)...")
    candidates = {}
    batch_size = 8
    for i in range(0, len(seeds), batch_size):
        batch = seeds[i:i + batch_size]
        js = f"""
        const ct0 = (document.cookie.match(/ct0=([^;]+)/) || [])[1];
        const headers = {{
            "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "x-csrf-token": ct0,
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session"
        }};
        const batch = {json.dumps(batch)};
        const feats = {json.dumps(FEATS)};
        const pagesMax = {pages_per_seed};
        const out = {{}};

        function extractUsersAndCursor(data) {{
            const users = [];
            let bottomCursor = null;
            const inst = data?.data?.user?.result?.timeline?.timeline?.instructions || [];
            for (const ins of inst) {{
                for (const ent of (ins.entries || [])) {{
                    if (ent?.content?.cursorType === "Bottom") {{
                        bottomCursor = ent.content.value;
                    }}
                    const ur = ent?.content?.itemContent?.user_results?.result;
                    if (ur && (ur.__typename === "User" || ur.rest_id)) {{
                        const sn = ur.core?.screen_name || ur.legacy?.screen_name;
                        const followers = ur.relationship_counts?.followers ?? ur.legacy?.followers_count ?? 0;
                        if (sn) {{
                            users.push({{
                                screen_name: sn,
                                rest_id: ur.rest_id || "",
                                name: ur.core?.name || ur.legacy?.name || sn,
                                followers: followers,
                                location: ur.location?.location ?? ur.legacy?.location ?? "",
                                bio: ur.profile_bio?.description ?? ur.legacy?.description ?? "",
                                is_blue_verified: Boolean(ur.is_blue_verified)
                            }});
                        }}
                    }}
                }}
            }}
            return {{ users, bottomCursor }};
        }}

        for (const [seedHandle, seedRid, seedNiche] of batch) {{
            const list = [];
            let cursor = null;
            for (let p = 0; p < pagesMax; p++) {{
                try {{
                    const vars = {{ userId: seedRid, count: 70, includePromotedContent: false }};
                    if (cursor) vars.cursor = cursor;
                    const u = "https://x.com/i/api/graphql/{QID_FOLLOWING}/Following?variables=" +
                        encodeURIComponent(JSON.stringify(vars)) +
                        "&features=" + encodeURIComponent(JSON.stringify(feats));
                    const r = await fetch(u, {{ headers, credentials: "include" }});
                    if (r.status === 429) {{
                        out._rate_limited = true;
                        break;
                    }}
                    if (r.status !== 200) break;
                    const j = await r.json();
                    const parsed = extractUsersAndCursor(j);
                    for (const uObj of parsed.users) {{
                        uObj.seed = seedHandle;
                        uObj.seed_niche = seedNiche;
                        list.push(uObj);
                    }}
                    if (!parsed.bottomCursor || parsed.users.length === 0) break;
                    cursor = parsed.bottomCursor;
                    await new Promise(r => setTimeout(r, 250));
                }} catch (e) {{
                    break;
                }}
            }}
            out[seedHandle] = list;
            await new Promise(r => setTimeout(r, 250));
        }}
        window["__followOut"] = JSON.stringify(out);
        """
        res = run_async_safari(js, "__followOut", timeout_s=120)
        got_rl = res.pop("_rate_limited", False)
        for seed_h, u_list in res.items():
            for u in u_list:
                key = u["screen_name"].lower()
                if key not in candidates:
                    candidates[key] = u
                    candidates[key]["sources"] = [f"follow:{seed_h}({u['seed_niche']})"]
                else:
                    if f"follow:{seed_h}" not in str(candidates[key].get("sources", [])):
                        candidates[key].setdefault("sources", []).append(f"follow:{seed_h}")
        print(f"  Batch {i//batch_size + 1}/{(len(seeds)-1)//batch_size + 1} -> unique network candidates: {len(candidates)}")
        if got_rl:
            print("  [!] Hit 429 on Following, sleeping 30s...")
            time.sleep(30)

    with open(SEED_OUT_PATH, "w") as f:
        json.dump(candidates, f, indent=2)
    return candidates
