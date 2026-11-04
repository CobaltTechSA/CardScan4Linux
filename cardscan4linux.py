#!/usr/bin/env python3
"""Find clear-text PANs without reproducing them in output."""
import argparse
import datetime
import fnmatch
import os
import re
import sys
import timeit
import zipfile
from pathlib import Path

VERSION = "1.2.0"
SUPPORTED_BRANDS = ("visa", "mastercard", "amex")
SIZE_RE = re.compile(r"^(\d+)([cKkMmGg]?)$")
PAN_RE = re.compile(r"(?<!\d)(?:\d[ \t-]?){12,18}\d(?!\d)")


class Colors:
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"


def luhn_checksum(number):
    total, parity = 0, len(number) % 2
    for index, character in enumerate(number):
        digit = int(character)
        if index % 2 == parity:
            digit = digit * 2 - (9 if digit > 4 else 0)
        total += digit
    return total % 10


def is_luhn_valid(number):
    return number.isdigit() and luhn_checksum(number) == 0


def card_brand(number):
    if number.startswith("4") and len(number) in (13, 16, 19):
        return "visa"
    if len(number) == 15 and number[:2] in ("34", "37"):
        return "amex"
    if len(number) == 16:
        if 51 <= int(number[:2]) <= 55 or 2221 <= int(number[:4]) <= 2720:
            return "mastercard"
    return None


def mask_pan(number):
    return number[:6] + "*" * max(0, len(number) - 10) + number[-4:]


def find_pans(text, brands=SUPPORTED_BRANDS):
    enabled = set(brands)
    for match in PAN_RE.finditer(text):
        number = re.sub(r"[ \t-]", "", match.group())
        brand = card_brand(number)
        if brand in enabled and is_luhn_valid(number):
            yield brand, number


def mask_pans_in_text(text):
    def replace(match):
        number = re.sub(r"[ \t-]", "", match.group())
        return mask_pan(number) if card_brand(number) and is_luhn_valid(number) else match.group()

    return PAN_RE.sub(replace, text)


def decode_content(data):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="ignore")


