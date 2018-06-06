from __future__ import unicode_literals
from __future__ import print_function
import os
import time
import json
import sys
import platform
import shutil
try:
    import configparser
except ImportError:
    import ConfigParser as configparser
import subprocess
from subprocess import Popen, PIPE

class autoSetup:
    def __init__(self, logger=None):
        self.python_location = None
        self.log = logger
         #Figure out what type of system we are running on
        if sys.platform == "linux" or sys.platform == "linux2":
            self.system_type = "linux"
        elif sys.platform == "darwin":
            self.system_type = "mac"
        elif sys.platform == "win32":
            self.system_type = "windows"

    def check_modules(self, talk=True):
        # Some modules don't show up.. here is the list of ones that will not show up :/
        # requests[security], setuptools
        # Not perfect.. but better than nothing i guess

        modules = ["requests", "requests-cache", "babelfish", "guessit", "subliminal", "stevedore==1.19.1", "deluge-client", "qtfaststart"]
        not_avail = []
        
        p = Popen([sys.executable, '-m', 'pip', 'freeze'], stdin=PIPE, stdout=PIPE, stderr=PIPE, encoding='utf8')
        installed_modules, err = p.communicate()

        for q in range(len(modules)):
            if modules[q] not in installed_modules:
                not_avail.append(modules[q])
        
        if len(not_avail) > 0:
            if talk and self.system_type != "windows":
                print("\n-----------------------------------------------------------\nSome packages are not installed: '\x1b[31m%s\x1b[0m'\n-----------------------------------------------------------\n" % (", ".join(not_avail)))
            elif talk: 
                print("\n-----------------------------------------------------------\nSome packages are not installed: %s\n-----------------------------------------------------------\n\n" % (", ".join(not_avail)))
                
            return 1
        elif talk:
            print("All required modules are installed.. proceeding")
        return 0
            
    def linux_whereis(self, find):
        p = Popen(['whereis', find], stdin=PIPE, stdout=PIPE, stderr=PIPE, encoding='utf8')
        output, err = p.communicate()
        my_split = output.split(' ')
        
        for i in range(len(my_split)):
            # Skip first iteration 
            if i == 0:
                continue
                
            if find in my_split[i]:
                return my_split[i]
        
        return None

    def install_all_modules(self):
        self.log.info("Starting modules installation")
        
        err = False
        modules = ["setuptools", "requests", "requests[security]", "requests-cache", "babelfish", "guessit<2", "subliminal<2", "stevedore==1.19.1", "deluge-client", "qtfaststart"]
        failed_modules = []
        
        for q in range(len(modules)):
            self.log.info("Installing Module: %s" % (modules[q]))
            
            p = Popen([sys.executable, '-m', 'pip', 'install', '{}'.format(modules[q])], stdin=PIPE, stdout=PIPE, stderr=PIPE, encoding='utf8')
            output, err = p.communicate()
            
            if err:
                self.log.error("ERROR while installing: %s. Error output: %s" % (modules[q], err))
                failed_modules.append(modules[q])
                
        if len(failed_modules) > 0:
            self.log.error("List of modules we failed to install:\n\n%s" % ("\n".join(failed_modules)))
            return 1
        return 0
    
    def setup_config(self):
        self.log.info("STARTING INI CONFIGURATOR\n")
        config = configparser.SafeConfigParser()
        currConfigFile = ("config-%s.ini" % (platform.node()))
        config.read('autoProcess.ini.sample')
        section = "MP4"
        curr_setting = 1
        change_setting = None

        while True:
            # FFMPEG Location
            if curr_setting == 1:
                ffmpeg_loc = config.get(section, "ffmpeg")
                if self.system_type == "windows":
                    ffmpeg_loc = "ffmpeg.exe"
                elif self.system_type == "linux" or self.system_type == "mac":
                    ffmpeg_loc = self.linux_whereis("ffmpeg")
                    if ffmpeg_loc is None:
                        ffmpeg_loc = ""
                
                new_ffmpeg_loc = input("Change the default ffmpeg location? (Enter for default '%s'): " % (ffmpeg_loc)) or ffmpeg_loc
                config.set(section, "ffmpeg", new_ffmpeg_loc)
                
                if change_setting is not None:
                    curr_setting = 11
                    
            # FFPROBE Location
            if curr_setting == 2:
                ffprobe_loc = config.get(section, "ffprobe")
                if self.system_type == "windows":
                    ffprobe_loc = "ffprobe.exe"
                elif self.system_type == "linux" or self.system_type == "mac":
                    ffprobe_loc = self.linux_whereis("ffprobe")
                    if ffprobe_loc is None:
                        ffprobe_loc = ""
                        
                new_ffprobe_loc = input("Change the default ffprobe location? (Enter for default '%s'): " % (ffprobe_loc)) or ffprobe_loc
                config.set(section, "ffprobe", new_ffprobe_loc)
                
                if change_setting is not None:
                    curr_setting = 11
                                 
            # Video-Codec setting
            if curr_setting == 3:
                vcodec = config.get(section, "video-codec")
                print("\ncodec options:\nh264\nx264\nh265\nx265\nBE SURE TO LIST EITHER h264 OR h265 AS THE FIRST ONE! THIS IS DEFAULT ENCODING CODEC.\n")
                new_codec = input("What codecs do you want to support? Enter as many as you would like, seperated by commas. example:  (Enter for default '%s'): " % (vcodec)) or vcodec
                config.set(section, "video-codec", new_codec)
                
                if change_setting is not None:
                    curr_setting = 11
                               
            # Output Extension setting
            if curr_setting == 4:
                extension = config.get(section, "output_extension")
                new_extension = input("What do you want the output extension to be? (Enter for default '%s'): " % (extension)) or extension
                config.set(section, "output_extension", new_extension)
                
                if change_setting is not None:
                    curr_setting = 11
                                
            # Output Format setting
            if curr_setting == 5:
                format = config.get(section, "output_format")
                print("\noutput formats:\nmp4\nmov\n")
                new_format = input("What do you want the output format to be? (Enter for default '%s'): " % (format)) or format
                config.set(section, "output_format", new_format)
                
                if change_setting is not None:
                    curr_setting = 11
                                 
            # CRF setting
            if curr_setting == 6:
                new_crf = input("Do you want to use CRF? (Enter for default 'yes'): ")
                
                if new_crf == "":
                    crf = config.get(section, "video-crf")
                    new_crf = input("What CFR Value do you want to use? (Enter for default '%s'): " % (crf)) or crf
                    config.set(section, "video-crf", new_crf)
                else:
                    config.set(section, "video-crf", "")
                
                if change_setting is not None:
                    curr_setting = 11
                               
            # Video Level setting
            if curr_setting == 7:
                use_level = input("Do you want to set a video level, or just use the default? If you aren't sure, use default. (Enter for default 'yes'): ")

                if use_level == "":
                    level = config.get(section, "h264-max-level")
                    print("\nCommon Video Levels:\n3\n3.1\n3.2\n4\n4.1\n4.2\n5\n5.1\n")
                    new_level = input("What video level do you want to use? (Enter for default '%s'): " % (level)) or level
                    config.set(section, "h264-max-level", new_level)
                else:
                    config.set(section, "h264-max-level", "")
                
                if change_setting is not None:
                    curr_setting = 11
                                 
            # Pixel Format setting
            if curr_setting == 8:
                use_pix_fmt = input("Do you want to use a pixel format, or just use the default? If you aren't sure, use default. (Enter for default 'no'): ")
       
                if not use_pix_fmt == "":
                    pixel_fmt = config.get(section, "pix-fmt")
                    print("\nCommon pixel formats:\nyuv420p\nyuyv422\nyuv422p\nyuv444p\nyuv420p10le(x265)\n")
                    new_pixel_fmt = input("What pixel format do you want to use? (Enter for default '%s'): " % (pixel_fmt)) or pixel_fmt
                    config.set(section, "pix-fmt", new_pixel_fmt)
                else:
                    config.set(section, "pix-fmt", "")
                
                if change_setting is not None:
                    curr_setting = 11
                                       
            # Video Profile setting    
            if curr_setting == 9:
                use_profile = input("Do you want to set a specific video profile? (Enter for default 'no'): ")
                
                if not use_profile == "":
                    video_prof = config.get(section, "video-profile")
                    print("\nAvailable Video Profiles:\nbaseline\nmain\nhigh\nhigh10\nhigh422\nhigh444\n")
                    new_video_prof = input("What video profile do you want to use? (Enter for default '%s'): " % (video_prof)) or video_prof
                    config.set(section, "video-profile", new_video_prof)
                else:
                    config.set(section, "video-profile", "")
                
                if change_setting is not None:
                    curr_setting = 11
                                
            # Output directory settings
            if curr_setting == 10:
                use_output_dir = input("Do you want to use an alternate output directory? Default is the same folder as the source. (Enter for default 'no'): ")
                
                if not use_output_dir == "":
                    new_output_dir = input("What directory do you want to use?: ")
                    config.set(section, "output_directory", new_output_dir)
                    create_sub_dir = config.get(section, "create_subdirectories")
                    new_create_sub_dir = input("Do you want to create subdirectories the same is the input file for easy copying? (Enter for default '%s'): " % (create_sub_dir)) or create_sub_dir
                    config.set(section, "create_subdirectories", new_create_sub_dir)
                else:
                    config.set(section, "output_directory", "")
                    config.set(section, "create_subdirectories", "False")
                
                if change_setting is not None:
                    curr_setting = 11
                                
            # FINAL READOUT OF SETTINGS
            if curr_setting > 10:
                list_of_settings = ["ffmpeg", "ffprobe", "video-codec", "output_extension", "output_format", "video-crf", "h264-max-level", "pix-fmt", "video-profile", "output_directory"]
                
                for i in range(len(list_of_settings)):
                    myi = i
                    myi += 1
                    
                    print("(%s) %s = %s" % (myi, list_of_settings[i], config.get(section, list_of_settings[i])))
                    
                change_setting = input("Do you want to change any settings? Enter the number of setting to change, or enter for none: ")
                
                if change_setting == "":
                    break;
                    
                elif int(change_setting) > 0 and int(change_setting) < 11:
                    print("changing setting %s" % (change_setting))
                    curr_setting = int(change_setting)
                    curr_setting -= 1
                    
                
            curr_setting += 1
            
        with open(currConfigFile, 'w') as configfile:
            config.write(configfile)    
            self.log.info("DONE WITH INI FILE")
            return 0
        return 1
            
    def setup_everything(self):
        if self.install_all_modules() > 0:
            self.log.error("There were errors while installing modules. Check logs, and try again.. Aborting remainder of setup..")
            return 1
            
        self.setup_config()
        
        if self.check_modules(False) > 0:
            return 1
        return 0

