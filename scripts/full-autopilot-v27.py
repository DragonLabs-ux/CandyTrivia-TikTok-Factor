from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import full_autopilot_fixed as base  # type: ignore
except ImportError:
    try:
        import full_autopilot as base  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "Could not find full_autopilot_fixed.py or full_autopilot.py in the project root. "
            "Keep your existing one-script autopilot in the repo root, then run this wrapper."
        ) from exc


STATE_CAPITALS = {
    "Alabama": "Montgomery", "Alaska": "Juneau", "Arizona": "Phoenix", "Arkansas": "Little Rock",
    "California": "Sacramento", "Colorado": "Denver", "Connecticut": "Hartford", "Delaware": "Dover",
    "Florida": "Tallahassee", "Georgia": "Atlanta", "Hawaii": "Honolulu", "Idaho": "Boise",
    "Illinois": "Springfield", "Indiana": "Indianapolis", "Iowa": "Des Moines", "Kansas": "Topeka",
    "Kentucky": "Frankfort", "Louisiana": "Baton Rouge", "Maine": "Augusta", "Maryland": "Annapolis",
    "Massachusetts": "Boston", "Michigan": "Lansing", "Minnesota": "Saint Paul", "Mississippi": "Jackson",
    "Missouri": "Jefferson City", "Montana": "Helena", "Nebraska": "Lincoln", "Nevada": "Carson City",
    "New Hampshire": "Concord", "New Jersey": "Trenton", "New Mexico": "Santa Fe", "New York": "Albany",
    "North Carolina": "Raleigh", "North Dakota": "Bismarck", "Ohio": "Columbus", "Oklahoma": "Oklahoma City",
    "Oregon": "Salem", "Pennsylvania": "Harrisburg", "Rhode Island": "Providence", "South Carolina": "Columbia",
    "South Dakota": "Pierre", "Tennessee": "Nashville", "Texas": "Austin", "Utah": "Salt Lake City",
    "Vermont": "Montpelier", "Virginia": "Richmond", "Washington": "Olympia", "West Virginia": "Charleston",
    "Wisconsin": "Madison", "Wyoming": "Cheyenne",
}

COUNTRY_CAPITALS = {
    "Argentina": "Buenos Aires", "Australia": "Canberra", "Austria": "Vienna", "Belgium": "Brussels",
    "Brazil": "Brasilia", "Canada": "Ottawa", "Chile": "Santiago", "China": "Beijing",
    "Colombia": "Bogota", "Croatia": "Zagreb", "Czech Republic": "Prague", "Denmark": "Copenhagen",
    "Egypt": "Cairo", "Finland": "Helsinki", "France": "Paris", "Germany": "Berlin",
    "Greece": "Athens", "Hungary": "Budapest", "Iceland": "Reykjavik", "India": "New Delhi",
    "Ireland": "Dublin", "Italy": "Rome", "Japan": "Tokyo", "Kenya": "Nairobi",
    "Mexico": "Mexico City", "Morocco": "Rabat", "Netherlands": "Amsterdam", "New Zealand": "Wellington",
    "Norway": "Oslo", "Peru": "Lima", "Philippines": "Manila", "Poland": "Warsaw",
    "Portugal": "Lisbon", "Romania": "Bucharest", "Russia": "Moscow", "Saudi Arabia": "Riyadh",
    "Singapore": "Singapore", "South Korea": "Seoul", "Spain": "Madrid", "Sweden": "Stockholm",
    "Switzerland": "Bern", "Thailand": "Bangkok", "Turkey": "Ankara", "Ukraine": "Kyiv",
    "United Kingdom": "London", "Vietnam": "Hanoi", "Cuba": "Havana", "Jamaica": "Kingston",
    "Nepal": "Kathmandu", "Pakistan": "Islamabad",
}

