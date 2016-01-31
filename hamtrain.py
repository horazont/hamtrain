#!/usr/bin/python3
import math
import random
import re


RNG = random.Random(random.SystemRandom().getrandbits(32))


FREQ_RE = re.compile(r"([0-9\.]+)\s*([kMG]?)")
FREQ_RANGE_RE = re.compile(r"(?P<start>{freq})\s*--\s*(?P<end>{freq})".format(
    freq=FREQ_RE.pattern
))
LENGTH_RE = re.compile(r"([0-9\.]+)\s*([kcm]?)m")
POWER_RE = re.compile(r"([0-9]+)\s*W\s*(ERP|PEP)")

PREFIXES = {
    "m": 10**-3,
    "c": 10**-2,
    "k": 10**3,
    "M": 10**6,
    "G": 10**9,
    "": 1,
}

REV_PREFIXES = {
    1: "k",
    2: "M",
    3: "G",
}


def parse_length(s):
    match = LENGTH_RE.match(s)
    if match is None:
        raise ValueError("not a valid length: {}".format(s))
    return PREFIXES[match.group(2)] * float(match.group(1))


def parse_frequency(s):
    match = FREQ_RE.match(s)
    if match is None:
        raise ValueError("not a valid frequency: {}".format(s))
    return round(PREFIXES[match.group(2)] * float(match.group(1)))


def parse_frequency_range(s):
    match = FREQ_RANGE_RE.match(s)
    if match is None:
        raise ValueError("not a valid frequency range: {}".format(s))
    return (parse_frequency(match.group("start")),
            parse_frequency(match.group("end")))


def format_frequency(f):
    order = math.floor(math.log(f, 10) / 3)-1
    if f / (10**(order*3)) >= 3000:
        order += 1

    f_scaled = f / (10**(order*3))
    if round(f_scaled) == f_scaled:
        f_scaled = round(f_scaled)
    return "{}{}".format(f_scaled, REV_PREFIXES[order])


def format_frequency_range(fs):
    start, end = fs
    return "{} -- {}".format(
        format_frequency(start),
        format_frequency(end),
    )


def read_database(infile):
    for row in infile:
        if row.lstrip().startswith("#"):
            continue
        parts = row.split()
        if parts[0] == "class":
            continue

        try:
            class_, λ, fs, status, P, bw = parts
            # λ = parse_length(λ)
            fs = parse_frequency_range(fs)
            if bw != "-":
                bw = parse_frequency(bw)
            else:
                bw = None
        except ValueError:
            print("failed to parse row:")
            print(row)
            raise

        yield class_, λ, fs, status, P, bw


def build_fullband_index(db):
    fullband = {}
    for class_, λ, fs, status, P, bw in db:
        if class_ == "E":
            continue
        try:
            start, end = fullband[λ]
        except KeyError:
            fullband[λ] = fs
        else:
            if end == fs[0]:
                end = fs[1]
            elif start == fs[1]:
                start = fs[0]
            else:
                raise ValueError("incoherent band data")
            fullband[λ] = start, end

    return fullband


with open("db", "r") as infile:
    db = list(read_database(infile))


fullband_index = build_fullband_index(db)


def query(prompt, parser=str):
    while True:
        value = input(prompt)
        if not value:
            return None

        try:
            return parser(value)
        except ValueError as exc:
            print("  {}".format(exc))
            continue


def print_eval(is_correct, actual_value):
    if is_correct:
        print("correct!\n")
    else:
        print("incorrect. the correct answer was:\n  {}\n".format(
            actual_value
        ))


def q_fullband():
    "band wavelength to frequency range"
    bands = list(fullband_index.keys())
    band = RNG.choice(bands)
    result = query("frequency range of {} band? ".format(band),
                   parse_frequency_range)
    print_eval(
        result == fullband_index[band],
        format_frequency_range(fullband_index[band])
    )


QUESTIONS = [
    q_fullband
]


while True:
    q = RNG.choice(QUESTIONS)
    q()
