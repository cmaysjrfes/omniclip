"""Category → sub-category tree for the niche selector (extend freely; free-text niche refines it)."""
TAXONOMY: dict[str, list[str]] = {
    "Business & Finance": ["Personal finance", "Investing", "Entrepreneurship", "Real estate", "Crypto", "Side hustles"],
    "Technology": ["AI & machine learning", "Programming", "Gadgets & reviews", "Cybersecurity", "Startups"],
    "Education": ["Science explainers", "History", "Language learning", "Study tips", "Math"],
    "Health & Fitness": ["Strength training", "Nutrition", "Mental health", "Running & endurance", "Longevity"],
    "Entertainment": ["Podcast clips", "Commentary", "Movie & TV breakdowns", "Comedy", "Celebrity interviews"],
    "Gaming": ["Esports", "Speedrunning", "Game reviews", "Let's plays", "Retro gaming"],
    "Lifestyle": ["Productivity", "Minimalism", "Travel", "Food & cooking", "Relationships"],
    "Motivation & Self-help": ["Mindset", "Discipline", "Public speaking", "Career growth"],
    "Sports": ["Football/Soccer", "Basketball", "Combat sports", "Motorsport", "Sports analysis"],
    "News & Politics": ["Explainers", "Debates", "Geopolitics", "Local news"],
}
