# -*- coding: utf-8 -*-
"""
Created on Wed Jul 14 23:16:51 2021

@author: Patrick
"""

import math
import cmath
import matplotlib
import numpy
import pylab as plt
import time


from PIL import Image
import scipy.ndimage as ndimage
import os
#from PP_Rainbow_LCD import PP_Rainbow_cmap

import struct
##############################################################################################################

ifn = r"P:\Data\LAPD\puff videos\21-07-10\run 6-7 f2.5 30kHz.cine"
MPEG_FN =                        r"p:\tmp\run 6-7 f2.5 30kHz.mp4"   # movie filename (also specifies what type of movie?)

ifn = r"P:\Data\LAPD\puff videos\21-07-10\run 6-7 f5.6 30kHz.cine"
MPEG_FN =                        r"p:\tmp\run 6-7 f5.6 30kHz.mp4"

ifn = r"P:\Data\LAPD\puff videos\21-07-10\run 8-9 f4 30kHz.cine"
MPEG_FN =                        r"p:\tmp\run 8-9 f4 30kHz.mp4"

ifn = r"P:\Data\LAPD\puff videos\21-07-10\run 4-5 f4 30kHz.cine"
MPEG_FN =                        r"p:\tmp\run 4-5 f4 30kHz.mp4"

ifn = r"P:\Data\LAPD\puff videos\21-07-10\run 6-7 f4 30kHz.cine"
MPEG_FN =                        r"p:\tmp\run 6-7 f4 30kHz.mp4"

ifn = r"P:\Data\LAPD\puff videos\22-01-24\2022-01-24 He puff 7.5 kA 25 ms.cine"
MPEG_FN = r"p:\tmp\22-01-24 He 2 sides puff.mp4"

ifn = r"P:\Data\LAPD\puff videos\22-01-24\2022-01-24 He Puff 7.5 kA lo-flo.cine"           # 260 MB
ifn = r"P:\Data\LAPD\puff videos\22-01-24\2022-01-24 He Puff 7.5 kA lo-flo (no.2).cine"    # 520 MB, for anode cool-down
MPEG_FN = r"p:\tmp\22-01-24 He 2 sides puff lo-flo abs.mp4"

ifn = r"P:\Data\LAPD\puff videos\gurl 22-01-28.cine"  # 205 MB
MPEG_FN = r"p:\tmp\22-01-28 rotatin (bias wrt limiters).mp4"

ifn = r"P:\Data\LAPD\cnie videos\LimBias165V_ShearExp_Jan292022.cine"
MPEG_FN = r"p:\tmp\22-01-29 rotation (bias wrt limiters).mp4"

##############################################################################################################
plt.rcParams['animation.ffmpeg_path'] = r"C:\Users\Patrick\Downloads\ffmpeg\ffmpeg-20160308-git-5061579-win64-static\bin\ffmpeg.exe"
WRITE_MPEG = True

#-----------------------------------------------------------------------
def read_L(f):
	return struct.unpack('l', f.read(4))[0]    # hoping endian is the same

def read_Q(f):
	return struct.unpack('Q', f.read(8))[0]    # unsigned 64 bit

def read_Q_array(f, n):
	a = numpy.zeros(n, dtype='Q')
	for i in range(n):
		a[i] = read_Q(f)   # unsigned 64 bit
	return a

def read_B_2Darray(f, ypix, xpix):
	n = xpix*ypix
	a = numpy.array( struct.unpack(F'{n}Q', f.read(n*1)), dtype='Q' )
	return a.reshape(ypix, xpix)

def read_H_2Darray(f, ypix, xpix):
	n = xpix*ypix
	a = numpy.array( struct.unpack(F'{n}H', f.read(n*2)), dtype='H' )
	return a.reshape(ypix, xpix)
#-----------------------------------------------------------------------


cf = open(ifn, 'rb')
t_read = time.time()
print("reading HDF file", end='')
hdr = cf.read(16)

