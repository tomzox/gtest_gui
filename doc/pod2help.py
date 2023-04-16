#!/usr/bin/env python3
#
#  Script for converting POD manpage to help dialog text.
#  (Originally developed in Perl language for the "nxtvepg" project.)
#
#  Copyright (C) 1999-2011, 2020-2021, 2023 T. Zoerner
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License Version 2 as
#  published by the Free Software Foundation. You find a copy of this
#  license in the file COPYRIGHT in the root directory of this release.
#
#  THIS PROGRAM IS DISTRIBUTED IN THE HOPE THAT IT WILL BE USEFUL,
#  BUT WITHOUT ANY WARRANTY; WITHOUT EVEN THE IMPLIED WARRANTY OF
#  MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#
#  Description:
#
#    Reads the manpage in POD format and creates a Python script defining texts
#    for the help dialog. The script will be included in the package. See the
#    Perl manual page 'perlpod' for details on the POD syntax.
#

import re
import sys

started = False
over = False
sectIndex = 0
subIndex = 0
helpSections = ""
helpIndex = ""
helpTexts = {}

docTitle = "Module-Tester's Gtest GUI"
rstOutput = docTitle + "\n" + ("=" * len(docTitle)) + "\n\n"
doRst = False

def ReplaceEntity(match):
   tag = match.group(1)

   if   tag == "lt"    : return "<"
   elif tag == "gt"    : return ">"
   elif tag == "auml"  : return "ae"
   elif tag == "eacute": return "e"
   else:
      print("Unknown entity E<%s>" % tag, file=sys.stderr)
      sys.exit(1)


def PrintParagraph(astr, indent, bullet=False):

    re.sub(r"E<([a-z]+)>", ReplaceEntity, astr)

    # Pre-process POD formatting expressions, e.g. I<some text>: replace pair
    # of opening and closing bracket with uniform separation character '#' and
    # appended format mode, which will be replaced with a tag later
    astr = re.sub(r'S<([^>]*)>', r'\1', astr)
    astr = re.sub(r'T<([^>]*)>', r'##\1##T##', astr)
    astr = re.sub(r'H<([^>]*)>', r'##\1##H##', astr)  # non-POD, internal format
    astr = re.sub(r'[IF]<([^>]*)>', r'##\1##I##', astr)
    astr = re.sub(r'C<([^>]*)>', r'##\1##C##', astr)
    astr = re.sub(r'L<"([^>]*)">', r'##\1##L##', astr)
    astr = re.sub(r'L<([^>]*)>', r'##\1##L##', astr)
    astr = re.sub(r'B<([^>]*)>', r'##\1##B##', astr)
    astr = re.sub(r'P<"([\x00-\xff]*?)">', r'##\1##P##', astr)
    astr += '####'
    astr = re.sub(r'^#+', r'', astr)

    # replace preprocessed format description with pairs of text and tags
    # - e.g. [list "text" underlined] to be inserted into a text widget
    # - note to hyperlinks: sections names are converted to lowercase;
    #   character ':' is a sub-section separator; see proc PopupHelp
    for match in re.finditer(r'([\x00-\xff]*?)##+(([IBCTHLP])#+)?', astr):
        chunk = match.group(1)
        tag   = match.group(3)

        if chunk:
            txt = chunk

            if tag == "B":
                fmt = "bold"
            elif tag == "I":
                fmt = "underlined"
            elif tag == "C":
                fmt = "fixed"
            elif tag == "P":
                fmt = "pfixed"
            elif tag == "T":
                fmt = "title1"
            elif tag == "H":
                fmt = "title2"
            elif tag == "L":
                fmt = "href"
                txt = chunk[0].upper() + chunk[1:].lower()
            else:
                fmt = ""

        if indent:
            fmt = ("('%s', 'indent')" % fmt) if fmt else "'indent'"
        else:
            fmt = "'%s'" % fmt

        helpTexts[sectIndex] += "('''%s''', %s), " % (txt, fmt)

        # ----------------------------

        if chunk:
            if tag == "B":
                txt = "**" + chunk + "**"
            elif tag == "I":
                txt = "*" + chunk + "*"
            elif tag == "C":
                txt = "``" + chunk + "``"
            elif tag == "P":
                txt = "::\n\n" + chunk
            elif tag == "T":
                txt = chunk + "\n" + ("-" * len(chunk))
            elif tag == "H":
                txt = chunk + "\n" + ("~" * len(chunk))
            elif tag == "L":
                txt = "`" + (chunk[0].upper() + chunk[1:].lower()) + "`_"
            else:
                txt = chunk
        else:
            txt = ""

        if indent:
            txt = "  " + txt

        global rstOutput
        rstOutput += txt

    if not bullet:
        rstOutput += "\n"



