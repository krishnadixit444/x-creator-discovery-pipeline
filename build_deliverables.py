import csv
import json
import os
import re
from collections import Counter
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT_DIR = "/Users/krishna/.gemini/antigravity/scratch/x_creator_partnerships_scraper"
BRAIN_DIR = "/Users/krishna/.gemini/antigravity/brain/84c4c806-ffe2-47c3-a5b8-9acb8a2d6cbd"
DESKTOP_DIR = "/Users/krishna/Desktop"

VERIFIED_FINAL_PATH = os.path.join(OUT_DIR, "verified_final.json")


def build_reason_for_fit(c: dict) -> str:
    if c.get("custom_reason"):
        return c["custom_reason"]
    niche = c["niche"]
    reg = "US-based" if c["region_label"] == "US" else f"{c['region_label']}-based"
    fc = c["followers"]
    rm = c["reach_metrics"]
    med_v = rm["median_views"]
    avg_likes = rm["avg_likes"]
    bio_clean = re.sub(r"https?://\S+", "", c.get("bio", "")).strip()
    bio_clean = re.sub(r"\s+", " ", bio_clean)[:130].rstrip(" .,;|/-")
    snippet = re.sub(r"https?://\S+", "", rm.get("sample_post_snippet", "")).strip()
    snippet = re.sub(r"\s+", " ", snippet)[:90].rstrip(" .,;|/-")

    niche_angle = {
        "Mobile App Developer": "mobile app builder posting hands-on iOS/Android shipping, paywalls & App Store growth",
        "App Developer": "consumer/indie app builder sharing product launches, retention & user growth",
        "Meta Ads Specialist": "Meta ads practitioner sharing live creative testing, ROAS & paid social breakdowns",
        "Ads Specialist": "performance ads & creative strategy creator posting scalable UA hooks & ad insights",
    }.get(niche, niche.lower())

    bio_part = f" ({bio_clean})" if bio_clean else ""
    return (
        f"{reg} {niche_angle}{bio_part}; {fc:,} followers with strong organic reach "
        f"(median {med_v:,} views, ~{avg_likes:.0f} avg likes/post)."
    )


