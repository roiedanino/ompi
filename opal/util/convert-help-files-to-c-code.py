#!/usr/bin/env python3
#
# Copyright (c) 2025      Jeffrey M. Squyres.  All rights reserved.
# $COPYRIGHT$
#
# Additional copyrights may follow
#
# $HEADER$
#

import os
import sys
import argparse

def find_help_files(root, verbose=False):
    # Search for help-*.txt files across the source tree, skipping
    # some directories (e.g., 3rd-party)
    help_files = []
    skip_dirs = ['.git', '3rd-party']
    for root_dir, dirs, files in os.walk(root):
        for sd in skip_dirs:
            if sd in dirs:
                dirs.remove(sd)

        for file in files:
            if file.startswith("help-") and file.endswith(".txt"):
                full_path = os.path.join(root_dir, file)
                help_files.append(full_path)
                if verbose:
                    print(f"Found: {full_path}")
    return help_files

def parse_ini_files(file_paths, verbose=False):
    # Parse INI-style files, returning a dictionary with filenames as
    # keys.  Don't use the Python configparse module in order to
    # reduce dependencies (i.e., so that we don't have to pip install
    # anything to run this script).
    data = {}
    for file_path in file_paths:
        sections = {}
        current_section = None
        with open(file_path) as file:
            for line in file:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                if line.startswith('[') and line.endswith(']'):
                    current_section = line[1:-1]
                    sections[current_section] = list()
                elif current_section is not None:
                    sections[current_section].append(line)

        data[os.path.basename(file_path)] = sections

        if verbose:
            print(f"Parsed: {file_path} ({len(sections)} sections found)")

    return data

def generate_c_code(parsed_data):
    # Generate C code with an array of filenames and their
    # corresponding INI sections.
    c_code = f"""// THIS FILE IS GENERATED AUTOMATICALLY! EDITS WILL BE LOST!
// This file generated by {sys.argv[0]}

"""
    # Rather than escaping the C code {} in f strings, make this a
    # separate (non-f-string) addition to c_code.
    c_code += """#include <stdio.h>
#include <string.h>

typedef struct {
    const char *section;
    const char *content;
} ini_entry;

typedef struct {
    const char *filename;
    ini_entry *entries;
} file_entry;

"""

    ini_arrays = []
    file_entries = []

    for idx, (filename, sections) in enumerate(parsed_data.items()):
        var_name = filename.replace('-', '_').replace('.', '_')

        ini_entries = []
        for section, content_list in sections.items():
            content = '\n'.join(content_list)
            c_content = content.replace('"','\\"').replace("\n", '\\n"\n"')
            ini_entries.append(f'    {{ "{section}", "{c_content}" }}')
        ini_entries.append(f'    {{ NULL, NULL }}')

        ini_array_name = f"ini_entries_{idx}"
        ini_arrays.append(f"static ini_entry {ini_array_name}[] = {{\n" + ",\n".join(ini_entries) + "\n};\n")
        file_entries.append(f'    {{ "{filename}", {ini_array_name} }}')
    file_entries.append(f'    {{ NULL, NULL }}')

    c_code += "\n".join(ini_arrays) + "\n"
    c_code += "static file_entry help_files[] = {\n" + ",\n".join(file_entries) + "\n};\n"

    c_code += """

const char *opal_show_help_get_content(const char *filename, const char* topic)
{
    file_entry *fe;
    ini_entry *ie;

    for (int i = 0; help_files[i].filename != NULL; ++i) {
        fe = &(help_files[i]);
        if (strcmp(fe->filename, filename) == 0) {
            for (int j = 0; fe->entries[j].section != NULL; ++j) {
                ie = &(fe->entries[j]);
                if (strcmp(ie->section, topic) == 0) {
                    return ie->content;
                }
            }
        }
    }

    return NULL;
}
"""

    return c_code

#-------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate C code from help text INI files.")
    parser.add_argument("--root",
                        required=True,
                        help="Root directory to search for help-*.txt files")
    parser.add_argument("--out",
                        required=True,
                        help="Output C file")
    parser.add_argument("--verbose",
                        action="store_true",
                        help="Enable verbose output")
    args = parser.parse_args()

    if args.verbose:
        print(f"Searching in: {args.root}")

    file_paths = find_help_files(args.root, args.verbose)
    parsed_data = parse_ini_files(file_paths, args.verbose)
    c_code = generate_c_code(parsed_data)

    if os.path.exists(args.out):
        with open(args.out) as f:
            existing_content = f.read()

            if existing_content == c_code:
                if args.verbose:
                    print(f"Help string content has not changed; not re-writing {args.out}")
                exit(0)

    with open(args.out, "w") as f:
        f.write(c_code)

    if args.verbose:
        print(f"Generated C code written to {args.out}")

if __name__ == "__main__":
    main()
