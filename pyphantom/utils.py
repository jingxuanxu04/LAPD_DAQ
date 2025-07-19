
#*****************************************************************************/
#                                                                   
#  Copyright (C) 1992-2023 Vision Research Inc. All Rights Reserved.
#                                                                   
#  The licensed information contained herein is the property of     
#  Vision Research Inc., Wayne, NJ, USA  and is subject to change   
#  without notice.                                                  
#                                                                   
#  No part of this information may be reproduced, modified or       
#  transmitted in any form or by any means, electronic or           
#  mechanical, for any purpose, without the express written         
#  permission of Vision Research Inc.                               
#                                        
#   Version                            
#          August 25, 2023
#          September 7, 2023
#           Added defines
#               1 - FAST_ALGORITHM
#               4 - BEST_ALGORITHM
#               6 - NO_DEMOSAICING
#
#*****************************************************************************/

from pyphantom.phantom import phGetPh, phDoPh, phSetPh
from pyphantom.phantom import phGetCam, phDoCam, phSetCam 
from pyphantom.phantom import phGetCine, phDoCine, phSetCine

from collections import namedtuple
from enum import *

_phantom_keys = None

#
# ---------- DATA TYPES ------------
#

#region
class SyncModeEnum(IntEnum):
    INTERNAL = 0
    EXTERNAL = 1
    LOCK_TO_IRIG = 2
    LOCK_TO_VIDEO = 3
    SYNC_TO_TRIGGER = 5

class SensorTypeEnum(IntEnum):
    MONO = 0
    COLOR = 1

class FileTypeEnum(Enum):
    SVV_RAWCINE = 0
    SVV_CINE =  1
    SVV_AVI = 3
    SVV_TIFCINE = 4
    SVV_QTIME = 8
#    SVV_MP4 = 9    Not working
    SVI_TIF8 = -8
    SVI_TIF12 = -9
    SVI_TIF16 = -10
    SVI_RAW = -25
    SVI_DNG = -26
    SVI_DPX = -27

class PartitionStateEnum(Enum):
    READY = 0
    RECORDING = 1
    STORED = 2


