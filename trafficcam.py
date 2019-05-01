#! /usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
print("Loading ...")
import time
import datetime
import os
import sys
import glob
import shutil
import logging
from threading import Thread
import subprocess

progVer = "9.09"

# Temporarily put these variables here so config.py does not need updating
# These are required for sqlite3 speed_cam.db database.
# Will work on reports and possibly a web query page for speed data.

mypath = os.path.abspath(__file__)  # Find the full path of this python script
# get the path location only (excluding script name)
baseDir = mypath[0:mypath.rfind("/")+1]
baseFileName = mypath[mypath.rfind("/")+1:mypath.rfind(".")]
progName = os.path.basename(__file__)
horz_line = "----------------------------------------------------------------------"
# Color data for OpenCV lines and text
cvWhite = (255, 255, 255)
cvBlack = (0, 0, 0)
cvBlue = (255, 0, 0)
cvGreen = (0, 255, 0)
cvRed = (0, 0, 255)

# Check for variable file to import and error out if not found.
configFilePath = os.path.join(baseDir, "config.py")
if not os.path.exists(configFilePath):
    print("ERROR : Missing config.py file - File Not Found %s"
          % configFilePath)
    import urllib2
    config_url = "https://raw.github.com/pageauc/speed-camera/master/config.py"
    print("INFO  : Attempting to Download config.py file from %s" % config_url)
    try:
        wgetfile = urllib2.urlopen(config_url)
    except:
        print("ERROR : Download of config.py Failed")
        print("        Try Rerunning the speed-install.sh Again.")
        print("        or")
        print("        Perform GitHub curl install per Readme.md")
        print("        and Try Again.")
        print("        %s %s Exiting Due to Error" % (progName, progVer))
        sys.exit(1)
    f = open('config.py', 'wb')
    f.write(wgetfile.read())
    f.close()
# Read Configuration variables from config.py file
from config import *

# Now that variables are imported from config.py Setup Logging
if loggingToFile:
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)-8s %(funcName)-10s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        filename=logFilePath,
                        filemode='w')
