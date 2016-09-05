#!/usr/bin/python3
import contextlib
import difflib
import itertools
import pickle
import os
import random
import re
import readline
import tempfile


# how many data points shall be kept
TRAIN_KEEP = 5

# threshold at which a pair is considered trained
TRAIN_THRESHOLD = 0.8

# maximum word distance at which a wrong submission is counted as correct (only
# for long keys)
TRAIN_CORRECT_THRESHOLD = 0.7

# number of already trained pairs to reconsider
TRAIN_RETRAIN = 5

# number of untrained pairs to include in the training set
TRAIN_SET_SIZE = 15


PREFIX_SET_RE = re.compile(r"^([A-Z0-9]+)-+([A-Z0-9]+)$")
PREFIX_SINGLE_RE = re.compile(r"^([A-Z0-9]+)$")
PREFIXCHAR_TO_BASE37 = {" ": 0}
PREFIXCHAR_TO_BASE37.update({
    c: ord(c) - ord("0") + 1
    for c in "0123456789"
})
PREFIXCHAR_TO_BASE37.update({
    c: ord(c) - ord("A") + 11
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
})
BASE37_TO_PREFIXCHAR = {
    v: k
    for k, v in PREFIXCHAR_TO_BASE37.items()
}


def prefix_to_base37(p):
    result = 0
    for i, c in enumerate(reversed(p)):
        result += PREFIXCHAR_TO_BASE37[c]*(37**i)
    return result


def base37_to_prefix(num):
    result = []
    while num > 0:
        result.append(BASE37_TO_PREFIXCHAR[num % 37])
        num = num // 37
    return "".join(reversed(result))


def expand_prefixset(start, end):
    r = range(prefix_to_base37(start), prefix_to_base37(end)+1)
    if len(r) == 0:
        raise ValueError("invalid prefix range: {}--{}".format(start, end))
    for i in r:
        yield base37_to_prefix(i)


def expand_prefixes(parts):
    for part in parts:
        m = PREFIX_SET_RE.match(part)
        if m is not None:
            yield from expand_prefixset(m.group(1), m.group(2))
            continue
        m = PREFIX_SINGLE_RE.match(part)
        if m is not None:
            yield m.group(1)
            continue
        raise ValueError("invalid prefix specifier: {}".format(part))


def read_database(infile):
    prio = 100
    for row in infile:
        parts = row.strip().split()
        if not parts or not parts[0]:
            continue
        if parts[0] == "#prio":
            prio = int(parts[1])
            continue
        if parts[0].startswith("#"):
            continue

        country_parts = parts[:1]
        i = 1
        while country_parts[-1].endswith("\\"):
            country_parts[-1] = country_parts[-1][:-1]
            country_parts.append(parts[i])
            i += 1

        prefixes = tuple(expand_prefixes(parts[i:]))
        country = " ".join(country_parts)
        yield country, prio, prefixes


def read_trainfile(filename):
    with open(filename, "rb") as f:
        return pickle.load(f)


@contextlib.contextmanager
def write_trainfile(filename, data):
    with tempfile.NamedTemporaryFile(
            dir=os.path.dirname(filename),
            delete=False) as f:
        try:
            yield
        finally:
            pickle.dump(data, f)
            os.rename(f.name, filename)


def train_generate_directional_trainingset(
        trainsubdata,
        grouped_db):
    already_trained = []
    to_train = []
    for pair in grouped_db:
        history = trainsubdata.get(pair, [])[-TRAIN_KEEP:]
        if not history:
            to_train.append(pair)
            continue

        score = sum(history) / len(history)
        if score < TRAIN_THRESHOLD or len(history) < TRAIN_KEEP / 2:
            to_train.append(pair)
        else:
            already_trained.append(pair)

    random.shuffle(already_trained)
    result = to_train[:TRAIN_SET_SIZE]
    result += already_trained[:(TRAIN_SET_SIZE-len(result)+TRAIN_RETRAIN)]
    random.shuffle(result)
    return result


def train_gather_trainingset(traindata, db, rng):
    grouped_db = []
    # sort by prio
    db = sorted(db, key=lambda x: x[1], reverse=True)

    for prio, rows in itertools.groupby(db, key=lambda x: x[1]):
        rows = list(rows)
        rng.shuffle(rows)
        grouped_db.extend(rows)

    forward_db = [(country, parts) for country, _, parts in grouped_db]
    reverse_db = [(parts, country) for country, _, parts in grouped_db]

    return (
        train_generate_directional_trainingset(
            traindata["forward"],
            forward_db
        ),
        train_generate_directional_trainingset(
            traindata["reverse"],
            reverse_db
        ),
    )


