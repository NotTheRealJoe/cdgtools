#!/usr/bin/env python

import cdgtools
import os
import os.path
import sys

NOFILES = 1
NOMATCH = 2
EXTRACTFAIL = 3
NOSUCHFILE = 4
NOTSUPPORTED = 5


def show_error(errno=0):
    if errno == NOFILES:
        print 'ERROR: No valid files were specified.'
        sys.exit(2)


def show_warning(warnno=0, extra=''):
    if warnno == NOMATCH:
        print 'WARNING: No matching file found for "%s", skipping track' % extra
    elif warnno == EXTRACTFAIL:
        print 'WARNING: Extracting "%s" failed, skipping track' % extra
    elif warnno == NOSUCHFILE:
        print 'WARNING: The specified file "%s" could not be found' % extra
    elif warnno == NOTSUPPORTED:
        print 'WARNING: The audio format in file "%s" is not supported' % extra


def checkfile(file):
    """Try to stat a file. Return True if it can be stat'd, False if not."""
    try:
        os.stat(file)
        return True
    except:
        show_warning(NOSUCHFILE, file)
        return False


def findmatch(file):
    """Given a CDG, MP3, or OGG file, locate its matching opposite. Returns
    a tuple (cdg filename, audio filename)."""

    ext = file[-3:].lower()
    basename = os.path.basename(file)
    basename_no_ext = basename[:-3]
    dirname = os.path.dirname(file)

    audio_file = None
    cdg_file = None

    if ext == 'mp3' or ext == 'ogg':
        audio_file = file
    elif ext == 'cdg':
        cdg_file = file

    for possible_file in os.listdir(dirname):
        pl = possible_file.lower()
        if cdg_file is None and pl == basename_no_ext.lower() + "cdg":
            cdg_file = os.path.join(dirname, possible_file)
            break
        elif audio_file is None and (pl == basename_no_ext.lower() + "mp3" or pl == basename_no_ext.lower() + 'ogg'):
            audio_file = os.path.join(dirname, possible_file)
            break

    if cdg_file and audio_file:
        return cdg_file, audio_file
    else:
        return False, False


def archivetype(file):
    """Determine an archive's type based on the extension. Returns false if
    no matching extension is found."""

    if file[-3:].lower() == 'zip':
        return 'zip'
    elif file[-6:].lower() == 'tar.gz':
        return 'tar'
    elif file[-7:].lower() == 'tar.bz2':
        return 'tar'
    else:
        return False


def extractarchive(file):
    """Extract the given archive to a temporary directory, and return the
    filenames contained within if available, or False if not available or
    the extraction fails. Tuple returned contains cdg and compressed audio
    filenames."""

    type = archivetype(file)
    names = []
    if type == 'zip':
        import zipfile
        z = zipfile.ZipFile(file, 'r')
        info = z.infolist()
        for i in info:
            names.append(i.filename)
    elif type == 'tar':
        import tarfile
        z = tarfile.open(file)
        names = z.getnames()

    (cdg, audio) = (False, False)

    for i in names:
        if type == 'zip':
            d = open(i, 'wb')
            d.write(z.read(i))
            d.close()
        elif type == 'tar':
            z.extract(i)
        if i[-3:].lower() == 'cdg':
            cdg = i
        elif i[-3:].lower() == 'mp3':
            audio = i
        elif i[-3:].lower() == 'off':
            audio = i
        if audio and cdg:
            break

    z.close()

    return (cdg, audio)


def fetchpair(file):
    """Given a file, return a tuple (CDG filename, raw audio filename). This
	means if we're given a .zip, .tar.gz, or .tar.bz2, we have to extract it
	first. When that step's done (if needed), if we find a .cdg, we have to
	look for a matching .ogg or .mp3. If we find a .ogg or .mp3, we have to
	look for a matching .cdg.

	Once we've got an MP3 or OGG, we decode it and return the name of the
	decoded raw audio and the CDG file together.

	In a dose of severe cleverness, fetchpair() calls itself when handed
	an archive, with the return value of extractarchive() as its argument.
	If that call fails, it returns False anyway, so the original caller of
	fetchpair() still gets the False it needs to realize something broke.

	Returns a tuple of (False, False) if things have gone wrong."""

    fail = (False, False)

    if not file:
        return fail

    if archivetype(file):
        # Nuts. We have an archive.
        return fetchpair(extractarchive(file))

    (cdg, audio) = findmatch(file)

    if not cdg and not audio:
        return fail

    audio = decode_file(audio)

    if audio:
        return (cdg, audio)
    else:
        return fail