elif verbose:
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)-8s %(funcName)-10s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
else:
    logging.basicConfig(level=logging.CRITICAL,
                        format='%(asctime)s %(levelname)-8s %(funcName)-10s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

from search_config import search_dest_path

# Import Settings from specified plugin if pluginEnable=True
if pluginEnable:     # Check and verify plugin and load variable overlay
    pluginDir = os.path.join(baseDir, "plugins")
    # Check if there is a .py at the end of pluginName variable
    if pluginName.endswith('.py'):
        pluginName = pluginName[:-3]    # Remove .py extensiion
    pluginPath = os.path.join(pluginDir, pluginName + '.py')
    #logging.info("pluginEnabled - loading pluginName %s", pluginPath)
    if not os.path.isdir(pluginDir):
        logging.error("plugin Directory Not Found at %s", pluginDir)
        #logging.info("Rerun github curl install script to install plugins")
        #logging.info("https://github.com/pageauc/pi-timolo/wiki/")
        #logging.info("How-to-Install-or-Upgrade#quick-install")
        logging.warn("%s %s Exiting Due to Error" % (progName, progVer))
        sys.exit(1)
    elif not os.path.exists(pluginPath):
        logging.error("File Not Found pluginName %s", pluginPath)
        #logging.info("Check Spelling of pluginName Value in %s", configFilePath)
        #logging.info("------- Valid Names -------")
        validPlugin = glob.glob(pluginDir + "/*py")
        validPlugin.sort()
        logging.warn("%s %s Exiting Due to Error", progName, progVer)
        sys.exit(1)
    else:
        pluginCurrent = os.path.join(pluginDir, "current.py")
        try:    # Copy image file to recent folder
            #logging.info("Copy %s to %s", pluginPath, pluginCurrent)
            shutil.copy(pluginPath, pluginCurrent)
        except OSError as err:
            logging.error('Copy Failed from %s to %s - %s',
                          pluginPath, pluginCurrent, err)
            #logging.info("Check permissions, disk space, Etc.")
            logging.warn("%s %s Exiting Due to Error", progName, progVer)
            sys.exit(1)
        #logging.info("Import Plugin %s", pluginPath)
        # add plugin directory to program PATH
        sys.path.insert(0, pluginDir)
        from plugins.current import *
        try:
            if os.path.exists(pluginCurrent):
                os.remove(pluginCurrent)
            pluginCurrentpyc = os.path.join(pluginDir, "current.pyc")
            if os.path.exists(pluginCurrentpyc):
                os.remove(pluginCurrentpyc)
        except OSError as err:
            logging.warn("Failed To Remove File %s - %s",
                         pluginCurrentpyc, err)

WEBCAM = True
camResult = subprocess.check_output("vcgencmd get_camera", shell=True)
camResult = camResult.decode("utf-8")
camResult = camResult.replace("\n", "")
try:   # Check to see if opencv is installed
    import cv2
except ImportError:
    logging.error("Could Not import cv2 library")
    if sys.version_info > (2, 9):
        logging.error("python3 failed to import cv2")
        logging.error("Try installing opencv for python3")
    else:
        logging.error("python2 failed to import cv2")
        logging.error("Try RPI Install per command")
        logging.error("%s %s Exiting Due to Error", progName, progVer)
    sys.exit(1)

# fix possible invalid values
if WINDOW_BIGGER < 1.0:
    WINDOW_BIGGER = 1.0
if image_bigger < 1.0:
    image_bigger = 1.0
# System Settings
if WEBCAM:
    # Set width of trigger point image to save
    image_width = int(WEBCAM_WIDTH * image_bigger)
    # Set height of trigger point image to save
    image_height = int(WEBCAM_HEIGHT * image_bigger)
else:
    # Set width of trigger point image to save
    image_width = int(CAMERA_WIDTH * image_bigger)
    # Set height of trigger point image to save
    image_height = int(CAMERA_HEIGHT * image_bigger)
# Calculate conversion from camera pixel width to actual speed.
px_to_kph = float(cal_obj_mm/cal_obj_px * 0.0036)
quote = '"'  # Used for creating quote delimited log file of speed data

if SPEED_MPH:
    speed_units = "mph"
    speed_conv = 0.621371 * px_to_kph #1KM = 3779575.17575025 pixel
else:
    speed_units = "kph"
    speed_conv = px_to_kph #1MI = 6082636.631643 pixel

try:
    x_buf_adjust   # check if variable exists in config.py
except:
    x_buf_adjust = 10   # Default=10 Divisor for screen width to Set space on left and right
                        # of Crop image to ensure object contour is mostly inside tracking area.
                        # smaller give more buffer space.
    logging.warn("x_buf_adjust Not Found in config.py Setting value to %d", x_buf_adjust)

# setup buffer area to ensure contour is mostly contained in crop area
x_buf = int((x_right - x_left) / x_buf_adjust)

try:
    track_counter  # check if variable exists in config.py
except:
    track_counter = 3  # number of consecutive movements before reporting speed
    fix_msg = ("""track_counter variable Not Found in config.py
    To Fix Problem Run menubox.sh UPGRADE menu pick.
    Latest config.py will be named config.py.new
    Do the following commands in SSH or terminal
        cd ~/speed-camera
        cp config.py config.py.bak
        cp config.py.new config.py
    Then Transfer settings from bak File to config.py
            Setting track_counter = %i""" % track_counter)
    logging.warn(fix_msg)
    try:
        raw_input("Press Enter to Continue...")  # python 2
    except:
        input("Press Enter to Continue...")  # python 3


#------------------------------------------------------------------------------
class WebcamVideoStream:
    def __init__(self, CAM_SRC=WEBCAM_SRC, CAM_WIDTH=WEBCAM_WIDTH,
                 CAM_HEIGHT=WEBCAM_HEIGHT):
        """
        initialize the video camera stream and read the first frame
        from the stream
        """
        self.stream = CAM_SRC
        self.stream = cv2.VideoCapture(CAM_SRC)
        self.stream.set(3, CAM_WIDTH)
        self.stream.set(4, CAM_HEIGHT)
        (self.grabbed, self.frame) = self.stream.read()
        # initialize the variable used to indicate if the thread should
        # be stopped
        self.stopped = False

    def start(self):
        """ start the thread to read frames from the video stream """
        t = Thread(target=self.update, args=())
        t.daemon = True
        t.start()
        return self

    def update(self):
        """ keep looping infinitely until the thread is stopped """
        while True:
            # if the thread indicator variable is set, stop the thread
            if self.stopped:
                return
            # otherwise, read the next frame from the stream
            (self.grabbed, self.frame) = self.stream.read()

    def read(self):
        """ return the frame most recently read """
        return self.frame

    def stop(self):
        """ indicate that the thread should be stopped """
        self.stopped = True

#------------------------------------------------------------------------------
def get_fps(start_time, frame_count):
    """ Calculate and display frames per second processing """
    if frame_count >= 1000:
        duration = float(time.time() - start_time)
        FPS = float(frame_count / duration)
        #logging.info("%.2f fps Last %i Frames", FPS, frame_count)
        frame_count = 0
        start_time = time.time()
    else:
        frame_count += 1
    return start_time, frame_count

#------------------------------------------------------------------------------
def show_settings():
    """Initialize and Display program variable settings from config.py"""
    cwd = os.getcwd()
    html_path = "media/html"
    if not os.path.isdir(image_path):
        #logging.info("Creating Image Storage Folder %s", image_path)
        os.makedirs(image_path)
    os.chdir(image_path)
    os.chdir(cwd)
    if imageRecentMax > 0:
        if not os.path.isdir(imageRecentDir):
            #logging.info("Create Recent Folder %s", imageRecentDir)
            try:
                os.makedirs(imageRecentDir)
            except OSError as err:
                logging.error('Failed to Create Folder %s - %s',
                              imageRecentDir, err)
    if not os.path.isdir(search_dest_path):
        #logging.info("Creating Search Folder %s", search_dest_path)
        os.makedirs(search_dest_path)
    if not os.path.isdir(html_path):
        #logging.info("Creating html Folder %s", html_path)
        os.makedirs(html_path)
    os.chdir(cwd)
    return

#------------------------------------------------------------------------------
def take_calibration_image(speed, filename, cal_image):
    """
    Create a calibration image for determining value of IMG_VIEW_FT variable
    Create calibration hash marks
    """
    # If there is bad contrast with background you can change the hash
    # colors to give more contrast.  You need to change values below
    # per values cvRed, cvBlue, cvWhite, cvBlack, cvGreen

    hash_color = cvRed
    motion_win_color = cvBlue

    for i in range(10, image_width - 9, 10):
        cv2.line(cal_image, (i, y_upper - 5), (i, y_upper + 30), hash_color, 1)
    # This is motion window
    cal_image = speed_image_add_lines(cal_image, motion_win_color)
    if SPEED_MPH:
        speed_units = 'mph'
    else:
        speed_units = 'kph'
    return cal_image

#------------------------------------------------------------------------------
def subDirLatest(directory):
    """ Scan for directories and return most recent """
    dirList = ([name for name in os.listdir(directory)
                if os.path.isdir(os.path.join(directory, name))])
    if len(dirList) > 0:
        lastSubDir = sorted(dirList)[-1]
        lastSubDir = os.path.join(directory, lastSubDir)
    else:
        lastSubDir = directory
    return lastSubDir

#------------------------------------------------------------------------------
def subDirCreate(directory, prefix):
    """ Create media subdirectories base on required naming """
    now = datetime.datetime.now()
    # Specify folder naming
    subDirName = ('%s%d%02d%02d-%02d%02d' %
                  (prefix,
                   now.year, now.month, now.day,
                   now.hour, now.minute))
    subDirPath = os.path.join(directory, subDirName)
    if not os.path.exists(subDirPath):
        try:
            os.makedirs(subDirPath)
        except OSError as err:
            logging.error('Cannot Create Dir %s - %s, using default location.',
                          subDirPath, err)
            subDirPath = directory
    else:
        subDirPath = directory
    return subDirPath

#------------------------------------------------------------------------------
def deleteOldFiles(maxFiles, dirPath, prefix):
    """
    Delete Oldest files gt or
    equal to maxfiles that match filename prefix
    """
    try:
        fileList = sorted(glob.glob(os.path.join(dirPath, prefix + '*')),
                          key=os.path.getmtime)
    except OSError as err:
        logging.error('Problem Reading Directory %s - %s', dirPath, err)
    else:
        while len(fileList) >= maxFiles:
            oldest = fileList[0]
            oldestFile = oldest
            try:   # Remove oldest file in recent folder
                fileList.remove(oldest)
                os.remove(oldestFile)
            except OSError as err:
                logging.error('Cannot Remove %s - %s', oldestFile, err)

#------------------------------------------------------------------------------
def subDirCheckMaxFiles(directory, filesMax):
    """ Count number of files in a folder path """
    fileList = glob.glob(directory + '/*jpg')
    count = len(fileList)
    if count > filesMax:
        makeNewDir = True
        #logging.info('Total Files in %s Exceeds %i ', directory, filesMax)
    else:
        makeNewDir = False
    return makeNewDir

#------------------------------------------------------------------------------
def subDirCheckMaxHrs(directory, hrsMax, prefix):
    """ extract the date-time from the directory name """
    # Note to self need to add error checking
    dirName = os.path.split(directory)[1]   # split dir path and keep dirName
    # remove prefix from dirName so just date-time left
    dirStr = dirName.replace(prefix, '')
    # convert string to datetime
    dirDate = datetime.datetime.strptime(dirStr, "%Y-%m-%d-%H:%M")
    rightNow = datetime.datetime.now()   # get datetime now
    diff = rightNow - dirDate  # get time difference between dates
    days, seconds = diff.days, diff.seconds
    dirAgeHours = days * 24 + seconds // 3600  # convert to hours
    if dirAgeHours > hrsMax:   # See if hours are exceeded
        makeNewDir = True
        #logging.info('MaxHrs %i Exceeds %i for %s',
                    # dirAgeHours, hrsMax, directory)
    else:
        makeNewDir = False
    return makeNewDir

#------------------------------------------------------------------------------
def subDirChecks(maxHours, maxFiles, directory, prefix):
    """ Check if motion SubDir needs to be created """
    if maxHours < 1 and maxFiles < 1:  # No Checks required
        # #logging.info('No sub-folders Required in %s', directory)
        subDirPath = directory
    else:
        subDirPath = subDirLatest(directory)
        if subDirPath == directory:   # No subDir Found
            #logging.info('No sub folders Found in %s', directory)
            subDirPath = subDirCreate(directory, prefix)
        elif (maxHours > 0 and maxFiles < 1): # Check MaxHours Folder Age Only
            if subDirCheckMaxHrs(subDirPath, maxHours, prefix):
                subDirPath = subDirCreate(directory, prefix)
        elif (maxHours < 1 and maxFiles > 0):   # Check Max Files Only
            if subDirCheckMaxFiles(subDirPath, maxFiles):
                subDirPath = subDirCreate(directory, prefix)
        elif maxHours > 0 and maxFiles > 0:   # Check both Max Files and Age
            if subDirCheckMaxHrs(subDirPath, maxHours, prefix):
                if subDirCheckMaxFiles(subDirPath, maxFiles):
                    subDirPath = subDirCreate(directory, prefix)
                #else:
                    #logging.info('MaxFiles Not Exceeded in %s', subDirPath)
    os.path.abspath(subDirPath)
    return subDirPath

#------------------------------------------------------------------------------
def filesToDelete(mediaDirPath, extension=image_format):
    """ Return a list of files to be deleted """
    return sorted(
        (os.path.join(dirname, filename)
         for dirname, dirnames, filenames in os.walk(mediaDirPath)
         for filename in filenames
         if filename.endswith(extension)),
        key=lambda fn: os.stat(fn).st_mtime, reverse=True)

#------------------------------------------------------------------------------
def saveRecent(recentMax, recentDir, filename, prefix):
    """
    Create a symlink file in recent folder or file if non unix system
    or symlink creation fails.
    Delete Oldest symlink file if recentMax exceeded.
    """
    src = os.path.abspath(filename)  # Original Source File Path
    # Destination Recent Directory Path
    dest = os.path.abspath(os.path.join(recentDir,
                                        os.path.basename(filename)))
    deleteOldFiles(recentMax, os.path.abspath(recentDir), prefix)
    try:    # Create symlink in recent folder
        #logging.info('   symlink %s', dest)
        os.symlink(src, dest)  # Create a symlink to actual file
    # Symlink can fail on non unix systems so copy file to Recent Dir instead
    except OSError as err:
        logging.error('symlink Failed: %s', err)
        try:  # Copy image file to recent folder (if no support for symlinks)
            shutil.copy(filename, recentDir)
        except OSError as err:
            logging.error('Copy from %s to %s - %s', filename, recentDir, err)

#------------------------------------------------------------------------------
def freeSpaceUpTo(freeMB, mediaDir, extension=image_format):
    """
    Walks mediaDir and deletes oldest files
    until spaceFreeMB is achieved Use with Caution
    """
    mediaDirPath = os.path.abspath(mediaDir)
    if os.path.isdir(mediaDirPath):
        MB2Bytes = 1048576  # Conversion from MB to Bytes
        targetFreeBytes = freeMB * MB2Bytes
        fileList = filesToDelete(mediaDir, extension)
        totFiles = len(fileList)
        delcnt = 0
        #logging.info('Session Started')
        while fileList:
            statv = os.statvfs(mediaDirPath)
            availFreeBytes = statv.f_bfree*statv.f_bsize
            if availFreeBytes >= targetFreeBytes:
                break
            filePath = fileList.pop()
            try:
                os.remove(filePath)
            except OSError as err:
                logging.error('Del Failed %s', filePath)
                logging.error('Error: %s', err)
            else:
                delcnt += 1
                #logging.info('Del %s', filePath)
                #logging.info('Target=%i MB  Avail=%i MB  Deleted %i of %i Files ',
                             # targetFreeBytes / MB2Bytes,
                             # availFreeBytes / MB2Bytes,
                             # delcnt, totFiles)
                # Avoid deleting more than 1/4 of files at one time
                if delcnt > totFiles / 4:
                    logging.warning('Max Deletions Reached %i of %i', delcnt, totFiles)
                    logging.warning('Deletions Restricted to 1/4 of total files per session.')
                    break
        #logging.info('Session Ended')
    else:
        logging.error('Directory Not Found - %s', mediaDirPath)

#------------------------------------------------------------------------------
def freeDiskSpaceCheck(lastSpaceCheck):
    """ Free disk space by deleting some older files """
    if spaceTimerHrs > 0:   # Check if disk free space timer hours is enabled
        # See if it is time to do disk clean-up check
        if (datetime.datetime.now() - lastSpaceCheck).total_seconds() > spaceTimerHrs * 3600:
            lastSpaceCheck = datetime.datetime.now()
            # Set freeSpaceMB to reasonable value if too low
            if spaceFreeMB < 100:
                diskFreeMB = 100
            else:
                diskFreeMB = spaceFreeMB
            #logging.info('spaceTimerHrs=%i  diskFreeMB=%i  spaceMediaDir=%s spaceFileExt=%s',
                         # spaceTimerHrs, diskFreeMB, spaceMediaDir, spaceFileExt)
            freeSpaceUpTo(diskFreeMB, spaceMediaDir, spaceFileExt)
    return lastSpaceCheck

#------------------------------------------------------------------------------
def get_image_name(path, prefix):
    """ build image file names by number sequence or date/time Added tenth of second"""
    rightNow = datetime.datetime.now()
    filename = ("%s/%s%04d%02d%02d-%02d%02d%02d%d.jpg" %
                (path, prefix, rightNow.year, rightNow.month, rightNow.day,
                 rightNow.hour, rightNow.minute, rightNow.second, rightNow.microsecond/100000))
    return filename

#------------------------------------------------------------------------------
def log_to_csv(data_to_append):
    """ Store date to a comma separated value file """
    log_file_path = baseDir + baseFileName + ".csv"
    if not os.path.exists(log_file_path):
        open(log_file_path, 'w').close()
        f = open(log_file_path, 'ab')
        # header_text = ('"YYYYMMDD","HH","MM","Speed","Unit",
        #                  "    Speed Photo Path            ",
        #                  "X","Y","W","H","Area","Direction"' + "\n")
        # f.write( header_text )
        f.close()
        #logging.info("Create New Data Log File %s", log_file_path)
    filecontents = data_to_append + "\n"
    f = open(log_file_path, 'a+')
    f.write(filecontents)
    f.close()
    #logging.info("   CSV - Updated Data  %s", log_file_path)
    return

#------------------------------------------------------------------------------

#------------------------------------------------------------------------------

def speed_get_contours(image, grayimage1):
    image_ok = False
    while not image_ok:
        image = vs.read() # Read image data from video steam thread instance
        if WEBCAM:
            if (WEBCAM_HFLIP and WEBCAM_VFLIP):
                image = cv2.flip(image, -1)
            elif WEBCAM_HFLIP:
                image = cv2.flip(image, 1)
            elif WEBCAM_VFLIP:
                image = cv2.flip(image, 0)
        # crop image to motion tracking area only
        try:
            image_crop = image[y_upper:y_lower, x_left:x_right]
            image_ok = True
        except ValueError:
            logging.error("image Stream Image is Not Complete. Cannot Crop. Retry.")
            image_ok = False
    # Convert to gray scale, which is easier
    grayimage2 = cv2.cvtColor(image_crop, cv2.COLOR_BGR2GRAY)
    # Get differences between the two greyed images
    differenceimage = cv2.absdiff(grayimage1, grayimage2)
    # Blur difference image to enhance motion vectors
    differenceimage = cv2.blur(differenceimage, (BLUR_SIZE, BLUR_SIZE))
    # Get threshold of blurred difference image
    # based on THRESHOLD_SENSITIVITY variable
    retval, thresholdimage = cv2.threshold(differenceimage,
                                           THRESHOLD_SENSITIVITY,
                                           255, cv2.THRESH_BINARY)
    try:
        # opencv 2 syntax default
        contours, hierarchy = cv2.findContours(thresholdimage,
                                               cv2.RETR_EXTERNAL,
                                               cv2.CHAIN_APPROX_SIMPLE)
    except ValueError:
        # opencv 3 syntax
        thresholdimage, contours, hierarchy = cv2.findContours(thresholdimage,
                                                               cv2.RETR_EXTERNAL,
                                                               cv2.CHAIN_APPROX_SIMPLE)
    # Update grayimage1 to grayimage2 ready for next image2
    grayimage1 = grayimage2
    return grayimage1, contours

def speed_image_add_lines(image, color):
    cv2.line(image, (x_left, y_upper),
             (x_right, y_upper), color, 1)
    cv2.line(image, (x_left, y_lower),
             (x_right, y_lower), color, 1)
    cv2.line(image, (x_left, y_upper),
             (x_left, y_lower), color, 1)
    cv2.line(image, (x_right, y_upper),
             (x_right, y_lower), color, 1)
    return image

def speed_notify():
    # if pluginEnable:
        #logging.info("Plugin Enabled per pluginName=%s", pluginName)
    # else:
        #logging.info("Plugin Disabled per pluginEnable=%s", pluginEnable)

    if verbose:
        if loggingToFile:
            print("Logging to File %s (Console Messages Disabled)" % logFilePath)
        # else:
            #logging.info("Logging to Console per Variable verbose=True")

        # if gui_window_on:
            #logging.info("Press lower case q on OpenCV GUI Window to Quit program")
            #logging.info("        or ctrl-c in this terminal session to Quit")
        # else:
            #logging.info("Press ctrl-c in this terminal session to Quit")
    else:
        print("Logging Messages Disabled per verbose=%s" % verbose)

    if calibrate:
        logging.warn("IMPORTANT: Camera Is In Calibration Mode ....")

    #logging.info("Begin Motion Tracking .....")

#------------------------------------------------------------------------------
def speed_camera():
    """ Main speed camera processing function """
    ave_speed = 0.0
    # initialize variables
    frame_count = 0
    fps_time = time.time()
    first_event = True   # Start a New Motion Track
    event_timer = time.time()
    start_pos_x = None
    end_pos_x = None
    prev_pos_x = None
    travel_direction = ""
    font = cv2.FONT_HERSHEY_SIMPLEX
    # Calculate position of text on the images
    if image_text_bottom:
        text_y = (image_height - 50)  # show text at bottom of image
    else:
        text_y = 10  # show text at top of image
    # Initialize prev_image used for taking speed image photo
    lastSpaceCheck = datetime.datetime.now()
    speed_path = image_path
    speed_notify()
    # initialize a cropped grayimage1 image
    image2 = vs.read()  # Get image from PiVideoSteam thread instance
    prev_image = image2  # make a copy of the first image
    try:
        # crop image to motion tracking area only
        image_crop = image2[y_upper:y_lower, x_left:x_right]
    except:
        vs.stop()
        logging.warn("Problem Connecting To Camera Stream.")
        logging.warn("Restarting Camera.  One Moment Please ...")
        time.sleep(4)
        return
    grayimage1 = cv2.cvtColor(image_crop, cv2.COLOR_BGR2GRAY)
    track_count = 0
    speed_list = []
    event_timer = time.time()
    still_scanning = True
    while still_scanning:  # process camera thread images and calculate speed
        image2 = vs.read() # Read image data from video steam thread instance
        grayimage1, contours = speed_get_contours(image2, grayimage1)
        # if contours found, find the one with biggest area
        if contours:
            total_contours = len(contours)
            motion_found = False
            biggest_area = MIN_AREA
            for c in contours:
                # get area of contour
                found_area = cv2.contourArea(c)
                if found_area > biggest_area:
                    (x, y, w, h) = cv2.boundingRect(c)
                    # check if object contour is completely within crop area
                    if (x > x_buf and x + w < x_right - x_left - x_buf):
                        cur_track_time = time.time() # record cur track time
                        track_x = x
                        track_y = y
                        track_w = w  # movement width of object contour
                        track_h = h  # movement height of object contour
                        motion_found = True
                        biggest_area = found_area
            if motion_found:
                # Check if last motion event timed out
                reset_time_diff = time.time() - event_timer
                if  reset_time_diff > event_timeout:
                    # event_timer exceeded so reset for new track
                    event_timer = time.time()
                    first_event = True
                    start_pos_x = None
                    prev_pos_x = None
                    end_pos_x = None
                    #logging.info("Reset- event_timer %.2f>%.2f sec Exceeded",
                                 # reset_time_diff, event_timeout)
                ##############################
                # Process motion events and track object movement
                ##############################
                if first_event:   # This is a first valid motion event
                    first_event = False  # Only one first track event
                    track_start_time = cur_track_time # Record track start time
                    prev_start_time = cur_track_time
                    start_pos_x = track_x
                    prev_pos_x = track_x
                    end_pos_x = track_x
                    #logging.info("New  - 0/%i xy(%i,%i) Start New Track",
                                 # track_counter, track_x, track_y)
                    event_timer = time.time() # Reset event timeout
                    track_count = 0
                    speed_list = []
                else:
                    prev_pos_x = end_pos_x
                    end_pos_x = track_x
                    if end_pos_x - prev_pos_x > 0:
                        travel_direction = "L2R"
                    else:
                        travel_direction = "R2L"
                    # check if movement is within acceptable distance
                    # range of last event
                    if (abs(end_pos_x - prev_pos_x) > x_diff_min and
                            abs(end_pos_x - prev_pos_x) < x_diff_max):
                        track_count += 1  # increment
                        cur_track_dist = abs(end_pos_x - prev_pos_x)
                        cur_ave_speed = float((abs(cur_track_dist /
                                               float(abs(cur_track_time -
                                                         prev_start_time)))) *
                                                         speed_conv)
                        speed_list.append(cur_ave_speed)
                        prev_start_time = cur_track_time
                        event_timer = time.time()
                        if track_count >= track_counter:
                            tot_track_dist = abs(track_x - start_pos_x)
                            tot_track_time = abs(track_start_time - cur_track_time)
                            # ave_speed = float((abs(tot_track_dist / tot_track_time)) * speed_conv)
                            ave_speed = sum(speed_list) / float(len(speed_list))
                            # Track length exceeded so take process speed photo
                            if ave_speed > max_speed_over or calibrate:
                                #logging.info(" Add - %i/%i xy(%i,%i) %3.2f %s"
                                             # # " D=%i/%i C=%i %ix%i=%i sqpx %s",
                                             # track_count, track_counter,
                                             # track_x, track_y,
                                             # cur_ave_speed, speed_units,
                                             # abs(track_x - prev_pos_x),
                                             # x_diff_max,
                                             # total_contours,
                                             # track_w, track_h, biggest_area,
                                             # travel_direction)
                                # Resize and process previous image
                                # before saving to disk
                                prev_image = image2
                                # Create a calibration image file name
                                # There are no subdirectories to deal with
                                if calibrate:
                                    log_time = datetime.datetime.now()
                                    filename = get_image_name(speed_path, "calib-")
                                    prev_image = take_calibration_image(ave_speed,
                                                                        filename,
                                                                        prev_image)
                                else:
                                    # Check if subdirectories configured
                                    # and create as required
                                    speed_path = subDirChecks(imageSubDirMaxHours,
                                                              imageSubDirMaxFiles,
                                                              image_path, image_prefix)
                                    # Create image file name prefix
                                    if image_filename_speed:
                                        speed_prefix = (str(int(round(ave_speed)))
                                                        + "-" + image_prefix)
                                    else:
                                        speed_prefix = image_prefix
                                    # Record log_time for use later in csv and sqlite
                                    log_time = datetime.datetime.now()
                                    # create image file name path
                                    filename = get_image_name(speed_path,
                                                              speed_prefix)
                                # Add motion rectangle to image if required
                                if image_show_motion_area:
                                    prev_image = speed_image_add_lines(prev_image, cvRed)
                                    # show centre of motion if required
                                    if SHOW_CIRCLE:
                                        cv2.circle(prev_image,
                                                   (track_x + x_left, track_y + y_upper),
                                                   CIRCLE_SIZE,
                                                   cvGreen, LINE_THICKNESS)
                                    else:
                                        cv2.rectangle(prev_image,
                                                      (int(track_x + x_left),
                                                       int(track_y + y_upper)),
                                                      (int(track_x + x_left + track_w),
                                                       int(track_y + y_upper + track_h)),
                                                      cvGreen, LINE_THICKNESS)
                                big_image = cv2.resize(prev_image,
                                                       (image_width,
                                                        image_height))
                                # Write text on image before saving
                                # if required.
                                if image_text_on:
                                    image_text = ("SPEED %.1f %s - %s"
                                                  % (ave_speed,
                                                     speed_units,
                                                     filename))
                                    text_x = int((image_width / 2) -
                                                 (len(image_text) *
                                                  image_font_size / 3))
                                    if text_x < 2:
                                        text_x = 2
                                    cv2.putText(big_image,
                                                image_text,
                                                (text_x, text_y),
                                                font,
                                                FONT_SCALE,
                                                (cvWhite), 2)
                                #logging.info(" Saved %s", filename)
                                # Save resized image
                                cv2.imwrite(filename, big_image)
                                # if required check free disk space
                                # and delete older files (jpg)
                                log_date = ("%04d%02d%02d" %
                                                (log_time.year,
                                                 log_time.month,
                                                 log_time.day))
                                log_hour = ("%02d" % log_time.hour)
                                log_minute = ("%02d" % log_time.minute)
                                m_area = track_w*track_h
                                ave_speed = round(ave_speed, 2)
                                if WEBCAM:
                                    camera = "WebCam"
                                else:
                                    camera = "PiCam"
                                if pluginEnable:
                                    plugin_name = pluginName
                                else:
                                    plugin_name = "None"
                                # create the speed data list ready for db insert
                                speed_data = (log_date, log_hour, log_minute,
                                              camera,
                                              ave_speed, speed_units, filename,
                                              image_width, image_height, image_bigger,
                                              travel_direction, plugin_name,
                                              track_x, track_y,
                                              track_w, track_h, m_area,
                                              x_left, x_right,
                                              y_upper, y_lower,
                                              max_speed_over,
                                              MIN_AREA, track_counter,
                                              cal_obj_px, cal_obj_mm)
                                payload = {"Type": "Vehicle_Speed", "MPH": ave_speed}
                                print (payload)

                                # Insert speed_data into sqlite3 database table
                                # Format and Save Data to CSV Log File
                                if log_data_to_CSV:
                                    log_csv_time = ("%s%04d%02d%02d%s,"
                                                    "%s%02d%s,%s%02d%s"
                                                    % (quote,
                                                       log_time.year,
                                                       log_time.month,
                                                       log_time.day,
                                                       quote,
                                                       quote,
                                                       log_time.hour,
                                                       quote,
                                                       quote,
                                                       log_time.minute,
                                                       quote))
                                    log_csv_text = ("%s,%.2f,%s%s%s,%s%s%s,"
                                                    "%i,%i,%i,%i,%i,%s%s%s"
                                                    % (log_csv_time,
                                                       ave_speed,
                                                       quote,
                                                       speed_units,
                                                       quote,
                                                       quote,
                                                       filename,
                                                       quote,
                                                       track_x, track_y,
                                                       track_w, track_h,
                                                       track_w * track_h,
                                                       quote,
                                                       travel_direction,
                                                       quote))
                                    log_to_csv(log_csv_text)
                                if spaceTimerHrs > 0:
                                    lastSpaceCheck = freeDiskSpaceCheck(lastSpaceCheck)
                                # Manage a maximum number of files
                                # and delete oldest if required.
                                if image_max_files > 0:
                                    deleteOldFiles(image_max_files,
                                                   speed_path,
                                                   image_prefix)
                                # Save most recent files
                                # to a recent folder if required
                                if imageRecentMax > 0 and not calibrate:
                                    saveRecent(imageRecentMax,
                                               imageRecentDir,
                                               filename,
                                               image_prefix)

                                ##logging.info("End  - Ave Speed %.1f %s Tracked %i px in %.3f sec Calib %ipx %imm",
                                             # ave_speed, speed_units,
                                             # tot_track_dist,
                                             # tot_track_time,
                                             # cal_obj_px,
                                             # cal_obj_mm)
                                # print(horz_line)
                                # Wait to avoid dual tracking same object.
                                # if track_timeout > 0:
                                    #logging.info("Sleep - %0.2f seconds to Clear Track"
                                                 # % track_timeout)
                                event_timer = time.time()
                                time.sleep(track_timeout)
                            else:
                                #logging.info("End  - Skip Photo SPEED %.1f %s"
                                             # " max_speed_over=%i  %i px in %.3f sec"
                                             # " C=%i A=%i sqpx",
                                             # ave_speed, speed_units,
                                             # max_speed_over, tot_track_dist,
                                             # tot_track_time, total_contours,
                                             # biggest_area)
                                # Optional Wait to avoid dual tracking
                                # if track_timeout > 0:
                                    #logging.info("Sleep - %0.2f seconds to Clear Track"
                                                 # % track_timeout)
                                event_timer = time.time()
                                time.sleep(track_timeout)
                            # Track Ended so Reset Variables ready for
                            # next tracking sequence
                            start_pos_x = None
                            end_pos_x = None
                            first_event = True # Reset Track
                            track_count = 0
                            event_timer = time.time()
                        else:
                            #logging.info(" Add - %i/%i xy(%i,%i) %3.2f %s"
                                         # " D=%i/%i C=%i %ix%i=%i sqpx %s",
                                         # track_count, track_counter,
                                         # track_x, track_y,
                                         # cur_ave_speed, speed_units,
                                         # abs(track_x - prev_pos_x),
                                         # x_diff_max,
                                         # total_contours,
                                         # track_w, track_h, biggest_area,
                                         # travel_direction)
                            end_pos_x = track_x
                            # valid motion found so update event_timer
                            event_timer = time.time()
                    # Movement was not within range parameters
                    else:
                        if show_out_range:
                            # movements exceeds Max px movement
                            # allowed so Ignore and do not update event_timer
                            if abs(track_x - prev_pos_x) >= x_diff_max:
                                #logging.info(" Out - %i/%i xy(%i,%i) Max D=%i>=%ipx"
                                             # " C=%i %ix%i=%i sqpx %s",
                                             # track_count, track_counter,
                                             # track_x, track_y,
                                             # abs(track_x - prev_pos_x),
                                             # x_diff_max,
                                             # total_contours,
                                             # track_w, track_h, biggest_area,
                                             # travel_direction)
                                # if track_count is over half way then do not start new track
                                if track_count > track_counter / 2:
                                    pass
                                else:
                                    first_event = True    # Too Far Away so restart Track
                            # Did not move much so update event_timer
                            # and wait for next valid movement.
                            else:
                                #logging.info(" Out - %i/%i xy(%i,%i) Min D=%i<=%ipx"
                                             # " C=%i %ix%i=%i sqpx %s",
                                             # track_count, track_counter,
                                             # track_x, track_y,
                                             # abs(track_x - end_pos_x),
                                             # x_diff_min,
                                             # total_contours,
                                             # track_w, track_h, biggest_area,
                                             # travel_direction)
                                # Restart Track if first event otherwise continue
                                if track_count == 0:
                                    first_event = True
                        event_timer = time.time()  # Reset Event Timer
                if gui_window_on:
                    # show small circle at contour xy if required
                    # otherwise a rectangle around most recent contour
                    if SHOW_CIRCLE:
                        cv2.circle(image2,
                                   (track_x + x_left * WINDOW_BIGGER,
                                    track_y + y_upper * WINDOW_BIGGER),
                                   CIRCLE_SIZE, cvGreen, LINE_THICKNESS)
                    else:
                        cv2.rectangle(image2,
                                      (int(x_left + track_x),
                                       int(y_upper + track_y)),
                                      (int(x_left + track_x + track_w),
                                       int(y_upper + track_y + track_h)),
                                      cvGreen, LINE_THICKNESS)
        if gui_window_on:
            # cv2.imshow('Difference Image',difference image)
            image2 = speed_image_add_lines(image2, cvRed)
            image_view = cv2.resize(image2, (image_width, image_height))
            cv2.imshow('Movement (q Quits)', image_view)
            if show_thresh_on:
                cv2.imshow('Threshold', thresholdimage)
            if show_crop_on:
                cv2.imshow('Crop Area', image_crop)
            # Close Window if q pressed
            if cv2.waitKey(1) & 0xFF == ord('q'):
                cv2.destroyAllWindows()
                #logging.info("End Motion Tracking ......")
                vs.stop()
                still_scanning = False
        if display_fps:   # Optionally show motion image processing loop fps
            fps_time, frame_count = get_fps(fps_time, frame_count)

#------------------------------------------------------------------------------
if __name__ == '__main__':
    show_settings()  # Show variable settings
    try:
        WEBCAM_TRIES = 0
        while True:
            # Start Web Cam stream (Note USB webcam must be plugged in)
            if WEBCAM:
                WEBCAM_TRIES += 1
                logging.info("Initializing USB Web Camera Try .. %i",
                             WEBCAM_TRIES)
                # Start video stream on a processor Thread for faster speed
                vs = WebcamVideoStream().start()
                vs.CAM_SRC = WEBCAM_SRC
                vs.CAM_WIDTH = WEBCAM_WIDTH
                vs.CAM_HEIGHT = WEBCAM_HEIGHT
                if WEBCAM_TRIES > 3:
                    logging.error("USB Web Cam Not Connecting to WEBCAM_SRC %i",
                                  WEBCAM_SRC)
                    logging.error("Check Camera is Plugged In and Working")
                    logging.error("on Specified SRC")
                    logging.error("and Not Used(busy) by Another Process.")
                    logging.error("%s %s Exiting Due to Error",
                                  progName, progVer)
                    vs.stop()
                    sys.exit(1)
                time.sleep(4.0)  # Allow WebCam to initialize
                print ("████████╗██████╗  █████╗ ███████╗███████╗██╗ ██████╗     ██████╗ █████╗ ███╗   ███╗     ██████╗ ███╗   ██╗██╗     ██╗███╗   ██╗███████╗")
                print ("╚══██╔══╝██╔══██╗██╔══██╗██╔════╝██╔════╝██║██╔════╝    ██╔════╝██╔══██╗████╗ ████║    ██╔═══██╗████╗  ██║██║     ██║████╗  ██║██╔════╝")
                print ("   ██║   ██████╔╝███████║█████╗  █████╗  ██║██║         ██║     ███████║██╔████╔██║    ██║   ██║██╔██╗ ██║██║     ██║██╔██╗ ██║█████╗  ")
                print ("   ██║   ██╔══██╗██╔══██║██╔══╝  ██╔══╝  ██║██║         ██║     ██╔══██║██║╚██╔╝██║    ██║   ██║██║╚██╗██║██║     ██║██║╚██╗██║██╔══╝  ")
                print ("   ██║   ██║  ██║██║  ██║██║     ██║     ██║╚██████╗    ╚██████╗██║  ██║██║ ╚═╝ ██║    ╚██████╔╝██║ ╚████║███████╗██║██║ ╚████║███████╗")
                print ("   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝     ╚═╝ ╚═════╝     ╚═════╝╚═╝  ╚═╝╚═╝     ╚═╝     ╚═════╝ ╚═╝  ╚═══╝╚══════╝╚═╝╚═╝  ╚═══╝╚══════╝")

            else:
                #logging.info("Initializing Pi Camera ....")
                # Start a pi-camera video stream thread
                vs = PiVideoStream().start()
                vs.camera.rotation = CAMERA_ROTATION
                vs.camera.hflip = CAMERA_HFLIP
                vs.camera.vflip = CAMERA_VFLIP
                time.sleep(2.0)  # Allow PiCamera to initialize
            speed_camera() # run main speed camera processing loop
    except KeyboardInterrupt:
        vs.stop()
        print("")
        #logging.info("User Pressed Keyboard ctrl-c")
        #logging.info("%s %s Exiting Program", progName, progVer)
        sys.exit()
