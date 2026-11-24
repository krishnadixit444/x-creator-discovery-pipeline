import re
from typing import Tuple, Optional

# Strictly US and European countries returned by X AboutAccountQuery or stated in profile location
US_EXACT_ABOUT = {
    "united states",
    "usa",
    "u.s.",
    "u.s.a.",
}

EUROPE_EXACT_ABOUT = {
    "united kingdom", "uk", "england", "scotland", "wales", "northern ireland",
    "ireland", "germany", "france", "netherlands", "the netherlands", "spain",
    "italy", "portugal", "switzerland", "sweden", "norway", "denmark", "finland",
    "poland", "belgium", "austria", "czech republic", "czechia", "estonia",
    "latvia", "lithuania", "slovakia", "slovenia", "croatia", "greece",
    "hungary", "romania", "bulgaria", "luxembourg", "iceland", "malta",
    "cyprus", "serbia", "bosnia and herzegovina", "montenegro", "albania",
    "north macedonia", "macedonia", "moldova", "ukraine", "andorra", "monaco", "liechtenstein",
}

EUROPE_REGION_ABOUT = {
    "europe",
    "western europe",
    "northern europe",
    "southern europe",
    "eastern europe",
    "eastern europe (non-eu)",
    "central europe",
}

BANNED_ABOUT_COUNTRIES = {
    "india", "pakistan", "bangladesh", "sri lanka", "nepal", "bhutan", "afghanistan",
    "canada", "mexico", "brazil", "argentina", "colombia", "chile", "peru",
    "australia", "new zealand", "japan", "south korea", "korea", "china",
    "hong kong", "taiwan", "singapore", "indonesia", "philippines", "vietnam", "viet nam",
    "malaysia", "thailand", "united arab emirates", "uae", "saudi arabia",
    "qatar", "kuwait", "bahrain", "oman", "jordan", "lebanon", "israel",
    "turkey", "türkiye", "russia", "russian federation", "nigeria", "south africa", "kenya", "ghana",
    "egypt", "morocco", "tunisia", "ethiopia", "africa", "south asia", "east asia",
    "southeast asia", "central asia", "asia", "middle east", "latin america", "south america",
    "oceania", "australasia", "caribbean", "west asia",
}

# Explicit non-US/non-EU text regex (word boundaries)
NON_US_EU_TEXT_RE = re.compile(
    r"\b("
    r"india|bengaluru|bangalore|\bblr\b|mumbai|delhi|new delhi|hyderabad|pune|chennai|kolkata|noida|gurgaon|gurugram|"
    r"pakistan|lahore|karachi|islamabad|bangladesh|dhaka|sri lanka|colombo|nepal|kathmandu|"
    r"canada|toronto|vancouver|montreal|ottawa|calgary|waterloo|edmonton|quebec|nova scotia|halifax|winnipeg|victoria, bc|alberta|british columbia|ontario|saskatoon|"
    r"australia|sydney|melbourne|brisbane|perth|adelaide|gold coast|new zealand|auckland|wellington|"
    r"dubai|abu dhabi|uae|saudi|riyadh|qatar|doha|tel aviv|israel|istanbul|izmir|ankara|turkey|"
    r"singapore|tokyo|osaka|japan|seoul|korea|beijing|shanghai|shenzhen|hong kong|taiwan|taipei|"
    r"jakarta|indonesia|manila|philippines|bangkok|thailand|kuala lumpur|malaysia|vietnam|hanoi|ho chi minh|"
    r"nigeria|lagos|abuja|kenya|nairobi|south africa|cape town|johannesburg|egypt|cairo|"
    r"brazil|sao paulo|são paulo|rio de janeiro|curitiba|florianopolis|mexico|mexico city|buenos aires|argentina|bogota|medellin|colombia|santiago|chile|"
    r"moscow|russia|st\.? petersburg|bali|canggu|ubud|chiang mai|phuket"
    r")\b",
    re.IGNORECASE,
)

