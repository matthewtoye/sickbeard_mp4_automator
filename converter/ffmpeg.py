#!/usr/bin/env python

from inspect import getsourcefile
from os.path import abspath
import os.path
import os
import re
import signal
import subprocess
import sys
from subprocess import Popen, PIPE
import logging
import locale
import time
from sys import platform

logger = logging.getLogger(__name__)
console_encoding = locale.getdefaultlocale()[1] or 'UTF-8'


class FFMpegError(Exception):
    pass

class FFMpegConvertError(Exception):
    def __init__(self, message, cmd, output, details=None, pid=0):
        """
        @param    message: Error message.
        @type     message: C{str}

        @param    cmd: Full command string used to spawn ffmpeg.
        @type     cmd: C{str}

        @param    output: Full stdout output from the ffmpeg command.
        @type     output: C{str}

        @param    details: Optional error details.
        @type     details: C{str}
        """
        super(FFMpegConvertError, self).__init__(message)

        self.cmd = cmd
        self.output = output
        self.details = details
        self.pid = pid
        self.message = message
        
    def __repr__(self):
        error = self.details if self.details else self.message
        
        return ('<FFMpegConvertError error="%s", pid=%s, cmd="%s">' %
                (error, self.pid, self.cmd))
    def __str__(self):
        try:
            s = self.__repr__()
        except Exception as e:
            print ("ERROR in FFMpegConvertError! %s %s" % (type(e),e))
        return s
        
class MediaFormatInfo(object):
    """
    Describes the media container format. The attributes are:
      * format - format (short) name (eg. "ogg")
      * fullname - format full (descriptive) name
      * bitrate - total bitrate (bps)
      * duration - media duration in seconds
      * filesize - file size
    """

    def __init__(self):
        self.format = None
        self.fullname = None
        self.bitrate = None
        self.duration = None
        self.filesize = None

    def parse_ffprobe(self, key, val):
        """
        Parse raw ffprobe output (key=value).
        """
        if key == 'format_name':
            self.format = val
        elif key == 'format_long_name':
            self.fullname = val
        elif key == 'bit_rate':
            self.bitrate = MediaStreamInfo.parse_float(val, None)
        elif key == 'duration':
            self.duration = MediaStreamInfo.parse_float(val, None)
        elif key == 'size':
            self.size = MediaStreamInfo.parse_float(val, None)

    def __repr__(self):
        if self.duration is None:
            return 'MediaFormatInfo(format=%s)' % self.format
        return 'MediaFormatInfo(format=%s, duration=%.2f)' % (self.format,
                                                              self.duration)