#
# PhSet/PhGet Selectors
#
class CamSelector(IntEnum):
    gsModel = 1069                      #(RO) (char[MAXSTDSTRSZ]) Camera model
    gsUvSensor = 1089                   #(RO) (BOOL) UV Sensor
    gsIPAddress = 1070                  #(RO) (char[MAXIPSTRSZ]) Camera current Ethernet address
    gsVideoPlayCine = 1033              #(RO) (INT)  Cine number currently played on video out
    gsVideoPlaySpeed = 1034             #(RO) (INT)  Video out play speed in mHz.
    gsVideoOutputConfig = 1035          #(RW) (INT)  Video output type. Possible values are:
                                        #   0 – Single-feed mode
                                        #   1 – Single-feed mode with dual-link 444
                                        #   2 – Dual-feed mode
                                        #   3 – Dual-feed mode with 444

    gsSensorTemperature = 1028          #(RO) (INT)  Sensor temperature
    gsCameraTemperature = 1029          #(RO) (INT)  Camera temperature
    gsLensFocus = 1059                  #(WO) (INT)  Move the focus ring by the given number of incremental units relative to current focus position.
    gsLensAperture = 1060               #(RW) (double) fstop value
    gsLensDescription = 1062            #(RO) (char[MAXSTDSTRSZ]) Lens description
    gsLensFocusInProgress = 1063        #(RO) (BOOL) Focus in progress
    gsLensFocusAtLimit = 1064           #(RO) (BOOL) Focus adjustment has hit a mechanical limit
    gsSupportsInternalBlackRef = 1026   #(RO) (BOOL) Tells if the camera knows to perform a black calibration
    gsSupportsImageTrig = 1040          #(RO) (BOOL) Image based auto trigger capability
    gsSupportsCardFlash = 1050          #(RO) (BOOL) Tells if the camera supports a compact flash
    gsSupportsMagazine = 8193           #(RO) (BOOL) Tells if the camera supports a CineMag
    gsSupportsHQMode = 8194             #(RO) (BOOL) Tells if HQ mode is supported
    gsSupportsGenlock = 8195            #(RO) (BOOL) Tells if video genlock is supported
    gsSupportsEDR = 8196                #(RO) (BOOL) Tells if EDR is supported
    gsSupportsAutoExposure = 8197       #(RO) (BOOL) Tells if auto-exposure is supported-
    gsHasV2AutoExposure = 2001          #(RO) (BOOL) Tells if auto-exposure is V1 or V2 type
    gsHasV2LockAtTrigger = 2002         #(RO) (BOOL) Tells if auto exposure supports Lock At Trigger
    gsSupportsTurbo = 8198              #(RO) (BOOL) Tells if turbo mode is supported
    gsSupportsBurstMode = 8199          #(RO) (BOOL) Tells if burst mode is supported
    gsSupportsShutterOff = 8200         #(RO) (BOOL) Tells if shutter off mode is supported
    gsSupportsDualSDIOutput = 8201      #(RO) (BOOL) Tells if dual SDI output is present
    gsSupportsRecordingCines = 8202     #(RO) (BOOL) Tells if this device can record cines.
    gsSupportsV444 = 8203               #(RO) (BOOL) Tells if HD-SDI 4:4:4 output is available
    gsSupportsInterlacedSensor = 8204   #(RO) (BOOL) Tells if sensor has interlaced channels.
    gsSupportsRampFRP = 8205            #(RO) (BOOL) Tells if camera supports frame rate profile using the ramp camera field.
    gsSupportsOffGainCorrections = 8206 #(RO) (BOOL) Tells if camera implements offset gain corrections internally.
    gsSupportsQuietMode = 8214          #(RO) (BOOL) Tells if camera supports quiet mode (i.e. turning off the fan)
    gsMaxPartitionCount = 1071          #(RO) (UINT) Maximum partition count.
    gsSupportsProgIO = 8221             #(RO) (BOOL) Tells if camera supports programmable I/O
    gsSupportsSensorModes = 8223        #(RO) (BOOL) Tells if camera supports sensor modes
    gsSupportsBattery = 8224            #(RO) (BOOL) Tells if the camera supports a internal battery
    gsSupportsExpIndex = 8225           #(RO) (BOOL) Tells if the camera supports exposure index
    gsSupportsPIV = 8232                #(RO) (BOOL) Tells if the camera supports PIV
    gsHasMechanicalShutter = 1025       #(RO) (BOOL) Mechanical shutter present or not
    gsHasBlackLevel4 = 1027             #(RO) (BOOL) Tells if the camera uses a non-zero value for black level.
    gsHasCardFlash = 1051               #(RO) (BOOL) Tells if the camera has a card flash inserted and mounted
    gsHas10G = 2000                     #(RO) (BOOL) Tells if the camera has a 10G connection up and running
    gsMechanicalShutter = 1036          #(RW) (INT)  Shutter control: on or off
    gsImageTrigThreshold = 1041         #(RW) (INT)  Amount a pixel value must change in order to be counted as an active pixel for auto trigger purposes
    gsImageTrigMode = 1044              #(RW) (INT)  Auto trigger mode:
                                        #   0 – auto trigger disabled
                                        #
                                        #   1 – the camera will both drive the autotrigger and trigger itself
                                        #       when an autotrigger condition is detected. If the autotrigger 
                                        #       signal is pulled low by an external device, the camera will be triggered.
                                        #
                                        #   2 – the image changes are analyzed, and when an auto trigger condition 
                                        #       is detected, the autotrigger signal is pulled low, as in mode 1, 
                                        #       but the camera will not trigger itself. An external device pulling low the
                                        #       autotrigger signal will not trigger the camera either
   
    gsAutoProgress = 1046               #(RW) (INT)  Number of frames still to do by the camera auto process.
    gsAutoBlackRef = 1047               #(RW) (INT)  Auto black reference enabled or not (performing a CSR before each new recording)
    gsCardFlashError = 1054             #(RO) (INT)  Last compact flash error
    gsGenlock = 1065                    #(RW) (INT)  Video genlock
    gsGenlockStatus = 1066              #(RO) (char[MAXIPSTRSZ]) Genlock status
    gsTurboMode = 1068                  #(RW) (INT)  Turbo mode support
    gsQuiet = 1074                      #(RW) (INT)  Camera fan: on or off
    gsClockPeriod = 1079                #(RO) (double) Obtain the camera clock period as a double value (seconds)
    gsPortCount = 1080                  #(RO) (UINT) How many ports (fixed & programmable) are available on this camera (0 =indicates none)
    gsTriggerEdgeAndVoltage = 1081      #(RW) (UINT) "bit 0 rising edge, bit 1 high voltage (6v threshold instead of 1.5v)"
                                        #
                                        #   Bit 0 Value,	Meaning
                                        #       0	Trigger on falling edge
                                        #       1	Trigger on rising edge
	                                    #
                                        #   Bit 1 Value,	Meaning
                                        #       0	Use 1.5 Voltage threshold
                                        #       1	Use high Voltage threshold
                                        #           (6v threshold instead of 1.5v)

    gsTriggerFilter = 1082              #(RW) (double) Filter constant (seconds)
    gsTriggerDelay = 1083               #(RW) (double) Trigger delay in seconds available at camera. Only valid for cameras with programmable I/O capability
    gsSensorModesList = 1087            #(RO) (char[MAXIPSTRSZ]) Get list of camera Sensor modes
    gsSensorMode = 1088                 #(RW) (UINT) Get/Set Sensor Mode
    gsBatteryEnable = 1100              #(RW) (BOOL) Enable/Disable battery operation
    gsBatteryCaptureEnable = 1101       #(RW) (BOOL) Enable/Disable battery operation during capture
    gsBatteryPreviewEnable = 1102       #(RW) (BOOL) Enable/Disable battery operation during preview
    gsBatteryWtrRuntime = 1103          #(RW) (UINT) Time in seconds the camera will run on battery in WTR if a cine is not triggered.
    gsBatteryVoltage = 1104             #(RW) (double) Battery voltage level
    gsBatteryState = 1105               #(RO) (UINT) Battery control status
                                        #   Value	Meaning
                                        #     0     battery not present
                                        #     1     battery charging
                                        #     2     battery charging, voltage above 1/2 capacity threshold;
                                        #     3     battery charged;
                                        #     4     battery discharging;
                                        #     5     battery low;
                                        #    16     battery charging fault.
                                        #   When the battery is armed, bit 3 is set (8 is added to the values above).

    gsBatteryArmDelay = 1107            #(RW) (UINT) "Delay, in seconds, from the moment the camera is placed into WTR and the time the battery is armed."
    gsBatteryPrevRuntime = 1108         #(RW) (UINT) Time in seconds the camera will run on battery in preview if a cine is not triggered.
    gsBatteryPwrOffDelay = 1109         #(RW) (UINT) Time in seconds the battery still supplies power to the camera after it has been disarmed.
    gsBatteryReadyGate = 1110           #(RW) (BOOL) Set/Get Battery readygate control
    gsExpIndex = 1090                   #(RO) (UINT) Set/Get exposure index ISO value
    gsExpIndexPresets = 1091            #(RW) (UINT) Get list of camera ISO values
    gsEthernetDefaultAddress = 1096     #(RO) (char[MAXIPSTRSZ]) Primary/Default IP address
    gsEthernetMask = 1056               #(RO) (char[MAXIPSTRSZ]) Network mask
    gsEthernetBroadcast = 1057          #(RO) (char[MAXIPSTRSZ]) Broadcast mask
    gsEthernetGateway = 1058            #(RO) (char[MAXIPSTRSZ]) IP address of default gateway
    gsEthernet10GAddress = 1093         #(RO) (char[MAXIPSTRSZ]) 10G IP address
    gsEthernet10GMask = 1094            #(RO) (char[MAXIPSTRSZ]) 10G Network mask
    gsEthernet10GBroadcast = 1095       #(RO) (char[MAXIPSTRSZ]) 10G Broadcast mask