# Unambiguous US patterns
US_TEXT_PATTERNS = [
    r"\bunited states\b", r"\bu\.s\.a\.?", r"\bu\.s\.(?!\w)", r"\busa\b", r"🇺🇸",
    r"\bnew york(?: city)?\b", r"\bnyc\b", r"\bmanhattan\b", r"\bbrooklyn\b",
    r"\bsan francisco\b", r"\bbay area\b", r"\bsilicon valley\b", r"\bpalo alto\b",
    r"\bmountain view\b", r"\bmenlo park\b", r"\bsanta monica\b", r"\blos angeles\b",
    r"\bsan diego\b", r"\bsan jose\b", r"\bcalifornia\b", r"\bseattle\b",
    r"\baustin\b", r"\bdallas\b", r"\bhouston\b", r"\btexas\b", r"\bmiami\b",
    r"\bflorida\b", r"\bchicago\b", r"\billinois\b", r"\bboston\b", r"\bcambridge,\s*ma\b",
    r"\bmassachusetts\b", r"\bdenver\b", r"\bboulder\b", r"\bcolorado\b",
    r"\batlanta\b", r"\bgeorgia\b", r"\bphoenix\b", r"\bscottsdale\b", r"\barizona\b",
    r"\bsalt lake\b", r"\butah\b", r"\bportland,\s*or\b", r"\bnashville\b",
    r"\btennessee\b", r"\bcharlotte\b", r"\braleigh\b", r"\bnorth carolina\b",
    r"\bphiladelphia\b", r"\bpittsburgh\b", r"\bdetroit\b", r"\bmichigan\b",
    r"\bminneapolis\b", r"\bminnesota\b", r"\blas vegas\b", r"\bnevada\b",
    r"\bst\.?\s*louis\b", r"\bmissouri\b", r"\bcolumbus,\s*oh\b", r"\bohio\b",
    r"\bwashington,?\s*d\.?c\.?\b", r"\bnew jersey\b", r"\bhoboken\b",
    r"\bconnecticut\b", r"\bvirginia\b", r"\bvenice beach\b",
    # Qualified State codes like "Austin, TX" or "St Louis, MO"
    r",\s*(?:CA|NY|TX|FL|WA|IL|MA|CO|GA|AZ|UT|OR|NC|PA|MI|NJ|VA|TN|OH|MN|NV|DC|MD|CT|WI|IN|MO|AL|AR|DE|HI|ID|IA|KS|KY|LA|ME|MS|MT|NE|NH|NM|OK|RI|SC|SD|VT|WV|WY)\b",
    r"\bSF\b",
]
US_TEXT_RE = re.compile("|".join(US_TEXT_PATTERNS), re.IGNORECASE)

# Unambiguous Europe patterns
EU_TEXT_PATTERNS = [
    r"\bunited kingdom\b", r"\bu\.k\.(?!\w)", r"\buk\b", r"\bengland\b", r"\bscotland\b", r"\bwales\b", r"\blondon\b",
    r"\bmanchester\b", r"\bedinburgh\b", r"\bbristol\b", r"\bbirmingham,?\s*uk\b", r"\boxford\b", r"🇬🇧",
    r"\bireland\b", r"\bdublin\b", r"\bcork\b", r"🇮🇪",
    r"\bgermany\b", r"\bdeutschland\b", r"\bberlin\b", r"\bmunich\b", r"\bmünchen\b", r"\bhamburg\b", r"\bfrankfurt\b", r"\bcologne\b", r"🇩🇪",
    r"\bfrance\b", r"\bparis\b", r"\blyon\b", r"\bmarseille\b", r"\btoulouse\b", r"🇫🇷",
    r"\bnetherlands\b", r"\bamsterdam\b", r"\brotterdam\b", r"\butrecht\b", r"\bholland\b", r",\s*nl\b", r"🇳🇱",
    r"\bspain\b", r"\bmadrid\b", r"\bbarcelona\b", r"\bvalencia\b", r"\bmálaga\b", r"🇪🇸",
    r"\bitaly\b", r"\bitalia\b", r"\bmilan\b", r"\bmilano\b", r"\brome\b", r"\broma\b", r"\bturin\b", r"🇮🇹",
    r"\bportugal\b", r"\blisbon\b", r"\blisboa\b", r"\bporto\b", r"🇵🇹",
    r"\bswitzerland\b", r"\bzurich\b", r"\bzürich\b", r"\bgeneva\b", r"\bbasel\b", r"\blausanne\b", r"🇨🇭",
    r"\bsweden\b", r"\bstockholm\b", r"\bgothenburg\b", r"🇸🇪",
    r"\bnorway\b", r"\boslo\b", r"\bbergen\b", r"🇳🇴",
    r"\bdenmark\b", r"\bcopenhagen\b", r"\baarhus\b", r"🇩🇰",
    r"\bfinland\b", r"\bhelsinki\b", r"🇫🇮",
    r"\bpoland\b", r"\bwarsaw\b", r"\bkrakow\b", r"\bkraków\b", r"\bwroclaw\b", r"🇵🇱",
    r"\bbelgium\b", r"\bbrussels\b", r"\bantwerp\b", r"\bghent\b", r"🇧🇪",
    r"\baustria\b", r"\bvienna\b", r"\bwien\b", r"🇦🇹",
    r"\bczechia\b", r"\bczech republic\b", r"\bprague\b", r"\bpraha\b", r"🇨🇿",
    r"\bestonia\b", r"\btallinn\b", r"🇪🇪",
    r"\blatvia\b", r"\briga\b", r"🇱🇻",
    r"\blithuania\b", r"\bvilnius\b", r"🇱🇹",
    r"\bhungary\b", r"\bbudapest\b", r"🇭🇺",
    r"\bromania\b", r"\bbucharest\b", r"\bcluj\b", r"🇷🇴",
    r"\bgreece\b", r"\bathens\b", r"🇬🇷",
    r"\bcroatia\b", r"\bzagreb\b", r"🇭🇷",
    r"\bslovakia\b", r"\bbratislava\b", r"🇸🇰",
    r"\bslovenia\b", r"\bljubljana\b", r"🇸🇮",
    r"\bbulgaria\b", r"\bsofia\b", r"🇧🇬",
    r"\bluxembourg\b", r"🇱🇺",
    r"\biceland\b", r"\breykjavik\b", r"🇮🇸",
    r"\bmalta\b", r"\bcyprus\b", r"\blimassol\b",
    r"\bukraine\b", r"\bkyiv\b", r"\bkiev\b",
    r"\bserbia\b", r"\bbelgrade\b",
    r"\beurope\b", r"\beuropean union\b", r"\bgalician\b", r"🇪🇺",
]
EU_TEXT_RE = re.compile("|".join(EU_TEXT_PATTERNS), re.IGNORECASE)