class MediaStreamInfo(object):
    """
    Describes one stream inside a media file. The general
    attributes are:
      * index - stream index inside the container (0-based)
      * type - stream type, either 'audio' or 'video'
      * codec - codec (short) name (e.g "vorbis", "theora")
      * codec_desc - codec full (descriptive) name
      * duration - stream duration in seconds
      * map - stream index for ffmpeg mapping
      * metadata - optional metadata associated with a video or audio stream
      * bitrate - stream bitrate in bytes/second
      * attached_pic - (0, 1 or None) is stream a poster image? (e.g. in mp3)
    Video-specific attributes are:
      * video_width - width of video in pixels
      * video_height - height of video in pixels
      * video_fps - average frames per second
    Audio-specific attributes are:
      * audio_channels - the number of channels in the stream
      * audio_samplerate - sample rate (Hz)
    """

    def __init__(self):
        self.index = None
        self.type = None
        self.codec = None
        self.codec_desc = None
        self.duration = None
        self.bitrate = None
        self.video_width = None
        self.video_height = None
        self.video_fps = None
        self.video_level = None
        self.pix_fmt = None
        self.profile = None
        self.audio_channels = None
        self.audio_samplerate = None
        self.attached_pic = None
        self.sub_forced = None
        self.sub_default = None
        self.sub_force_guess = None
        self.metadata = {}

    @staticmethod
    def parse_float(val, default=0.0):
        try:
            return float(val)
        except:
            return default

    @staticmethod
    def parse_int(val, default=0):
        try:
            return int(val)
        except:
            return default

    def parse_ffprobe(self, key, val):
        """
        Parse raw ffprobe output (key=value).
        """

        if key == 'index':
            self.index = self.parse_int(val)
        elif key == 'codec_type':
            self.type = val
        elif key == 'codec_name':
            self.codec = val
        elif key == 'codec_long_name':
            self.codec_desc = val
        elif key == 'duration':
            self.duration = self.parse_float(val)
        elif key == 'bit_rate':
            self.bitrate = self.parse_int(val, None)
        elif key == 'width':
            self.video_width = self.parse_int(val)
        elif key == 'height':
            self.video_height = self.parse_int(val)
        elif key == 'channels':
            self.audio_channels = self.parse_int(val)
        elif key == 'sample_rate':
            self.audio_samplerate = self.parse_float(val)
        elif key == 'DISPOSITION:attached_pic':
            self.attached_pic = self.parse_int(val)
        elif key == 'profile':
            self.profile = val

        if key.startswith('TAG:'):
            key = key.split('TAG:')[1].lower()
            value = val.lower().strip()
            self.metadata[key] = value

        if self.type == 'audio':
            if key == 'avg_frame_rate':
                if '/' in val:
                    n, d = val.split('/')
                    n = self.parse_float(n)
                    d = self.parse_float(d)
                    if n > 0.0 and d > 0.0:
                        self.video_fps = float(n) / float(d)
                elif '.' in val:
                    self.video_fps = self.parse_float(val)

        if self.type == 'video':
            if key == 'r_frame_rate':
                if '/' in val:
                    n, d = val.split('/')
                    n = self.parse_float(n)
                    d = self.parse_float(d)
                    if n > 0.0 and d > 0.0:
                        self.video_fps = float(n) / float(d)
                elif '.' in val:
                    self.video_fps = self.parse_float(val)
            if key == 'level':
                self.video_level = self.parse_float(val)
            if key == 'pix_fmt':
                self.pix_fmt = val

        if self.type == 'subtitle':
            if key == 'DISPOSITION:forced': # Give higher preference for proper usage of forced tag, unfortunately this is not used very often.
                self.sub_forced = self.parse_int(val)
                if self.sub_forced == 1:
                    self.sub_forced = 2
            if key == 'DISPOSITION:default':
                self.sub_default = self.parse_int(val)
            if key == 'title': #Some videos just casually mention in the title if the sub is forced or not. 
                possible_ways_of_saying_forced = { "forced", "english subs for non-english parts", "force", "non-english parts",
                                                   "foreign parts only", "non english parts", "non english part", "foreign parts", "valyrian", "dothraki" }
                                                   #unfortunately this is not standardized at all, and there are probably 30 other ways that this is labeled
                newval = val.lower()
                logger.info( "Title name: %s" % newval ) #Just to check later and find the other methods of saying alien language.
                if newval in possible_ways_of_saying_forced or "forced" in newval or "alien only" in newval:
                    self.sub_forced = 1
            if key == 'duration' and val != 'N/A': #Sometimes there are 2 english subs, one of which has a much shorter duration than the other.
                                  #This shorter duration subtitle tends to be the forced subs, and we will use this in a last ditch effort
                                  # to figure out which subtitles need to be encoded into the video. 
                self.sub_force_guess = val

    def __repr__(self):
        d = ''
        metadata_str = ['%s=%s' % (key, value) for key, value
                        in self.metadata.items()]
        metadata_str = ', '.join(metadata_str)

        if self.type == 'audio':
            d = 'type=%s, codec=%s, channels=%d, rate=%.0f' % (self.type, self.codec, self.audio_channels, self.audio_samplerate)
        elif self.type == 'video':
            d = 'type=%s, codec=%s, width=%d, height=%d, fps=%.1f' % (
                self.type, self.codec, self.video_width, self.video_height,
                self.video_fps)
        elif self.type == 'subtitle':
            d = 'type=%s, codec=%s' % (self.type, self.codec)
        if self.bitrate is not None:
            d += ', bitrate=%d' % self.bitrate

        if self.metadata:
            value = 'MediaStreamInfo(%s, %s)' % (d, metadata_str)
        else:
            value = 'MediaStreamInfo(%s)' % d

        return value


