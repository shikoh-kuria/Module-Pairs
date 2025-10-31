def validate_positive_integer(value):
    if value is None or value < 0:
        raise ValueError("Value must be a positive integer.")
    return value

def parse_fan_pairs(fan_pairs_str):
    pairs = []
    if fan_pairs_str:
        for token in fan_pairs_str.split(","):
            a, b = token.split("-")
            pairs.append((int(a.strip()), int(b.strip())))
    return pairs

def prompt_list_ints(msg, default=None):
    s = input(msg).strip()
    if not s and default is not None:
        return default
    parts = [p.strip() for p in s.split(",") if p.strip()]
    try:
        vals = [int(p) for p in parts]
    except ValueError:
        print("Invalid numbers — using defaults.")
        return default
    return vals

def get_fixed_makespan():
    s = input("Fixed makespan (hours) — press Enter for no fixed makespan: ").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        print("Invalid number — ignoring.")
        return None