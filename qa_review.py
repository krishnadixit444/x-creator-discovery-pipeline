import json
import os
from collections import Counter

OUT_DIR = "/Users/krishna/.gemini/antigravity/scratch/x_creator_partnerships_scraper"
VERIFIED_FINAL_PATH = os.path.join(OUT_DIR, "verified_final.json")


def run_qa(path: str = VERIFIED_FINAL_PATH):
    with open(path) as f:
        creators = json.load(f)

    handles = [c["screen_name"].lower() for c in creators]
    rids = [c.get("rest_id") for c in creators if c.get("rest_id")]
    assert len(handles) == len(set(handles)), "Duplicate @handle detected!"
    assert len(rids) == len(set(rids)), "Duplicate rest_id detected!"
    assert len(creators) >= 100, f"Only {len(creators)} creators, need >= 100!"

    for c in creators:
        assert c["followers"] >= 5000, f"@{c['screen_name']} < 5000 followers"
        assert c.get("location_evidence"), f"@{c['screen_name']} missing location evidence"
        assert c.get("niche") in {"Mobile App Developer", "App Developer", "Meta Ads Specialist", "Ads Specialist"}
        rm = c["reach_metrics"]
        assert rm["median_views"] >= 800 or rm["avg_views"] >= 1500
        assert rm["avg_likes"] >= 8
        assert rm["latest_post_date"] >= "2026-10-15"

    print(f"QA PASSED: {len(creators)} deduplicated, verified US/EU creators (>= 5k followers, active Oct-Nov 2026)")
    print("Niche distribution:", Counter(c["niche"] for c in creators))
    print("Region breakdown:", Counter("US" if c["region_label"] == "US" else "Europe" for c in creators))
    print("Min/Median/Max followers:",
          min(c["followers"] for c in creators),
          sorted(c["followers"] for c in creators)[len(creators)//2],
          max(c["followers"] for c in creators))
    print("Min/Median/Max median_views:",
          min(c["reach_metrics"]["median_views"] for c in creators),
          sorted(c["reach_metrics"]["median_views"] for c in creators)[len(creators)//2],
          max(c["reach_metrics"]["median_views"] for c in creators))


if __name__ == "__main__":
    run_qa()
