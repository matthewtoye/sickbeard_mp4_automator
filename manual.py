#!/usr/bin/env python

from __future__ import print_function
import sys
import os
import time
import curses
import guessit
import locale
import glob
import argparse
import struct
import logging
from subprocess import call
from readSettings import ReadSettings
from tvdb_mp4 import Tvdb_mp4
from tmdb_mp4 import tmdb_mp4
from mkvtomp4 import MkvtoMp4
from post_processor import PostProcessor
from tvdb_api import tvdb_api
from tmdb_api import tmdb
from extensions import tmdb_api_key
from logging.config import fileConfig

if sys.version[0] == "3":
    raw_input = input

fileConfig(os.path.join(os.path.dirname(sys.argv[0]), 'logging.ini'), defaults={'logfilename': os.path.join(os.path.dirname(sys.argv[0]), 'info.log').replace("\\", "/")})
log = logging.getLogger("MANUAL")
logging.getLogger("subliminal").setLevel(logging.CRITICAL)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("enzyme").setLevel(logging.WARNING)
logging.getLogger("qtfaststart").setLevel(logging.WARNING)

log.info("Manual processor started.")

settings = ReadSettings(os.path.dirname(sys.argv[0]), "autoProcess.ini", logger=log)


def mediatype():
    print("Select media type:")
    print("1. Movie (via IMDB ID)")
    print("2. Movie (via TMDB ID)")
    print("3. TV")
    print("4. Convert without tagging")
    print("5. Skip file")
    result = raw_input("#: ")
    if 0 < int(result) < 6:
        return int(result)
    else:
        print("Invalid selection")
        return mediatype()


def getValue(prompt, num=False):
    print(prompt + ":")
    value = raw_input("#: ").strip(' \"')
    # Remove escape characters in non-windows environments
    if os.name != 'nt':
        value = value.replace('\\', '')
    try:
        value = value.decode(sys.stdout.encoding)
    except:
        pass
    if num is True and value.isdigit() is False:
        print("Must be a numerical value")
        return getValue(prompt, num)
    else:
        return value


def getYesNo():
    yes = ['y', 'yes', 'true', '1']
    no = ['n', 'no', 'false', '0']
    data = raw_input("# [y/n]: ")
    if data.lower() in yes:
        return True
    elif data.lower() in no:
        return False
    else:
        print("Invalid selection")
        return getYesNo()

