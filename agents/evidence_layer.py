"""
Evidence Layer — reads raw reviews and prepares them for the
Insights Agent. Pure code, no LLM involved at this stage.

Each source gets its own ID prefix (REV- for Google reviews, ENC- for
survey responses), so an ID always points to exactly one entry in one
source — needed for the triangulation step, which checks whether a
pattern appears in BOTH sources.
"""


def load_reviews(filepath: str, prefix: str = "REV") -> list[dict]:
    """Reads the review file and splits it into individual,
    ID-tagged review records. Skips header/metadata lines."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Split on blank lines between entries
    raw_entries = [entry.strip() for entry in content.split("\n\n") if entry.strip()]

    reviews = []
    review_number = 1
    for entry in raw_entries:
        lines = entry.split("\n", 1)
        header = lines[0] if len(lines) > 0 else ""

        # Skip anything that's a section marker, not a real review
        if header.startswith("===") or header.startswith("---"):
            continue

        text = lines[1].strip('"') if len(lines) > 1 else ""

        reviews.append({
            "id": f"{prefix}-{review_number:03d}",
            "header": header,
            "text": text
        })
        review_number += 1

    return reviews


if __name__ == "__main__":
    reviews = load_reviews("data/reviews/padel_club_reviews_anonymized.txt")
    survey = load_reviews("data/reviews/padel_club_survey_sept_week3.txt", prefix="ENC")
    print(f"Loaded {len(reviews)} reviews and {len(survey)} survey responses.\n")
    for r in reviews[:2] + survey[:2]:
        print(r)