#
# PhSetCineInfo/PhGetCineInfo Selectors
#
class CineSelector(IntEnum):
    GCI_ISFILECINE = 12                 #(RO) (BOOL) TRUE if this is a file cine.
    GCI_FROMFILETYPE = 20               #(RO) (INT) File type (see Supported File Formats).
    GCI_COMPRESSION = 21                #(RO) (UINT) Compression type. Possible values are:
                                        #   0 – Gray cine
                                        #   1 – JPEG compressed cine (*.cci)
                                        #   2 – Uninterpolated cine (RAW)

    GCI_IMAGECOUNT = 29                 #(RO) (UINT) Saved image count.
    GCI_TOTALIMAGECOUNT = 30            #(RO) (UINT) Total recorded image count.
    GCI_FIRSTIMAGENO = 38               #(RO) (INT) First image number for the selected/saved range.
    GCI_FIRSTMOVIEIMAGE = 39            #(RO) (INT) First recorded image number.
    GCI_MAXIMGSIZE = 400                #(RO) (UINT) Maximum size in bytes required for reading and processing one image of this cine.
    GCI_CINEDESCRIPTION = 603           #(RO) (UINT) Cine description,,char[4096]
    GCI_CAMERAVERSION = 22              #(RO) (UINT) An integer describing camera version.
    GCI_CAMERASERIAL = 5                #(RO) (UINT) The serial of the camera that acquired the cine.
    GCI_FRAMERATE = 1                   #(RO) (UINT) Cine frame rate as an UINT.
    GCI_DFRAMERATE = 480                #(RO) (double) Cine frame rate as a double
    GCI_EXPOSURENS = 16                 #(RO) (UINT) Image exposure in nanoseconds.
    GCI_CFA = 0                         #(RO) (UINT) CFA of the camera this cine was recorded on.
    GCI_UVSENSOR = 54                   #(RO) (BOOL) Sensor supports UV light
    GCI_SENSORMODE = 52                 #(RO) (UINT) Sensor configuration
    GCI_IMWIDTH = 24                    #(RO) (UINT) Current image width.
    GCI_IMHEIGHT = 25                   #(RO) (UINT) Current image height.
    GCI_IMWIDTHACQ = 26                 #(RO) (UINT) Image width at acquisition time.
    GCI_IMHEIGHTACQ = 27                #(RO) (UINT) Image height at acquisition time.
    GCI_LENSDESCRIPTION = 110           #(RO) (char[MAXSTDSTRSZ]) "Null terminated string containing various lens information such as producer, model or focal range."
    GCI_LENSAPERTURE = 111              #(RO) (FLOAT) Aperture f number.
    GCI_LENSFOCALLENGTH = 112           #(RO) (FLOAT) Lens focal length (zoom factor).
    GCI_RECORDINGTIMEZONE = 37          #(RO) (INT) The time zone active during the recording of the cine.
    GCI_PBRATE = 472                    #(RW) (FLOAT) Video playback rate (fps) active when the cine was captured.
    GCI_TCRATE = 473                    #(RW) (FLOAT) Playback rate (fps) used for generating SMPTE time code.
    GCI_TRIGTIMESEC = 10                #(RO) (UINT) The seconds of the trigger time.
    GCI_TRIGTIMEFR = 11                 #(RO) (UINT) The fractions of the trigger time.
    GCI_POSTTRIGGER = 28                #(RO) (UINT) Post-trigger frames.
    GCI_TRIGFRAME = 31                  #(RO) (UINT) Information about sync image mode:
                                        #   0 – internal
                                        #   1 – external
                                        #   2 – locktoIrig.
   
    GCI_FRAMEDELAYNS = 19               #(RO) (UINT) Frame delay in nanoseconds.
    GCI_EDREXPOSURENS = 17              #(RO) (UINT) EDR exposure in nanoseconds.
    GCI_AUTOEXPOSURE = 3                #(RO) (UINT) Cine auto-exposure.
    GCI_AUTOEXPLEVEL = 32               #(RO) (UINT) Level for autoexposure control.    
    GCI_RECBPP = 48                     #(RO) (UINT) Recording bit depth for the cine
    GCI_REALBPP = 4                     #(RO) (UINT) Pixel color depth for the cine.
    GCI_IS16BPPCINE = 13                #(RO) (BOOL) TRUE if this is a 16 bpp cine.
    GCI_ISCOLORCINE = 14                #(RO) (BOOL) TRUE if this is a color cine.
    GCI_WBISMETA = 230                  #(RO) (BOOL) "If TRUE, white balance gains are stored as metadata."
    GCI_BRIGHT = 202                    #(RW) (FLOAT) Image offset.
    GCI_CONTRAST = 203                  #(RW) (FLOAT) Gain image processing.
    GCI_GAMMA = 204                     #(RW) (FLOAT) Per-component gamma
    GCI_GAMMAR = 223                    #(RW) (FLOAT) Difference between red channel gamma and overall gamma
    GCI_GAMMAB = 224                    #(RW) (FLOAT) Difference between blue channel gamma and overall gamma.
    GCI_SATURATION = 205                #(RW) (FLOAT) Saturation
    GCI_HUE = 206                       #(RW) (FLOAT) Degrees and fractions of degree to rotate the color hue of every image pixel.
    GCI_FLIPH = 207                     #(RW) (BOOL) Flip the image horizontally.
    GCI_FLIPV = 208                     #(RW) (BOOL) Flip the image vertically.
    GCI_ROTATE = 23                     #(RW) (INT) Rotate information:
                                        #     0	No rotation
                                        #   +90	Counterclockwise
                                        #   -90	Clockwise
    
    GCI_FILTERCODE = 209                #(RW) (INT) Image filter code.
    GCI_IMFILTER = 210                  #(RW) (UINT) User defined convolution filter.,,IMFILTER
    GCI_INTALGO = 211                   #(RW) (UINT) Demosaicing algorithm selector. 
                                        # Phantom SDK offers the following options (see PhInt.h):
                                        #   1 - FAST_ALGORITHM
                                        #   4 - BEST_ALGORITHM
                                        #   6 - NO_DEMOSAICING

    GCI_DEMOSAICINGFUNCPTR = 222        #(RW) (UINT) Pointer to current demosaicing responsible function.,,DEMOSAICINGFUNCPTR
    GCI_TONE = 227                      #(RW) (UINT) Tone description.,,TONEDESC
    GCI_RESAMPLEACTIVE = 215            #(RW) (BOOL) "If TRUE, resampling is active."
    GCI_RESAMPLEWIDTH = 216             #(RW) (UINT) Desired resample width.
    GCI_RESAMPLEHEIGHT = 217            #(RW) (UINT) Desired resample height.
    GCI_CROPACTIVE = 218                #(RW) (BOOL) "If TRUE, crop is active."
    GCI_CROPRECTANGLE = 219             #(RW) (UINT) Rectangle to crop from the input image.,,RECT
    GCI_GAIN16_8 = 221                  #(RW) (FLOAT) Sensitivity value used when converting cine images to 8 bits per sample:
    GCI_PEDESTALR = 212                 #(RW) (FLOAT) Red channel offset to be applied after gamma.
    GCI_PEDESTALG = 213                 #(RW) (FLOAT) Green channel offset to be applied after gamma.
    GCI_PEDESTALB = 214                 #(RW) (FLOAT) Blue channel offset to be applied after gamma.
    GCI_ENABLEMATRICES = 228            #(RW) (BOOL) TRUE if the user matrix is currently active.
    GCI_USERMATRIX = 229                #(RW) (UINT) User color matrix description.,,CMDESC
    GCI_FLARE = 225                     #(RW) (FLOAT) Offset to be applied before white balance.
    GCI_CHROMA = 226                    #(RW) (FLOAT) Chrominance adjustment applied after gamma.
    GCI_VFLIPVIEWACTIVE = 300           #(RW) (BOOL) "For UC_VIEW use cases, cine images are vertically flipped if this parameter is TRUE."
    GCI_UNCALIBRATEDIMAGE = 600         #(RW) (BOOL) "If TRUE, no calibration correction is applied for this cine images. Camera calibration or CSR results will thus be ignored. Bad pixel correction will also be disabled."
    GCI_NOPROCESSING = 601              #(RW) (BOOL) "If TRUE, no image processing is applied for this cine images except for calibration corrections and bad pixel repairing."
    GCI_BADPIXELREPAIR = 602            #(RW) (BOOL) "If TRUE, bad pixel correction is enabled."
    GCI_SAVERANGE = 500                 #(RW) (UINT) Image range to be saved.,,IMRANGE
    GCI_SAVEFILENAME = 501              #(RW) (char[MAX_PATH]) Destination file name.
    GCI_SAVEFILETYPE = 502              #(RW) (INT) Destination file type. See Supported File Formats for possible values.
    GCI_SAVE16BIT = 503                 #(RW) (BOOL) "If TRUE, save on 16 bits when more than 8 bits are available."
    GCI_SAVEPACKED = 504                #(RW) (UINT) "If >0 and if source cine is packed, destination format is also packed."
                                        #   0 – Not Packed
                                        #   1 – Packed 10
                                        #   2 – Packed 12L
    
    GCI_SAVEXML = 505                   #(RW) (BOOL) "If TRUE, an XML file will be created containing destination cine header."
    GCI_SAVESTAMPTIME = 506             #(RW) (INT) Image time stamp options. Possible values are:
                                        #   0 – no time stamp
                                        #   1 – stamp the absolute time
                                        #   3 – stamp the time from trigger

    GCI_SAVEDECIMATION = 1035           #(RW) (FLOAT) Decimation value for image save. Value must be an integer value
    GCI_SAVEAVIFRAMERATE = 520          #(RW) (UINT) Preferred avi playback frame rate
    GCI_SAVEAVICOMPRESSORINDEX = 522    #(RW) (UINT) Preferred avi compressor index.
    GCI_SAVEDPXLSB = 530                #(RW) (BOOL) "If TRUE, preferred DPX byte order is least significant byte first (little endian). Otherwise, big endian byte order is used."
    GCI_SAVEDPXTO10BPS = 531            #(RW) (BOOL) "If TRUE, images are converted to 10 bits per sample."
    GCI_SAVEDPXDATAPACKING = 532        #(RW) (UINT) Preferred DPX data packing. Possible values are:
                                        #   0 – Filled to 32-bit method A
                                        #   1 – Filled to 32-bit method B
                                        #   2 – Packed into 32-bit words
  
    GCI_SAVEDPX10BITLOG = 533           #(RW) (BOOL) "If TRUE, images are converted to 10bit log format."
    GCI_SAVEDPXEXPORTLOGLUT = 534       #(RO) (UINT) "If TRUE, look-up tables for linear to log and log to linear are saved in separate files.",,
    GCI_SAVEDPX10BITLOGREFWHITE = 535   #(RW) (UINT) White reference for 10bit log format.
    GCI_SAVEDPX10BITLOGREFBLACK = 536   #(RW) (UINT) Black reference for 10bit log format.
    GCI_SAVEDPX10BITLOGGAMMA = 537      #(RW) (FLOAT) Gamma for 10bit log format.
    GCI_SAVEDPX10BITLOGFILMGAMMA = 538  #(RW) (FLOAT) Film gamma for 10bit log format.
    GCI_SAVEQTPLAYBACKRATE = 550        #(RW) (UINT) Preferred playback frame rate for MOV QuickTime files.
    GCI_SAVECCIQUALITY = 560            #(RW) (UINT) CCI preferred quality in percents.
    GCI_CINENAME = 40                   #(RW) (char[MAXSTDSTRSZ]) Cine name.
    GCI_WRITEERR = 109                  #(RO) (INT) Last error encountered during a save operation from this cine.
    GCI_TIMEFORMAT = 41                 #(RO) (UINT) Preferred time format for this cine.
                                        #   TF_LT    – Local Time
                                        #   TF_UT    – Universal Time
                                        #   TF_SMPTE – SMPTE TimeCode


