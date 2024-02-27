"""
Created on Mon Feb 12 13:16:24 2024

@author: Michael Zepp
LIF data acquisition using D-tAcq unit over network
Based on acq400_hapi
"""

import acq400_hapi
import numpy as np
import os
from os import path
import time
import socket
import matplotlib.pyplot as plt
import errno
import timeit
import h5py
from datetime import datetime


def increment_shot(save_data):
    save_root = os.path.dirname(save_data)        # ignore shot formatter

    if save_root != '':
        try:
            os.makedirs(save_root)
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise
    else:
        save_root = '.'
    
    shotfile = "{}/SHOT".format(save_root)
    if os.path.exists(shotfile):
        with open(shotfile) as sf:
            for line in sf:
                shot = int(line)
    else:
        shot = 0
        with open(shotfile, "a") as sf:
            sf.write("{}\n".format(shot))
    with open(shotfile) as sf:
        for line in sf:
            shot = int(line)
    shot += 1

    with open(shotfile, "a") as sf:
            sf.write("{}\n".format(shot))
    return shotfile


class Dtacq_Control():
    def __init__(self,filesize=0,totaldata=0,pre=5e-3,post=100e-3, data_num=0):
        self.collect_pre=True #collect data before trigger
        self.save_ind=False #saves data from individual shots in separate files
        self.save_data="data\\transient_capture{}" #where to save individual shot files
        self.hdf_root="data\\acq1001_420_hdf" #where to save hdf files
        self.root="" #where to save streamed data
        
        self.directory=""    
        self.ip = '10.128.18.162'
        self.uut = acq400_hapi.Acq400(self.ip)
        self.RXBUF_LEN = 4096*64
        self.runtime=120 #s, How long to stream data for
        self.filesize=filesize*200000
        self.totaldata=totaldata*0x100000
        self.pre = int(2e6*pre)
        self.post = int(2e6*post)
        if self.collect_pre:
            self.total = self.pre + self.post
        else:
            self.total = self.post
        self.save_root = os.path.dirname(self.save_data)
        self.trace=0 #print timing of various processes
        
        self.callback=None #for client program use only. Assume object with __call_ method
        self.data_num=str(data_num)
        
        self.hdfname = datetime.today().strftime('%y%m%d') + ".h5"
        self.filename = path.join(self.hdf_root,self.hdfname)
        
        self.ips = [self.ip,"erb605-dtacq.ep.wisc.edu"]
        
    def __exit__(self):
        self.uut.close()
        
    
    def make_data_dir(self, verbose=True):
        
        try:
            os.makedirs(self.directory)
        except Exception:
            if verbose:
                print("Directory already exists")
            pass
    

    
    
    def run_stream(self,verbose=True):
        cycle = 1
        root = self.root + self.ip + "/" + "{:06d}".format(cycle)
        data = bytes()
        num = 0
    
    
        skt = socket.socket()
        skt.connect((self.ip, 4210))
        self.make_data_dir()
        start_time = time.time()
        # upload_time = time.time()
        data_length = 0
        connected=0
        if self.filesize > self.totaldata:
            self.filesize = self.totaldata
        bytestogo = self.filesize
    
        while time.time() < (start_time + self.runtime) and data_length < self.totaldata:
            rxbuf = self.RXBUF_LEN if bytestogo > self.RXBUF_LEN else bytestogo
            # loop_time = time.process_time()
            data += skt.recv(rxbuf)
            if connected==0:
                print('Connected to server.')
                connected+=1
            bytestogo = self.filesize - len(data)
            
            if len(data) >= self.filesize:
                data_length += len(data)
                if num > 99:
                    num = 0
                    cycle += 1
                    root = self.root + self.ip + "/" + "{:06d}".format(cycle)
                    self.make_data_dir()
    
                data_file = open("{}/{:04d}".format(root, num), "wb")
                data = np.frombuffer(data, dtype="<i2")
                data = np.asarray(data).reshape((-1, 16))
                data.tofile(data_file, '')
                plt.plot(data[:,0])
                
                if verbose:
                    print("New data file written.")
                    print("Data Transferred: ", data_length/1000000, "MB")
                    print("Streaming time remaining: ", -1*(time.time() - (start_time + self.runtime)))
                    print("")
                    print("")
    
                num += 1
                data_file.close()
                data = bytes()  # Remove data from variable once it has been written
                # upload_time = time.time()  # Reset upload time
                data_written_flag = 1
    
                if self.callback is not None and self.callback():
                    print("Callback says \"enough\"")
                    break
        
        try:
            data_written_flag
        except NameError:
            data_file = open("{}/{:04d}".format(root, num), "wb")
            data = np.frombuffer(data, dtype="<i2")
            data = np.asarray(data)
            data.tofile(data_file, '')
            print("runtime exceeded: all stream data written to single file")
    
    def Trig_setup(self, verbose=False):
        # Dtacq=Dtacq_Control()
        # acq400_hapi.Acq400UI.add_args(transient=True)
        # if hasattr(self.uut.s0, 'TIM_CTRL_LOCK'):
        #     print("LOCKDOWN {}".format(self.uut))
        #     self.uut.s0.TIM_CTRL_LOCK = 0
        # print("Default transient capture configured")
        if self.collect_pre:
            self.uut.configure_pre_post(role="master",trigger=[1,1,1],pre=self.pre, post=self.post)
        else:
            self.uut.configure_post(role="master",trigger=[1,1,1], post=self.post)

        self.uut.s0.set_arm = 1
        if verbose:
            print('Trigger armed: awaiting trigger')
        
 
            
    def send_soft_trigger(self, verbose=False):
        if verbose:
            print("waiting until armed")
        time.sleep(2) #trigger only works after delay
        self.uut.statmon.wait_armed
        self.uut.s0.soft_trigger = 1
        if verbose:
            print('soft trigger sent')
        
        
        
    ####################functions for saving and plotting data########################
        
    
    def read_chan(self, chan, nsam = 0, data_size = 2, save_individual=False):
        if chan != 0 and nsam == 0:
            if self.collect_pre:
                nsam = self.pre+self.post
            else:
                nsam = self.post
                
        cc = acq400_hapi.ChannelClient(self.ip, chan)
        ccraw = cc.read(nsam, data_size=data_size, maxbuf=8000000)

        if self.uut.save_data and save_individual:
            try:
                os.makedirs(self.uut.save_data)
            except OSError as exception:
                if exception.errno != errno.EEXIST:
                    raise

            # with open("%s/%s_CH%02d" % (self.uut.save_data, self.ip, chan), 'wb') as fid:
            #     ccraw.tofile(fid, '')
        if self.uut.save_data:   
            try:
                os.makedirs(self.hdf_root)
            except OSError as exception:
                if exception.errno != errno.EEXIST:
                    raise        

        return ccraw
    
    
    def collect_data(self, channels=(), nsam=0):
        # if channels == ():
        #     channels = list(range(1, self.uut.nchan()+1))
            

        chx = []
        data_size = 2
        

        for ch in channels:
            if self.trace:
                print("%s CH%02d start.." % (self.ip, ch))
                start = timeit.default_timer()

            chx.append(self.read_chan(ch, nsam, data_size=data_size))

            if self.trace:
                tt = timeit.default_timer() - start
                print("%s CH%02d complete.. %.3f s %.2f MB/s" %
                    (self.ip, ch, tt, len(chx[-1])*2/1000000/tt))
        t_scale=chx[0].shape[0]/2000
        self.t = np.linspace(0, t_scale, chx[0].shape[0])
        return chx
    
    
    
    def live_plotter(self, plot_channels, chx, nchan, nsam, one_plot, verbose=False):
        try:
            import matplotlib.pyplot as plt
        except Exception as e:
            plt = e

        if isinstance(plt, Exception):
            print("Sorry, plotting not available")
            return        
            
        if plot_channels == 0 or plot_channels > nchan:
            plot_channels = nchan
        
        if plot_channels < 0:
            _nchan = -plot_channels
            if _nchan < nchan:                    
                nchan = _nchan
                # overlay_plot = True
                # print("overlay plotting first {} channels".format(nchan))
        else:
            _nchan = plot_channels
            if _nchan < nchan:                    
                nchan = _nchan
                # print("plotting first {} channels".format(nchan))
                       
        # ax = {}
        # ax0 = None
       
                           
        for chn in range(0, nchan):
            _data = self.uut.chan2volts(self.cmap[0][chn], chx[0][chn]) 
            if not one_plot:
                # axkey = '{}'.format(chn)    
                fignum = 1 + chn
                if verbose:
                    print("calling plt.subplot({}, {}, {})".format(nchan, 1, fignum))
                # if not ax0:                           
                #     ax[axkey] = plt.subplot(nchan, 1, fignum)                        
                #     ax0 = ax[axkey]
                # else:
                #     ax[axkey] = plt.subplot(nchan, 1, fignum, sharex=ax0) 
            _label = "{}.{:03d}".format(self.uut, self.cmap[0][chn])

            if plot_channels < 0:      
                plt.suptitle('{} shot {}'.format(self.uut, self.uut.s1.shot))
                plt.xlabel("Time [ms]")
                plt.ylabel("Volts")  
                # print("ax[{}].plot( ... label={})".format(axkey, _label))  
                plt.plot(self.t,_data, label=_label)
                if self.collect_pre:
                    plt.axvline(x=self.pre/2000, label="trigger", color="k")
                # line = ax[axkey].plot(_data, label=_label)                            
                # ax[axkey].legend()
                # plt.legend()
                plt.tight_layout()
                plt.show()
            else:
                plt.suptitle('{} shot {}'.format(self.uut, self.uut.s1.shot))
                plt.xlabel("Time [ms]")
                plt.ylabel("counts")                           
                plt.plot(self.t,chx[0][chn])
                plt.show()

        
        
        


    def map_channels(self, channels):
        cmap = {}
        #print("map_channels {}".format(channels))
        ii = 0

        if channels == ():
            cmap[0] = list(range(1, self.uut.nchan()+1))  # default : ALL
        elif type(channels[0]) != tuple:
            cmap[0] = channels                  # same tuple all UUTS
        else:
            try:
                cmap[0] = channels[ii]          # dedicated tuple
            except:
                cmap[0] = 1                     # fallback, ch1

        return cmap
    
    
    def acquire_data(self, save_data, channels, one_plot=False, plot_channels=0, verbose=False):
        
        self.cmap = self.map_channels(channels)
        if verbose:
            print("INFO: Shotcontroller.handle_data() {} data valid: {}".format(
                self.ip, self.uut.statmon.data_valid))
        if save_data:
            shotfile = increment_shot(save_data)
            with open(shotfile) as sf:
                last_line = sf.readlines()[-1]
            shotdir = save_data.format(last_line[:-1])
            self.uut.save_data = shotdir
        # if trace_upload:
        #     self.uut.trace = 1


        if verbose:
            print("reading data")
        chx = [self.collect_data(self.cmap[0])]
        nchan, nsam = len(chx[0]), len(chx[0][0])
        
        if plot_channels != 0:
            self.live_plotter(plot_channels, chx, nchan, nsam, one_plot) 
            
                    
        self.data_saving(nchan, chx) 
        
    def data_saving(self, nchan, chx, verbose=False):
        for chn in range(0, nchan):
            _data = self.uut.chan2volts(self.cmap[0][chn], chx[0][chn])  
            with h5py.File(self.filename, mode="a", libver="latest") as dataFile:
                grp = dataFile.require_group(self.data_num)
                try:
                    grp.create_dataset("Ch%02d"%(chn+1), shape=(len(_data),1), data=_data, 
                                       dtype='float64', maxshape=(None,None))
                    print("Created dataset Ch%02d"%(chn+1))
                    print("Saved data to file %s, group %s, dataset 'Ch%02d'"
                          %(self.hdfname, self.data_num, chn+1))
                except:
                    if np.array_equal(_data[:100], dataFile[self.data_num]["Ch%02d"%(chn+1)][:100,-1]) or\
                        np.array_equal(_data[-100:], dataFile[self.data_num]["Ch%02d"%(chn+1)][-100:,-1]):
                        dataFile[self.data_num]["Ch%02d"%(chn+1)].attrs["Error in shot {} or {}".format(
                            len(dataFile[self.data_num]["Ch%02d"%(chn+1)][0,:])-1,  
                            len(dataFile[self.data_num]["Ch%02d"%(chn+1)][0,:]))] = 1
                        print("likely error identified")
                    # if not np.array_equal(_data[:100], dataFile[self.data_num]["Ch%02d"%(chn+1)][:100,-1]):
                    dataFile[self.data_num]["Ch%02d"%(chn+1)].resize(dataFile[self.data_num]["Ch%02d"%(chn+1)].shape[1]+1, axis=1)
                    dataFile[self.data_num]["Ch%02d"%(chn+1)][:,-1] = _data
                    print("Saved data to file %s, group %s, dataset 'Ch%02d'"
                          %(self.hdfname, self.data_num, chn+1))
                    # else:
                    #     print("Bad data on channel {} not saved".format(chn))
                                   
                dataFile.close()
        
        # with h5py.File(self.filename, mode="a", libver="latest") as dataFile:
        #     if nchan>3:
        #         dataFile[str(data_num)]["Ch01"].attrs["Channel Name"] = "LIA"
        #         dataFile[str(data_num)]["Ch02"].attrs["Channel Name"] = "ref"
        #         dataFile[str(data_num)]["Ch03"].attrs["Channel Name"] = "open"
        #         dataFile[str(data_num)]["Ch04"].attrs["Channel Name"] = "open"
                
            dataFile.close()

    def hdf_plot(self, channels, data_num, verbose=False):
        full_data=np.zeros((self.total,1))
        plt.figure()
        for chn in channels:
            with h5py.File(self.filename, mode="a", libver="latest") as dataFile:
                data = np.array(dataFile[self.data_num]["Ch%02d"%(chn)])
                num_averages = len(data[1,:])
                data = np.average(data, axis=1)
                data = np.reshape(data, (-1,1))
                full_data=np.hstack((full_data,data))
            if verbose:
                print("plotting averaged data)")
            
  
            label = "Ch%02d averaged %d times"%(chn, num_averages)
            # plt.suptitle('{} averages'.format(num_averages))
            plt.xlabel("Time [ms]")
            plt.ylabel("Volts")  
            plt.plot(self.t,full_data[:,chn], label=label)
        
        if self.collect_pre:
            plt.axvline(x=self.pre/2000, label="trigger", color="k")
        plt.title("Averaged Data")
        plt.legend()
        plt.tight_layout()

        
        plt.show()

def apply_attributes(filename, data_num, parDict=dict(), nchan=0): 
    

    with h5py.File(filename, mode="a", libver="latest") as dataFile:
        dataFile[str(data_num)].attrs.update(parDict)
        dataFile[str(data_num)]["Ch01"].attrs["Channel Name"] = "LIA"
        if nchan>1:
            dataFile[str(data_num)]["Ch02"].attrs["Channel Name"] = "ref"
        if nchan>2:
            dataFile[str(data_num)]["Ch03"].attrs["Channel Name"] = "open"
        if nchan>3:
            dataFile[str(data_num)]["Ch04"].attrs["Channel Name"] = "open"
        
        dataFile.close()

    
    
    
    