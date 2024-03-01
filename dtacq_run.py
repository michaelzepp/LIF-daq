# -*- coding: utf-8 -*-
"""
Created on Tue Feb 27 08:44:57 2024

@author: Michael Zepp
"""
from dtacq_control_modules import Dtacq_Control, apply_attributes
import timeit
import time
        



filesize=1 #MB
totaldata=filesize #MB
pre=5e-3 #s         max: 4 s
post=10e-3 #s      max: 49.9995 s
data_num = 6
averages = 2
trgsrc = "ext" #   "soft" or "ext"
Dtacq=Dtacq_Control(filesize, totaldata, pre=pre, post=post, data_num=data_num)


save_data="data/transient_capture{}"
shotfile="{}/SHOT".format(Dtacq.save_root)
channels=(1,2)
plot_channels=-1

for shot in range(averages):
    print('Beginning acquisition', shot+1)
    start = timeit.default_timer()
    Dtacq.Trig_setup(trgsrc = trgsrc, verbose=True)
    Dtacq.send_soft_trigger(trgsrc, verbose=True)
    Dtacq.acquire_data(save_data, channels, plot_channels=plot_channels)
    tt = timeit.default_timer() - start
    print("Total acquisition took %.3f s" % (tt))
    print()
   
if averages != 0:
    Dtacq.hdf_plot(channels, data_num, verbose=False)
    
# save_params = input('Finished taking data. Shall I save parameters? [y/n] ')
# if save_params == 'y' or save_params == 'Y':
    
#     parDict = {'B [G]': 500,
#                 'P_rf [kW]': 2,
#                 'Neutral Pressure [Pa]': 3,
#                 'Radial Position [mm]': 0,
#                 'Axial Position [cm]': 15,
#                 'LIA Sensitivity': '1 mV',
#                 'LIA Time Constant': '1 ms',
#                 'LIA Dynamic Reserve': '54 dB',
#                 'LIA Phase [deg]': 135,
#                 'Laser On?': 'Yes',
#                 'Modulation Frequency [kHz]': 84.7,
#                 'PMT Optical Density': 1.5,
#                 'PMT Bandwidth': '250 kHz',
#                 'PMT Gain': 1,
#                 'Pulse Length [ms]': 100,
#                 'Trigger Position in Pulse': '0 ms',
#                 'Other Pulse Parameters': 'None',
#                 'QWP Angle': 0,
#                 'Species': 'Ar II',
#                 'Description': 'Ar II LIF'
#                 }

#     apply_attributes(Dtacq.filename, data_num, parDict, nchan=len(channels))
# else:
#     print("WARNING: Parameters not saved to .h5 file. Consider updating 'parDict', setting 'averages = 0', and running again")
    
# time.sleep(3)
# Dtacq.close()
    