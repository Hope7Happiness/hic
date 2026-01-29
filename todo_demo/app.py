import json

DATA = [
    {"name": "Pencil", "price": 0.5, "tags": ["stationery", "writing"]},
    {"name": "Notebook", "price": 2.75, "tags": ["stationery", "paper"]},
    {"name": "Eraser", "tags": ["stationery", "rubber", "stationery"]},
    {"name": "Marker", "price": -1.0, "tags": ["writing"]},
    {"name": "Desk Lamp", "price": 12.0, "tags": []},
    {"name": "Stapler"},
]


def load_items(raw: str):
    # TODO(high): parse JSON; return list of dicts; raise ValueError on invalid input
    pass


def normalize_item(item: dict):
    # TODO(medium): ensure name string, price >= 0 float default 0, tags list of strings
    # - tags should be unique, sorted alphabetically
    pass


def render_report(items):
    # TODO(low): render multiline report:
    # - Title line: "Inventory Report"
    # - "Total items: N"
    # - "Average price: $X.XX"
    # - Bullet list sorted by name: "- Name ($price) [tag1, tag2]"
    pass


def main():
    items = load_items(DATA)
    normalized = [normalize_item(item) for item in items]
    print(render_report(normalized))


if __name__ == "__main__":
    main()