def draw_menu(stdscr):
	k = 0
	cursor_x = 0
	cursor_y = 0

	# Clear and refresh the screen for a blank canvas
	stdscr.clear()
	stdscr.refresh()

	# Start colors in curses
	curses.start_color()
	curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
	curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
	curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)

	# Loop where k is the last character pressed
	while (k != ord('q')):

		# Initialization
		stdscr.clear()
		height, width = stdscr.getmaxyx()

		if k == curses.KEY_DOWN:
			cursor_y = cursor_y + 1
		elif k == curses.KEY_UP:
			cursor_y = cursor_y - 1
		elif k == curses.KEY_RIGHT:
			cursor_x = cursor_x + 1
		elif k == curses.KEY_LEFT:
			cursor_x = cursor_x - 1

		cursor_x = max(0, cursor_x)
		cursor_x = min(width-1, cursor_x)

		cursor_y = max(0, cursor_y)
		cursor_y = min(height-1, cursor_y)

		# Declaration of strings
		title = "FFMPEG Converter"[:width-1]
		subtitle = "Written by Matthew Toye"[:width-1]
		keystr = "Last key pressed: {}".format(k)[:width-1]
		statusbarstr = "Press 'q' to exit | STATUS BAR | Pos: {}, {}".format(cursor_x, cursor_y)
		progress_title = "Current Progress"[:width-1]
		bitrate_title = "Current Bitrate"
		speed_title = "Current Speed"
		quality_title = "Current Quality"
		fps_title = "Current Fps"
		
		if k == 0:
			keystr = "No key press detected..."[:width-1]
		
		# Centering calculations
		start_x_title = int((width // 2) - (len(title) // 2) - len(title) % 2)
		start_x_subtitle = int((width // 2) - (len(subtitle) // 2) - len(subtitle) % 2)
		start_x_keystr = int((width // 2) - (len(keystr) // 2) - len(keystr) % 2)
		start_y = int((height // 2) - 2)
 
		# Render dividers and boxes to surround values and text
		divide_by_six = int((width-2) // 6)                                          
		first_position_div = (divide_by_six - (divide_by_six // 2))
		first_position_x = int(divide_by_six - (len(progress_title) // 2))      
		second_position_div = (divide_by_six + (divide_by_six // 2))
		second_position_x = int((divide_by_six * 2) - len(speed_title) // 2)    
		third_position_div = ((divide_by_six*2) - (divide_by_six // 2))
		third_position_x = int((divide_by_six * 3) - len(speed_title) // 2)     
		fourth_position_div = ((divide_by_six*3) - (divide_by_six // 2))
		fourth_position_x = int((divide_by_six * 4) - len(quality_title) // 2)  
		fifth_position_div = ((divide_by_six*4) - (divide_by_six // 2))
		fifth_position_x = int((divide_by_six * 5) - len(bitrate_title) // 2)   
		sixth_position_div = ((divide_by_six*5) - (divide_by_six // 2))
		seventh_position_div = ((divide_by_six*5) + (divide_by_six // 2))
 
		middle_div = ""
		for x in range(divide_by_six):
			middle_div += "-"    
		bottom_div = ""
		for x in range(divide_by_six):
			bottom_div += "_"        
					
		stdscr.addstr(0, first_position_x, progress_title, curses.color_pair(1))        
		stdscr.addstr(0, second_position_x, fps_title, curses.color_pair(1))       
		stdscr.addstr(0, third_position_x, speed_title, curses.color_pair(1))       
		stdscr.addstr(0, fourth_position_x, quality_title, curses.color_pair(1))      
		stdscr.addstr(0, fifth_position_x, bitrate_title, curses.color_pair(1))      
		stdscr.addstr(0, first_position_div, "|", curses.color_pair(1))
		stdscr.addstr(0, second_position_div, "|", curses.color_pair(1))
		stdscr.addstr(0, third_position_div, "|", curses.color_pair(1))
		stdscr.addstr(0, fourth_position_div, "|", curses.color_pair(1))
		stdscr.addstr(0, fifth_position_div, "|", curses.color_pair(1))
		stdscr.addstr(0, sixth_position_div, "|", curses.color_pair(1))
		stdscr.addstr(0, seventh_position_div, "|", curses.color_pair(1))
		stdscr.addstr(1, first_position_div, ("|%s" % (middle_div)), curses.color_pair(1))
		stdscr.addstr(1, second_position_div, ("|%s" % (middle_div)), curses.color_pair(1))
		stdscr.addstr(1, third_position_div, ("|%s" % (middle_div)), curses.color_pair(1))
		stdscr.addstr(1, fourth_position_div, ("|%s" % (middle_div)), curses.color_pair(1))
		stdscr.addstr(1, fifth_position_div, ("|%s" % (middle_div)), curses.color_pair(1))
		stdscr.addstr(1, sixth_position_div, ("|%s" % (middle_div)), curses.color_pair(1))
		stdscr.addstr(1, seventh_position_div, "|", curses.color_pair(1))
		stdscr.addstr(2, first_position_div, "|", curses.color_pair(1))
		stdscr.addstr(2, second_position_div, "|", curses.color_pair(1))
		stdscr.addstr(2, third_position_div, "|", curses.color_pair(1))
		stdscr.addstr(2, fourth_position_div, "|", curses.color_pair(1))
		stdscr.addstr(2, fifth_position_div, "|", curses.color_pair(1))
		stdscr.addstr(2, sixth_position_div, "|", curses.color_pair(1))
		stdscr.addstr(2, seventh_position_div, "|", curses.color_pair(1))                    
		stdscr.addstr(3, first_position_div, ("|%s" % (bottom_div)), curses.color_pair(1))
		stdscr.addstr(3, second_position_div, ("|%s" % (bottom_div)), curses.color_pair(1))
		stdscr.addstr(3, third_position_div, ("|%s" % (bottom_div)), curses.color_pair(1))
		stdscr.addstr(3, fourth_position_div, ("|%s" % (bottom_div)), curses.color_pair(1))
		stdscr.addstr(3, fifth_position_div, ("|%s" % (bottom_div)), curses.color_pair(1))
		stdscr.addstr(3, sixth_position_div, ("|%s" % (bottom_div)), curses.color_pair(1))
		stdscr.addstr(3, seventh_position_div, "|", curses.color_pair(1))
		
		# Render status bar
		stdscr.attron(curses.color_pair(3))
		stdscr.addstr(height-1, 0, statusbarstr)
		stdscr.addstr(height-1, len(statusbarstr), " " * (width - len(statusbarstr) - 1))
		stdscr.attroff(curses.color_pair(3))

		# Turning on attributes for title
		stdscr.attron(curses.color_pair(2))
		stdscr.attron(curses.A_BOLD)

		# Rendering title
		stdscr.addstr(start_y, start_x_title, title)

		# Turning off attributes for title
		stdscr.attroff(curses.color_pair(2))
		stdscr.attroff(curses.A_BOLD)

		# Print rest of text
		stdscr.addstr(start_y + 1, start_x_subtitle, subtitle)
		stdscr.addstr(start_y + 3, (width // 2) - 2, '-' * 4)
		stdscr.addstr(start_y + 5, start_x_keystr, keystr)
		stdscr.move(cursor_y, cursor_x)

		# Refresh the screen
		stdscr.refresh()

		# Wait for next input
		k = stdscr.getch()

def getinfo(fileName=None, silent=False, tag=True, tvdbid=None):
    tagdata = None
    # Try to guess the file is guessing is enabled
    if fileName is not None:
        tagdata = guessInfo(fileName, tvdbid)

    if silent is False:
        if tagdata:
            print("Proceed using guessed identification from filename?")
            if getYesNo():
                return tagdata
        else:
            print("Unable to determine identity based on filename, must enter manually")
        m_type = mediatype()
        if m_type is 3:
            tvdbid = getValue("Enter TVDB Series ID", True)
            season = getValue("Enter Season Number", True)
            episode = getValue("Enter Episode Number", True)
            return m_type, tvdbid, season, episode
        elif m_type is 1:
            imdbid = getValue("Enter IMDB ID")
            return m_type, imdbid
        elif m_type is 2:
            tmdbid = getValue("Enter TMDB ID", True)
            return m_type, tmdbid
        elif m_type is 4:
            return None
        elif m_type is 5:
            return False
    else:
        if tagdata and tag:
            return tagdata
        else:
            return None


def guessInfo(fileName, tvdbid=None):
    if tvdbid:
        guess = guessit.guess_episode_info(fileName)
        return tvdbInfo(guess, tvdbid)
    if not settings.fullpathguess:
        fileName = os.path.basename(fileName)
    guess = guessit.guess_file_info(fileName)
    try:
        if guess['type'] == 'movie':
            return tmdbInfo(guess)
        elif guess['type'] == 'episode':
            return tvdbInfo(guess, tvdbid)
        else:
            return None
    except Exception as e:
        print(e)
        return None


def tmdbInfo(guessData):
    tmdb.configure(tmdb_api_key)
    movies = tmdb.Movies(guessData["title"].encode('ascii', errors='ignore'), limit=4)
    for movie in movies.iter_results():
        # Identify the first movie in the collection that matches exactly the movie title
        foundname = ''.join(e for e in movie["title"] if e.isalnum())
        origname = ''.join(e for e in guessData["title"] if e.isalnum())
        # origname = origname.replace('&', 'and')
        if foundname.lower() == origname.lower():
            print("Matched movie title as: %s %s" % (movie["title"].encode(sys.stdout.encoding, errors='ignore'), movie["release_date"].encode(sys.stdout.encoding, errors='ignore')))
            movie = tmdb.Movie(movie["id"])
            if isinstance(movie, dict):
                tmdbid = movie["id"]
            else:
                tmdbid = movie.get_id()
            return 2, tmdbid
    return None


def tvdbInfo(guessData, tvdbid=None):
    series = guessData["series"]
    if 'year' in guessData:
        fullseries = series + " (" + str(guessData["year"]) + ")"
    season = guessData["season"]
    episode = guessData["episodeNumber"]
    t = tvdb_api.Tvdb(interactive=False, cache=False, banners=False, actors=False, forceConnect=True, language='en')
    try:
        tvdbid = str(tvdbid) if tvdbid else t[fullseries]['id']
        series = t[int(tvdbid)]['seriesname']
    except:
        tvdbid = t[series]['id']
    try:
        print("Matched TV episode as %s (TVDB ID:%d) S%02dE%02d" % (series.encode(sys.stdout.encoding, errors='ignore'), int(tvdbid), int(season), int(episode)))
    except:
        print("Matched TV episode")
    return 3, tvdbid, season, episode


def processFile(inputfile, tagdata, relativePath=None):
    # Gather tagdata
    if tagdata is False:
        return  # This means the user has elected to skip the file
    elif tagdata is None:
        tagmp4 = None  # No tag data specified but convert the file anyway
    elif tagdata[0] is 1:
        imdbid = tagdata[1]
        tagmp4 = tmdb_mp4(imdbid, language=settings.taglanguage, logger=log)
        try:
            print("Processing %s" % (tagmp4.title.encode(sys.stdout.encoding, errors='ignore')))
        except:
            print("Processing movie")
    elif tagdata[0] is 2:
        tmdbid = tagdata[1]
        tagmp4 = tmdb_mp4(tmdbid, True, language=settings.taglanguage, logger=log)
        try:
            print("Processing %s" % (tagmp4.title.encode(sys.stdout.encoding, errors='ignore')))
        except:
            print("Processing movie")
    elif tagdata[0] is 3:
        tvdbid = int(tagdata[1])
        season = int(tagdata[2])
        episode = int(tagdata[3])
        tagmp4 = Tvdb_mp4(tvdbid, season, episode, language=settings.taglanguage, logger=log)
        try:
            print("Processing %s Season %02d Episode %02d - %s" % (tagmp4.show.encode(sys.stdout.encoding, errors='ignore'), int(tagmp4.season), int(tagmp4.episode), tagmp4.title.encode(sys.stdout.encoding, errors='ignore')))
        except:
            print("Processing TV episode")

    # Process
    if MkvtoMp4(settings, logger=log).validSource(inputfile):
        converter = MkvtoMp4(settings, logger=log)
        output = converter.process(inputfile, True)
        if output:
            print("We made it past output")
            if tagmp4 is not None:
                try:
                    tagmp4.setHD(output['x'], output['y'])
                    tagmp4.writeTags(output['output'], settings.artwork, settings.thumbnail)
                except Exception as e:
                    print("There was an error tagging the file")
                    print(e)
            if settings.relocate_moov:
                converter.QTFS(output['output'])
            output_files = converter.replicate(output['output'], relativePath=relativePath)
            if settings.postprocess:
                post_processor = PostProcessor(output_files)
                if tagdata:
                    if tagdata[0] is 1:
                        post_processor.setMovie(tagdata[1])
                    elif tagdata[0] is 2:
                        post_processor.setMovie(tagdata[1])
                    elif tagdata[0] is 3:
                        post_processor.setTV(tagdata[1], tagdata[2], tagdata[3])
                post_processor.run_scripts()

def getFileInfo(inputfile):
    if os.path.isdir(inputfile):
        cpt = sum([len(files) for r, d, files in os.walk(inputfile)])
        count = 0
        once = False
        print("total files in directory: %s" % (cpt))
        print("Resetting filesToConvert.log")
        file = open(os.path.join(os.path.dirname(sys.argv[0]), 'filesToConvert.log'),"w")  
        file.write("")          
        file.close()
        
        for r, d, f in os.walk(inputfile):
            for file in f:
                count += 1
                updatedCount = percentage(count, cpt)
                print("Completion: %%%s" % round(updatedCount, 2), end='\r')
                
                filepath = os.path.join(r, file)
                try:
                    if MkvtoMp4(settings, logger=log).validSource(filepath):

                        reason = MkvtoMp4(settings, logger=log).needConversion(filepath)
                        if reason:
                            print("Logging file: %s because of incorrect %s" % (filepath, reason))
                            file = open(os.path.join(os.path.dirname(sys.argv[0]), 'filesToConvert.log'),"a")
                            
                            if once == False:
                                file.write("%s" % (filepath))
                                once = True
                            else:
                                file.write("\n")
                                file.write("%s" % (filepath))
                            file.close()                
                except Exception as e:
                    print("An unexpected error occurred, processing of this file has failed")
                    print(str(e))
                    
    elif (os.path.isfile(inputfile) and MkvtoMp4(settings, logger=log).validSource(inputfile)):
        if MkvtoMp4(settings, logger=log).validSource(inputfile):

            reason = MkvtoMp4(settings, logger=log).needConversion(inputfile, True)
            if reason:
                print("Conversion needed on File: %s because of incorrect %s" % (inputfile, reason))
         
    else:
        try:
            print("File %s is not in the correct format" % (path))
        except:
            print("File is not in the correct format")
      
def walkDir(dir, silent=False, preserveRelative=False, tvdbid=None, tag=True):
    biggest_file_size = 0
    biggest_file_name = ""
    m2ts_file = False
    for r, d, f in os.walk(dir):
        for file in f:
            filepath = os.path.join(r, file)
            if filepath.endswith('.m2ts'): #m2ts files just screw up everything, but typically the largest file is the file that we want to convert.
                m2ts_file = True
                size = os.path.getsize(filepath)
                if size > biggest_file_size:
                    biggest_file_size = size
                    biggest_file_name = filepath

        for file in f:
            filepath = os.path.join(r, file)
            if m2ts_file == True:
                dir_name = os.path.dirname(os.path.realpath( biggest_file_name ))
                filepath = biggest_file_name
            relative = os.path.split(os.path.relpath(filepath, dir))[0] if preserveRelative else None
            try:
                if MkvtoMp4(settings, logger=log).validSource(filepath):
                    try:
                        print("Processing file %s" % (filepath.encode(sys.stdout.encoding, errors='ignore')))
                    except:
                        try:
                            print("Processing file %s" % (filepath.encode('utf-8', errors='ignore')))
                        except:
                            print("Processing file")
                    if tag:
                        tagdata = getinfo(filepath, silent, tvdbid=tvdbid)
                    else:
                        tagdata = None
                    processFile(filepath, tagdata, relativePath=relative)
                    if m2ts_file == True:
                        filelist = [ f_r for f_r in os.listdir(dir_name) if f_r.endswith(".m2ts") ]
                        for f_r in filelist:
                            file_to_remove = os.path.join(r, f_r)
                            os.remove(file_to_remove)
                        break
            except Exception as e:
                print("An unexpected error occurred, processing of this file has failed")
                print(str(e))

def percentage(part, whole):
  return 100 * float(part)/float(whole)
  
def checkForSpot(maxproc, printlog=True):
  for pos in range(1, maxproc):
    fname='.spot' + str(pos)
    if not os.path.isfile(fname):
        try:
            f = open(fname ,'w')
        except:
            f = False
        if not f == False:
          f.close()
          return pos
  if printlog == True:
      print("Waiting for other scripts to finish..")
  time.sleep(1)
  return checkForSpot(maxproc, False)


def main():
    global settings

    parser = argparse.ArgumentParser(description="Manual conversion and tagging script for sickbeard_mp4_automator")
    parser.add_argument('-i', '--input', help='The source that will be converted. May be a file or a directory')
    parser.add_argument('-r', '--readonly', action="store_true", help='Read all data from files in the directory provided, and list them in a file')
    parser.add_argument('-c', '--config', help='Specify an alternate configuration file location')
    parser.add_argument('-a', '--auto', action="store_true", help="Enable auto mode, the script will not prompt you for any further input, good for batch files. It will guess the metadata using guessit")
    parser.add_argument('-tv', '--tvdbid', help="Set the TVDB ID for a tv show")
    parser.add_argument('-s', '--season', help="Specifiy the season number")
    parser.add_argument('-e', '--episode', help="Specify the episode number")
    parser.add_argument('-imdb', '--imdbid', help="Specify the IMDB ID for a movie")
    parser.add_argument('-tmdb', '--tmdbid', help="Specify theMovieDB ID for a movie")
    parser.add_argument('-nm', '--nomove', action='store_true', help="Overrides and disables the custom moving of file options that come from output_dir and move-to")
    parser.add_argument('-nc', '--nocopy', action='store_true', help="Overrides and disables the custom copying of file options that come from output_dir and move-to")
    parser.add_argument('-nd', '--nodelete', action='store_true', help="Overrides and disables deleting of original files")
    parser.add_argument('-nt', '--notag', action="store_true", help="Overrides and disables tagging when using the automated option")
    parser.add_argument('-np', '--nopost', action="store_true", help="Overrides and disables the execution of additional post processing scripts")
    parser.add_argument('-pr', '--preserveRelative', action='store_true', help="Preserves relative directories when processing multiple files using the copy-to or move-to functionality")
    parser.add_argument('-cmp4', '--convertmp4', action='store_true', help="Overrides convert-mp4 setting in autoProcess.ini enabling the reprocessing of mp4 files")
    parser.add_argument('-mp', '--maxproc', help="Specify the max amount of concurrent scripts can happen. Passmark score of your CPU / 2000 is a good baseline.")
    parser.add_argument('-m', '--moveto', help="Override move-to value setting in autoProcess.ini changing the final destination of the file")
    parser.add_argument('-fc', '--forceConvert', action='store_true', help="Override video copying and force encoding, useful for files that have timescale issues.") 

    args = vars(parser.parse_args())

    # Setup the silent mode
    silent = args['auto']
    tag = True

    print("%sbit Python." % (struct.calcsize("P") * 8))

    #Concurrent
    if not args['maxproc'] == None:
        checkForSpot(args['maxproc'])


    # Settings overrides
    if(args['config']):
        if os.path.exists(args['config']):
            print('Using configuration file "%s"' % (args['config']))
            settings = ReadSettings(os.path.split(args['config'])[0], os.path.split(args['config'])[1], logger=log)
        elif os.path.exists(os.path.join(os.path.dirname(sys.argv[0]), args['config'])):
            print('Using configuration file "%s"' % (args['config']))
            settings = ReadSettings(os.path.dirname(sys.argv[0]), args['config'], logger=log)
        else:
            print('Configuration file "%s" not present, using default autoProcess.ini' % (args['config']))

    # IF READONLY IS SET, WE WILL ONLY DO THAT. WE WILL NOT USE ANY OTHER CMD ARGUMENT GIVEN (EXCEPT CONFIG)
    if (args['readonly']):
        print("Reading info about files only..Ignoring all other command arguments..")
        readonly = True
    else:
        readonly = False
        if (args['nomove']):
            settings.output_dir = None
            settings.moveto = None
            print("No-move enabled")
        elif (args['moveto']):
            settings.moveto = args['moveto']
            print("Overriden move-to to " + args['moveto'])
        if (args['nocopy']):
            settings.copyto = None
            print("No-copy enabled")
        if (args['nodelete']):
            settings.delete = False
            print("No-delete enabled")
        if (args['convertmp4']):
            settings.processMP4 = True
            print("Reprocessing of MP4 files enabled")
        if (args['notag']):
            settings.tagfile = False
            print("No-tagging enabled")
        if (args['nopost']):
            settings.postprocess = False
            print("No post processing enabled")
        if (args['forceConvert']):
            settings.forceConvert = True

    # Establish the path we will be working with
    if (args['input']):
        path = (str(args['input']))
        try:
            path = glob.glob(path)[0]
        except:
            pass
    else:
        path = getValue("Enter path to file")
    
    if readonly:
        getFileInfo(path)
    else:
        tvdbid = int(args['tvdbid']) if args['tvdbid'] else None
        if os.path.isdir(path):
            walkDir(path, silent, tvdbid=tvdbid, preserveRelative=args['preserveRelative'], tag=settings.tagfile)
        elif (os.path.isfile(path) and MkvtoMp4(settings, logger=log).validSource(path)):
            if (not settings.tagfile):
                tagdata = None
            elif (args['tvdbid'] and not (args['imdbid'] or args['tmdbid'])):
                season = int(args['season']) if args['season'] else None
                episode = int(args['episode']) if args['episode'] else None
                if (tvdbid and season and episode):
                    tagdata = [3, tvdbid, season, episode]
                else:
                    tagdata = getinfo(path, silent=silent, tvdbid=tvdbid)
            elif ((args['imdbid'] or args['tmdbid']) and not args['tvdbid']):
                if (args['imdbid']):
                    imdbid = args['imdbid']
                    tagdata = [1, imdbid]
                elif (args['tmdbid']):
                    tmdbid = int(args['tmdbid'])
                    tagdata = [2, tmdbid]
            else:
                tagdata = getinfo(path, silent=silent, tvdbid=tvdbid)
            processFile(path, tagdata)
        elif (os.path.isfile(path)):
            try:
                with open(path) as f:
                    content = f.readlines()
                    content = [x.strip() for x in content]
                    contentCopy = list(content)
                    contentLen = len(content)
                    print("TOTAL FILES TO CONVERT: %s" % contentLen)
                    count = 0
                
                try:            
                    for x in content:
                        currFile = x;
                        updatedCount = percentage(count, contentLen)
                        print("Completion: %%%s" % round(updatedCount, 2), end='\r')    
                        
                        if MkvtoMp4(settings, logger=log).validSource(currFile):
                            if (not settings.tagfile):
                                tagdata = None
                            elif (args['tvdbid'] and not (args['imdbid'] or args['tmdbid'])):
                                tvdbid = int(args['tvdbid']) if args['tvdbid'] else None
                                season = int(args['season']) if args['season'] else None
                                episode = int(args['episode']) if args['episode'] else None
                                if (tvdbid and season and episode):
                                    tagdata = [3, tvdbid, season, episode]
                                else:
                                    tagdata = getinfo(currFile, silent=silent, tvdbid=tvdbid)
                            elif ((args['imdbid'] or args['tmdbid']) and not args['tvdbid']):
                                if (args['imdbid']):
                                    imdbid = args['imdbid']
                                    tagdata = [1, imdbid]
                                elif (args['tmdbid']):
                                    tmdbid = int(args['tmdbid'])
                                    tagdata = [2, tmdbid]
                            else:
                                tagdata = getinfo(currFile, silent=silent)
                            
                            print("PROCCESSING: %s" % (currFile))
                            processFile(currFile, tagdata)
                            
                            count += 1
                            print("removing %s from file..list length before: %s" % (currFile, len(contentCopy)))
                            contentCopy.remove(currFile)
                            print("list length after: %s" % (len(contentCopy)))
                            
                            data = open(path, "w")
                            for c in contentCopy:
                                   data.write("%s\n" % (c))
                            data.close()
                except Exception as e:
                    print(e)
  
            except:
                print("File %s is not in the correct format" % (path))
        else:
            try:
                print("File %s is not in the correct format" % (path))
            except:
                print("File is not in the correct format")


if __name__ == '__main__':
    main()