def export_deliverables(creators: list):
    headers = [
        "Rank",
        "Name",
        "Handle",
        "X Profile URL",
        "Follower Count",
        "Region / Country",
        "Location Evidence",
        "Niche",
        "Recent-Post Reach & Engagement Evidence",
        "Median Post Views",
        "Avg Post Likes",
        "Bio",
        "Short Reason for Fit",
    ]

    rows = []
    for idx, c in enumerate(creators, 1):
        handle_at = "@" + c["screen_name"]
        url = f"https://x.com/{c['screen_name']}"
        rm = c["reach_metrics"]
        bio_clean = re.sub(r"\s+", " ", (c.get("bio") or "")).strip()
        rows.append([
            idx,
            c["name"],
            handle_at,
            url,
            int(c["followers"]),
            c["region_label"],
            c["location_evidence"],
            c["niche"],
            rm["reach_evidence"],
            int(rm["median_views"]),
            round(float(rm["avg_likes"]), 1),
            bio_clean,
            build_reason_for_fit(c),
        ])

    csv_paths = [
        os.path.join(BRAIN_DIR, "X_Creator_Partnerships_Apps_Ads_US_EU.csv"),
        os.path.join(DESKTOP_DIR, "X_Creator_Partnerships_Apps_Ads_US_EU.csv"),
    ]
    for cp in csv_paths:
        with open(cp, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        print(f"Wrote CSV: {cp} ({len(rows)} rows)")

    xlsx_paths = [
        os.path.join(BRAIN_DIR, "X_Creator_Partnerships_Apps_Ads_US_EU.xlsx"),
        os.path.join(DESKTOP_DIR, "X_Creator_Partnerships_Apps_Ads_US_EU.xlsx"),
    ]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Verified Creators"

    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    alt_fill = PatternFill(start_color="F5F8FC", end_color="F5F8FC", fill_type="solid")
    base_font = Font(name="Calibri", size=10, color="111827")
    bold_font = Font(name="Calibri", size=10, bold=True, color="111827")
    link_font = Font(name="Calibri", size=10, color="0563C1", underline="single")
    thin_border = Border(
        left=Side(style="thin", color="E5E7EB"),
        right=Side(style="thin", color="E5E7EB"),
        top=Side(style="thin", color="E5E7EB"),
        bottom=Side(style="thin", color="E5E7EB"),
    )

    ws.append(headers)
    ws.row_dimensions[1].height = 28
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center" if col_idx in (1, 5, 10, 11) else "left", vertical="center", wrap_text=True)
        cell.border = thin_border

    for r_idx, r_data in enumerate(rows, 2):
        ws.append(r_data)
        est_lines = max(
            3,
            int(len(str(r_data[8])) / 42) + 1,
            int(len(str(r_data[11])) / 35) + 1,
            int(len(str(r_data[12])) / 44) + 1,
        )
        ws.row_dimensions[r_idx].height = max(48, min(95, est_lines * 15))
        fill = alt_fill if r_idx % 2 == 1 else PatternFill(fill_type=None)
        for c_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=r_idx, column=c_idx)
            if fill.fill_type:
                cell.fill = fill
            cell.border = thin_border
            if c_idx == 4:
                cell.hyperlink = r_data[3]
                cell.font = link_font
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=False)
            elif c_idx in (1, 5, 10, 11):
                cell.font = bold_font if c_idx in (5, 10) else base_font
                cell.alignment = Alignment(horizontal="right" if c_idx != 1 else "center", vertical="top")
                if c_idx in (5, 10):
                    cell.number_format = "#,##0"
                elif c_idx == 11:
                    cell.number_format = "#,##0.0"
            elif c_idx == 2 or c_idx == 3:
                cell.font = bold_font if c_idx == 2 else base_font
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
            else:
                cell.font = base_font
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

    col_widths = [7, 24, 20, 32, 15, 22, 34, 22, 48, 17, 15, 40, 50]
    for idx, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(idx)].width = w

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"

    # Sheet 2: Summary Breakdown
    ws2 = wb.create_sheet("Summary")
    ws2.append(["Category", "Metric", "Count / Value"])
    for c_idx in range(1, 4):
        cell = ws2.cell(row=1, column=c_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = thin_border

    summary_rows = [
        ("Overview", "Total Verified Creators (Deduplicated)", len(creators)),
        ("Overview", "Min Follower Count", min(c["followers"] for c in creators) if creators else 0),
        ("Overview", "Max Follower Count", max(c["followers"] for c in creators) if creators else 0),
        ("Overview", "Median Post Views (Across Roster)", int(sorted(c["reach_metrics"]["median_views"] for c in creators)[len(creators)//2]) if creators else 0),
        ("Eligibility", "Regions Included", "United States & Europe only (X AboutAccountQuery + Profile/Bio)"),
        ("Eligibility", "Minimum Followers", ">= 5,000 verified live via X Safari"),
        ("Eligibility", "Recent Organic Reach Gate", "Active Oct–Nov 2026 original posts, healthy median views & likes, non-bait"),
    ]
    niche_counts = Counter(c["niche"] for c in creators)
    for k, v in niche_counts.most_common():
        summary_rows.append(("Niche Breakdown", k, v))
    broad_reg_counts = Counter("United States" if c["region_label"] == "US" else "Europe" for c in creators)
    for k, v in broad_reg_counts.most_common():
        summary_rows.append(("Region Group", k, v))
    reg_counts = Counter("United States" if c["region_label"] == "US" else c["region_label"] for c in creators)
    for k, v in reg_counts.most_common():
        summary_rows.append(("Region / Country Breakdown", k, v))

    for sr in summary_rows:
        ws2.append(list(sr))
    for r_idx in range(2, len(summary_rows) + 2):
        for c_idx in range(1, 4):
            cell = ws2.cell(row=r_idx, column=c_idx)
            cell.font = base_font
            cell.border = thin_border
            if isinstance(cell.value, int):
                cell.number_format = "#,##0"
    ws2.column_dimensions["A"].width = 22
    ws2.column_dimensions["B"].width = 36
    ws2.column_dimensions["C"].width = 58
    ws2.freeze_panes = "A2"

    for xp in xlsx_paths:
        wb.save(xp)
        print(f"Wrote XLSX: {xp} ({len(rows)} rows)")


if __name__ == "__main__":
    with open(VERIFIED_FINAL_PATH) as f:
        data = json.load(f)
    export_deliverables(data)