#
# namedTuples
#
WhiteBalance = namedtuple('WhiteBalance', 'red_gain, blue_gain')
FrameRange = namedtuple('FrameRange', 'first_image, last_image')
Resolution = namedtuple('Resolution', 'x, y')
LensApertureRange = namedtuple('LensApertureRange', 'min, max')
PulseProcParam = namedtuple('PulseProcParam', 'port, invert, falling, delay, width, filter')
PioSignal  = namedtuple('PioSignal', 'port, signal')
SetSelector  = namedtuple('SetSelector', 'selector, value')
CameraDiscoverInfo = namedtuple('CameraDiscoverInfo', 'name, serial, model, camera_number')
BlackWhiteLevels = namedtuple('BlackWhiteLevels', 'black_level, white_level')
MMI = namedtuple('MMI', 'max, min, inc')
AutoTrig = namedtuple('AutoTrig', 'r1, r2, r3, r4, active_px_pct, trig_speed, trig_threshold')
MeasureWhiteBalance = namedtuple('MeasureWhiteBalance', 'x, y, frame_count')

# TODO add autoexposure types once added into pyd
#endregion

def _generate_phantom_keys():
    _phantom_dict = dict((('_' + str(k)), v) for k, v in phGetPh() .items())
    global _phantom_keys
    _phantom_keys = _PhantomKeys(_phantom_dict)

class _PhantomKeys(object):
    def __init__(self, my_dict):    
        # Turns a dictionary into a class      
        for key in my_dict:
            setattr(self, key, my_dict[key])

        