def prefixes_parser(s):
    return set(expand_prefixes(item.strip(",") for item in s.split()))


def query(prompt, parser=str, subline=None):
    readline.clear_history()

    while True:
        if subline is not None:
            print()
            print(" ({})".format(subline), end="\r\x1b[A")
        value = input(prompt)
        if subline is not None:
            print("\x1b[K", end="")
        if not value:
            return None

        try:
            return parser(value)
        except ValueError as exc:
            print("  {}".format(exc))
            continue


def train_single_forward(trainsubdata, pair):
    country, (primary, *others) = pair
    answer = query(
        "Landeskenner von {}? ".format(country),
        parser=prefixes_parser
    ) or set()

    if primary not in answer:
        print("  Primärer Landeskenner: fehlt.")
        print("    Richtige Antwort: {}".format(primary))
        score = 0
    else:
        print("  Primärer Landeskenner: korrekt!")
        score = 0.5

    others = set(others)

    # ignore if primary re-occurs
    answer -= {primary}
    others -= {primary}

    if others == answer:
        print("  Sekundäre Landeskenner: korrekt!")
        score += 0.5
    else:
        print("  Sekundäre Landeskenner: inkorrekt.")
        print("    Richtige Antwort: {}".format(", ".join(sorted(others))))
        print("    es fehlten: {}".format(", ".join(
            sorted(others - answer))))
        print("    es waren falsch: {}".format(", ".join(
            sorted(answer - others))))

        score += ((1 - len(others - answer) / (len(others) or 1)) *
                  (1 - len(answer - others) / (len(answer) or 1))) * 0.5

    print()
    print()

    trainsubdata.setdefault(pair, []).append(score)

    return score


def train_forward(trainsubdata, pairs):
    score = 0
    for pair in pairs:
        score += train_single_forward(trainsubdata, pair)
    return score


def train_single_reverse(trainsubdata, pair):
    (primary, *_), country = pair
    answer = query(
        "Welches Land hat {} als Landeskenner? ".format(primary)
    )

    print()

    if answer is None:
        score = 0
    else:
        matcher = difflib.SequenceMatcher(None, answer, country)
        score = matcher.ratio()

    if score >= TRAIN_CORRECT_THRESHOLD:
        print("  korrekt! ({})".format(country))
        score = 1
    else:
        print("  inkorrekt. Richtige Antwort: {}".format(country))
        score = 0

    print()
    print()

    trainsubdata.setdefault(pair, []).append(score)

    return score


def train_reverse(trainsubdata, pairs):
    score = 0
    for pair in pairs:
        score += train_single_reverse(trainsubdata, pair)
    return score


def train(args, db):
    try:
        traindata = read_trainfile(args.trainfile)
    except FileNotFoundError:
        traindata = {}

    traindata.setdefault("seed", random.SystemRandom().getrandbits(32))
    traindata.setdefault("forward", {})
    traindata.setdefault("reverse", {})

    rng = random.Random(traindata["seed"])

    with write_trainfile(args.trainfile, traindata):
        forward, reverse = train_gather_trainingset(
            traindata,
            db,
            rng
        )

        forward_score = train_forward(traindata["forward"], forward)
        reverse_score = train_reverse(traindata["reverse"], reverse)

    total_score = forward_score + reverse_score
    total_questions = len(forward) + len(reverse)
    print("Gesamtpunktzahl: {:.1f} / {}  ({:.0f}%)".format(
        total_score,
        total_questions,
        (total_score / total_questions) * 100
    ))
    print("  Länder -> Kenner: {:.1f} / {}  ({:.0f}%)".format(
        forward_score,
        len(forward),
        forward_score / len(forward) * 100
    ))
    print("  Kenner -> Länder: {} / {}  ({:.0f}%)".format(
        reverse_score,
        len(reverse),
        reverse_score / len(reverse) * 100
    ))


def dumpdb(args, db):
    import pprint
    pprint.pprint(db)


if __name__ == "__main__":
    import argparse
    import sys

    mainparser = argparse.ArgumentParser()
    mainparser.add_argument(
        "-d", "--db", "--database",
        dest="database",
        default="itudb",
        type=argparse.FileType("r"),
    )

    subparsers = mainparser.add_subparsers()

    parser = subparsers.add_parser("train")
    parser.set_defaults(func=train)
    parser.add_argument(
        "trainfile",
    )

    parser = subparsers.add_parser("dumpdb")
    parser.set_defaults(func=dumpdb)

    args = mainparser.parse_args()

    if not hasattr(args, "func"):
        mainparser.print_help()
        print()
        print("no action selected")
        sys.exit(2)

    with args.database:
        db = sorted(read_database(args.database))

    args.func(args, db)
