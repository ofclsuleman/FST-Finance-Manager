"""CSV import / export helpers shared by every data page."""
import csv


def read_csv(path, required):
    """Return a list of (line_number, row) with lower-case, stripped keys.

    Raises ValueError if a required column is missing, so the caller can show
    a friendly message instead of importing bad data.
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
        missing = [r for r in required if r not in headers]
        if missing:
            raise ValueError("missing column(s): " + ", ".join(missing))
        return [
            (n, {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()})
            for n, row in enumerate(reader, start=2)
        ]


def write_csv(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def to_float(text, default=0.0):
    text = str(text).replace(",", "").strip()
    if text == "":
        return default
    value = float(text)
    if value < 0:
        raise ValueError("value cannot be negative")
    return value


def to_int(text, default=0):
    return int(to_float(text, default))
