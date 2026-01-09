#!/usr/bin/env python
import datetime
# Version: 1.1.0
# Author: Adam Govier (ins1gn1a) - September 2015
# Email: me@ins1gn1a.com
#
# Disclaimer:
# I am not responsible for any problems or issues that are potentially caused
# by running this tool. There should not be any problems as this script uses
# in-built functionality and was created with performance and availability
# in mind. Nevertheless, you've been told!

# Modules
import timeit
import re
import os
import sys
import argparse
import subprocess
import traceback
from itertools import islice


# Colouring!
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# Input argument setup
p = argparse.ArgumentParser(description='Search Linux-based systems for payment card numbers (VISA, AMEX, Mastercard).')
p.add_argument('-o', '--output', dest='output', help='Output data to a file instead of the Terminal.')
p.add_argument('-b', '--brands', dest='brands',
               help='Indicates card brands separate by spaces (Default is [visa mastercard amex]',
               default='visa mastercard amex')
p.add_argument('-D', '--max-depth', dest='depth',
               help='Enter the max depth that the scanner will search from the given directory (Default is 3).',
               type=int, default=3)
p.add_argument('-d', '--min-depth', dest='mindepth',
               help='Enter the min depth that the scanner will search from the given directory (No Default).', type=int)
p.add_argument('-l', '--lines', dest='lines',
               help='Enter the number of lines from the file to cycle through (Default is 50)', type=int, default=50)
p.add_argument('-p', '--path',
               help='Input the directory path that you want to recursively search through, e.g. /var (Default is /)',
               default='/')
p.add_argument('-e', '--extensions', dest='extensions',
               help='Input the file extensions that should be searched for, separated by spaces.',
               nargs='+')
p.add_argument('-x', '--exclude', dest='exclude_dir',
               help='Input the directories to exclude, separated by spaces. Wildcards can be used, e.g. /var/*',
               required=False, nargs='+', default="")
p.add_argument('-max', '--max-size',
               help='Enter the maximum file-size to search for (Default 100 Kilobytes). Units: "c" for bytes, '
                    '"k" for Kilobytes, "M" for Megabytes',
               dest="maxsize", default="10M")
p.add_argument('-min', '--min-size',
               help='Enter the minimum file-size to search for (Default 16 Bytes). Units: "c" for bytes, '
                    '"k" for Kilobytes, "M" for Megabytes',
               dest="minsize", default="16c")
p.add_argument('-mount', '--scan-mount', dest='mounted',
               help='Enable to scan the mounted remote file systems (Default is off.)', required=False,
               action='store_true')
p.add_argument('-v', '--verbose', dest='verbose', help='Display verbose messages (Warning: output can be huge).',
               required=False, action='store_true')
options = p.parse_args()

# Banner
print("----------------------------------------------------------------------------")
print("  ____              _ ____                  _  _   _     _           ")
print(" / ___|__ _ _ __ __| / ___|  ___ __ _ _ __ | || | | |   (_)_ __  _   ___  __")
print("| |   / _` | '__/ _` \___ \ / __/ _` | '_ \| || |_| |   | | '_ \| | | \ \/ /")
print("| |__| (_| | | | (_| |___) | (_| (_| | | | |__   _| |___| | | | | |_| |>  <")
print(" \____\__,_|_|  \__,_|____/ \___\__,_|_| |_|  |_| |_____|_|_| |_|\__,_/_/\_\ ")
print("----------------------------------------------------------- Version 1.1.0 --")


def luhn_checksum(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]

    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = 0
    checksum += sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10


def is_luhn_valid(card_number):
    return luhn_checksum(card_number) == 0


# String concatenation for file extension searching.
extCmd = ""
z = 0
if options.extensions is not None:
    for ext in options.extensions:
        if z == 0:
            extCmd = " -name '*.%s'" % (ext)
            z += 1
        else:
            extCmd = extCmd + (" -o -name '*.%s'" % (ext))
            z += 1

# Sizing
max = ("-size -" + options.maxsize)  # Default 100 Kilobytes (100k)
min = ("-size +" + options.minsize)  # Default 16 bytes (16 c)

# Exclude files via -x/--exclude
y = 0
exclude_cmd = ""
for excl in options.exclude_dir:
    if y == 0:
        exclude_cmd = " ! -path '%s/*'" % (excl)
        y += 1
    else:
        exclude_cmd = exclude_cmd + (" -a ! -path '%s/*'" % (excl))
        y += 1

if y > 0:
    exclude_cmd = exclude_cmd + " "
    header_exclusions = options.exclude_dir
else:
    header_exclusions = "None"

brands = options.brands.split(' ')

# Output to stdout
if options.extensions is not None and len(options.extensions) > 3:
    header_line = "=============================================================================="
else:
    header_line = "========================================================="
print(bcolors.HEADER + header_line)
print(bcolors.HEADER + "[*]" + bcolors.ENDC + " Root Path \t\t" + bcolors.HEADER + ":\t" + bcolors.ENDC + str(
    options.path))
print(bcolors.HEADER + "[*]" + bcolors.ENDC + " Brands \t\t" + bcolors.HEADER + ":\t" + bcolors.ENDC + str(
    options.brands))
print(bcolors.HEADER + "[*]" + bcolors.ENDC + " Max Size \t\t" + bcolors.HEADER + ":\t" + bcolors.ENDC + str(
    options.maxsize))
print(bcolors.HEADER + "[*]" + bcolors.ENDC + " Min Size \t\t" + bcolors.HEADER + ":\t" + bcolors.ENDC + str(
    options.minsize))
print(bcolors.HEADER + "[*]" + bcolors.ENDC + " Extensions \t\t" + bcolors.HEADER + ":\t" + bcolors.ENDC + str(
    options.extensions))
