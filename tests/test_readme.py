def test_readme_covers_the_submission_points():
    text = open("README.md", encoding="utf-8").read().lower()
    for needle in ("approval", "recurring support", "fee confusion", "playstore.csv", "evals", "twelve", "known limit"):
        assert needle in text