def evaluate_location(about_info: dict, profile_loc: str, bio: str) -> Tuple[bool, str, str]:
    """
    Returns (is_eligible, region_label, location_evidence).
    Strictly accepts ONLY US or Europe.
    """
    based_in = (about_info.get("account_based_in") or "").strip()
    source = (about_info.get("source") or "").strip()
    loc_clean = (profile_loc or "").strip()
    bio_clean = (bio or "").strip()
    combined_text = f"{loc_clean} | {bio_clean}"

    based_lower = based_in.lower()

    # Hard reject explicit non-US/EU countries in AboutAccountQuery
    if based_lower in BANNED_ABOUT_COUNTRIES:
        return False, "REJECT", f"About: {based_in} (outside US/Europe)"

    # Special case: "North America" in AboutAccountQuery -> require positive US profile/bio signal & no Canada/Mexico
    if based_lower == "north america":
        if NON_US_EU_TEXT_RE.search(loc_clean) or re.search(r"\b(canada|toronto|vancouver|montreal|ottawa|calgary|waterloo|mexico)\b", combined_text, re.IGNORECASE):
            return False, "REJECT", f"About: North America + non-US loc '{loc_clean}'"
        if US_TEXT_RE.search(combined_text):
            ev = f"X About: North America ({source}); Profile/Bio: '{loc_clean or 'US refs in bio'}'"
            return True, "US", ev
        return False, "AMBIGUOUS", f"About: North America (could be Canada/Mexico), loc='{loc_clean}'"

    # Exact US from AboutAccountQuery
    if based_lower in US_EXACT_ABOUT:
        # Check if user visibly lives outside US/EU (e.g., Dubai/Bali expat) — reject if location field claims another continent
        m_ban = NON_US_EU_TEXT_RE.search(loc_clean)
        if m_ban:
            return False, "REJECT", f"About: {based_in}, but Profile Loc='{loc_clean}'"
        parts = [f"X About: {based_in}" + (f" ({source})" if source else "")]
        if loc_clean:
            parts.append(f"Profile Loc: '{loc_clean}'")
        elif US_TEXT_RE.search(bio_clean):
            parts.append("Bio mentions US city/state")
        return True, "US", "; ".join(parts)

    # Exact European country from AboutAccountQuery
    if based_lower in EUROPE_EXACT_ABOUT:
        m_ban = NON_US_EU_TEXT_RE.search(loc_clean)
        if m_ban:
            return False, "REJECT", f"About: {based_in}, but Profile Loc='{loc_clean}'"
        parts = [f"X About: {based_in}" + (f" ({source})" if source else "")]
        if loc_clean:
            parts.append(f"Profile Loc: '{loc_clean}'")
        return True, f"Europe ({based_in})", "; ".join(parts)

    # Region "Europe" / "Eastern Europe (Non-EU)" / etc. from AboutAccountQuery
    if based_lower in EUROPE_REGION_ABOUT:
        m_ban = NON_US_EU_TEXT_RE.search(loc_clean) or NON_US_EU_TEXT_RE.search(bio_clean)
        if m_ban:
            return False, "REJECT", f"About: {based_in}, but Profile/Bio mentions '{m_ban.group(0)}'"
        country_note = "Europe"
        parts = [f"X About: {based_in}" + (f" ({source})" if source else "")]
        if loc_clean:
            parts.append(f"Profile Loc: '{loc_clean}'")
        elif EU_TEXT_RE.search(bio_clean):
            parts.append("Bio has European refs")
        return True, country_note, "; ".join(parts)

    # Fallback ONLY when AboutAccountQuery returned empty/unavailable
    if not based_lower:
        if NON_US_EU_TEXT_RE.search(combined_text):
            return False, "REJECT", f"No X About; non-US/EU loc '{loc_clean}'"
        if US_TEXT_RE.search(loc_clean):
            return True, "US", f"Profile Loc: '{loc_clean}' (X About unavailable)"
        if EU_TEXT_RE.search(loc_clean):
            return True, "Europe", f"Profile Loc: '{loc_clean}' (X About unavailable)"
        return False, "UNKNOWN", f"No X About & unverified Profile Loc: '{loc_clean}'"

    # Any other unrecognized country in AboutAccountQuery -> reject strictly
    return False, "REJECT", f"About: {based_in}"


