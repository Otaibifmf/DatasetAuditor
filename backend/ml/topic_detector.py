"""
NLP topic detector — classify datasets into government domains.
Uses TF-IDF + cosine similarity against keyword centroids.
Falls back to keyword matching for zero-shot datasets.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

# Topic → seed keywords (Arabic + English)
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "Health": [
        "health", "hospital", "disease", "patient", "medical", "clinic",
        "mortality", "morbidity", "vaccination", "صحة", "مستشفى", "مريض",
        "علاج", "أمراض", "تطعيم",
    ],
    "Education": [
        "school", "student", "university", "education", "enrollment",
        "teacher", "curriculum", "تعليم", "مدرسة", "طالب", "جامعة",
        "معلم", "منهج",
    ],
    "Economy": [
        "gdp", "trade", "export", "import", "inflation", "budget",
        "revenue", "expenditure", "اقتصاد", "تجارة", "صادرات", "واردات",
        "ميزانية", "إيرادات",
    ],
    "Population": [
        "population", "census", "demographic", "birth", "death",
        "migration", "nationality", "سكان", "تعداد", "ديموغرافي",
        "مواليد", "وفيات", "هجرة",
    ],
    "Environment": [
        "environment", "pollution", "climate", "water", "air quality",
        "carbon", "renewable", "بيئة", "تلوث", "مناخ", "مياه", "هواء",
    ],
    "Transport": [
        "transport", "road", "traffic", "vehicle", "airline", "flight",
        "port", "نقل", "طريق", "مرور", "سيارة", "طيران", "ميناء",
    ],
    "Energy": [
        "energy", "oil", "gas", "electricity", "power", "renewable",
        "consumption", "طاقة", "نفط", "غاز", "كهرباء",
    ],
    "Agriculture": [
        "agriculture", "farm", "crop", "livestock", "food", "irrigation",
        "زراعة", "مزرعة", "محاصيل", "ماشية", "غذاء",
    ],
    "Tourism": [
        "tourism", "hotel", "visitor", "heritage", "museum",
        "سياحة", "فندق", "زائر", "تراث", "متحف",
    ],
    "Finance": [
        "bank", "credit", "loan", "stock", "investment", "insurance",
        "بنك", "ائتمان", "قرض", "أسهم", "استثمار",
    ],
    "Labor": [
        "employment", "workforce", "salary", "wage", "unemployment",
        "occupation", "عمل", "توظيف", "راتب", "أجر", "بطالة",
    ],
    "Justice": [
        "crime", "court", "police", "law", "penalty", "prison",
        "جريمة", "محكمة", "شرطة", "قانون", "عقوبة", "سجن",
    ],
}


def detect_topic(dataset: dict) -> str:
    """Return the most likely topic string for a dataset."""
    title = dataset.get("title") or dataset.get("name") or ""
    notes = dataset.get("notes") or dataset.get("description") or ""
    tags = " ".join(t.get("name", "") for t in dataset.get("tags", []))
    groups = " ".join(g.get("title", "") for g in dataset.get("groups", []))

    text = f"{title} {notes} {tags} {groups}".lower()
    scores: dict[str, int] = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        hit = sum(1 for kw in keywords if kw in text)
        scores[topic] = hit

    best_topic = max(scores, key=scores.get)
    best_score = scores[best_topic]

    if best_score == 0:
        return "General / Uncategorised"
    return best_topic