# read the complete paragraph, i.e. until an empty line
def ReadParagraph(f):
    line = ""
    while True:
        chunk = f.readline()
        if not chunk:
            return

        chunk = chunk.rstrip()
        if len(chunk) == 0 and line:
            break

        line += chunk

        # insert whitespace to separate lines inside the paragraph,
        # except for pre-formatted paragraphs in which the newline is kept
        if re.match(r"^\s+\S", line):
            line += "\n"
        elif line:
            line += " "

    # remove white space at line end
    return line.rstrip()


if (len(sys.argv) != 3) or (sys.argv[1] != "-help" and sys.argv[1] != "-rst"):
    print("Usage: %s [-help|-rst] input" % sys.argv[0], file=sys.stderr)
    sys.exit(1)

if sys.argv[1] == "-rst":
    doRst = True

f = open(sys.argv[2])

# process every text line of the manpage
while True:
    line = ReadParagraph(f)

    if not line:
        print("Ran into EOF - where's section 'DESCRIPTION'?", file=sys.stderr)
        sys.exit(1)

    # check for command paragraphs and process its command
    if line.startswith("=head1 "):
        title = line.partition(" ")[2].strip()

        # skip UNIX manpage specific until 'DESCRIPTION' chapter
        if started or (title == "DESCRIPTION"):
            if started:
                # close the string of the previous chapter
                helpTexts[sectIndex] += ")\n"
                sectIndex += 1

            # skip the last chapters
            if title == "AUTHOR":
                break

            # initialize new chapter
            started = True
            title = title[0].upper() + title[1:].lower()
            subIndex = 0

            # build array of chapter names for access from help buttons in popups
            helpIndex += "helpIndex['%s'] = %s\n" % (title, sectIndex)

            # put chapter heading at the front of the chapter
            helpTexts[sectIndex] = "helpTexts[%d] = (" % sectIndex
            PrintParagraph("T<%s>\n" % title, False)

    elif started:
        if line.startswith("=head2 "):
            if over:
                print("Format error: =head2 within =over (without =back)", file=sys.stderr)
            title = line.partition(" ")[2].strip()
            subIndex += 1
            helpSections += "helpSections[(%d,%d)] = '''%s'''\n" % (sectIndex, subIndex, title)
            # sub-header: handle like a regular paragraph, just in bold
            PrintParagraph("H<%s>\n" % title, False)

        elif line.startswith("=over"):
            if over:
                print("Format error: =over nesting is unsupported", file=sys.stderr)
            # start of an indented paragraph or a list
            over = True

        elif line.startswith("=back"):
            # end of an indented paragraph or list
            over = False

        elif line.startswith("=item "):
            if not over:
                print("Format error: =item outside of =over/=back", file=sys.stderr)
            title = line.partition(" ")[2].strip()
            # start a new list item, with a bullet at start of line or a title
            if title != "*":
                PrintParagraph("%s\n" % title, False, True)
            else:
                rstOutput += "- "

        else:
            # this is a regular paragraph
            # check for a pre-formatted paragraph: starts with white-space
            if re.match(r"^\s+(\S.*)", line):
                # add space after backslashes before newlines
                # to prevent interpretation by Python
                line = re.sub(r"\\\n", r"\\ \n", line);
                PrintParagraph("P<\"%s\n\n\">" % line, over)

            else:
                # append text of an ordinary paragraph to the current chapter
                if line and not line.isspace():
                    PrintParagraph(line + "\n", over)

if not doRst:
    print("# This file is automatically generated - do not edit")
    print("# Generated by %s from %s\n" % (sys.argv[0], sys.argv[2]))

    print("helpIndex = {}")
    print(helpIndex)

    print("helpSections = {}")
    print(helpSections)

    print("helpTexts = {}")
    for idx in range(sectIndex):
        print(helpTexts[idx])

else:
    print(rstOutput)