BAIT_PATTERNS = [
    r"\bcomment\s+[\"']?[A-Z0-9 _-]{2,20}[\"']?\s+(and|&|to|for)\b",
    r"\breply\s+(with\s+)?[\"']?[A-Z0-9 _-]{2,20}[\"']?\s+(and|&|to|for)\b",
    r"\bi['’]ll\s+(send|dm)\s+(you|it|the)\b",
    r"\bmust\s+be\s+following\b",
    r"\b(like|bookmark)\s*(\+|and|&)\s*(rt|repost|comment|reply)\b",
    r"\bdrop\s+a\s+[^\s]{1,12}\s+(and|&|to)\s+(get|receive|i'll)\b",
    r"\bgiveaway\b",
    r"\bsend\s+to\s+everyone\s+who\b",
]
BAIT_RE = re.compile("|".join(BAIT_PATTERNS), re.IGNORECASE)


def count_bait_tweets(texts) -> int:
    return sum(1 for t in texts if BAIT_RE.search(t or ""))


def classify_niche(bio: str, tweets_text: str) -> Optional[str]:
    """
    Assigns one of the 4 target partnership niches based on practitioner identity in bio
    and/or recurring domain focus across recent tweets:
    - Mobile App Developer
    - App Developer
    - Meta Ads Specialist
    - Ads Specialist
    Returns None if not aligned with any target niche.
    """
    bio_l = (bio or "").lower()
    tw_l = (tweets_text or "").lower()
    all_l = f"{bio_l}\n{tw_l}"

    off_niche_bio = re.search(
        r"\b(memecoin|solana\s+airdrop|crypto\s+signals|forex|sports\s+betting|parlay|"
        r"onlyfans\s+agency|news\s+anchor|senator|congressman|podcast\s+about\s+everything)\b",
        bio_l,
    )

    mob_re = re.compile(
        r"\b(ios\s+dev(?:eloper)?|ios\s+engineer|ios\s+(?:&\s*macos\s+)?apps?|swiftui|swift\s+dev(?:eloper)?|"
        r"ios\s*(?:&|and|/|@|,)\s*(?:swift|macos|mac|goodnotesapp|whop)|swift\s*(?:&|and|/)\s*ios|former\s+iosdev|iosdev|"
        r"ios\s*(?:&|and|/)\s*(?:web|macos)\s+dev|synara\s+ios|my\s+apps\s+have\s+millions\s+of\s+downloads|"
        r"xcode|testflight|app\s*store|react\s*native|flutter|android\s+dev(?:eloper)?|android\s+apps?|"
        r"mobile\s+apps?|mobile\s+dev(?:eloper)?|mobile\s+engineer|iphone\s+(?:app|game)s?|"
        r"revenuecat|superwall|adapty|paywall|paywalls|in-app\s+purchase|arkit|coreml|kotlin|jetpack\s+compose|app\s+downloads|"
        r"aso)\b"
    )
    meta_re = re.compile(
        r"\b(meta\s+ads|facebook\s+ads|fb\s+ads|instagram\s+ads|meta\s+media\s+buy\w*|"
        r"meta[’']?s\s+#?\d*\s*independent\s+agency|meta\s*\+\s*google|advertorials\s+w/\s*meta|"
        r"(?:meta|fb|facebook)\s+(?:ads?\s+)?andromeda|meta\s+agency|"
        r"meta\s+ad\s+account|meta\s+ad\s+creative|meta\s+advertising|meta\s+creative|meta\s+targeting)\b"
    )
    ads_re = re.compile(
        r"\b(creative\s+strateg(?:ist|y|ies)|creative\s+startegist|media\s+buy(?:er|ing)|paid\s+social|"
        r"user\s+acquisition|performance\s+marketing|paid\s+acquisition|paid\s+ads|paid\s+media|tiktok\s+ads|"
        r"google\s+ads|youtube\s+ads|applovin|ugc\s+ads|ai\s+ugc|static\s+ads|ad\s+creatives?|native\s+ads|"
        r"ad\s+buy(?:er|ing)|dr\s+creative|direct\s+response|ad\s+swipe|winning\s+(?:native\s+|ai\s+song\s+)?ads?|ads\s+that\s+print|hook\s+rate|"
        r"hold\s+rate|paid\s+growth|ad\s+spend|ad\s+budgets?|ad\s+account|ad\s*tech|performance\s+creative\w*|creative\s+agenc(?:y|ies)|"
        r"creative\s+partner\s+for\s+\d|bad_marketers|bad\s+ads|"
        r"ai\s+creative\s+director|commercial\s+director|brand\s+series\s+w/ai|making\s+epic\s+ads|top\s+performing\s+ads\s+with\s+ai|"
        r"spent\s+on\s+(?:our\s+|meta\s+|tiktok\s+)?ads|spending\s+\$?\d+[km]\+?\s+(?:per\s+day|a\s+day|daily|monthly|on\s+ads)|"
        r"making?\s+(?:\d+\+?\s+)?ads|banger\s+ads|ugc\s+creator\s+tip|roas|cpm|cpa)\b"
    )
    app_re = re.compile(
        r"\b(app\s+developer|app\s+builder|indie\s+dev|(?:build|building|built|scaling|making|marketing)\s+(?:[\w#]+\s+){0,3}apps?\b|"
        r"(?:make|making|scale|scaled|own|marketing)\s+(?:a\s+few\s+|viral\s+|guitar\s+|consumer\s+|my\s+)?apps?\b|"
        r"(?:built|scaled)\s+@?\w+\s+to\s+[\d,.]+[km]?\+?\s*(?:users|downloads)|[\d,.]+[km]?\+\s+downloads|millions\s+of\s+downloads|000\s+downloads\s+with\s+this|"
        r"indie\s+apps?|consumer\s+apps?|consumer\s+tech|built\s+an\s+app|building\s+an\s+app|app\s+studio|"
        r"app\s+founders?|macos\s+apps?|native\s+macos|desktop\s+apps?|screenstudio|indie\s+maker|indie\s+hacker|"
        r"ship\s+apps|solo\s+products|micro-saas|software\s+maker|app\s+shortcuts|app\s+intents|vibecode|mrr)\b"
    )

    bio_mob = len(mob_re.findall(bio_l))
    tw_mob = len(mob_re.findall(tw_l))
    bio_meta = len(meta_re.findall(bio_l))
    tw_meta = len(meta_re.findall(tw_l))
    bio_ads = len(ads_re.findall(bio_l))
    tw_ads = len(ads_re.findall(tw_l))
    bio_app = len(app_re.findall(bio_l))
    tw_app = len(app_re.findall(tw_l))

    if off_niche_bio and (bio_mob + bio_meta + bio_ads == 0):
        return None

    # 1. Meta Ads Specialist
    if bio_meta >= 1 or tw_meta >= 2 or (re.search(r"\b(meta\s+ads|facebook\s+ads|fb\s+ads|\bfb\b|\bfacebook\b)\b", all_l) and bio_ads >= 1 and bio_app == 0):
        return "Meta Ads Specialist"
    if tw_meta >= 1 and (bio_ads >= 1 or tw_ads >= 2):
        return "Meta Ads Specialist"

    # 2. Mobile App Developer
    if bio_mob >= 1 or tw_mob >= 2:
        return "Mobile App Developer"

    # 3. Ads Specialist
    if bio_ads >= 1 or (tw_ads >= 2 and bio_app == 0 and tw_app == 0 and not re.search(r"\b(vc|venture\s+partner|partner\s+@)\b", bio_l)):
        return "Ads Specialist"

    # 4. App Developer (verify bio/tweets genuinely discuss building/scaling apps or software products)
    if bio_app >= 1 and re.search(r"\b(app|apps|ios|macos|saas|software|mrr|arr|users|downloads|ship|launched|built|screenstudio|vibecode)\b", all_l):
        return "App Developer"
    if tw_app >= 2 and re.search(r"\b(app|apps|ios|macos|ship|built|launching)\b", all_l):
        return "App Developer"

    return None