def decode_file(file):
    """Decode the given Ogg Vorbis to a raw, big-endian file suitable for
	interleaving. Returns the new temporary filename."""
    if checkfile(file):
        outfile = '%s.raw' % file
        if file[-3:].lower() == 'mp3':
            if options.byteswap:
                decode = 'lame --silent --decode -t "%s" "%s"' % (file, outfile)
            else:
                decode = 'lame --silent --decode -tx "%s" "%s"' % (file, outfile)
        elif file[-3:].lower() == 'ogg':
            decode = 'oggdec -QR -e 1 -o "%s" "%s"' % (outfile, file)
        else:
            # We should do something more intelligent here, like supporting
            # more filetypes (including WAV), but my brain hurts right now
            # too much to implement it.
            show_warning(NOTSUPPORTED, file)
            return False
        if not os.system(decode):
            return outfile

    return False


def pad_data(data, length):
    """Pads the provided data with trailing zeroes so the result is
    'length' bytes long. Does nothing to the data if it's already
    the correct length."""

    if len(data) == length:
        return data
    else:
        return data + chr(0) * (length - len(data))


def produce_bin(raw, cdg, binfile, rawbin=0):
    """Create an interleaved (cooked) BIN file suitable for writing with
    cdrdao. Pass filenames and an opened file object. Set raw = 1 to
    write a raw BIN image instead of a cooked one.

    raw = raw audio filename
    cdg = cdg data filename
    bin = output BIN file object, opened with 'wb' mode

    This function doesn't actually create the BIN file itself (it just
    writes to an open descriptor) because it can be used to write a new
    file (that the caller has just created) or append to an existing
    one (that the caller's had opened for awhile).

    Returns the exact number of frames and bytes written to the image
    (as a tuple).

    Raw BIN image writing is not yet implemented."""

    rawaudio = open(raw, 'rb')
    rawcdg = open(cdg, 'rb')

    if rawbin:
        print 'WARNING: Raw mode is not yet supported. Writing cooked data.'

    # Now that everything's opened, we start interleaving the data.
    frames = 0
    bytes = 0
    stop = 0

    while 1:
        pcm = rawaudio.read(2352)
        cdg = pad_data(rawcdg.read(96), 96)

        if not (len(pcm) == 2352):
            pcm = pad_data(pcm, 2352)
            stop = 1
        if len(pcm) and len(cdg):
            binfile.write(pcm)
            binfile.write(cdg)
            frames += 1
            bytes += (len(pcm) + len(cdg))
            if stop:
                break
        else:
            # We're out of data, so we're done writing
            break

    rawaudio.close()
    rawcdg.close()
    return (frames, bytes)


def calctime(frames):
    time_frames = frames % 75
    time_secs = frames / 75
    time_mins = time_secs / 60
    time_secs = time_secs % 60

    return '%02d:%02d:%02d' % (time_mins, time_secs, time_frames)


def tocblock(filename, track, offset, frames, raw=0):
    """Returns a Table of Contents block for use by cdrdao.
	Pass in the filename holding the encoded data, the track
	number (just used in comments, so not incredibly important),
	exact offset (in bytes) into the binary file this track
	begins on, the exact frame count for the track, and optionally
	whether it is cooked or raw (raw = 0 for cooked, raw = 1 for raw)."""

    # There are 2352 audio bytes and 96 CDG bytes in every frame.
    bytes = frames * (2352 + 96)

    time = calctime(frames)

    if raw:
        raw = 'RW_RAW'
    else:
        raw = 'RW'

    if offset:
        offset = '#%d ' % offset
    else:
        offset = ''

    string = '\n// Track %d\nTRACK AUDIO %s\nNO COPY\nNO PRE_EMPHASIS\nTWO_CHANNEL_AUDIO\nDATAFILE "%s" %s%s // length in bytes: %d\n' % (
        track, raw, filename, offset, time, bytes)

    return string