baseline_image = read_L(cf)         # as specified in camera UI, e.g. -70
image_count = read_L(cf)

pointers = numpy.zeros(3, dtype='L')
pointers[0] = read_L(cf)
pointers[1] = read_L(cf)
pointers[2] = read_L(cf)

cf.seek(58)
nbit = read_L(cf)

cf.seek(pointers[0]+4)
xpix = read_L(cf)
ypix = read_L(cf)

cf.seek(pointers[1]+768)
pps = read_L(cf)
exposure = read_L(cf)

cf.seek(pointers[2])
pimage = read_Q_array(cf, image_count)

if nbit == 8:
	frame_arr = numpy.zeros((image_count, ypix, xpix), dtype='B')
else:
	frame_arr = numpy.zeros((image_count, ypix, xpix), dtype='H')

for i in range(image_count):
	p = struct.unpack('=l', struct.pack('=L', pimage[i] & 0xffffffffffffffff))[0]    # need integer, apparently
	cf.seek(p)
	ofs = read_L(cf)
	cf.seek(p+ofs)
	if nbit == 8:
		frame = read_B_2Darray(cf, ypix, xpix)
	else:
		frame = read_H_2Darray(cf, ypix, xpix)
	frame_arr[i,:,:] = frame

time_arr = numpy.linspace(baseline_image/pps, (baseline_image+image_count)/pps, image_count, endpoint=False)

cf.close()
print("...done (%.1f s)"%(time.time()-t_read))

fig = plt.figure(figsize=(8,8), dpi=100, facecolor='white')   # figsize in inches...
fig.canvas.manager.set_window_title('read_cine.py')
fig.set_tight_layout(True)
plt.title(MPEG_FN)

if WRITE_MPEG:
	import matplotlib.animation as mpla

	metadata = dict(title=MPEG_FN, artist='PP', comment='computed by '+__file__)

	#writer = mpla.FFMpegWriter(fps=30, metadata=metadata, extra_args=("-crf","0","-g", "30"), bitrate=1000)
	writer = mpla.FFMpegWriter(fps=30, metadata=metadata, bitrate=1000)
	           #                                           extra_args=("-crf","0","-g", "30") causes VLC to crash
               # bitrate is in kbits/sec, 1000 results in almost no visible jpeg artifacts (1 MB file); this seems to override crf
               # setting crf 0 and no bitrate give 0.6 MB file with minor artifacts;   no crf and bitrate 1000 gives 1.7 MB
               # Rather than specify a constant bitrate, it is claimed to be better to use "constant rate factor" = 0-51;
               #    0 is nominally lossless, 23 is default, 18 is marginal; this is exponential, so 6 = 2x bitrate
               # 2016-11-07:   0 may result in the default?  it certainly was not lossless
               # -g is the keyframe interval for ffmpeg, in #frames
	writer.setup(fig, MPEG_FN, dpi=fig.dpi)

baseline_image = numpy.average(frame_arr[0:7].astype('f'), axis=0)

frame = frame_arr[1].astype('f')-baseline_image
tstr = '%.2f'%(time_arr[1]*1000)
p = plt.imshow(frame, origin='lower')
txt = plt.text(5, 8, tstr, fontsize=11, color='yellow', backgroundcolor='black')

abs_clim = 0 # 8000
if abs_clim > 0:
	p.set_clim(0,abs_clim)
else:
	p.set_clim(0,numpy.max(frame))

for frame_ndx in range(0,image_count):
	tstr = '%.2f'%(time_arr[frame_ndx]*1000)
	#print(tstr, end=' ')

	frame = frame_arr[frame_ndx].astype('f')-baseline_image
	p.set_data(frame)
	if abs_clim > 0:
		p.set_clim(0,abs_clim)
	else:
		p.set_clim(0,numpy.max(frame))
	txt.set_text(tstr)

	plt.draw()
	plt.pause(0.01)

	if WRITE_MPEG:
		writer.grab_frame()

if WRITE_MPEG:
	writer.finish()

print('done')
