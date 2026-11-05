#!/usr/bin/env python3
"""Generate course buttons in menus.json from the official programme lists.

Sources (official only):
- IGNOU UG: ODL Bachelor Degree Programmes PDF, ignou.ac.in
  (duplicates collapsed: BAFSM kept once, BSW kept once, BSCG kept once;
   Agniveer-only Applied Skills programmes excluded — not open to general applicants)
- IGNOU PG: ODL Master Degree Programmes PDF, ignou.ac.in (82 programmes)
- SGOU UG/PG: SGOU Prospectus Feb 2026 session, §9.1 (16 UG + 14 PG)

Re-run after editing the lists below; the running bot picks up menus.json
without a restart.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MENUS_PATH = os.path.join(HERE, "menus.json")

# (code, full official name, short button label)
IGNOU_UG = [
    ("BAAHD", "Bachelor of Arts (Applied Hindi)", "Applied Hindi"),
    ("BAASK", "Bachelor of Arts (Applied Sanskrit)", "Applied Sanskrit"),
    ("BAAUD", "Bachelor of Arts (Applied Urdu)", "Applied Urdu"),
    ("BAECH", "Bachelor of Arts (Honours) Economics", "Economics (Hons)"),
    ("BAEGH", "Bachelor of Arts (Honours) English", "English (Hons)"),
    ("BAFEC", "Bachelor of Arts (Economics)", "Economics"),
    ("BAFEDU", "Bachelor of Arts (Education)", "Education"),
    ("BAFEG", "Bachelor of Arts (English)", "English"),
    ("BAFHD", "Bachelor of Arts (Hindi)", "Hindi"),
    ("BAFHI", "Bachelor of Arts (History)", "History"),
    ("BAFHSC", "Bachelor of Arts (Home Science)", "Home Science"),
    ("BAFJDM", "Bachelor of Arts (Journalism and Digital Media)", "Journalism & Digital Media"),
    ("BAFPA", "Bachelor of Arts (Public Administration)", "Public Administration"),
    ("BAFPS", "Bachelor of Arts (Political Science)", "Political Science"),
    ("BAFPY", "Bachelor of Arts (Philosophy)", "Philosophy"),
    ("BAFSK", "Bachelor of Arts (Sanskrit)", "Sanskrit"),
    ("BAFSM", "Bachelor of Arts (Facility and Services Management)", "Facility & Services Mgmt"),
    ("BAFSO", "Bachelor of Arts (Sociology)", "Sociology"),
    ("BAFUD", "Bachelor of Arts (Urdu)", "Urdu"),
    ("BAFVTM", "Bachelor of Arts (Vocational Studies) Tourism Management", "Tourism Management"),
    ("BAGS", "Bachelor of Arts (Gender Studies)", "Gender Studies"),
    ("BAHDH", "Bachelor of Arts (Honours) Hindi", "Hindi (Hons)"),
    ("BAHIH", "Bachelor of Arts (Honours) History", "History (Hons)"),
    ("BAM", "Bachelor of Arts", "BA (General)"),
    ("BAMSME", "Bachelor of Arts (Micro, Small & Medium Enterprises)", "MSME"),
    ("BAPAH", "Bachelor of Arts (Honours) Public Administration", "Public Admin (Hons)"),
    ("BAPFHMH", "Bachelor of Arts (Performing Arts) Hindustani Music Honours", "Performing Arts – Hindustani Music (Hons)"),
    ("BAPSH", "Bachelor of Arts (Hons) Political Science", "Political Science (Hons)"),
    ("BASKH", "Bachelor of Arts (Hons) Sanskrit", "Sanskrit (Hons)"),
    ("BASOH", "Bachelor of Arts (Hons) Sociology", "Sociology (Hons)"),
    ("BAUDH", "Bachelor of Arts (Hons) URDU", "Urdu (Hons)"),
    ("BBA", "Bachelor of Business Administration", "BBA"),
    ("BBARIL", "Bachelor of Business Administration (Retailing)", "BBA (Retailing)"),
    ("BBASM", "Bachelor of Business Administration (Services Management)", "BBA (Services Mgmt)"),
    ("BCA_NEW", "Bachelor of Computer Applications", "BCA"),
    ("BCOMF", "Bachelor of Commerce", "BCom"),
    ("BED", "Bachelor of Education", "BEd"),
    ("BFTTM", "Bachelor of Tourism & Travel Management", "Tourism & Travel Mgmt"),
    ("BHM", "Bachelor of Science (Hospitality & Hotel Administration)", "Hospitality & Hotel Admin"),
    ("BLIS", "Bachelor of Library and Information Science", "Library & Info Science"),
    ("BPAFHM", "Bachelor of Performing Arts (Hindustani Music)", "Performing Arts – Hindustani Music"),
    ("BSCAEY", "Bachelor of Science (Applied Science-Energy)", "Applied Science – Energy"),
    ("BSCANH", "Bachelor of Science (Honours) Anthropology", "Anthropology (Hons)"),
    ("BSCBCH", "Bachelor of Science (Hons) Biochemistry", "Biochemistry (Hons)"),
    ("BSCFAN", "Bachelor of Science (Anthropology)", "Anthropology"),
    ("BSCFBC", "Bachelor of Science (Biochemistry)", "Biochemistry"),
    ("BSCFFSQM", "Bachelor of Science (Food Safety and Quality Management)", "Food Safety & Quality Mgmt"),
    ("BSCFMT", "Bachelor of Science (Mathematics)", "Mathematics"),
    ("BSCG", "Bachelor of Science", "BSc (General)"),
    ("BSCN", "Bachelor of Science (Nursing (Post Basic))", "Nursing (Post Basic)"),
    ("BSW", "Bachelor of Social Work", "Social Work"),
    ("BABED", "BA-BEd Secondary Stage", "BA–BEd"),
    ("BCOMBED", "BCom-BEd Secondary Stage", "BCom–BEd"),
    ("BSCBED", "BSc-BEd Secondary Stage", "BSc–BEd"),
    ("BSCFFAD", "Bachelor of Science (Fabric and Apparel Design)", "Fabric & Apparel Design"),
]

IGNOU_PG = [
    ("MAAE", "Master of Arts (Adult Education)", "Adult Education"),
    ("MAANY", "Master of Arts (Anthropology)", "Anthropology"),
    ("MAARB", "Master of Arts (Arabic)", "Arabic"),
    ("MAAUD", "Master of Arts (Applied Urdu)", "Applied Urdu"),
    ("MABGS", "Master of Arts (Bhagavadgita Studies)", "Bhagavadgita Studies"),
    ("MACSR", "Master of Arts (Corporate Social Responsibility)", "Corporate Social Responsibility"),
    ("MADE", "Master of Arts (Distance Education)", "Distance Education"),
    ("MADJ", "Master of Arts (Development Journalism)", "Development Journalism"),
    ("MADVS", "Master of Arts (Development Studies)", "Development Studies"),
    ("MAEC", "Master of Arts (Economics)", "Economics"),
    ("MAEDU", "Master of Arts (Education)", "Education"),
    ("MAENOH", "Master of Arts (Environmental and Occupational Health)", "Environmental & Occupational Health"),
    ("MAER", "Master of Arts (Entrepreneurship)", "Entrepreneurship"),
    ("MAEVS", "Master of Arts (Environmental Studies)", "Environmental Studies"),
    ("MAFCS", "Master of Arts (Folklore and Culture Studies)", "Folklore & Culture Studies"),
    ("MAFL", "Master of Arts (French Language)", "French Language"),
    ("MAGD", "Master of Arts (Gender and Development Studies)", "Gender & Development Studies"),
    ("MAHI", "Master of Arts (History)", "History"),
    ("MAHN", "Master of Arts (Hindu Studies)", "Hindu Studies"),
    ("MAHV", "Master of Arts (Hindi Vyavsayik Lekhan)", "Hindi Vyavsayik Lekhan"),
    ("MAJDM", "Master of Arts (Journalism and Digital Media)", "Journalism & Digital Media"),
    ("MAJEM", "Master of Arts (Journalism and Electronic Media)", "Journalism & Electronic Media"),
    ("MAJMC", "Master of Arts (Journalism & Mass Communication)", "Journalism & Mass Communication"),
    ("MAJMCT", "Master of Arts (Journalism and Mass Communication) Tamil", "JMC (Tamil)"),
    ("MAJY", "Master of Arts (Jyotish)", "Jyotish"),
    ("MAMIDI", "Master of Arts (Migration and Diaspora)", "Migration & Diaspora"),
    ("MAPFHS", "Master of Arts (Population and Family Health Studies)", "Population & Family Health Studies"),
    ("MAPY", "Master of Arts (Philosophy)", "Philosophy"),
    ("MARD", "Master of Arts (Rural Development)", "Rural Development"),
    ("MARUS", "Master of Arts (Russian)", "Russian"),
    ("MASL", "Master of Arts (Spanish)", "Spanish"),
    ("MASS", "Master of Arts (Sustainability Science)", "Sustainability Science"),
    ("MATS", "Master of Arts (Translation Studies)", "Translation Studies"),
    ("MAUD", "Master of Arts (Urdu)", "Urdu"),
    ("MAUS", "Master of Arts (Urban Studies)", "Urban Studies"),
    ("MAVS", "Master of Arts (Vedic Studies)", "Vedic Studies"),
    ("MAWGSR", "Master of Arts (Women's and Gender Studies)", "Women's & Gender Studies"),
    ("MBA", "Master of Business Administration", "MBA"),
    ("MBAMM", "Master of Business Administration (Marketing Management)", "MBA (Marketing)"),
    ("MBAFM", "Master of Business Administration (Financial Management)", "MBA (Finance)"),
    ("MBAHM", "Master of Business Administration (Human Resource Management)", "MBA (HR)"),
    ("MBAOM", "Master of Business Administration (Operations Management)", "MBA (Operations)"),
    ("MBAABM", "Master of Business Administration (Agribusiness Management)", "MBA (Agribusiness)"),
    ("MBACN", "Master of Business Administration (Construction Management)", "MBA (Construction)"),
    ("MBAHCHM", "Master of Business Administration (Health Care and Hospital Management)", "MBA (Health Care & Hospital)"),
    ("MBALS", "Master of Business Administration (Logistics & Supply Chain Management)", "MBA (Logistics & Supply Chain)"),
    ("MBF", "Master of Business Administration (Banking and Finance)", "MBA (Banking & Finance)"),
    ("MCA_NEW", "Master of Computer Applications", "MCA"),
    ("MCOM", "Master of Commerce", "MCom"),
    ("MAEG", "Master of Arts (English)", "English"),
    ("MGPS", "Master of Arts (Gandhi and Peace Studies)", "Gandhi & Peace Studies"),
    ("MHA", "Master of Science (Hospitality Administration)", "Hospitality Administration"),
    ("MAHD", "Master of Arts (Hindi)", "Hindi"),
    ("MLIS", "Master of Library and Information Science", "Library & Info Science"),
    ("MPA", "Master of Arts (Public Administration)", "Public Administration"),
    ("MAPS", "Master of Arts (Political Science)", "Political Science"),
    ("MSCANCHEM", "Master of Science (Analytical Chemistry)", "Analytical Chemistry"),
    ("MSCAST", "Master of Science (Applied Statistics)", "Applied Statistics"),
    ("MSCBCH", "Master of Science (Biochemistry)", "Biochemistry"),
    ("MSCCHEM", "Master of Science (Chemistry)", "Chemistry"),
    ("MSCENV", "Master of Science (Environmental Science)", "Environmental Science"),
    ("MSCFSQM", "Master of Science (Food Safety and Quality Management)", "Food Safety & Quality Mgmt"),
    ("MSCGG", "Master of Science (Geography)", "Geography"),
    ("MSCGI", "Master of Science (Geoinformatics)", "Geoinformatics"),
    ("MSCHSC", "Master of Science (Home Science - Community Development and Extension Management)", "Home Science – Community Dev."),
    ("MSCIDS", "Master of Science (Industrial Safety)", "Industrial Safety"),
    ("MSCIS", "Master of Science (Information Security)", "Information Security"),
    ("MSCMACS", "M.Sc. (Mathematics with Applications in Computer Science)", "Maths with Applications in CS"),
    ("MSCPH", "Master of Science (Physics)", "Physics"),
    ("MSCRWEE", "Master of Science (Renewable Energy and Environment)", "Renewable Energy & Environment"),
    ("MSCZOO", "Master of Science (Zoology)", "Zoology"),
    ("MSK", "Master of Arts (Sanskrit)", "Sanskrit"),
    ("MASO", "Master of Arts (Sociology)", "Sociology"),
    ("MSW", "Master of Social Work", "Social Work"),
    ("MSWC", "Master of Social Work (Counselling)", "Social Work (Counselling)"),
    ("MTTM_NEW", "Master of Tourism & Travel Management", "Tourism & Travel Mgmt"),
    ("MFAP", "Master of Fine Arts (Painting)", "Fine Arts (Painting)"),
    ("MSCDSA", "Master of Science (Data Science and Analytics)", "Data Science & Analytics"),
    ("MAHUE", "Master of Arts (Human Values and Ethics)", "Human Values & Ethics"),
    ("MSCAIML", "Master of Science (Artificial Intelligence and Machine Learning)", "AI & Machine Learning"),
    ("MSCCC", "Master of Science (CLIMATE CHANGE)", "Climate Change"),
    ("MPATHA", "Master of Performing Arts (Theatre Arts)", "Performing Arts (Theatre Arts)"),
]

# (slug, full official name, short button label) — SGOU prospectus prints no codes, names only
SGOU_UG = [
    ("bba-hons", "BBA (Honours) — HR / Marketing / Logistics & Supply Chain Management", "BBA (Honours)"),
    ("bcom-hons", "B.Com (Honours) — Finance / Cooperation / Logistics & Supply Chain Management", "B.Com (Honours)"),
    ("ba-hons-english", "B.A. (Honours) English", "B.A. (Honours) English"),
    ("ba-hons-malayalam", "B.A. (Honours) Malayalam", "B.A. (Honours) Malayalam"),
    ("ba-hons-history", "B.A. (Honours) History", "B.A. (Honours) History"),
    ("ba-hons-sociology", "B.A. (Honours) Sociology", "B.A. (Honours) Sociology"),
    ("ba-afsal", "B.A. Afsal-Ul-Ulama", "B.A. Afsal-Ul-Ulama"),
    ("ba-arabic", "B.A. Arabic", "B.A. Arabic"),
    ("ba-hindi", "B.A. Hindi", "B.A. Hindi"),
    ("ba-sanskrit", "B.A. Sanskrit", "B.A. Sanskrit"),
    ("ba-economics", "B.A. Economics", "B.A. Economics"),
    ("ba-nano", "B.A. Nano Entrepreneurship", "B.A. Nano Entrepreneurship"),
    ("ba-philosophy", "B.A. Philosophy", "B.A. Philosophy"),
    ("ba-polsci", "B.A. Political Science", "B.A. Political Science"),
    ("bca", "BCA (Bachelor of Computer Applications)", "BCA"),
    ("bsc-dsa", "BSc Data Science and Analytics", "BSc Data Science and Analytics"),
]

SGOU_PG = [
    ("ma-arabic", "M.A. Arabic", "M.A. Arabic"),
    ("ma-english", "M.A. English", "M.A. English"),
    ("ma-hindi", "M.A. Hindi", "M.A. Hindi"),
    ("ma-malayalam", "M.A. Malayalam", "M.A. Malayalam"),
    ("ma-sanskrit", "M.A. Sanskrit", "M.A. Sanskrit"),
    ("ma-economics", "M.A. Economics", "M.A. Economics"),
    ("ma-history", "M.A. History", "M.A. History"),
    ("ma-philosophy", "M.A. Philosophy", "M.A. Philosophy"),
    ("ma-polsci", "M.A. Political Science", "M.A. Political Science"),
    ("ma-pubadmin", "M.A. Public Administration", "M.A. Public Administration"),
    ("ma-sociology", "M.A. Sociology", "M.A. Sociology"),
    ("mcom", "M.Com (Master of Commerce)", "M.Com"),
    ("mba", "MBA", "MBA"),
    ("mca", "MCA", "MCA"),
]


FYUG_8_IGNOU = {
    # IGNOU FYUGP honours programmes (4-year, 8 semesters) + integrated 4-year BEd
    "BAECH", "BAEGH", "BAHDH", "BAHIH", "BAPAH", "BAPSH", "BASKH", "BASOH",
    "BAUDH", "BAPFHMH", "BSCANH", "BSCBCH", "BABED", "BCOMBED", "BSCBED",
}
FYUG_8_SGOU = {
    # SGOU Four-Year UG Honours (FYUGP) programmes
    "bba-hons", "bcom-hons", "ba-hons-english", "ba-hons-malayalam",
    "ba-hons-history", "ba-hons-sociology",
}

# IGNOU programmes that stay SEMESTER-based. Everything else IGNOU is YEARLY
# (annual system: UG = 3 years, PG = 2 years).
SEMESTER_IGNOU = FYUG_8_IGNOU | {
    # professional semester-based programmes
    "BCA_NEW", "BBA", "BBARIL", "BBASM",
    "MBA", "MBAMM", "MBAFM", "MBAHM", "MBAOM", "MBAABM", "MBACN",
    "MBAHCHM", "MBALS", "MBF", "MCA_NEW",
    "BED", "BLIS", "MLIS", "BSCN", "BHM", "MTTM_NEW",
}


def is_yearly(uni: str, ident: str) -> bool:
    """IGNOU yearly (annual-system) courses; SGOU stays semester-based."""
    return uni == "IGNOU" and ident not in SEMESTER_IGNOU


def year_count(level: str) -> int:
    return 3 if level == "UG" else 2


def sem_count(uni: str, level: str, ident: str) -> int:
    """Semesters per course: FYUG 8, standard UG 6, PG 4, 1-year BLIS/MLIS 2."""
    if level == "UG":
        if uni == "IGNOU" and ident in FYUG_8_IGNOU:
            return 8
        if uni == "SGOU" and ident in FYUG_8_SGOU:
            return 8
        if ident in ("BLIS",):
            return 2
        if ident in ("BED", "BSCN"):
            return 4
        return 6
    # PG: 2-year master's = 4 semesters, except 1-year MLIS = 2
    if ident == "MLIS":
        return 2
    return 4


def content_action_buttons(menus: dict, full: str, parent_key: str,
                           scope: str, back_to: str) -> list[list[dict]]:
    """Notes / Assignments / Question Papers / Others rows + their pages + Back."""
    rows: list[list[dict]] = []
    for label, slug in [("Notes", "notes"), ("Assignments", "assignments"),
                        ("Question Papers", "papers"), ("Others", "others")]:
        if not rows or len(rows[-1]) == 2:
            rows.append([])
        rows[-1].append({"text": label, "to": f"{parent_key}-{slug}"})
        menus[f"{parent_key}-{slug}"] = {
            "text": f"{full} — {scope} — {label}\n\nContent coming soon.",
            "buttons": [[{"text": "⬅ Back", "to": parent_key}]],
        }
    rows.append([{"text": "⬅ Back", "to": back_to}])
    return rows


CATEGORIES = {
    # level menu -> [(category key, button label, [course idents])]
    "ignou-ug": [
        ("ba", "BA", ["BAAHD", "BAASK", "BAAUD", "BAECH", "BAEGH", "BAFEC", "BAFEDU",
                      "BAFEG", "BAFHD", "BAFHI", "BAFHSC", "BAFJDM", "BAFPA", "BAFPS",
                      "BAFPY", "BAFSK", "BAFSM", "BAFSO", "BAFUD", "BAFVTM", "BAGS",
                      "BAHDH", "BAHIH", "BAM", "BAMSME", "BAPAH", "BAPFHMH", "BAPSH",
                      "BASKH", "BASOH", "BAUDH"]),
        ("bba", "BBA", ["BBA", "BBARIL", "BBASM"]),
        ("bca", "BCA", ["BCA_NEW"]),
        ("bcom", "BCom", ["BCOMF"]),
        ("bed", "BEd", ["BED", "BABED", "BCOMBED", "BSCBED"]),
        ("bsc", "BSc", ["BSCAEY", "BSCANH", "BSCBCH", "BSCFAN", "BSCFBC", "BSCFFSQM",
                        "BSCFMT", "BSCG", "BSCN", "BSCFFAD"]),
        ("other", "Other", ["BSW", "BFTTM", "BHM", "BLIS", "BPAFHM"]),
    ],
    "ignou-pg": [
        ("ma", "MA", ["MAAE", "MAANY", "MAARB", "MAAUD", "MABGS", "MACSR", "MADE",
                      "MADJ", "MADVS", "MAEC", "MAEDU", "MAENOH", "MAER", "MAEVS",
                      "MAFCS", "MAFL", "MAGD", "MAHI", "MAHN", "MAHV", "MAJDM",
                      "MAJEM", "MAJMC", "MAJMCT", "MAJY", "MAMIDI", "MAPFHS", "MAPY",
                      "MARD", "MARUS", "MASL", "MASS", "MATS", "MAUD", "MAUS", "MAVS",
                      "MAWGSR", "MAEG", "MGPS", "MAHD", "MPA", "MSK", "MASO", "MAHUE",
                      "MAPS"]),
        ("mba", "MBA", ["MBA", "MBAMM", "MBAFM", "MBAHM", "MBAOM", "MBAABM", "MBACN",
                        "MBAHCHM", "MBALS", "MBF"]),
        ("mca", "MCA", ["MCA_NEW"]),
        ("mcom", "MCom", ["MCOM"]),
        ("msc", "MSc", ["MSCANCHEM", "MSCAST", "MSCBCH", "MSCCHEM", "MSCENV",
                        "MSCFSQM", "MSCGG", "MSCGI", "MSCHSC", "MSCIDS", "MSCIS",
                        "MSCMACS", "MSCPH", "MSCRWEE", "MSCZOO", "MSCDSA", "MSCAIML",
                        "MSCCC"]),
        ("msw", "MSW", ["MSW", "MSWC"]),
        ("other", "Other", ["MLIS", "MHA", "MTTM_NEW", "MFAP", "MPATHA"]),
    ],
    "sgou-ug": [
        ("ba", "BA", ["ba-hons-english", "ba-hons-malayalam", "ba-hons-history",
                      "ba-hons-sociology", "ba-afsal", "ba-arabic", "ba-hindi",
                      "ba-sanskrit", "ba-economics", "ba-nano", "ba-philosophy",
                      "ba-polsci"]),
        ("bba", "BBA", ["bba-hons"]),
        ("bcom", "BCom", ["bcom-hons"]),
        ("bca", "BCA", ["bca"]),
        ("bsc", "BSc", ["bsc-dsa"]),
    ],
    "sgou-pg": [
        ("ma", "MA", ["ma-arabic", "ma-english", "ma-hindi", "ma-malayalam",
                      "ma-sanskrit", "ma-economics", "ma-history", "ma-philosophy",
                      "ma-polsci", "ma-pubadmin", "ma-sociology"]),
        ("mcom", "MCom", ["mcom"]),
        ("mba", "MBA", ["mba"]),
        ("mca", "MCA", ["mca"]),
    ],
}


MAJOR = {
    # (level menu, category) -> idents shown directly with readable names.
    # The rest go under an "Other Courses" submenu. Categories not listed
    # here show all their courses directly.
    ("ignou-ug", "ba"): ["BAM", "BAFEG", "BAEGH", "BAFEC", "BAECH", "BAFHI", "BAHIH",
                         "BAFPS", "BAPSH", "BAFSO", "BASOH", "BAFHD", "BAHDH",
                         "BAFSK", "BASKH", "BAFUD", "BAUDH", "BAFPY", "BAFPA",
                         "BAPAH", "BAFEDU", "BAFHSC", "BAFJDM"],
    ("ignou-ug", "bsc"): ["BSCG", "BSCFMT", "BSCFAN", "BSCFBC", "BSCN", "BSCFFSQM"],
    ("ignou-pg", "ma"): ["MAEG", "MAHD", "MAHI", "MAPS", "MASO", "MAEC", "MAEDU",
                         "MPA", "MSK", "MAUD", "MAPY", "MAJMC", "MARD", "MGPS",
                         "MATS", "MAGD", "MADVS", "MADE"],
    ("ignou-pg", "mba"): ["MBA", "MBAHM", "MBAFM", "MBAMM", "MBAOM"],
    ("ignou-pg", "msc"): ["MSCCHEM", "MSCPH", "MSCBCH", "MSCENV", "MSCGG", "MSCZOO",
                          "MSCAST", "MSCMACS", "MSCDSA", "MSCAIML"],
    ("sgou-ug", "ba"): ["ba-hons-english", "ba-hons-malayalam", "ba-hons-history",
                        "ba-hons-sociology", "ba-arabic", "ba-economics", "ba-hindi",
                        "ba-sanskrit", "ba-polsci", "ba-philosophy"],
    ("sgou-pg", "ma"): ["ma-english", "ma-malayalam", "ma-history", "ma-sociology",
                        "ma-economics", "ma-polsci", "ma-hindi", "ma-arabic",
                        "ma-sanskrit"],
}


def build(menus: dict) -> dict:
    groups = [
        ("ignou-ug", "IGNOU", "UG", IGNOU_UG, "ignou"),
        ("ignou-pg", "IGNOU", "PG", IGNOU_PG, "ignou"),
        ("sgou-ug", "SGOU", "UG", SGOU_UG, "sgou"),
        ("sgou-pg", "SGOU", "PG", SGOU_PG, "sgou"),
    ]
    for level_key, uni, level, courses, parent in groups:
        by_ident = {}
        for entry in courses:
            if uni == "IGNOU":
                code, full, short = entry
                key = f"{level_key}-{code.lower().replace('_', '')}"
                ident = code
            else:
                slug, full, short = entry
                key = f"{level_key}-{slug}"
                ident = slug
                code = None
            by_ident[ident] = (key, full, short, code)
        cats = CATEGORIES[level_key]
        seen: list[str] = []
        for _, _, idents in cats:
            seen.extend(idents)
        assert sorted(seen) == sorted(by_ident), \
            f"category coverage mismatch in {level_key}: missing={sorted(set(by_ident) - set(seen))} extra={sorted(set(seen) - set(by_ident))}"
        cat_rows: list[list[dict]] = []
        for cat_key, cat_label, idents in cats:
            cat_menu_key = f"{level_key}-{cat_key}"
            if not cat_rows or len(cat_rows[-1]) == 3:
                cat_rows.append([])
            cat_rows[-1].append({"text": cat_label, "to": cat_menu_key})
            major = MAJOR.get((level_key, cat_key), idents)
            other = [i for i in idents if i not in major]
            assert sorted(major + other) == sorted(idents), \
                f"major/other split mismatch in {cat_menu_key}"
            course_rows: list[list[dict]] = []
            for ident in major:
                key, full, short, code = by_ident[ident]
                label = short  # readable course name (code shown on the course page)
                assert len(label.encode()) <= 64, f"button too long: {label}"
                assert len(("menu:" + key).encode()) <= 64, f"callback too long: {key}"
                if not course_rows or len(course_rows[-1]) == 3:
                    course_rows.append([])
                course_rows[-1].append({"text": label, "to": key})
                _course_pages(menus, uni, level, key, full, code, cat_menu_key, ident)
            if other:
                other_key = f"{cat_menu_key}-other"
                course_rows.append([{"text": "Other Courses", "to": other_key}])
                other_rows: list[list[dict]] = []
                for ident in other:
                    key, full, short, code = by_ident[ident]
                    label = f"{code} · {short}" if code else short
                    assert len(label.encode()) <= 64, f"button too long: {label}"
                    other_rows.append([{"text": label, "to": key}])
                    _course_pages(menus, uni, level, key, full, code, other_key, ident)
                other_rows.append([{"text": "⬅ Back", "to": cat_menu_key}])
                menus[other_key] = {
                    "text": f"{uni} — {level} — {cat_label} — Other Courses:",
                    "buttons": other_rows,
                }
            course_rows.append([{"text": "⬅ Back", "to": level_key}])
            menus[cat_menu_key] = {
                "text": f"{uni} — {level} — {cat_label}:",
                "buttons": course_rows,
            }
        cat_rows.append([{"text": "⬅ Back", "to": parent}])
        menus[level_key] = {
            "text": f"{uni} — {level} programmes:\n\nChoose a category:",
            "buttons": cat_rows,
        }
    return menus


def _course_pages(menus: dict, uni: str, level: str, key: str, full: str,
                  code: str | None, back_to: str, ident: str) -> None:
    """Year/Semester buttons + Notes/Assignments/Papers/Others for one course."""
    title = f"{code} — {full}" if code else full
    if is_yearly(uni, ident):
        n = year_count(level)
        year_row = [{"text": f"Year {i}", "to": f"{key}-yr{i}"}
                    for i in range(1, n + 1)]
        for i in range(1, n + 1):
            yr_key = f"{key}-yr{i}"
            menus[yr_key] = {
                "text": f"{title} — Year {i}\n\nChoose what you need:",
                "buttons": content_action_buttons(menus, title, yr_key, f"Year {i}", key),
            }
        menus[key] = {
            "text": f"{title}\n\nChoose a year:",
            "buttons": [year_row, [{"text": "⬅ Back", "to": back_to}]],
        }
        return
    n = sem_count(uni, level, ident)
    sem_rows: list[list[dict]] = []
    for i in range(1, n + 1):
        if (i - 1) % 4 == 0:
            sem_rows.append([])
        sem_key = f"{key}-sem{i}"
        sem_rows[-1].append({"text": f"Sem {i}", "to": sem_key})
        menus[sem_key] = {
            "text": f"{title} — Semester {i}\n\nChoose what you need:",
            "buttons": content_action_buttons(menus, title, sem_key, f"Semester {i}", key),
        }
    menus[key] = {
        "text": f"{title}\n\nChoose a semester:",
        "buttons": sem_rows + [[{"text": "⬅ Back", "to": back_to}]],
    }


def main() -> None:
    with open(MENUS_PATH, encoding="utf-8") as f:
        menus = json.load(f)
    # drop all generated keys (course / semester / year / action pages) so
    # stale pages from earlier structures don't linger; build() regenerates them
    shell_keys = {"home", "welcome", "ignou", "sgou", "ignou-faq", "sgou-faq",
                  "daily-study"}
    menus = {k: v for k, v in menus.items() if k in shell_keys}
    menus = build(menus)
    # main menu: universities + Daily Study product
    menus["home"] = {
        "text": "Welcome to Mission Academy! 🎓\n\nChoose an option:",
        "buttons": [[{"text": "IGNOU", "to": "ignou"},
                     {"text": "SGOU", "to": "sgou"}],
                    [{"text": "📝 Daily Study", "to": "daily-study"}]],
    }
    # Daily Study hub: quiz + notes + subscribe (the three action buttons are
    # intercepted by handlers.py, not real menus)
    menus["daily-study"] = {
        "text": ("📝 Daily Study\n\n"
                 "One quiz + one notes card every day — free.\n"
                 "Tap below to take today's quiz or read today's notes."),
        "buttons": [[{"text": "❓ Take Today's Quiz", "to": "daily-quiz-take"}],
                    [{"text": "📚 Today's Notes", "to": "daily-notes"}],
                    [{"text": "🔔 Subscribe to Daily Study", "to": "daily-subscribe"}],
                    [{"text": "⬅ Back", "to": "home"}]],
    }
    # entry screen: a Start button that opens the main menu + channel link
    menus["welcome"] = {
        "text": ("Welcome to Mission Academy! 🎓\n\n"
                 "Tap Start to continue:\n\n"
                 "📢 Join our channel:\n"
                 "https://t.me/missionacademy_official"),
        "buttons": [[{"text": "▶ Start", "to": "home"}]],
    }
    # verify every route resolves (action buttons are intercepted by
    # handlers.py, not real menus)
    ACTION_KEYS = {"daily-quiz-take", "daily-notes", "daily-subscribe"}
    for key, menu in menus.items():
        for row in menu["buttons"]:
            for b in row:
                assert b["to"] in menus or b["to"] in ACTION_KEYS, \
                    f"dead link {key} -> {b['to']}"
    with open(MENUS_PATH, "w", encoding="utf-8") as f:
        json.dump(menus, f, ensure_ascii=False, indent=2)
    counts = {k: len(v["buttons"]) - 1 for k, v in menus.items()
              if k in ("ignou-ug", "ignou-pg", "sgou-ug", "sgou-pg")}
    print("course buttons:", counts, "| total menus:", len(menus))


if __name__ == "__main__":
    main()