try:
    from optparse import OptionParser
except:
    from optik import OptionParser

usage = """usage: %prog [options] <file1> [fileN [ ... fileN]]

After any appropriate program options, list files to be added to the CD+G disc.
They will be placed on the disc in the order provided on the command line.
Files can be any combination of tar.gz, tar.bz2, .zip, .mp3+cdg, .ogg+cdg, and
.wav+cdg. For .mp3+cdg and .ogg+cdg, specify either the CDG file or the sound
file; cdg2bin will find the matching file."""

version = '%prog ' + cdgtools.VERSION_STRING

parser = OptionParser(usage=usage, version=version, conflict_handler='resolve')

parser.add_option('-o', '--output-prefix', dest='output', type='string', metavar='NAME',
                  help='Output filename prefix to use when creating files; "-o foo" produces "foo.toc" and "foo.bin" files',
                  default='cdg')
parser.add_option('-s', '--split-image', dest='split', action='store_true',
                  help='Produce individual .bin images for each track instead of a single .bin image for the whole disc',
                  default=False)
parser.add_option('-r', '--raw', dest='raw', action='store_true',
                  help='Produce raw data instead of cooked data (cooked data is the default)',
                  default=False)
parser.add_option('-b', '--byte-swap', dest='byteswap', action='store_true',
                  help='Swap byte order while processing audio.',
                  default=False)

(options, args) = parser.parse_args()

if not len(args):
    parser.print_help()
    print '\nERROR: at least one file must be specified.'
    sys.exit(2)

# We always start at Track 1
track = 1

# Create an empty cue sheet
toc = ''
index = ''

# Nothing's written yet
bytes = 0
offset = 0
totframes = 0

if not options.split:
    # We're writing a single BIN image, so we just open it once and
    # keep writing to it.
    bin = open(options.output + '.bin', 'wb')

for file in args:
    print 'Processing %s' % file

    # Find a matching pair and decode the audio
    compaudio = ''

    if archivetype(file):
        # Extract the archive first
        (cdg, compaudio) = extractarchive(file)
        audio = decode_file(compaudio)
        purge_all = 1
    else:
        (cdg, audio) = fetchpair(file)
        purge_all = 0

    if cdg and audio:
        if options.split:
            # We're writing multiple BIN images, so we have to
            # create a new BIN image file here first
            bin = open(options.output + '-%02d.bin' % track, 'wb')

        # Encode the CDG and audio data
        (frames, bytes) = produce_bin(audio, cdg, bin, options.raw)

        # We created the raw audio file, but now we're done with it
        os.unlink(audio)
        if purge_all:
            # Also clean up extracted archive files if we were given any
            os.unlink(cdg)
            os.unlink(compaudio)

        # Add to the cue sheet
        toc += tocblock(bin.name, track, offset, frames, options.raw)
        offset += bytes
        totframes += frames

        if options.split:
            # We're writing multiple BIN images, so we have to
            # close the current one before moving on to the next.
            bin.close()
            offset = 0

        # Write the index entry for this track.
        index += '%s-%02d: %s\n' % (options.output, track, file)
        track += 1
    else:
        print 'Warning, couldn\'t process %s. NOT adding to image.' % file

if not options.split:
    bin.close()

# Write the finished cue sheet
tocfile = open(options.output + '.toc', 'w')
tocfile.write(toc)
tocfile.close()

# Write the finished index file
indexfile = open(options.output + '.txt', 'w')
indexfile.write(index)
indexfile.close()

time = calctime(totframes)

print 'Processing complete. Added %d tracks.' % (track - 1)
print 'Finished CD length is %s.' % time