def searchable_contents(path):
    """Yield text from a regular file or members of DOCX/XLSX/other ZIP files."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if member.is_dir() or member.flag_bits & 1 or member.file_size > 100 * 1024 * 1024:
                    continue
                with archive.open(member) as stream:
                    yield "%s!%s" % (path, member.filename), decode_content(stream.read())
    else:
        with open(path, "rb") as stream:
            yield str(path), decode_content(stream.read())


def parse_size(value):
    if value is None:
        return None
    match = SIZE_RE.fullmatch(value)
    if not match:
        raise argparse.ArgumentTypeError("invalid size %r; use c, k, M or G" % value)
    factors = {"": 1, "c": 1, "k": 1024, "m": 1024 ** 2, "g": 1024 ** 3}
    return int(match.group(1)) * factors[match.group(2).lower()]


def excluded(path, patterns):
    return any(fnmatch.fnmatch(str(path), pattern.rstrip("/")) for pattern in patterns)


def discover_files(root, max_depth=None, min_depth=0, extensions=None,
                   exclusions=(), min_size=0, max_size=None, cross_mounts=False):
    root = Path(root).resolve()
    device = root.stat().st_dev
    suffixes = ({"." + item.lower().lstrip(".") for item in extensions}
                if extensions else None)
    walks = [(root.parent, [], [root.name])] if root.is_file() else os.walk(root)
    for directory, dirnames, filenames in walks:
        directory = Path(directory)
        depth = 0 if root.is_file() or directory == root else len(directory.relative_to(root).parts)
        kept = []
        for dirname in dirnames:
            child = directory / dirname
            try:
                if not excluded(child, exclusions) and (cross_mounts or child.stat().st_dev == device):
                    kept.append(dirname)
            except OSError:
                pass
        dirnames[:] = kept if max_depth is None or depth < max_depth else []
        if depth < min_depth or (max_depth is not None and depth > max_depth):
            continue
        for filename in filenames:
            path = directory / filename
            if excluded(path, exclusions) or (suffixes and path.suffix.lower() not in suffixes):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size >= min_size and (max_size is None or size <= max_size):
                yield path


def scan_file(path, brands=SUPPORTED_BRANDS, line_limit=0):
    return [(source, brand, masked) for source, brand, masked, _, _
            in scan_file_details(path, brands, line_limit)]


def scan_file_details(path, brands=SUPPORTED_BRANDS, line_limit=0):
    findings = []
    for source, text in searchable_contents(path):
        lines = text.splitlines()
        if line_limit:
            lines = lines[:line_limit]
        for line_number, line in enumerate(lines, start=1):
            for match in PAN_RE.finditer(line):
                number = re.sub(r"[ \t-]", "", match.group())
                brand = card_brand(number)
                if brand not in brands or not is_luhn_valid(number):
                    continue
                context_start = max(0, match.start() - 80)
                context_end = min(len(line), match.end() + 80)
                sample = mask_pans_in_text(line[context_start:context_end].strip())
                findings.append((source, brand, mask_pan(number), line_number, sample))
    return findings


def format_elapsed(seconds):
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "%02d:%02d:%02d" % (hours, minutes, seconds)


def build_parser():
    parser = argparse.ArgumentParser(description="Search Linux files for clear-text PANs.")
    parser.add_argument("-o", "--output", help="Append findings to this file.")
    parser.add_argument("-b", "--brands", nargs="+", choices=SUPPORTED_BRANDS,
                        default=list(SUPPORTED_BRANDS))
    parser.add_argument("-D", "--max-depth", type=int, default=None,
                        help="Default: unlimited.")
    parser.add_argument("-d", "--min-depth", dest="mindepth", type=int, default=0)
    parser.add_argument("-l", "--lines", type=int, default=0,
                        help="Lines per content stream; 0 scans the complete stream (default).")
    parser.add_argument("-p", "--path", default="/")
    parser.add_argument("-e", "--extensions", nargs="+")
    parser.add_argument("-x", "--exclude", dest="exclude_dir", nargs="+", default=[])
    parser.add_argument("-max", "--max-size", dest="maxsize", type=parse_size, default=None,
                        help="Default: unlimited; example: 10M.")
    parser.add_argument("-min", "--min-size", dest="minsize", type=parse_size, default=0)
    parser.add_argument("-mount", "--scan-mount", dest="mounted", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show masked findings; full PANs are never printed.")
    return parser


def main(argv=None):
    options = build_parser().parse_args(argv)
    if any(value < 0 for value in (options.mindepth, options.lines)) or (
            options.max_depth is not None and options.max_depth < 0):
        raise SystemExit("depth and line limits must be non-negative")
    print("CardScan4Linux %s" % VERSION)
    print(Colors.OKGREEN + "[*] " + Colors.ENDC + "Starting file-system scan...")
    started_at = datetime.datetime.now()
    started = timeit.default_timer()
    start_line = "Fecha de inicio: %s" % started_at.strftime("%Y-%m-%d %H:%M:%S")
    print(start_line)
    output = None
    try:
        if options.output:
            output = open(options.output, "a", encoding="utf-8")
            output.write(start_line + "\n")
        file_count = finding_count = 0
        files = discover_files(options.path, options.max_depth, options.mindepth,
                               options.extensions, options.exclude_dir, options.minsize,
                               options.maxsize, options.mounted)
        for path in files:
            file_count += 1
            try:
                findings = scan_file_details(path, options.brands, options.lines)
            except (OSError, zipfile.BadZipFile, RuntimeError) as error:
                print(Colors.WARNING + "[*] " + Colors.ENDC +
                      "Cannot process %s: %s" % (path, error), file=sys.stderr)
                continue
            finding_count += len(findings)
            if findings:
                summary = "Found %d PAN candidate(s) in %s\n" % (len(findings), path)
                output.write(summary) if output else print(summary, end="")
                for source, brand, masked, line_number, sample in findings:
                    if output:
                        output.write("\t%s:%d:\t%s (%s)\n\tSample: %s\n" %
                                     (source, line_number, masked, brand.upper(), sample))
                    elif options.verbose:
                        detail = "\t%s:\t%s (%s)\n" % (brand.upper(), masked, source)
                        print(detail, end="")
        print(Colors.OKGREEN + "[*] " + Colors.ENDC +
              "Scan complete: %d files, %d findings." %
              (file_count, finding_count))
        return 0
    except (OSError, ValueError) as error:
        print(Colors.FAIL + "[*] " + Colors.ENDC + str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        end_line = "Fecha de finalización: %s" % datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S")
        elapsed_line = "Tiempo transcurrido: %s" % format_elapsed(
            timeit.default_timer() - started)
        if output:
            output.write(end_line + "\n")
            output.write(elapsed_line + "\n")
            output.close()
        print(end_line)
        print(elapsed_line)


if __name__ == "__main__":
    sys.exit(main())
