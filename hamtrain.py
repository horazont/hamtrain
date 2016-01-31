#!/usr/bin/python3
import math
import random
import re
import readline


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
    0: "",
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


def format_frequency(f, wide=True):
    order = math.floor(math.log(f, 10) / 3)-1
    if f / (10**(order*3)) >= 3000 or not wide:
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
            (start, end), curr_bw = fullband[λ]
        except KeyError:
            fullband[λ] = fs, bw
        else:
            if end == fs[0]:
                end = fs[1]
            elif start == fs[1]:
                start = fs[0]
            else:
                raise ValueError("incoherent band data")
            if bw != curr_bw:
                curr_bw = None
            fullband[λ] = (start, end), curr_bw

    return fullband


def build_classband_index(db):
    classbands = {}
    for class_, λ, *_ in db:
        classbands.setdefault(class_, set()).add(λ)

    return classbands


def build_statusband_index(db):
    statusbands = []
    prev_endf = 0
    prev_startf = 0
    prev_status = None
    for class_, _, (startf, endf), status, *_ in db:
        if class_ == "E":
            continue

        if startf == prev_endf and prev_status == status:
            startf = prev_startf
            statusbands[-1] = (startf, endf), status
        else:
            statusbands.append(((startf, endf), status))

        prev_startf, prev_endf, prev_status = startf, endf, status

    return statusbands


def build_powerband_index(db):
    powerbands = []
    prev_endf = 0
    prev_startf = 0
    prev_class = None
    prev_P = None
    for class_, _, (startf, endf), _, P, *_ in db:
        if startf == prev_endf and prev_P == P and prev_class == class_:
            startf = prev_startf
            powerbands[-1] = (startf, endf), class_, P
        else:
            powerbands.append(((startf, endf), class_, P))

        prev_startf, prev_endf, prev_class, prev_P = startf, endf, class_, P

    return powerbands

try:
    with open("db", "r") as infile:
        db = list(read_database(infile))
except FileNotFoundError:
    import sys
    print("copy db_master to db and remove everything you don’t want to learn")
    sys.exit(1)


fullband_index = build_fullband_index(db)
classbands_index = build_classband_index(db)
statusband_index = build_statusband_index(db)
powerband_index = build_powerband_index(db)


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


def print_eval(is_correct, actual_value, missing=None, surplus=None):
    if is_correct:
        print("correct!\n")
    else:
        print("incorrect.")
        if actual_value is not None:
            print("  the correct answer was: {}".format(
                actual_value
            ))
        if missing:
            print("  you missed: {}".format(missing))
        if surplus:
            print("  you incorrectly had: {}".format(surplus))
        print()


def q_fullband():
    "band wavelength to frequency range"
    bands = list(fullband_index.keys())
    band = RNG.choice(bands)
    result = query("frequency range of {} band? ".format(band),
                   parse_frequency_range)
    print_eval(
        result == fullband_index[band][0],
        format_frequency_range(fullband_index[band][0])
    )


def q_class_E():
    "name all class E bands"

    def parse_bandset(s):
        bands = {
            band.strip(",").replace(" ", "")
            for band in s.split()
        }
        return bands

    result = query("all bands of class E? ")
    if result is None:
        result = set()
    else:
        result = parse_bandset(result)
    bands = classbands_index["E"]

    print_eval(
        result == bands,
        None,
        ", ".join(bands - result),
        ", ".join(result - bands)
    )


def q_fullband_bw():
    "band wavelength to max. bandwidth"
    bands = list(fullband_index.keys())
    while True:
        band = RNG.choice(bands)
        if fullband_index[band][1]:
            break

    result = query("max. bandwidth of {} band? ".format(band),
                   parse_frequency)
    print_eval(
        result == fullband_index[band][1],
        format_frequency(fullband_index[band][1], wide=False)
    )


def q_freq_to_fullband():
    "identify band by frequency"
    bands = list(fullband_index.keys())
    band = RNG.choice(bands)

    def mess_with_frequency(f):
        order = math.floor(math.log(f, 10))
        factor = 0
        while factor == 0:
            factor = RNG.randint(-5, 5)
        modifier = factor * 10**(order-1)
        return f + modifier

    (start, end), *_ = fullband_index[band]
    if RNG.randint(1, 4) != 1:
        # mess with the numbers
        n = RNG.randint(1, 3)
        if n & 1:
            new_start = mess_with_frequency(start)
        else:
            new_start = start
        if n & 2:
            new_end = mess_with_frequency(end)
            if new_end < new_start:
                new_end = new_start + (end - start)
        else:
            new_end = end
            if new_end < new_start:
                new_start = new_end + (start - end)

        is_correct = (start, end) == (new_start, new_end)
        correct_answer = "none" if not is_correct else band
        if not is_correct:
            correct_answer_str = (
                "none (close to {}, which is the {} band)".format(
                    format_frequency_range((start, end)),
                    band
                )
            )
        else:
            correct_answer_str = band
        start, end = new_start, new_end
    else:
        correct_answer = band
        correct_answer_str = band

    def check_length(s):
        s = s.strip()
        if not LENGTH_RE.match(s):
            raise ValueError("not a valid length: {}".format(s))
        return s.replace(" ", "")

    result = query(
        "which band is this: {}? ".format(
            format_frequency_range((start, end))
        ),
        subline="type 'none' if you think this is incorrect",
        parser=check_length
    )

    print_eval(
        result == correct_answer,
        correct_answer_str
    )


def q_subband_status():
    "service status in subband"
    fs, status = RNG.choice(statusband_index)

    def parse_status(s):
        s = s.strip()
        if s not in ["S", "P", "P+"]:
            raise ValueError("not a valid status: {}".format(s))
        return s

    result = query(
        "which status does HAM radio have in {}? ".format(
            format_frequency_range(fs)
        ),
        parse_status
    )

    print_eval(
        status.startswith(result),
        status
    )


def q_subband_power():
    "maximum power in subband"
    fs, class_, P = RNG.choice(powerband_index)

    def parse_power(s):
        s = s.strip()
        if not POWER_RE.match(s):
            raise ValueError("not a valid power: {}".format(s))
        return s.replace(" ", "")

    result = query(
        "which maximum power is allowed in {} for class {}? ".format(
            format_frequency_range(fs),
            class_
        ),
        parse_power
    )

    print_eval(
        P == result,
        P
    )


QUESTIONS = [
    q_fullband,
    q_fullband_bw,
    q_freq_to_fullband,
    q_subband_status,
    q_subband_power,
]*3 + [
    q_class_E
]


while True:
    q = RNG.choice(QUESTIONS)
    q()
