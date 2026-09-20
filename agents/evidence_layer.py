"""
Evidence Layer — reads raw reviews and prepares them for the
Insights Agent. Pure code, no LLM involved at this stage.
"""

def load_reviews(filepath: str) -> list[dict]:
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
            "id": f"REV-{review_number:03d}",
            "header": header,
            "text": text
        })
        review_number += 1

    return reviews


if __name__ == "__main__":
    reviews = load_reviews("data/reviews/mcp_padel_reviews.txt")
    print(f"Loaded {len(reviews)} reviews.\n")
    for r in reviews[:3]:
        print(r)