class MediaInfo(object):
    """
    Information about media object, as parsed by ffprobe.
    The attributes are:
      * format - a MediaFormatInfo object
      * streams - a list of MediaStreamInfo objects
    """

    def __init__(self, posters_as_video=True):
        """
        :param posters_as_video: Take poster images (mainly for audio files) as
            A video stream, defaults to True
        """
        self.format = MediaFormatInfo()
        self.posters_as_video = posters_as_video
        self.streams = []

    def parse_ffprobe(self, raw):
        """
        Parse raw ffprobe output.
        """
        in_format = False
        current_stream = None

        for line in raw.split('\n'):
            line = line.strip()
            if line == '':
                continue
            elif line == '[STREAM]':
                current_stream = MediaStreamInfo()
            elif line == '[/STREAM]':
                if current_stream.type:
                    self.streams.append(current_stream)
                current_stream = None
            elif line == '[FORMAT]':
                in_format = True
            elif line == '[/FORMAT]':
                in_format = False
            elif '=' in line:
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip()
                if current_stream:
                    current_stream.parse_ffprobe(k, v)
                elif in_format:
                    self.format.parse_ffprobe(k, v)

    def __repr__(self):
        return 'MediaInfo(format=%s, streams=%s)' % (repr(self.format),
                                                     repr(self.streams))

    @property
    def video(self):
        """
        First video stream, or None if there are no video streams.
        """
        for s in self.streams:
            if s.type == 'video' and (self.posters_as_video or not s.attached_pic):
                return s
        return None

    @property
    def posters(self):
        return [s for s in self.streams if s.attached_pic]

    @property
    def audio(self):
        """
        All audio streams
        """
        result = []
        for s in self.streams:
            if s.type == 'audio':
                result.append(s)
        return result

    @property
    def subtitle(self):
        """
        All subtitle streams
        """
        result = []
        for s in self.streams:
            if s.type == 'subtitle':
                result.append(s)
        return result