print(
    bcolors.HEADER + "[*]" + bcolors.ENDC + " Lines per file \t" + bcolors.HEADER + ":\t" + bcolors.ENDC + str(
        options.lines))
print(bcolors.HEADER + "[*]" + bcolors.ENDC + " Depth of search \t" + bcolors.HEADER + ":\t" + bcolors.ENDC + str(
    options.depth))
print(bcolors.HEADER + "[*]" + bcolors.ENDC + " Scan Mounted Dirs \t" + bcolors.HEADER + ":\t" + bcolors.ENDC + str(
    options.mounted))
print(bcolors.HEADER + "[*]" + bcolors.ENDC + " Exclusions \t\t" + bcolors.HEADER + ":\t" + bcolors.ENDC + str(
    header_exclusions))
print(bcolors.HEADER + header_line + bcolors.ENDC)
print(bcolors.OKGREEN + "\n[*] " + bcolors.ENDC + "Starting file-system scan. This may take a while...")
start_time = timeit.default_timer()

# Local or Remote Mounting
if options.mounted:
    remote_mount = ""
else:
    remote_mount = "-mount "

# Min depth
if options.mindepth is None:
    min_depth = ""
else:
    min_depth = "-mindepth %s " % (str(options.mindepth))

# Create a list of all files with the provided inputs
try:
    cmdStr = 'find %s %s-maxdepth %s %s-type f \( %s %s\) %s %s ' % (
        options.path, remote_mount, options.depth, min_depth, extCmd, exclude_cmd, max, min)
    # print('Command: ' + cmdStr)
    full_path_list = subprocess.check_output(cmdStr, shell=True)
    full_path_list = full_path_list.rstrip().split('\n'.encode())
except Exception as e:
    print(bcolors.FAIL + "[*] " + bcolors.ENDC + "Cannot retrieve file list: " + str(e))
    traceback.print_exc()
    sys.exit()

# Count how many entries in the list file
file_lines = len(full_path_list)

# Output to user
print(bcolors.OKGREEN + "[*] " + bcolors.ENDC + "File-system search complete. " + str(
    file_lines) + " files to check for card-data.")

# Regex to filter card numbers
brandRegex = {
    'amex': [
        re.compile("(3(4[0-9]{2}|7[0-9]{2})( |-|)[0-9]{6}( |-|)[0-9]{5})")  # 16 Digit AMEX
    ],
    "mastercard": [
        re.compile("(5[0-9]{3}( |-|)([0-9]{4})( |-|)([0-9]{4})( |-|)([0-9]{4}))"),
        re.compile("(2[0-9]{3}( |-|)([0-9]{4})( |-|)([0-9]{4})( |-|)([0-9]{4}))")
    ],
    'visa': [
        re.compile("(4[0-9]{3}( |-|)([0-9]{4})( |-|)([0-9]{4})( |-|)([0-9]{4}))")
    ]
}

# Log file - counting
total_count = 0

# Search through files in the list
try:
    log_file = None
    if options.output:
        log_file = open(options.output, 'a')
        now = datetime.datetime.now()
        log_file.write("Hunting card numbers on " + now.strftime('%Y-%m-%d %H:%M:%S') + "\n")

    for filepath in full_path_list:
        filepath = filepath.rstrip('\n'.encode())
        try:
            with open(filepath) as file:
                if options.verbose:
                    print(bcolors.OKBLUE + '[*] Scanning file %s...' % filepath + bcolors.ENDC)
                total_count += 1

                i = 0
                results = []
                head = list(islice(file, options.lines))  # Opens 50 lines by default

                # Loops through each item in list
                for item in head:
                    for b in brands:
                        searchsRegex = brandRegex[b]
                        for r in searchsRegex:
                            result = re.search(r, item.rstrip('\n'))
                            if result:
                                result = result.group().replace(',', '').strip()
                                result = result.replace(" ", "").replace("-", '')
                                if is_luhn_valid(result):
                                    i += 1
                                    results.append("\t" + b.upper() + ":\t" + bcolors.FAIL + result + bcolors.ENDC)

                has_card_numbers = i > 0
                if has_card_numbers:
                    fileResultOutput = "Found %d card numbers on file %s\n" % (len(results), str(filepath))
                else:
                    fileResultOutput = "No card numbers found on file %s\n" % (str(filepath))

                if log_file:
                    log_file.write(fileResultOutput)
                    if options.verbose:
                        for result in results:
                            log_file.write(result + "\n")
                else:
                    print(bcolors.FAIL + fileResultOutput + bcolors.ENDC)
                    if options.verbose:
                        for result in results:
                            print(result)


        except KeyboardInterrupt:
            break
        except Exception as e:
            if log_file:
                traceback.print_exc()
                log_file.write("File: " + str(filepath) + "\n" + str(e) + "\n")
            print(bcolors.FAIL + "[*] " + bcolors.ENDC + "Cannot process file '" + str(filepath) + "'.")
            continue
except Exception as e:
    print(bcolors.WARNING + "\r[*] " + bcolors.ENDC + "There are no files that match the search.")
    traceback.print_exc()
    sys.exit()

# Removes the temp file
try:
    os.remove("/tmp/cardscan4linux.log")
except OSError:
    pass

total_time = int(timeit.default_timer()) - int(start_time)
# End of file
print(bcolors.OKGREEN + "[*] " + bcolors.ENDC + "Card scanning complete. " + str(
    file_lines) + " total files were scanned in " + str(total_time) + " seconds.")
if options.output:
    print(bcolors.OKGREEN + "[*] " + bcolors.ENDC + "Output saved to " + (os.path.realpath(options.output)))
