#!/usr/bin/python3
import contextlib
import difflib
import itertools
import pickle
import os
import random
import readline
import tempfile


# how many data points shall be kept
TRAIN_KEEP = 5

# threshold at which a pair is considered trained
TRAIN_THRESHOLD = 0.95

# maximum word distance at which a wrong submission is counted as correct (only
# for long keys)
TRAIN_CORRECT_THRESHOLD = 0.7

# number of already trained pairs to reconsider
TRAIN_RETRAIN = 5

# number of untrained pairs to include in the training set
TRAIN_SET_SIZE = 15


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

        prefixes = tuple(parts[i:])
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
    result = to_train[:TRAIN_SET_SIZE] + already_trained[:TRAIN_RETRAIN]
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
    return {item.strip(",").upper() for item in s.split()}


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
    primary_answer = query(
        "Primärer Landeskenner von {}? ".format(country)
    )
    others_answer = query(
        "  Weitere Landeskenner? ",
        subline=" (leer lassen falls keine)",
        parser=prefixes_parser
    )

    print()

    if primary_answer != primary:
        print("  Primärer Landeskenner: inkorrekt.")
        print("    Richtige Antwort: {}".format(primary))
    else:
        print("  Primärer Landeskenner: korrekt!")

    score = (primary_answer == primary) * 0.5

    if others_answer is None:
        others_answer = set()

    others = set(others)
    if others == others_answer:
        print("  Sekundäre Landeskenner: korrekt!")
        score += 0.5
    else:
        print("  Sekundäre Landeskenner: inkorrekt.")
        print("    Richtige Antwort: {}".format(", ".join(sorted(others))))
        print("    es fehlten: {}".format(", ".join(
            sorted(others - others_answer))))
        print("    es waren falsch: {}".format(", ".join(
            sorted(others_answer - others))))

        score += ((1 - len(others - others_answer) / len(others)) *
                  (1 - len(others_answer - others) / (len(others) or 1))) * 0.5

    print()
    print()

    trainsubdata.setdefault(country, []).append(score)

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

        reverse_score = train_reverse(traindata["reverse"], reverse)
        forward_score = train_forward(traindata["forward"], forward)

    total_score = forward_score + reverse_score
    total_questions = len(forward) + len(reverse)
    print("Gesamtpunktzahl: {} / {}  ({:.0f}%)".format(
        total_score,
        total_questions,
        (total_score / total_questions) * 100
    ))
    print("  Länder -> Kenner: {} / {}  ({:.0f}%)".format(
        forward_score,
        len(forward),
        forward_score / len(forward) * 100
    ))
    print("  Kenner -> Länder: {} / {}  ({:.0f}%)".format(
        reverse_score,
        len(reverse),
        reverse_score / len(reverse) * 100
    ))


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

    args = mainparser.parse_args()

    if not hasattr(args, "func"):
        mainparser.print_help()
        print()
        print("no action selected")
        sys.exit(2)

    with args.database:
        db = sorted(read_database(args.database))

    args.func(args, db)