class FFMpeg(object):
    """
    FFMPeg wrapper object, takes care of calling the ffmpeg binaries,
    passing options and parsing the output.

    >>> f = FFMpeg()
    """
    DEFAULT_JPEG_QUALITY = 4

    def __init__(self, ffmpeg_path=None, ffprobe_path=None):
        """
        Initialize a new FFMpeg wrapper object. Optional parameters specify
        the paths to ffmpeg and ffprobe utilities.
        """

        def which(name):
            path = os.environ.get('PATH', os.defpath)
            for d in path.split(':'):
                fpath = os.path.join(d, name)
                if os.path.exists(fpath) and os.access(fpath, os.X_OK):
                    return fpath
            return None

        if ffmpeg_path is None:
            ffmpeg_path = 'ffmpeg'

        if ffprobe_path is None:
            ffprobe_path = 'ffprobe'

        if '/' not in ffmpeg_path:
            ffmpeg_path = which(ffmpeg_path) or ffmpeg_path
        if '/' not in ffprobe_path:
            ffprobe_path = which(ffprobe_path) or ffprobe_path

        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path

        if not os.path.exists(self.ffmpeg_path):
            raise FFMpegError("ffmpeg binary not found: " + self.ffmpeg_path)

        if not os.path.exists(self.ffprobe_path):
            raise FFMpegError("ffprobe binary not found: " + self.ffprobe_path)

    @staticmethod
    def _spawn(cmds):
        clean_cmds = []
        try:
            for cmd in cmds:
                clean_cmds.append(str(cmd))
            cmds = clean_cmds
        except:
            logger.exception("There was an error making all command line parameters a string")
        logger.debug('Spawning ffmpeg with command: ' + ' '.join(cmds))
        kwargs = {}
        if sys.platform == 'win32':
        # from msdn [1]
            kwargs.update(shell=False)
            CREATE_NEW_PROCESS_GROUP = 0x00000200  # note: could get it from subprocess
            DETACHED_PROCESS = 0x00000008          # 0x8 | 0x200 == 0x208
            kwargs.update(creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)  
        elif sys.version_info < (3, 2):  # assume posix
            kwargs.update(preexec_fn=os.setsid)
        else:  # Python 3.2+ and Unix
            kwargs.update(start_new_session=True)
        return subprocess.Popen(cmds, stdin=PIPE, stdout=PIPE, stderr=PIPE, **kwargs )

    def probe(self, fname, posters_as_video=True):
        """
        Examine the media file and determine its format and media streams.
        Returns the MediaInfo object, or None if the specified file is
        not a valid media file.

        >>> info = FFMpeg().probe('test1.ogg')
        >>> info.format
        'ogg'
        >>> info.duration
        33.00
        >>> info.video.codec
        'theora'
        >>> info.video.width
        720
        >>> info.video.height
        400
        >>> info.audio.codec
        'vorbis'
        >>> info.audio.channels
        2
        :param posters_as_video: Take poster images (mainly for audio files) as
            A video stream, defaults to True
        """

        if not os.path.exists(fname):
            return None

        info = MediaInfo(posters_as_video)

        p = self._spawn([self.ffprobe_path, '-analyzeduration', '9999999999', '-probesize', '1999999999',
                         '-show_format', '-show_streams', fname])
        stdout_data, _ = p.communicate()
        stdout_data = stdout_data.decode(console_encoding, errors='ignore')
        info.parse_ffprobe(stdout_data)

        if not info.format.format and len(info.streams) == 0:
            return None

        return info

    def convert(self, infile, outfile, opts, stop_event, timeout=10, preopts=None, postopts=None):
        """
        Convert the source media (infile) according to specified options
        (a list of ffmpeg switches as strings) and save it to outfile.

        Convert returns a generator that needs to be iterated to drive the
        conversion process. The generator will periodically yield timecode
        of currently processed part of the file (ie. at which second in the
        content is the conversion process currently).

        The optional timeout argument specifies how long should the operation
        be blocked in case ffmpeg gets stuck and doesn't report back. See
        the documentation in Converter.convert() for more details about this
        option.

        >>> conv = FFMpeg().convert('test.ogg', '/tmp/output.mp3',
        ...    ['-acodec libmp3lame', '-vn'])
        >>> for timecode in conv:
        ...    pass # can be used to inform the user about conversion progress

        """
        if os.name == 'nt':
            timeout = 0

        if not os.path.exists(infile):
            raise FFMpegError("Input file doesn't exist: " + infile)

        cmds = [self.ffmpeg_path]
        if preopts:
            cmds.extend(preopts)
        cmds.extend(['-i', infile])

        alreadykludged = False
        # Move additional inputs to the front of the line
        for ind, command in enumerate(opts):
            if command == '-vcodec' and opts[ind + 1] != 'copy':
                alreadykludged = True
            if command == '-i':
                cmds.extend(['-i', opts[ind + 1]])
                del opts[ind]
                del opts[ind]

        cmds.extend(opts)
        if postopts:
            cmds.extend(postopts)
        cmds.extend(['-y', outfile])

        if timeout:
            def on_sigalrm(*_):
                signal.signal(signal.SIGALRM, signal.SIG_DFL)
                raise Exception('timed out while waiting for ffmpeg')

            signal.signal(signal.SIGALRM, on_sigalrm)
        print("command is: %s" % (cmds))
        try:
            p = self._spawn(cmds)
        except OSError:
            raise FFMpegError('Error while calling ffmpeg binary')

        yielded = False
        buf = ''
        total_output = ''
        ctime = re.compile(r'time=([0-9.:]+) ')
        cframe = re.compile(r'frame=(\s*\d+) ')
        cfps = re.compile(r'fps=(\s*\d+) ')
        cq = re.compile(r'q=([\d*.]+) ')
        cspeed = re.compile(r'speed=([\s*\d*.\d*x\s*]+) ')
        cbitrate = re.compile(r'bitrate=([\s*\d*.\d*\w*/\w*]+) ')
        frame = 0
        starttime = time.time()
        lastframetime = starttime
        ignore_non_monotonous = False
        timecode = 0
        fpsspec = 0
        cqspec = 0
        cspeedspec = 0
        bitratespec = 0
        
        while not stop_event.is_set():
           
            event_is_set = stop_event.wait(.1)
            
            if event_is_set:
                pid = p.pid

                try:
                    p.terminate()
                except:
                    print ("Terminated gracefully")
                return

                    
            if timeout:
                signal.alarm(timeout)

            ret = p.stderr.read(30)

            if timeout:
                signal.alarm(0)

            if not ret:
                # For small or very fast jobs, ffmpeg may never output a '\r'.  When EOF is reached, yield if we haven't yet.
                if not yielded:
                    yielded = True
                    yield 10
                break

            try:
                #print("in decode try")
                ret = ret.decode(console_encoding)
            except UnicodeDecodeError:
                try:
                    #print("in unicode decode error try")
                    ret = ret.decode(console_encoding, errors="ignore")
                except:
                    pass

            total_output += ret
            buf += ret
            #print(buf)
            #print("buf is %s" % (buf))
            # If the audio is being converted but the video is not, sometimes ffmpeg will spam warnings about 
            # how there is a "non-monotonous dts in output stream" -- This basically means that the sound is going
            # to be out of sync with the video and the only way to fix this it to re-encode the video along with the sound.
            # I don't feel like reorganizing everything to support sending the same file back through ffmpeg with different commands
            # Instead, we're going to close the current ffmpeg instance, and pipe the file through manual.py with a 
            # new option to force re-encoding.
            # The script will wait here until the subprocess is finished, in which it then exits this function and
            # pretends that everything is a-okay so that sabn/nzbget/etc scripts will properly autoimport the file.

            if 'Queue input is backward in time' in ret: # This warning tends to come up at the very end of a file
                ignore_non_monotonous = True # generally it's because the audio stream ends a few seconds before the video.
                # After this, it will spam warnings about non-monotonous DTS, but it doesn't matter since it's during the credits.
                # So, we won't re-encode a video just because the last few seconds of audio are trash.

            if 'Non-monotonous DTS' in ret and ignore_non_monotonous == False: #engage kludge... but don't do it at the end of the audio stream.
                p.terminate()
                if alreadykludged == False:
                    for i in range( 3 ):
                        try:
                            os.remove(outfile)
                            break
                        except:
                            time.sleep(10)
                    os.chdir( os.path.dirname( abspath(getsourcefile(lambda:0)) ) ) #ugh, path problems.
                    os.chdir( '..' )
                    subprocess.call(["python", "manual.py", "-a", "-i", infile, "--forceConvert"])
                    return

            if '\r' in buf:
                #print("in buf")
                line, buf = buf.split('\r', 1)

                tmptime = ctime.findall(line)
                tmpframe = cframe.findall(line)
                tmpcfps = cfps.findall(line)
                tmpcq = cq.findall(line)
                tmpcspeed = cspeed.findall(line)
                tmpcbitrate = cbitrate.findall(line)

                if len(tmpframe) == 1 and frame != 0 and frame == int( tmpframe[0] ):
                    if starttime == lastframetime:
                        lastframetime = time.time()
                    elif ( time.time() - lastframetime ) > 600.0:
                        cmd = ' '.join(cmds)
                        p.terminate()
                        raise FFMpegConvertError('Forcing ffmpeg to close due to taking more than 10 minutes to render a single frame. Source file may be corrupt.', cmd, total_output, "None", pid=p.pid)
                else:
                    starttime = time.time()
                    lastframetime = starttime
                if len( tmpframe ) == 1:
                    frame = int( tmpframe[0] )
                if len(tmptime) == 1:
                    timespec = tmptime[0]
                    if ':' in timespec:
                        timecode = 0
                        for part in timespec.split(':'):
                            timecode = 60 * timecode + float(part)
                    else:
                        timecode = float(tmptime[0])
                if len(tmpcfps) == 1:
                    fpsspec = tmpcfps[0].strip()
                if len(tmpcq) == 1:
                    cqspec = tmpcq[0]
                if len(tmpcspeed) == 1:
                    cspeedspec = tmpcspeed[0].strip()
                if len(tmpcbitrate) == 1:
                    bitratespec = tmpcbitrate[0]
                yielded = True                
                yield [timecode, fpsspec, cqspec, cspeedspec, bitratespec, p.pid]
        if timeout:
            signal.signal(signal.SIGALRM, signal.SIG_DFL)

        p.communicate()  # wait for process to exit

        if total_output == '':
            raise FFMpegError('Error while calling ffmpeg binary')

        cmd = ' '.join(cmds)
        if '\n' in total_output:
            line = total_output.split('\n')[-2]

            if line.startswith('Received signal'):
                # Received signal 15: terminating.
                raise FFMpegConvertError(line.split(':')[0], cmd, total_output, pid=p.pid)
            if line.startswith(infile + ': '):
                err = line[len(infile) + 2:]
                raise FFMpegConvertError('Encoding error', cmd, total_output,
                                         err, pid=p.pid)
            if line.startswith('Error while '):
                raise FFMpegConvertError('Encoding error', cmd, total_output,
                                         line, pid=p.pid)
            if line.startswith('Conversion failed!'):
                raise FFMpegConvertError('Encoding error', cmd, total_output,
                                         line, pid=p.pid)
            if not yielded:
                raise FFMpegConvertError('Unknown ffmpeg error', cmd,
                                         total_output, line, pid=p.pid)
        if p.returncode != 0:
            raise FFMpegConvertError('Exited with code %d' % p.returncode, cmd,
                                    total_output, pid=p.pid)
        
    def thumbnail(self, fname, time, outfile, size=None, quality=DEFAULT_JPEG_QUALITY):
        """
        Create a thumbnal of media file, and store it to outfile
        @param time: time point (in seconds) (float or int)
        @param size: Size, if specified, is WxH of the desired thumbnail.
            If not specified, the video resolution is used.
        @param quality: quality of jpeg file in range 2(best)-31(worst)
            recommended range: 2-6

        >>> FFMpeg().thumbnail('test1.ogg', 5, '/tmp/shot.png', '320x240')
        """
        return self.thumbnails(fname, [(time, outfile, size, quality)])

    def thumbnails(self, fname, option_list):
        """
        Create one or more thumbnails of video.
        @param option_list: a list of tuples like:
            (time, outfile, size=None, quality=DEFAULT_JPEG_QUALITY)
            see documentation of `converter.FFMpeg.thumbnail()` for details.

        >>> FFMpeg().thumbnails('test1.ogg', [(5, '/tmp/shot.png', '320x240'),
        >>>                                   (10, '/tmp/shot2.png', None, 5)])
        """
        if not os.path.exists(fname):
            raise IOError('No such file: ' + fname)

        cmds = [self.ffmpeg_path, '-i', fname, '-y', '-an']
        for thumb in option_list:
            if len(thumb) > 2 and thumb[2]:
                cmds.extend(['-s', str(thumb[2])])

            cmds.extend([
                '-f', 'image2', '-vframes', '1',
                '-ss', str(thumb[0]), thumb[1],
                '-q:v', str(FFMpeg.DEFAULT_JPEG_QUALITY if len(thumb) < 4 else str(thumb[3])),
            ])

        p = self._spawn(cmds)
        _, stderr_data = p.communicate()
        if stderr_data == '':
            raise FFMpegError('Error while calling ffmpeg binary')
        stderr_data.decode(console_encoding)
        if any(not os.path.exists(option[1]) for option in option_list):
            raise FFMpegError('Error creating thumbnail: %s' % stderr_data)