CURATED = [
    ("How many continents are there on Earth?", "7"),
    ("What is the largest planet in our solar system?", "Jupiter"),
    ("What gas do plants absorb from the air?", "Carbon dioxide"),
    ("How many hearts does an octopus have?", "3"),
    ("What is the fastest land animal?", "Cheetah"),
    ("What is the tallest animal in the world?", "Giraffe"),
    ("What is the largest mammal on Earth?", "Blue whale"),
    ("What planet is known as the Red Planet?", "Mars"),
    ("Which ocean is the largest?", "Pacific Ocean"),
    ("What is H2O commonly called?", "Water"),
    ("How many sides does a hexagon have?", "6"),
    ("What is the smallest prime number?", "2"),
    ("What is the boiling point of water in Celsius?", "100"),
    ("How many days are in a leap year?", "366"),
    ("What color do you get by mixing red and blue?", "Purple"),
    ("Which planet is famous for its rings?", "Saturn"),
    ("What is the hardest natural substance?", "Diamond"),
    ("How many bones are in the adult human body?", "206"),
    ("What is the main gas in Earth's atmosphere?", "Nitrogen"),
    ("What is the largest organ in the human body?", "Skin"),
    ("What shape has three sides?", "Triangle"),
    ("What do bees collect from flowers?", "Nectar"),
    ("Which animal is known for changing color?", "Chameleon"),
    ("What is the nearest star to Earth?", "The Sun"),
    ("What is the only mammal capable of true flight?", "Bat"),
    ("How many planets are in our solar system?", "8"),
    ("What instrument commonly has 88 keys?", "Piano"),
    ("Which month has the fewest days?", "February"),
    ("How many minutes are in an hour?", "60"),
    ("What is frozen water called?", "Ice"),
    ("What do caterpillars turn into?", "Butterflies"),
    ("Which planet is closest to the Sun?", "Mercury"),
    ("Which metal is liquid at room temperature?", "Mercury"),
    ("What is the square root of 64?", "8"),
    ("How many colors are traditionally named in a rainbow?", "7"),
    ("What is the primary language spoken in Brazil?", "Portuguese"),
    ("What is the currency of Japan?", "Yen"),
    ("Which continent is Egypt in?", "Africa"),
    ("Which mammal is famous for laying eggs and having a duck-like bill?", "Platypus"),
    ("What is the largest cat species?", "Tiger"),
    ("What process do plants use to make food from light?", "Photosynthesis"),
    ("What is the center of an atom called?", "Nucleus"),
    ("Which planet has the Great Red Spot?", "Jupiter"),
    ("What is the most abundant metal in Earth's crust?", "Aluminum"),
    ("What organ pumps blood through the body?", "Heart"),
    ("Which organ helps you breathe?", "Lungs"),
    ("What is a baby frog called?", "Tadpole"),
    ("What is the largest island in the world?", "Greenland"),
    ("Which continent contains the Sahara Desert?", "Africa"),
    ("How many hours are in a day?", "24"),
    ("How many cents are in one U.S. dollar?", "100"),
    ("What is the chemical symbol for gold?", "Au"),
    ("What is the chemical symbol for oxygen?", "O"),
    ("What is the largest internal organ in the human body?", "Liver"),
    ("Which sea creature has eight arms?", "Octopus"),
    ("What is the main ingredient in guacamole?", "Avocado"),
    ("Which sport uses a shuttlecock?", "Badminton"),
    ("How many players from one soccer team are normally on the field?", "11"),
    ("Which fruit is known for having seeds on the outside?", "Strawberry"),
    ("What do you call molten rock below Earth's surface?", "Magma"),
    ("Which organ controls most body functions?", "Brain"),
    ("What is the longest bone in the human body?", "Femur"),
    ("What is the largest bear species?", "Polar bear"),
    ("Which planet is often called Earth's twin because of its similar size?", "Venus"),
    ("What is Saturn's largest moon?", "Titan"),
    ("Which instrument measures temperature?", "Thermometer"),
    ("What color is chlorophyll?", "Green"),
    ("Which animal is famous for black and white stripes?", "Zebra"),
    ("What is the fastest bird in a dive?", "Peregrine falcon"),
    ("What is the deepest known ocean trench?", "Mariana Trench"),
    ("Which animal is famous for building dams?", "Beaver"),
    ("Which blood cells help fight infection?", "White blood cells"),
    ("Which animal carries a hard shell on its back?", "Turtle"),
    ("Which organ stores bile?", "Gallbladder"),
    ("Which country gifted the Statue of Liberty to the United States?", "France"),
    ("What is the only continent located in all four hemispheres?", "Africa"),
    ("Which layer of the atmosphere helps absorb harmful ultraviolet radiation?", "Ozone layer"),
    ("What is water vapor turning into liquid called?", "Condensation"),
    ("What is Earth's main source of energy?", "The Sun"),
    ("Which part of a plant usually absorbs water from soil?", "Roots"),
    ("What gas do humans need to breathe to survive?", "Oxygen"),
    ("How many legs does a spider have?", "8"),
    ("Which animal is famous for carrying young in a pouch?", "Kangaroo"),
    ("What does a meteor become if it reaches the ground?", "Meteorite"),
    ("Which continent has the most countries?", "Africa"),
    ("What is the process of a caterpillar becoming a butterfly called?", "Metamorphosis"),
    ("Which animal is known for a hump and desert travel?", "Camel"),
    ("Which device keeps a steady beat for musicians?", "Metronome"),
    ("What is the freezing point of water in Celsius?", "0"),
    ("Which shape has eight sides?", "Octagon"),
    ("How many strings does a standard violin have?", "4"),
    ("Which planet spins on its side?", "Uranus"),
    ("What is the brightest planet commonly visible from Earth?", "Venus"),
    ("What is the main ingredient used to make most bread?", "Flour"),
    ("What is the top number of a fraction called?", "Numerator"),
    ("What is the bottom number of a fraction called?", "Denominator"),
    ("Which animal is known for having a trunk?", "Elephant"),
    ("What is the smallest ocean?", "Arctic Ocean"),
    ("What is the largest country in the world by area?", "Russia"),
]


def build_question_bank():
    items: list[tuple[str, str]] = []

    for state, capital in STATE_CAPITALS.items():
        items.append((f"What is the capital of {state}?", capital))

    for country, capital in COUNTRY_CAPITALS.items():
        items.append((f"What is the capital of {country}?", capital))

    # 50 deterministic arithmetic questions. Values are deliberately varied so every prompt is unique.
    for i in range(1, 26):
        a = 7 + i
        b = 3 + (i % 9)
        items.append((f"What is {a} plus {b}?", str(a + b)))
    for i in range(1, 26):
        a = 6 + i
        b = 2 + (i % 7)
        items.append((f"What is {a} multiplied by {b}?", str(a * b)))

    items.extend(CURATED)

    # De-duplicate defensively. The generator must never silently recycle questions.
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str]] = []
    for question, answer in items:
        key = (" ".join(question.lower().split()), " ".join(answer.lower().split()))
        if key in seen:
            continue
        seen.add(key)
        unique.append((question, answer))

    if len(unique) < 220:
        raise RuntimeError(f"Expanded question bank is unexpectedly small: {len(unique)} unique questions")

    return [base.TriviaQuestion(question, answer) for question, answer in unique]


base.build_question_bank = build_question_bank

if __name__ == "__main__":
    raise SystemExit(base.main())
