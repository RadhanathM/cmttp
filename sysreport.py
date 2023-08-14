import sys
import os
import os.path
import time
import plotlib
import re
import commands
import datetime

Process_poll_interval=120
DB_poll_interval=900
System_poll_interval=240
rotate_interval=3600
ReleaseVal=6
ipaddress='UNKNOWN'
hostname='UNKNOWN'
cardtype='UNKNOWN'
hardwaretype='UNKNOWN'
portarray = [53384,53389,53400,53388]
IParray = [] 
IPFlag = 0
ProcessName = []

custom_parameter = ['rotate_interval','Process_poll_interval','DB_poll_interval','System_poll_interval']

for keyparam in custom_parameter:
    string = keyparam
    if os.path.isfile('/DG/activeRelease/Tools/Fieldutils/customized_sysmonitor_parameter'):
       vars()[string] = commands.getoutput("grep "+keyparam+" /DG/activeRelease/Tools/Fieldutils/customized_sysmonitor_parameter|grep -v '#' |cut -f2 -d '='").strip()

rotate_interval = float(rotate_interval)
Process_poll_interval   = float(Process_poll_interval)
DB_poll_interval   = float(DB_poll_interval)
System_poll_interval   = float(System_poll_interval)

Process_poll_interval   = Process_poll_interval/60
DB_poll_interval   = DB_poll_interval/60
System_poll_interval   = System_poll_interval/60
rotate_interval = rotate_interval/60

def filetstamp_to_epoch(t_start):
    return time.mktime((2000+int(t_start[:2]),\
        int(t_start[2:4]),\
        int(t_start[4:6]),\
        int(t_start[7:9]),\
        int(t_start[9:11]),\
        int(t_start[11:13]),0,0,0))

def Usage():
    print "Usage:"
    print "    python2.6 sysreport.py <perf-reports-path> --Port=Port-Number(optional) --IP=IPAddress(optional)"
    print "    --Port = list of port number for which the netstat output has to be ploted(list multiple ports seperated by (,)"
    print "    --IP = list of IP Address for which the netstat output has to be ploted(list multiple IPAddress seperated by (,)"
    print "    EX: python2.6 sysreport.py perfreports_EMS/ --Port=53389,53384 --IP=192.168.5.86,127.0.0.1"
    sys.exit(0)

if len(sys.argv) < 2:
   Usage()
# Get the directory to be analyzed.
# Create a working directory within it to extract the data files.
reports_directory = sys.argv[1]
countargv = 0

for value in sys.argv:
   if countargv > 1:
      matchObj = re.match( r'--(Port|IP)=(.*)', value, re.M)
      if matchObj:
           matchObj = re.match( r'--Port=(.*)', value, re.M)
           if matchObj: 
                if matchObj.group(1) == '':
                   Usage() 
                portarraytemp = matchObj.group(1).split(',')
                portarray = portarraytemp
           matchObj = re.match( r'--IP=(.*)', value, re.M)
           if matchObj: 
                if matchObj.group(1) == '':
                   Usage() 
                IParraytemp = matchObj.group(1).split(',')
                IPFlag = 1
                IParray = IParraytemp
      else:
           Usage() 
           
   countargv = countargv + 1

if reports_directory[-1] == '/':
    reports_directory = reports_directory[:-1]
print "Processing sysmonitor data files in:", reports_directory
working_dir = reports_directory + '/plot-data-tmp'
print "Creating working directory for creating the plots in:"
print working_dir
if os.path.exists(working_dir):
    print "Cleaning up existing working directory at:", working_dir
    os.system('rm -rf '+working_dir)
os.system('mkdir '+working_dir)

plot_startime=''

# Get a listing of all available files.
files = [x for x in os.listdir(reports_directory) 
    if os.path.isfile(reports_directory+'/'+x)]
tar_files = [x for x in files if (x[:8] == 'reports_' and x[-4:] == '.tgz')]
tar_files.sort()
unarchived_files = [x for x in files if tar_files.count(x) == 0]

# Check if there are any discontinuities in the data and report them.
# We get this from the time-stamps on files that weren't archived.
unarchived_process_files = [x for x in unarchived_files 
    if x[:12] == 'processinfo_']
# Warn users if any discontinuity is seen in the data.
if len(unarchived_process_files) > 1:
    print """
WARNING: The sysmonitor data being processed contains discontinuities.
WARNING: There is a break in the collected data at these times:
"""
    unarchived_process_files.sort()
    for file in unarchived_process_files[:-1]:
        discontinuity_time = file[-13:]
        f = open(reports_directory+'/'+file)
        lines = f.readlines()
        t1 = float(lines[0].split(',')[0].split(':')[1])
        t2 = float(lines[-1].split(',')[0].split(':')[1])
        t3 = filetstamp_to_epoch(discontinuity_time) + (t2-t1)
        print "WARNING:",time.ctime(t3)
    print """
WARNING: This could be a result of system reboots or the sysmonitor script 
WARNING: going down. The graphs generated will not show this discontinuity. 
WARNING: You may see straight lines in the intervals where data is not 
WARNING: available. You could separate out the data files and generate the
WARNING: plots as separate sets for each interval. Each file has a timestamp
WARNING: at the end indicating the time at which it was logged. Use this to
WARNING: to separate out the data.
"""
    raw_input("Press enter to continue ...")

# Process each tar file now
print "Unpacking tar files ..."
for tar_file in tar_files:
    os.system('tar -vxzf %s -C %s >>/dev/null 2>>/dev/null' % (
        reports_directory+'/'+tar_file, working_dir))
os.system('find %s/perfreports/ -name "*_*" -exec mv -f {} %s' % (working_dir, working_dir)+ '/ \;')
unarchived_file_str = [reports_directory+'/'+x for x in unarchived_files]
unarchived_file_str = ' '.join(unarchived_file_str)
os.system('cp %s %s' % (unarchived_file_str, working_dir))
print "Data files extracted in:", working_dir
print "You may use the files there for additional analysis"

file_list = [x for x in os.listdir(working_dir) if os.path.isfile(working_dir+'/'+x)]
file_list.sort()

print "Analysing systemstat specific data ..."
systemstat = [open(working_dir+'/'+x) for x in file_list if x[:11] == 'systemstat_']
for systemstat_file in systemstat:
    for line in systemstat_file.xreadlines():
        if line == '':
           continue
        matchObj = re.match( r'LOCAL_IP_ADDRESS\s*(.*)', line, re.M)
        if matchObj:
           if matchObj.group(1) == '':
              ipaddress = 'UNKNOWN'
           else:
              ipaddress = matchObj.group(1)

        matchObj = re.match( r'HOSTNAME\s*(.*)', line, re.M)
        if matchObj:
           if matchObj.group(1) == '':
              hostname = 'UNKNOWN'
           else:
              hostname = matchObj.group(1)

        matchObj = re.match( r'CARD_TYPE\s*(.*)', line, re.M)
        if matchObj:
           if matchObj.group(1) == '':
              cardtype = 'UNKNOWN'
           else:
              cardtype = matchObj.group(1)

        matchObj = re.match( r'HARDWARE_TYPE\s*(.*)', line, re.M)
        if matchObj:
           if matchObj.group(1) == '':
              hardwaretype = 'UNKNOWN'
           else:
              hardwaretype = matchObj.group(1)
        
        matchObj = re.match( r'rotate_interval\s*(.*)', line, re.M)
        if matchObj:
           if matchObj.group(1) == '':
              rotate_interval = 'UNKNOWN'
           else:
              rotate_interval = matchObj.group(1)
              rotate_interval = float(rotate_interval)
              rotate_interval = rotate_interval/60

        matchObj = re.match( r'DB_poll_interval\s*(.*)', line, re.M)
        if matchObj:
           if matchObj.group(1) == '':
              DB_poll_interval = 'UNKNOWN'
           else:
              DB_poll_interval = matchObj.group(1)
              DB_poll_interval = float(DB_poll_interval)
              DB_poll_interval = DB_poll_interval/60
 
        matchObj = re.match( r'Process_poll_interval\s*(.*)', line, re.M)
        if matchObj:
           if matchObj.group(1) == '':
              Process_poll_interval = 'UNKNOWN'
           else:
              Process_poll_interval = matchObj.group(1)
              Process_poll_interval = float(Process_poll_interval)
              Process_poll_interval = Process_poll_interval/60

        matchObj = re.match( r'System_poll_interval\s*(.*)', line, re.M)
        if matchObj:
           if matchObj.group(1) == '':
              System_poll_interval = 'UNKNOWN'
           else:
              System_poll_interval = matchObj.group(1)
              System_poll_interval = float(System_poll_interval)
              System_poll_interval = System_poll_interval/60

        matchObj = re.match( r'RELEASEVER\s*(.*)', line, re.M)
        if matchObj:
           if matchObj.group(1) == '':
              ReleaseVal = 6 
           else:
              ReleaseVal = matchObj.group(1)
              ReleaseVal = int(ReleaseVal)

print "Analysing process specific data ..."
# Create a plot of CPU usage of all processes
process_files = [open(working_dir+'/'+x) for x in file_list if x[:12] == 'processinfo_']

processes = {}
ProcessAvg = {}
CPUAvg = {}
PvtAvg = {}
for process_file in process_files:
    for line in process_file.xreadlines():
        if line == '':
            continue 

        flag = 0
        line1 = []
        line.split(',')
        if line[:4] == 'time':
            line = line.split(',')
            for x in line:
               matchObj = re.match( r'(.*):(.*)', x, re.M)
               if not matchObj: 
                   flag = 1
                   break
               else:
                   a,b= x.split(':',1)
                   if not a or not b:
                      flag = 1
                      break
                   else:
                      m = [a,b]
                      line1.append(m)
            if flag == 1:
               print "data incomplete in "+str(process_file)+""
               continue

            line = line1
            line = [(a.strip(),b.strip()) for a,b in line ]
            dict = {}
            for name,val in line:
                dict[name] = val
            if 'time' in dict.keys():
               if dict['time']:
                  try:
                      ticks = float(dict['time'])
                  except:
                      print "data incomplete in "+str(process_file)+""
                      continue
               else:
                  print "data incomplete in "+str(process_file)+""
                  continue
            else:
               print "data incomplete in "+str(process_file)+""
               continue    

            if 'name' in dict.keys():
               if dict['name']:
                  try:
                      name = dict['name']
                  except:
                      print "data incomplete in "+str(process_file)+""
                      continue
               else:
                  print "data incomplete in "+str(process_file)+""
                  continue
            else:
               print "data incomplete in "+str(process_file)+""
               continue

            if 'cpu' in dict.keys():
               if dict['cpu']:
                  try:
                      cpu = dict['cpu']
                      if float(cpu) > 100:
                         cpu = '100'
                  except:
                      print "data incomplete in "+str(process_file)+""
                      continue
               else:
                  print "data incomplete in "+str(process_file)+""
                  continue
            else:
               print "data incomplete in "+str(process_file)+""
               continue

            if 'pvt-wr-mem' in dict.keys():
               if dict['pvt-wr-mem']:
                  try:
                      private_writable_mem = dict['pvt-wr-mem']
                      private_writable_mem_Value = float(private_writable_mem.split()[0])/1024
                      private_writable_mem = ""+str(private_writable_mem_Value)+" MB"
                  except:
                      print "data incomplete in "+str(process_file)+""
                      continue
               else:
                  print "data incomplete in "+str(process_file)+""
                  continue
            else:
               print "data incomplete in "+str(process_file)+"" 
               continue

            if 'rss' in dict.keys():
               if dict['rss']:
                  try:
                      rss = dict['rss']
                      rss_Value = float(rss.split()[0])/1024
                      rss = ""+str(rss_Value)+" MB"
                  except:
                      print "data incomplete in "+str(process_file)+""
                      continue
               else:
                  print "data incomplete in "+str(process_file)+""
                  continue
            else:
               print "data incomplete in "+str(process_file)+""
               continue
    
            if 'threads' in dict.keys():
               if dict['threads']:
                  try:
                      threads = dict['threads']
                  except:
                      print "data incomplete in "+str(process_file)+""
                      continue
               else:
                  print "data incomplete in "+str(process_file)+""
                  continue
            else:
               print "data incomplete in "+str(process_file)+""
               continue 

            if 'fdcount' in dict.keys():
               if dict['fdcount']:
                  try:
                      fdcount = dict['fdcount']
                  except:
                      print "data incomplete in "+str(process_file)+""
                      continue
               else:
                  print "data incomplete in "+str(process_file)+""
                  continue
            else:
               print "data incomplete in "+str(process_file)+""
               continue 

            if 'ctime' in dict.keys():
               if dict['ctime']:
                  try:
                      endtime = dict['ctime']
                  except:
                      print "data incomplete in "+str(process_file)+""
                      continue
               else:
                  print "data incomplete in "+str(process_file)+""
                  continue
            else:
               print "data incomplete in "+str(process_file)+""
               continue

            if not processes.has_key(name):
                if dict.has_key('ctime'):
                    ctime = dict['ctime']
                else:
                    ctime = ''
                processes[name] = {
                    'start_time':  ticks,
                    'start_ctime': ctime,
                    'files': (open(working_dir+'/'+name+'_cpu','w'),
                        open(working_dir+'/'+name+'_rss','w'),
                        open(working_dir+'/'+name+'_threads','w'),
                        open(working_dir+'/'+name+'_pvtwrmem','w'),
                        open(working_dir+'/'+name+'_fdcount','w'))
                    }
            current_process = processes[name]
            start_time = current_process['start_time']
            ticks = time.strftime('%Y/%m/%d %H:%M:%S', time.localtime(ticks))
            namecpu = name +'cpu' 
            namepvtmem = name+'pvtmem'
            namecount = name+'count'
            if not ProcessAvg.has_key(namecpu):
               ProcessAvg[namecpu] = 0
               ProcessAvg[namepvtmem] = 0
               ProcessAvg[namecount] = 0
            ProcessAvg[namecpu] = float(cpu) + ProcessAvg[namecpu]
            ProcessAvg[namepvtmem] = float(private_writable_mem.split()[0]) + ProcessAvg[namepvtmem]
            ProcessAvg[namecount] += 1
            print >> current_process['files'][0],ticks,cpu
            print >> current_process['files'][1],ticks,rss
            print >> current_process['files'][2],ticks,threads
            print >> current_process['files'][3],ticks,private_writable_mem
            print >> current_process['files'][4],ticks,fdcount
    
for process in processes.values():
    for f in process['files']:
        f.close()

print "ctime ==",ctime,endtime
plot_startime=ctime

ipaddress.strip()
hostname.strip()
cardtype.strip()
hardwaretype.strip()
os.system(">AvgValues.txt");

Processsystemval =  "IPAddress:"+ipaddress+" HostName:"+hostname+" CardType:"+cardtype+" H/W:"+hardwaretype+"\\nCollection-StartTime:"+plot_startime+"\\nCollection-EndTime:"+endtime+" Process-PollInterval:"+str(Process_poll_interval)+""
DBsystemval =  "IPAddress:"+ipaddress+" HostName:"+hostname+" CardType:"+cardtype+" H/W:"+hardwaretype+"\\nCollection-StartTime:"+plot_startime+"\\nCollection-EndTime:"+endtime+" DB-PollInterval:"+str(DB_poll_interval)+""
systemval =  "IPAddress:"+ipaddress+" HostName:"+hostname+" CardType:"+cardtype+" H/W:"+hardwaretype+"\\nCollection-StartTime:"+plot_startime+"\\nCollection-EndTime:"+endtime+" System-PollInterval:"+str(System_poll_interval)+""
Defaultsystemval =  "IPAddress:"+ipaddress+" HostName:"+hostname+" CardType:"+cardtype+" H/W:"+hardwaretype+"\\nCollection-StartTime:"+plot_startime+"\\nCollection-EndTime:"+endtime+""

# Split the processes into multiple groups if graphs get too crowded.
process_count = len(processes.keys())
# We'll have at most 5 processes in each graph
split_segments = (process_count - 1)/5 + 1
split_len = (process_count-1)/split_segments + 1

for type in ('cpu (%)','rss (MB)','threads','pvtwrmem (MB)','fdcount'):
    type_split = type.split(' ',1)
    if len(type_split) > 1:
        type, units = type_split
    else:
        units = ''
    start_ind = 0
    i = 1
    countdel=1
    while start_ind < process_count:
        if type == 'cpu':
           systemvalprocess = Processsystemval + "\\nAvg CPU::\\n"
        elif type == 'pvtwrmem':
           systemvalprocess = Processsystemval + "\\nAvg PVTMEM(MB)::\\n"
        else:
           systemvalprocess = Processsystemval
            
        filelist = []
        for name in processes.keys()[start_ind:start_ind+split_len]:
            if name not in ProcessName:
			    ProcessName.append(name)
            namecount = name + 'count'
            delim=", "
            if countdel%4 == 0:
               delim="\\n"
            if type == 'cpu':
               namecpu = name + 'cpu'
               ProcessAvg[namecpu] = float(ProcessAvg[namecpu])/ProcessAvg[namecount]
               ProcessAvg[namecpu] = "%.2f" % ProcessAvg[namecpu] 
               systemvalprocess = systemvalprocess + name+":" + str(ProcessAvg[namecpu])+ delim 
               os.system("echo \"CPU: "+name+"="+str(ProcessAvg[namecpu])+"\" >> AvgValues.txt") 
               CPUAvg[name] = ProcessAvg[namecpu]  
            elif type == 'pvtwrmem':
               namepvtmem = name + 'pvtmem'
               ProcessAvg[namepvtmem] = float(ProcessAvg[namepvtmem])/ProcessAvg[namecount]
               ProcessAvg[namepvtmem] = "%.2f" % ProcessAvg[namepvtmem] 
               systemvalprocess = systemvalprocess + name+":" + str(ProcessAvg[namepvtmem])+ delim 
               os.system("echo \"PVTWERMEM: "+name+"="+str(ProcessAvg[namecpu])+"\" >> AvgValues.txt") 
               PvtAvg[name] = ProcessAvg[namepvtmem]  
            filelist.append((working_dir+'/'+name+'_'+type,name))
            countdel += 1
        if type == 'cpu' or type == 'pvtwrmem':         
            if delim == ',':
               systemvalprocess = systemvalprocess[:-1]
        plotlib.plotfile(systemvalprocess,filelist,type+' '+units,'Date & Time','processes_'+type+'_'+`i`)
        start_ind += split_len
        i += 1

print "Analysing system CPU usage, memory, swapping and disk activity ..."
# Overall system CPU usage plots
# Overall system free memory plot
sar_files = [open(working_dir+'/'+x) for x in file_list if x[:4] == 'sar_']
CPUSarOutput = {}
PSwpSarOutput = {}
KBMemSarOutput = {}
PPagSarOutput = {}
SarOutput_rxpcks = {}
SarOutput_txpcks = {}
SarOutput_rxkBs = {}
SarOutput_txkBs = {}
SarOutput_rxcmps = {}
SarOutput_txcmps = {}
SarOutput_rxmcsts = {}
CPUAvgCnt=0
OverallCPU=0
MemAvgCnt=0
OverallMem=0
OverallActualFreeMem=0
OverallActualMemUsed=0
SwpMemAvgCnt=0
CacheAvgCnt=0
OverallSwpMem=0
OverallCacheMem=0
PreviousHour = ''

CPUArray = ['User','Nice','System','IOWait','Steal','Idle']
PSwpArray = ['pswpin','pswpout']
PPagingArray = ['pgpgin','pgpgout']
KBMemArray = ['MemFree','MemUsed','Buffers','Cached']
KBSWPArray = ['SwpFree','SwpUsed']
DEVStatArray = ['IFACE','rxpcks','txpcks','rxkBs','txkBs','rxcmps','txcmps','rxmcsts']

for sar_file in sar_files:
    CurDate = ''
    CurMon = ''
    CurYear = ''
    CPUFlag = 0
    SWAPFlag = 0
    PagFlag = 0
    KBMEM = 0
    KBSWAP = 0
    DEVStatusFlag = 0

    for cpuVal in CPUArray:
        if cpuVal not in CPUSarOutput:
           CPUSarOutput[cpuVal] = open(working_dir+"/"+cpuVal,'a')
    CPUSarOutput['System-CPU'] = open(working_dir+"/System-CPU",'a')

    for PSwpVal in PSwpArray:
        if PSwpVal not in PSwpSarOutput:
           PSwpSarOutput[PSwpVal] = open(working_dir+"/"+PSwpVal,'a')

    for PpagVal in PPagingArray:
        if PpagVal not in PPagSarOutput:
           PPagSarOutput[PpagVal] = open(working_dir+"/"+PpagVal,'a')

    for KBMemVal in KBMemArray:
        if KBMemVal not in KBMemSarOutput:
           KBMemSarOutput[KBMemVal] = open(working_dir+"/"+KBMemVal,'a')

    for KBSWPVal in KBSWPArray:
        if KBSWPVal not in KBMemSarOutput:
           KBMemSarOutput[KBSWPVal] = open(working_dir+"/"+KBSWPVal,'a')
    KBMemSarOutput['System-Memory'] = open(working_dir+"/System-Memory",'a')
    KBMemSarOutput['Actual-Memory-Used'] = open(working_dir+"/Actual-Memory-Used",'a')
    KBMemSarOutput['Actual-Free-Memory'] = open(working_dir+"/Actual-Free-Memory",'a')

    for line in sar_file.xreadlines():
        if line == '':
		   continue

        matchObj = re.match(r'.*\s+(\d+)\/(\d+)\/(\d+)\s+.*',line,re.M)
        if matchObj:
	       CurDate = matchObj.group(2)
	       CurMon = matchObj.group(1)
	       CurYear = matchObj.group(3)
	       matchObj = re.match(r'(\d\d)',CurYear,re.M)
	       if matchObj:
                    CurYear = "20"+CurYear+"" 
	       continue

        matchObj = re.match(r'.*CPU.*',line,re.M)
        if matchObj:
	       CPUFlag = 1
	       SWAPFlag = 0
	       KBMEM = 0
	       KBSWAP = 0
	       PagFlag = 0
	       DEVStatusFlag = 0
	       continue

        matchObj = re.match(r'.*pswpin.*',line,re.M)
        if matchObj:
	       CPUFlag = 0
	       SWAPFlag = 1
	       KBMEM = 0
	       KBSWAP = 0
	       PagFlag = 0
	       DEVStatusFlag = 0
	       continue

        matchObj = re.match(r'.*pgpgin.*',line,re.M)
        if matchObj:
	       CPUFlag = 0
	       SWAPFlag = 0
	       KBMEM = 0
	       KBSWAP = 0
	       PagFlag = 1
	       DEVStatusFlag = 0
	       continue
        
        matchObj = re.match(r'.*kbmemfree.*',line,re.M)
        if matchObj:
	       CPUFlag = 0
	       SWAPFlag = 0
	       KBMEM = 1
	       KBSWAP = 0
	       PagFlag = 0
	       DEVStatusFlag = 0
	       continue

        matchObj = re.match(r'.*kbswpfree.*',line,re.M)
        if matchObj:
	       CPUFlag = 0
	       SWAPFlag = 0
	       KBMEM = 0
	       KBSWAP = 1
	       PagFlag = 0
	       DEVStatusFlag = 0
	       continue

        matchObj = re.match(r'.*IFACE.*',line,re.M)
        if matchObj:
	       CPUFlag = 0
	       SWAPFlag = 0
	       KBMEM = 0
	       KBSWAP = 0
	       PagFlag = 0
	       PagFlag = 0
	       DEVStatusFlag = 1
	       continue

        matchObj = re.match(r'.*\d+:\d+:\d+\s+.*',line,re.M)
        if matchObj:
	       line1 = line.split()
	       count = 1
	       HrMinSec = line1[0].split(':')
	       if CPUFlag == 1:
		      StartDateSar = ""+CurMon+"/"+CurDate+"/"+CurYear+""
		      Date = datetime.datetime.strptime(StartDateSar, "%m/%d/%Y")

	       if int(HrMinSec[0]) == 00 and PreviousHour != int(HrMinSec[0]) and PreviousHour != '':
		      EndDate = Date + datetime.timedelta(days=1)
		      matchObj = re.match(r'(\d+)-(\d+)-(\d+).*',str(EndDate),re.M)
		      if matchObj:
			     CurDate = matchObj.group(3)
			     CurMon = matchObj.group(2)
			     CurYear = matchObj.group(1)
	       CurDateTime = ""+CurYear+"/"+CurMon+"/"+CurDate+" "+str(HrMinSec[0])+":"+HrMinSec[1]+":"+HrMinSec[2]+""
	       PreviousHour = int(HrMinSec[0])

	       if CPUFlag == 1:
		      line1.pop(1)
		      TotalCPU = 100 - float(line1[-1])
		      for cpuVal in CPUArray:
			      print >> CPUSarOutput[cpuVal],CurDateTime,line1[count]
			      count = count + 1
                      if 'System-CPU' not in CPUSarOutput:
                          CPUSarOutput['System-CPU'] = open(working_dir+"/System-CPU",'a')
		      print >> CPUSarOutput['System-CPU'],CurDateTime,TotalCPU
		      CPUAvgCnt=CPUAvgCnt+1 
		      OverallCPU=OverallCPU+TotalCPU 
		      continue 
		   
	       if SWAPFlag == 1:
		      for PSwpVal in PSwpArray: 
			      print >> PSwpSarOutput[PSwpVal],CurDateTime,line1[count]
			      count = count + 1
		      continue 
		   
	       if PagFlag == 1:
		      del line1[3:]
		      for PpagVal in PPagingArray: 
			      print >> PPagSarOutput[PpagVal],CurDateTime,line1[count]
			      count = count + 1
		      continue 
	       
               if KBMEM == 1:
		      TotalMem = 0
		      TotalCache = 0
                      del line1[3]
                      del line1[5:]
		      for KBMemVal in KBMemArray:
			      if KBMemVal == 'MemFree' or KBMemVal == 'MemUsed' or KBMemVal == 'Buffers' or KBMemVal == 'Cached':
				    line1[count] = int(line1[count])/1024
			      print >> KBMemSarOutput[KBMemVal],CurDateTime,line1[count]
			      if KBMemVal == 'MemFree' or KBMemVal == 'MemUsed':
				    TotalMem = TotalMem + int(line1[count])
			      if KBMemVal == 'Cached':
				    TotalCache = line1[count]
			      if KBMemVal == 'Buffers':
				    Buffers = line1[count]
			      if KBMemVal == 'MemUsed':
				    MemUsed = line1[count]
			      count = count + 1
                      if 'System-Memory' not in KBMemSarOutput:
                          KBMemSarOutput['System-Memory'] = open(working_dir+"/System-Memory",'a')
		      print >> KBMemSarOutput['System-Memory'],CurDateTime,TotalMem
                      if 'Actual-Memory-Used' not in KBMemSarOutput:
                          KBMemSarOutput['Actual-Memory-Used'] = open(working_dir+"/Actual-Memory-Used",'a')
                      if 'Actual-Free-Memory' not in KBMemSarOutput:
                          KBMemSarOutput['Actual-Free-Memory'] = open(working_dir+"/Actual-Free-Memory",'a')
                      ActualMemoryUsed = MemUsed - Buffers - TotalCache
                      ActualFreeMemory = TotalMem - ActualMemoryUsed
                      print >> KBMemSarOutput['Actual-Memory-Used'],CurDateTime,ActualMemoryUsed
                      print >> KBMemSarOutput['Actual-Free-Memory'],CurDateTime,ActualFreeMemory
		      MemAvgCnt=MemAvgCnt+1 
		      CacheAvgCnt=CacheAvgCnt+1 
		      OverallCacheMem=OverallCacheMem+TotalCache
		      OverallMem=OverallMem+TotalMem
                      OverallActualMemUsed=OverallActualMemUsed+ActualMemoryUsed
                      OverallActualFreeMem=OverallActualFreeMem+ActualFreeMemory              
		      continue 
		   
	       if KBSWAP == 1:
		      TotalSwp = 0 
                      del line1[3:]
		      for KBSWPVal in KBSWPArray: 
			      if KBSWPVal == 'SwpFree' or KBSWPVal == 'SwpUsed':
				    line1[count] = int(line1[count])/1024
				    if KBSWPVal == 'SwpUsed':
                                       TotalSwp = line1[count]
			      print >> KBMemSarOutput[KBSWPVal],CurDateTime,line1[count]
			      count = count + 1
		      SwpMemAvgCnt=SwpMemAvgCnt+1 
		      OverallSwpMem=OverallSwpMem+TotalSwp
		      continue 

	       if DEVStatusFlag == 1:
		      for DevStatVal in DEVStatArray:
			      if DevStatVal == 'IFACE':
				    try:
				       Name=line1[count]
				    except:
				       print "data incomplete in "+str(sar_file)+""
			      else:
				    Keyword = DevStatVal + "_" + Name 
				    if DevStatVal == 'rxpcks':
					   if not SarOutput_rxpcks.has_key(Name): 
					      SarOutput_rxpcks[Name] = open(working_dir+"/"+Keyword,'a') 
					   else:
					      try:
					         print >> SarOutput_rxpcks[Name],CurDateTime,line1[count] 
					      except:
					         print "data incomplete in "+str(sar_file)+""
				    if DevStatVal == 'txpcks':
					   if not SarOutput_txpcks.has_key(Name): 
					      SarOutput_txpcks[Name] = open(working_dir+"/"+Keyword,'a') 
					   else:
					      try:
					         print >> SarOutput_txpcks[Name],CurDateTime,line1[count] 
					      except:
					         print "data incomplete in "+str(sar_file)+""
				    if DevStatVal == 'rxkBs':
					   if not SarOutput_rxkBs.has_key(Name): 
					      SarOutput_rxkBs[Name] = open(working_dir+"/"+Keyword,'a') 
					   else:
					      try:
					         print >> SarOutput_rxkBs[Name],CurDateTime,line1[count] 
					      except:
					         print "data incomplete in "+str(sar_file)+""
				    if DevStatVal == 'txkBs':
					   if not SarOutput_txkBs.has_key(Name): 
					      SarOutput_txkBs[Name] = open(working_dir+"/"+Keyword,'a') 
					   else:
					      try:
					         print >> SarOutput_txkBs[Name],CurDateTime,line1[count] 
					      except:
					         print "data incomplete in "+str(sar_file)+""
				    if DevStatVal == 'rxcmps':
					   if not SarOutput_rxcmps.has_key(Name): 
					      SarOutput_rxcmps[Name] = open(working_dir+"/"+Keyword,'a') 
					   else:
					      try:
					         print >> SarOutput_rxcmps[Name],CurDateTime,line1[count] 
					      except:
					         print "data incomplete in "+str(sar_file)+""
				    if DevStatVal == 'txcmps':
					   if not SarOutput_txcmps.has_key(Name): 
					      SarOutput_txcmps[Name] = open(working_dir+"/"+Keyword,'a') 
					   else:
					      try:
					         print >> SarOutput_txcmps[Name],CurDateTime,line1[count]
					      except:
					         print "data incomplete in "+str(sar_file)+""
				    if DevStatVal == 'rxmcsts':
					   if not SarOutput_rxmcsts.has_key(Name): 
					      SarOutput_rxmcsts[Name] = open(working_dir+"/"+Keyword,'a') 
					   else:
					      try:
					         print >> SarOutput_rxmcsts[Name],CurDateTime,line1[count] 
					      except:
					         print "data incomplete in "+str(sar_file)+""
			      count = count + 1
		      continue 

plotlist = []
for dufile in CPUSarOutput.values():
   plotlist.append((dufile.name, dufile.name.split('/')[-1]))
   dufile.close()

if plotlist != []:
   AvgCPU = 0
   if OverallCPU != 0:
      AvgCPU = OverallCPU/CPUAvgCnt
   AvgCPU = "%.2f" % AvgCPU
   CPUsystemval = systemval + "\\nAvg System CPU::"+ AvgCPU + "\\n"
   os.system("echo \"System CPU=\"AvgCPU+\"\" >> AvgValues.txt") 
   print "Generating plots.","CPUDetails"
   plotlib.plotfile(CPUsystemval,plotlist,\
        'CPU Parameters(%)','Date & Time',"Host_system_cpu")
    
plotlist = []
for dufile in PSwpSarOutput.values():
   plotlist.append((dufile.name, dufile.name.split('/')[-1]))
   dufile.close()

if plotlist != []:
   print "Generating plots.","SwapDetails"
   plotlib.plotfile(systemval,plotlist,\
        'Swap Parameters','Date & Time',"system_swap")

plotlist = []
for dufile in PPagSarOutput.values():
   plotlist.append((dufile.name, dufile.name.split('/')[-1]))
   dufile.close()

if plotlist != []:
   print "Generating plots.","PagingDetails"
   plotlib.plotfile(systemval,plotlist,\
        'Paging Parameters','Date & Time',"system_paging")

plotlist = []
for dufile in KBMemSarOutput.values():
   plotlist.append((dufile.name, dufile.name.split('/')[-1]))
   dufile.close()

if plotlist != []:
   AvgMem = 0
   AvgSwpMem = 0
   AvgCacheMem = 0

   if OverallMem != 0:
      AvgMem = OverallMem/MemAvgCnt
   AvgMem = "%.2f" % AvgMem
   Avgsystemval = systemval + "\\nSystem Mem::"+ AvgMem + ","
   os.system("echo \"System Memory=\"AvgMem+\"\" >> AvgValues.txt") 

   if OverallActualMemUsed != 0:
      AvgActMemUsed = OverallActualMemUsed/MemAvgCnt
   AvgActMemUsed = "%.2f" % AvgActMemUsed
   Avgsystemval = Avgsystemval + "\\nAvg Actual Memory Used::"+ AvgActMemUsed + ","
   os.system("echo \"System Actual Memory Used=\"AvgActMemUsed+\"\" >> AvgValues.txt") 

   if OverallActualFreeMem != 0:
      AvgActFreeMem = OverallActualFreeMem/MemAvgCnt
   AvgActFreeMem = "%.2f" % AvgActFreeMem
   Avgsystemval = Avgsystemval + "\\nAvg Actual Free Memory::"+ AvgActFreeMem + ","
   os.system("echo \"System Actual Free Memory=\"AvgActFreeMem+\"\" >> AvgValues.txt") 

   if OverallSwpMem != 0:
      AvgSwpMem = OverallSwpMem/SwpMemAvgCnt
   AvgSwpMem = "%.2f" % AvgSwpMem
   Avgsystemval = Avgsystemval + "Avg Swap Mem Used::"+ AvgSwpMem + "\\n"
   os.system("echo \"System Swap Memory Used=\"AvgSwpMem+\"\" >> AvgValues.txt") 

   if OverallCacheMem != 0:
      AvgCacheMem = OverallCacheMem/CacheAvgCnt
   AvgCacheMem = "%.2f" % AvgCacheMem
   Avgsystemval = Avgsystemval + "Avg Cache Mem Used::"+ AvgCacheMem + "\\n"
   os.system("echo \"System Cache Memory Used=\"AvgCacheMem+\"\" >> AvgValues.txt") 
   
   print "Generating plots.","MemoryDetails"
   plotlib.plotfile(Avgsystemval,plotlist,\
        'Memory Parameters(MB)','Date & Time',"system_memory")

plotlist = []
count = 1
counttemp = 0
for dufile in SarOutput_rxpcks.values():
   plotlist.append((dufile.name, dufile.name.split('_')[-1]))
   dufile.close()
   if count % 5 == 0:
	  counttemp = counttemp + 1
	  filename="No_Of_Pack_Rec_" + str(counttemp)
	  plotlib.plotfile(systemval,plotlist,\
           'Total Number Of Packets Rec/Sec','Date & Time',filename)
	  plotlist = []
   count = count + 1 

if plotlist != []:
   print "Generating plots.","Total number of packets Received"
   counttemp = counttemp + 1
   filename="No_Of_Pack_Rec_" + str(counttemp)
   plotlib.plotfile(systemval,plotlist,\
        'Total Number Of Packets Rec/Sec','Date & Time',filename)

plotlist = []
for dufile in SarOutput_txpcks.values():
   plotlist.append((dufile.name, dufile.name.split('_')[-1]))
   dufile.close()

if plotlist != []:
   print "Generating plots.","Total number of packets Transfered"
   counttemp = counttemp + 1
   filename="No_Of_Kilobytes_rec_" + str(counttemp)
   plotlib.plotfile(systemval,plotlist,\
        'Total Number Of Packets Xfer/Sec','Date & Time',filename)

plotlist = []
count = 1
counttemp = 0
for dufile in SarOutput_rxkBs.values():
   plotlist.append((dufile.name, dufile.name.split('_')[-1]))
   dufile.close()
   if count % 5 == 0:
	  counttemp = counttemp + 1
	  filename="No_Of_Kilobytes_rec_" + str(counttemp)
	  plotlib.plotfile(systemval,plotlist,\
           'Total Number Of Kilobytes Rec/Sec','Date & Time',filename)
	  plotlist = []
   count = count + 1 

if plotlist != []:
   print "Generating plots.","Total number of kilobytes Received"
   counttemp = counttemp + 1
   filename="No_Of_Kilobytes_rec_" + str(counttemp)
   plotlib.plotfile(systemval,plotlist,\
        'Total Number Of Kilobytes Rec/Sec','Date & Time',filename)

plotlist = []
count = 1
counttemp = 0
for dufile in SarOutput_txkBs.values():
   plotlist.append((dufile.name, dufile.name.split('_')[-1]))
   dufile.close()
   if count % 5 == 0:
	  counttemp = counttemp + 1
	  filename="No_Of_Kilobytes_xfer_" + str(counttemp)
	  plotlib.plotfile(systemval,plotlist,\
           'Total Number Of Kilobytes Xfer/Sec','Date & Time',filename)
	  plotlist = []
   count = count + 1 

if plotlist != []:
   print "Generating plots.","Total number of kilobytes Transfered"
   counttemp = counttemp + 1
   filename="No_Of_Kilobytes_xfer_" + str(counttemp)
   plotlib.plotfile(systemval,plotlist,\
        'Total Number Of Kilobytes Xfer/Sec','Date & Time',filename)

plotlist = []
count = 1
counttemp = 0
for dufile in SarOutput_rxcmps.values():
   plotlist.append((dufile.name, dufile.name.split('_')[-1]))
   dufile.close()
   if count % 5 == 0:
	  counttemp = counttemp + 1
	  filename="No_Of_Comp_Pack_rec_" + str(counttemp)
	  plotlib.plotfile(systemval,plotlist,\
           'Total Number Of Compressed Packets Rec/Sec','Date & Time',filename)
	  plotlist = []
   count = count + 1 

if plotlist != []:
   print "Generating plots.","Total number of Compressed Packets Recieved"
   counttemp = counttemp + 1
   filename="No_Of_Comp_Pack_rec_" + str(counttemp)
   plotlib.plotfile(systemval,plotlist,\
        'Total Number Of Compressed Packets Rec/Sec','Date & Time',filename)

plotlist = []
count = 1
counttemp = 0
for dufile in SarOutput_txcmps.values():
   plotlist.append((dufile.name, dufile.name.split('_')[-1]))
   dufile.close()
   if count % 5 == 0:
          counttemp = counttemp + 1
          filename="No_Of_Comp_Pack_xfer_" + str(counttemp)
          plotlib.plotfile(systemval,plotlist,\
           'Total Number Of Compressed Packets Xfer/Sec','Date & Time',filename)
          plotlist = []
   count = count + 1

if plotlist != []:
   print "Generating plots.","Total number of Compressed Packets Transfered"
   counttemp = counttemp + 1
   filename="No_Of_Comp_Pack_xfer_" + str(counttemp)
   plotlib.plotfile(systemval,plotlist,\
        'Total Number Of Compressed Packets Xfer/Sec','Date & Time',filename)

plotlist = []
count = 1
counttemp = 0
for dufile in SarOutput_rxmcsts.values():
   plotlist.append((dufile.name, dufile.name.split('_')[-1]))
   dufile.close()
   if count % 5 == 0:
	  counttemp = counttemp + 1
	  filename="No_Of_MultiCast_Pack_rec_" + str(counttemp)
	  plotlib.plotfile(systemval,plotlist,\
           'Total Number Of MultiCast Packets Rec/Sec','Date & Time',filename)
	  plotlist = []
   count = count + 1 

if plotlist != []:
   print "Generating plots.","Total number of MultiCast Packets Recieved"
   counttemp = counttemp + 1
   filename="No_Of_MultiCast_Pack_rec_" + str(counttemp)
   plotlib.plotfile(systemval,plotlist,\
        'Total Number Of MultiCast Packets Rec/Sec','Date & Time',filename)

plotlist = []
CPUAvg = sorted(CPUAvg.items(), key=lambda x: float(x[1]),reverse=True)
CPUAvgfiles = {}
Count = 0
ProcesssystemvalTemp  = Processsystemval +" System-PollInterval:"+str(System_poll_interval)+"\\nAvg CPU::\\n"

for process in CPUAvg:
   namecpu = process[0] + 'cpu'
   if Count == 4:
      ProcesssystemvalTemp = ProcesssystemvalTemp + "\\n"
   ProcesssystemvalTemp = ProcesssystemvalTemp + process[0] + ":" + str(ProcessAvg[namecpu]) + ','
   CPUAvgfiles[process[0]] = ""+working_dir+"/"+process[0]+"_cpu"
   Count = Count + 1
   if Count == 5:
      break

if 'System-CPU' in CPUSarOutput:
   ProcesssystemvalTemp = ProcesssystemvalTemp + "\\n" + "Avg System CPU:" + AvgCPU + "\\n"

plotlist = []
for dufile in CPUAvgfiles.values():
	  name = dufile.split('/')[-1]
	  plotlist.append((dufile,name.split('_cpu')[0]))
plotlist.append((""+working_dir+"/System-CPU",'System CPU'))

if plotlist != []:
      print "Generating plots."
      plotlib.plotfile(ProcesssystemvalTemp,plotlist,\
          'CPU Used (percentage)','Date & Time','Top5CPUProcess')

PvtAvg = sorted(PvtAvg.items(), key=lambda x: float(x[1]),reverse=True)
PvtAvgfiles = {}
Count = 0
ProcesssystemvalTemp = Processsystemval + "\\nAvg PVT::\\n"

for process in PvtAvg:
   namepvtmem = process[0] + 'pvtmem'
   if Count == 4:
      ProcesssystemvalTemp = ProcesssystemvalTemp + "\\n"
   ProcesssystemvalTemp = ProcesssystemvalTemp + process[0] + ":" + str(ProcessAvg[namepvtmem]) + ','
   PvtAvgfiles[process[0]] = ""+working_dir+"/"+process[0]+"_pvtwrmem"
   Count = Count + 1
   if Count == 5:
      break

plotlist = []
for dufile in PvtAvgfiles.values():
	  name = dufile.split('/')[-1]
	  plotlist.append((dufile,name.split('_pvtwrmem')[0]))

if plotlist != []:
      print "Generating plots."
      plotlib.plotfile(ProcesssystemvalTemp,plotlist,\
          'PvtMemory Used (MB)','Date & Time','Top5PvtMemProcess')

#DB System Stats plots
print "Analysing DB System Stats reports."
Fields = "'log.buffer.bytes_inserted |log.buffer.waits|log.file.reads|log.file.writes|log.files.generated|log.file.earliest|connections.established.count|connections.established.direct|connections.established.client_server|connections.disconnected|stmt.executes.updates |stmt.executes.deletes |stmt.executes.inserts |stmt.executes.selects |log.buffer.bytes_inserted '"

ttlogholds = {}
ttlogholdsDiffHash = {}
ttlogholdsTotal = {}
ttlogholdscnt = {}
Temp = 0
System_Stats = commands.getoutput("egrep "+Fields+" "+working_dir+"/ttlogholds_* 2>>/dev/null | sed -e \"s/'//g\"").split('\n')
for ttlogline in System_Stats:
    if ttlogline == '':
	   continue 
    ttloglineArray = ttlogline.split('(')
    matchObj = re.match(r'.*_6_.*',ttloglineArray[0],re.M)
    if matchObj:
	   Temp = 1
    ttlognamevalue = ttloglineArray[1].split(',')
    TimeVal = ttlognamevalue[0].split('.')[0]
    TimeVal = re.sub(r'-', '/', TimeVal)

    FieldName = ttlognamevalue[1].strip()
    if Temp == 1:
	   FieldName = "ttholds_6-"+FieldName
	   Name = "ttholds_6"
    else:
	   FieldName = "ttholds-"+FieldName
	   Name = "ttholds"

    FieldValue = ttlognamevalue[2].strip()
    matchObj = re.match(r'.*None.*',FieldValue,re.IGNORECASE)
    if matchObj:
	   FieldValue = 0 
   
    if not ttlogholds.has_key(Name):
	   ttlogholds[Name] = {
				     FieldName: open(working_dir+"/"+FieldName,'a') 
							 }
    else:
	   ttlogholds[Name][FieldName] = open(working_dir+"/"+FieldName,'a')

    if not ttlogholdsDiffHash.has_key(FieldName):
	    ttlogholdsDiffHash[FieldName] = FieldValue
    if not ttlogholdsTotal.has_key(FieldName): 
	    ttlogholdsTotal[FieldName] = 0
    if not ttlogholdscnt.has_key(FieldName): 
	    ttlogholdscnt[FieldName] = 0
	   	
    DiffVal = int(FieldValue) - int(ttlogholdsDiffHash[FieldName])
    if DiffVal < 0:
	    DiffVal = int(FieldValue)
	    Total = 0 + int(ttlogholdsTotal[FieldName])
    else:
	    Total = DiffVal + int(ttlogholdsTotal[FieldName])
    print >> ttlogholds[Name][FieldName],TimeVal,DiffVal
    ttlogholdsDiffHash[FieldName] = FieldValue
    ttlogholdsTotal[FieldName] = Total
    ttlogholdscnt[FieldName] = ttlogholdscnt[FieldName] + 1

for pttid in ttlogholds.keys():
    plotlist = []
    plotlist1 = []
    plotlist2 = []
    DBsystemval1 = DBsystemval
    
    FileHash = ttlogholds[pttid]
    for dufile in FileHash.values():
        matchObj = re.match(r'.*(stmt.executes.updates|stmt.executes.deletes|stmt.executes.inserts|stmt.executes.selects|log.buffer.bytes_inserted).*',dufile.name,re.M)
        if matchObj:
           plotlist2.append((dufile.name, dufile.name.split('-')[-1]))
           fname = dufile.name.split('/')[-1]
           fname1 = fname.split('-')[-1]
           Avg = ttlogholdsTotal[fname] / ttlogholdscnt[fname]
           DBsystemval1 = DBsystemval1 + "\\n" + fname1 + ":" + str(Avg)
        else:
           matchObj = re.match(r'.*(bytes_inserted|file\.writes|log\.file\.reads|log\.file\.earliest).*',dufile.name,re.M)
           if matchObj:
               plotlist1.append((dufile.name, dufile.name.split('-')[-1]))
           else:
	       plotlist.append((dufile.name, dufile.name.split('-')[-1]))
        dufile.close()

    if plotlist != []:
        print "Generating plots.",pttid
        plotlib.plotfile(DBsystemval,plotlist,\
           'SystemStats Parameters','Date & Time',pttid)

    if plotlist1 != []:
        pttid = pttid + "_1"
        print "Generating plots.",pttid
        plotlib.plotfile(DBsystemval,plotlist1,\
           'SystemStats Parameters','Date & Time',pttid)

    if plotlist2 != []:
        pttid = pttid + "_2"
        print "Generating plots.",pttid
        plotlib.plotfile(DBsystemval1,plotlist2,\
           'SystemStats Parameters','Date & Time',pttid)

# repadmin plots
print "Analysing repadmin reports."
repadmin_files = [open(working_dir+'/'+x) for x in file_list if x[:9] == 'repadmin_']
repadminpttid = []

for repadmin_file in repadmin_files:
    t_file = repadmin_file.name[:-14].split('/')[-1]
    if t_file not in repadminpttid:
       repadminpttid.append(t_file)

for repadmin_filepttid in repadminpttid:
   start_ctime = 0
   repadminfiles = {}
   newcount=0
   prev_file_time=0

   for repadmin_file in repadmin_files:
       t_start = repadmin_file.name[-13:]
       t_file = repadmin_file.name[:-14].split('/')[-1]
       if t_file != repadmin_filepttid:
          continue

       file_start_time = filetstamp_to_epoch(t_start)
       if not start_ctime:
          start_ctime = file_start_time
       offset = (file_start_time - start_ctime)/60.0

       if not prev_file_time:
          prev_file_time=file_start_time

       prevdiff = (file_start_time - prev_file_time)/60.0
       offset=0

       if prevdiff > rotate_interval:
          offset=prevdiff-rotate_interval

       count1 = 0
       count = 0
       for line in repadmin_file.xreadlines():
          if line == '':
             continue 
          if line[:4] == 'Date':
             if count > 0:
                count1 += 1
                newcount += 1

          newval=newcount*DB_poll_interval*60
          newval += offset
          matchObj = re.match(r'(\w+)\s+(\d+.\d+.\d+.\d+)\s+(.*)',line,re.M)
          if matchObj:
             sentname = 'sent'+matchObj.group(1) + matchObj.group(2)
             recievename = 'recieve'+matchObj.group(1) + matchObj.group(2)
             name  = matchObj.group(1) + '_' + matchObj.group(2)

          matchObj = re.match( r'(\d+:\d+:\d+)\s+(\d+:\d+:\d+)\s+(.*)', line, re.M)
          if matchObj:
             lastmesgsent  = matchObj.group(1)
             lastmesgrecev = matchObj.group(2)
             hours, minutes, seconds = lastmesgsent.split(':')
             hourr, minuter, secondr = lastmesgrecev.split(':')

             sentmessage = int(hours)*60 + int(minutes) + int(seconds)/60.0
             recievemessage = int(hourr)*60 + int(minuter) + int(secondr)/60.0

             repadminfiles[sentname] = open(working_dir+"/"+repadmin_filepttid+"sentmsg_"+name+"",'a')
             repadminfiles[recievename] = open(working_dir+"/"+repadmin_filepttid+"recievemsg_"+name+"",'a')
			 
             newval += start_ctime
             newval=time.strftime('%Y/%m/%d %H:%M:%S', time.localtime(newval))

             print >> repadminfiles[sentname],newval, sentmessage
             print >> repadminfiles[recievename],newval, recievemessage
             count += 1

       prev_file_time=file_start_time

   plotlist = []
   for dufile in repadminfiles.values():
      plotlist.append((dufile.name, dufile.name.split('/')[-1]))
      dufile.close()

   if plotlist != []:
      print "Generating plots.",repadmin_filepttid
      plotlib.plotfile(systemval,plotlist,\
          'Repadmin Parameters (minutes)','Date & Time',repadmin_filepttid)

#Heap Memory plots
print "Analysing Java Heap reports."
Heap_files = [open(working_dir+'/'+x) for x in file_list if x[:9] == 'heapinfo_']

HeapProcesses = {}
HeapProcessesCount = {}
HeapProcessesTot = {}

for Heap_file in Heap_files:
    for line in Heap_file.xreadlines():
		if line == '':
		   continue 
		matchObj = re.match( r'^\s*(\d+/\d+/\d+\s\d+:\d+:\d+)\s*,\s*name\s*:\s*(.*),\s*HeapMemory\s*:\s*(\d+)\s*MB.*',line, re.M)
		if matchObj:
		   ticks = matchObj.group(1)
		   Value =  matchObj.group(3)
		   name =  matchObj.group(2)
		else:
		     print "data incomplete in "+str(Heap_file)+""
		     continue    
    
		if not HeapProcessesCount.has_key(name):
		     HeapProcessesCount[name] = 0
		     HeapProcessesTot[name] = Value
		else:
			 HeapProcessesCount[name] = HeapProcessesCount[name] + 1
			 HeapProcessesTot[name] = int(HeapProcessesTot[name]) + int(Value)
		
		if not HeapProcesses.has_key(name):
		     HeapProcesses[name] = open(working_dir+'/'+name+'_HeapMem','a')
		   
		print >> HeapProcesses[name],ticks,Value

plotlist = []
Heapsystemval=DBsystemval + "\\nAvg Heap Mem::" + "\\n"
for process in HeapProcesses.keys():
        Avg = 0
        if HeapProcessesCount[process] != 0:
           Avg = int(HeapProcessesTot[process])/HeapProcessesCount[process]
           Avg = "%.2f" % Avg
        Heapsystemval = Heapsystemval + process + ":"+ Avg + ","
        os.system("echo \"Heap Memory:"+process+"="+Avg+"\" >> AvgValues.txt") 
	plotlist.append((HeapProcesses[process].name, process))
	HeapProcesses[process].close()

if plotlist != []:
   print "Generating plots."
   plotlib.plotfile(Heapsystemval,plotlist,\
     'Heap Memory (MB)','Date & Time','HeapMemory')

# TimesTen Datasize
print "Analysing TimesTen usage reports ..."
dssize_files = [open(working_dir+'/'+x) for x in file_list if x[:7] == 'dssize_']
dssizepttid = []

for dssize_file in dssize_files:
    t_file = dssize_file.name[:-14].split('/')[-1]
    if t_file not in dssizepttid:
       dssizepttid.append(t_file)
    
for dssizepttidval in dssizepttid:
    dsfiles = {}
    for dssize_file in dssize_files:
       t_start = dssize_file.name[-13:]
       t_file = dssize_file.name[:-14].split('/')[-1]
       if t_file != dssizepttidval:
          continue
   
       for line in dssize_file.xreadlines():
          if line == '':
               continue
          matchObj = re.match(r"(.*\d+\s+\d+:\d+:\d+.*\d+).*",line,re.M)
          if matchObj:
               DateValue = matchObj.group(1)
               DateValue = datetime.datetime.strptime(DateValue, '%a %b %d %H:%M:%S %Z %Y')
               DateValue = re.sub(r'-', '/', str(DateValue))
               continue
          matchObj = re.match(r"Date",line,re.M)
          if matchObj:
               continue
          line = re.sub(r'(\(|\))', '', str(line))
          FieldArray = line.split(', ')
          for val in FieldArray:
			   val = re.sub(r"'", '', str(val))
			   dssizevalues = val.split('=')
			   if len(dssizevalues) == 1:
			      continue
			   dssizevalues[1] = int(dssizevalues[1])/1024
			   if not dsfiles.has_key(dssizevalues[0]):
	                           dsfiles[dssizevalues[0]] = open(working_dir+"/"+dssizepttidval+"-"+dssizevalues[0],'w')
			   print >> dsfiles[dssizevalues[0]],DateValue, dssizevalues[1]
          
    plotlist = [] 
    for dufile in dsfiles.values():
       plotlist.append((dufile.name, dufile.name.split('-')[-1]))
       dufile.close()

    if plotlist != []:
       print "Generating plots.",dssizepttidval
       plotlib.plotfile(DBsystemval,plotlist,\
          'DSSIZE Parameters (MB)','Date & Time',dssizepttidval)

if ReleaseVal != 6:
   print "Analysing Container CPU."

   CPUOutput = {}
   MemOutput = {}
   CPUOutputTotal = {}
   MemOutputTotal = {}
   CPUCnt = {}
   MemCnt = {}
   CPUArray = ['DockerSysCPU','DockerSysIdle']
   MemoryArray = ['DockerSysTotalMem','DockerSysTotalFreeMem','DockerSysTotalMemUsed','DockerSysTotalSwapMem','DockerSysTotalSwapFreeMem','DockerSysTotalSwapMemUsed','DockerSysCache']

   for cpuVal in CPUArray:
       CPUOutput[cpuVal] = open(working_dir+"/"+cpuVal,'a')
       CPUCnt[cpuVal] = 0 
       CPUOutputTotal[cpuVal] = 0 
   for MemVal in MemoryArray:
       MemOutput[MemVal] = open(working_dir+"/"+MemVal,'a')
       MemCnt[MemVal] = 0 
       MemOutputTotal[MemVal] = 0 

   Dockerinfo_files = [open(working_dir+'/'+x) for x in file_list if x[:11] == 'Dockerinfo_']

   for Docker_file in Dockerinfo_files:
      DocFlag = 0
      for line in Docker_file.xreadlines():
           if line == '':
                continue
           matchObj = re.match( r'.*(DockerSysCPU|DockerSysIdle|DockerSysTotalMem|DockerSysTotalFreeMem|DockerSysTotalMemUsed|DockerSysTotalSwapMem|DockerSysTotalSwapFreeMem|DockerSysTotalSwapMemUsed|DockerSysCache),(.*),(.*)(%|MB).*', line, re.M)
           if matchObj:
                Key = matchObj.group(1)
                Time = matchObj.group(2)
                Value = matchObj.group(3)
                if Key == 'DockerSysCPU' and DocFlag == 0 and float(Value) == 0:
                   DocFlag = 1
                   continue 
                if Key == 'DockerSysIdle' and DocFlag == 1:
                   DocFlag = 2
                   continue

                if CPUOutput.has_key(Key):
                   print >> CPUOutput[Key],Time,Value
                   CPUCnt[Key] = CPUCnt[Key] + 1
                   CPUOutputTotal[Key] = CPUOutputTotal[Key] + float(Value)
                else:
                   print >> MemOutput[Key],Time,Value
                   MemCnt[Key] = MemCnt[Key] + 1
                   MemOutputTotal[Key] = MemOutputTotal[Key] + float(Value)

   plotlist = []
   CPUsystemval = systemval + "\\nAvg:\\n"
   for dufile in CPUOutput.values():
      plotlist.append((dufile.name, dufile.name.split('/')[-1]))
      if CPUOutputTotal[dufile.name.split('/')[-1]] == 0:
          AvgVal=0
      else:
          AvgVal = CPUOutputTotal[dufile.name.split('/')[-1]]/CPUCnt[dufile.name.split('/')[-1]] 
      AvgVal = "%.2f" % AvgVal 
      os.system("echo \"Container CPU="+AvgVal+"\" >> AvgValues.txt") 
      CPUsystemval = CPUsystemval + " " + dufile.name.split('/')[-1] +"::"+ AvgVal 
      dufile.close()

   print "Generating plots.","CPUDetails"
   plotlib.plotfile(CPUsystemval,plotlist,\
        'CPU Parameters(%)','Date & Time',"Docker_system_cpu")

   plotlist = []
   Count = 0
   Memsystemval = systemval + "\\nAvg:\\n"
   for dufile in MemOutput.values():
      plotlist.append((dufile.name, dufile.name.split('/')[-1]))
      if MemOutputTotal[dufile.name.split('/')[-1]] == 0:
          AvgVal=0
      else:
          AvgVal = MemOutputTotal[dufile.name.split('/')[-1]]/MemCnt[dufile.name.split('/')[-1]] 
      AvgVal = "%.2f" % AvgVal
      if Count == 4:
          Memsystemval = Memsystemval + "\\n" 
          Count = 0 
      os.system("echo \"Container Memory="+AvgVal+"\" >> AvgValues.txt") 
      Memsystemval = Memsystemval + " " + dufile.name.split('/')[-1] +"::"+ AvgVal
      Count = Count + 1
      dufile.close()

   print "Generating plots.","MemoryDetails"
   plotlib.plotfile(Memsystemval,plotlist,\
        'Memory Parameters(MB)','Date & Time',"Docker_system_memory")

# disk usage plots
print "Analysing disk usage reports."
diskusage_files = [open(working_dir+'/'+x) for x in file_list if x[:11] == 'disk_usage_']
start_ctime = 0
dufiles = {}
newcount=0
prev_file_time=0

for diskusage_file in diskusage_files:
        t_start = diskusage_file.name[-13:]
        file_start_time = filetstamp_to_epoch(t_start)
        if not start_ctime:
           start_ctime = file_start_time
        offset = (file_start_time - start_ctime)/60.0
    
        if not prev_file_time:
           prev_file_time=file_start_time

        prevdiff = (file_start_time - prev_file_time)/60.0
        offset=0

        if prevdiff > rotate_interval:
           offset=prevdiff-rotate_interval

        count1 = 0
        count = 0
        for line in diskusage_file.xreadlines():
            if line == '':
                continue
            if line[0] != '/':
                if line[:4] == 'Date':
                   count1 += 1
                   newcount += 1
                continue

            newval=newcount*DB_poll_interval*60
            newval += offset
            newval += start_ctime
            newval = time.strftime('%Y/%m/%d %H:%M:%S', time.localtime(newval))

            line = line.split()
            try:
                 partition_name = line[5][1:]
                 partition_name = partition_name.replace('/','_')
                 partition_name = 'du_'+partition_name
            except:
                 print "data incomplete in "+str(diskusage_file)+""
                 a = ''
            if not dufiles.has_key(partition_name):
                 dufiles[partition_name] = open(working_dir+"/"+partition_name,'w')
            try:
                 print >> dufiles[partition_name],newval, line[4][:-1]
            except:
                 print "data incomplete in "+str(diskusage_file)+""
                 a = ''
            count += 1
        prev_file_time=file_start_time

plotlist = []
for dufile in dufiles.values():
        plotlist.append((dufile.name, '/'+dufile.name.split('/')[-1][3:].replace('_','/')))
        dufile.close()

if plotlist != []:
        print "Generating plots."
        plotlib.plotfile(systemval,plotlist,\
           'Partition Usage (%)','Date & Time','diskusage')

print """
      Analysing Netstat usage reports may take more time
"""
Status = raw_input('Do you wish to Continue[Y|N]:').strip('\n')
if Status != 'Y' and Status != 'y':
   print "Ignoring Analysing netstat usage reports"
else:
   print "Analysing netstat usage reports."
   netstat_files = [open(working_dir+'/'+x) for x in file_list if x[:8] == 'netstat_']
   netstat_id = []

   for netstat_file in netstat_files:
      t_file = netstat_file.name[:-14].split('/')[2]
      if t_file not in netstat_id:
         netstat_id.append(t_file)

   for netstat_fileid in netstat_id:
      start_ctime = 0
      establish_count_outgoing = {} 
      timewait_count_outgoing = {}
      closewait_count_outgoing = {}
      establish_count_incoming = {}
      timewait_count_incoming = {}
      closewait_count_incoming = {}
      establish_incoming = {}
      establish_outgoing = {}
      timewait_incoming = {}
      timewait_outgoing = {}
      closewait_incoming = {}
      closewait_outgoing = {}
      newcount=0
      count = 0
      prev_file_time=0

      for netstat_file in netstat_files:
         t_start = netstat_file.name[-13:]
         t_file = netstat_file.name[:-14].split('/')[2]
         if t_file != netstat_fileid:
            continue

         file_start_time = filetstamp_to_epoch(t_start)
         if not start_ctime:
            start_ctime = file_start_time
         offset = (file_start_time - start_ctime)/60.0

         if not prev_file_time:
            prev_file_time=file_start_time

         prevdiff = (file_start_time - prev_file_time)/60.0
         offset=0

         if prevdiff > rotate_interval:
            offset=prevdiff-rotate_interval

         for line in netstat_file.xreadlines():
            if line == '':
                continue
            if line[:4] == 'Date':
               flag = 1
               count = count + 1
            matchObj = re.match(r".*[\s|:](\d+\.\d+\.\d+\.\d+):(\d+)\s+.*[\s|:](\d+\.\d+\.\d+\.\d+):(\d+)\s+(\w+)\s+.*",line,re.M)
            if matchObj:
               if matchObj.group(5) != 'ESTABLISHED' and matchObj.group(5) != 'TIME_WAIT' and matchObj.group(5) != 'CLOSE_WAIT':
                   continue 
               portnumber_in = matchObj.group(2)
               portnumber_out = matchObj.group(4)
               if matchObj.group(3) not in IParray and IPFlag == 0:
                  IParray.append(matchObj.group(3))
            else:
               continue 

            if flag == 1:
               newval=newcount*DB_poll_interval*60
               newval += offset
               newval += start_ctime
               newval = time.strftime('%Y/%m/%d %H:%M:%S', time.localtime(newval))
               if count > 1:
                   for port in portarray:
                       for IPAddress in IParray:
                           port = int(port)
                           portaddress = str(port) + "_" + IPAddress
                           establish_incoming[portaddress] = open(working_dir+"/Established_incoming_"+IPAddress+"_"+str(port)+"",'a')
                           closewait_incoming[portaddress] = open(working_dir+"/CloseWait_incoming_"+IPAddress+"_"+str(port)+"",'a')
                           timewait_incoming[portaddress] = open(working_dir+"/Timewait_incoming_"+IPAddress+"_"+str(port)+"",'a')
                           establish_outgoing[portaddress] = open(working_dir+"/Established_outgoing_"+IPAddress+"_"+str(port)+"",'a')
                           closewait_outgoing[portaddress] = open(working_dir+"/CloseWait_outgoing_"+IPAddress+"_"+str(port)+"",'a')
                           timewait_outgoing[portaddress] = open(working_dir+"/Timewait_outgoing_"+IPAddress+"_"+str(port)+"",'a')
                           if portaddress not in establish_count_incoming.keys():
                                 establish_count_incoming[portaddress] = 0
                           print >> establish_incoming[portaddress],newval,establish_count_incoming[portaddress]
                           if portaddress not in closewait_count_incoming.keys():
                                 closewait_count_incoming[portaddress] = 0
                           print >> closewait_incoming[portaddress],newval,closewait_count_incoming[portaddress]
                           if portaddress not in timewait_count_incoming.keys():
                                 timewait_count_incoming[portaddress] = 0
                           print >> timewait_incoming[portaddress],newval,timewait_count_incoming[portaddress]
                           if portaddress not in establish_count_outgoing.keys():
                                 establish_count_outgoing[portaddress] = 0
                           print >> establish_outgoing[portaddress],newval,establish_count_outgoing[portaddress]
                           if portaddress not in closewait_count_outgoing.keys():
                                 closewait_count_outgoing[portaddress] = 0
                           print >> closewait_outgoing[portaddress],newval,closewait_count_outgoing[portaddress]
                           if portaddress not in timewait_count_outgoing.keys():
                                 timewait_count_outgoing[portaddress] = 0
                           print >> timewait_outgoing[portaddress],newval,timewait_count_outgoing[portaddress]
               newcount += 1
      
            for port in portarray:
                   for IPAddress in IParray:
                       portnumber_in = int(portnumber_in)
                       portnumber_out = int(portnumber_out)
                       port = int(port)
                       portaddress = str(port) + "_" + IPAddress
                       if flag == 1:
                           establish_count_incoming[portaddress] = 0
                           timewait_count_incoming[portaddress] = 0
                           closewait_count_incoming[portaddress] = 0
                           establish_count_outgoing[portaddress] = 0
                           timewait_count_outgoing[portaddress] = 0
                           closewait_count_outgoing[portaddress] = 0
                 
                       if portnumber_in == port and IPAddress == matchObj.group(3):
                           if matchObj.group(5) == 'ESTABLISHED':
                               if portaddress not in establish_count_incoming.keys():
                                   establish_count_incoming[portaddress] = 0
                               establish_count_incoming[portaddress]  = establish_count_incoming[portaddress] + 1
                           if matchObj.group(4) == 'TIME_WAIT':
                               if portaddress not in timewait_count_incoming.keys():
                                   timewait_count_incoming[portaddress] = 0  
                               timewait_count_incoming[portaddress]  =  timewait_count_incoming[portaddress] + 1
                           if matchObj.group(4) == 'CLOSE_WAIT':
                               if portaddress not in closewait_count_incoming.keys():
                                   closewait_count_incoming[portaddress] = 0  
                               closewait_count_incoming[portaddress]  =  closewait_count_incoming[portaddress] + 1

                       if portnumber_out == port and IPAddress == matchObj.group(3):
                           if matchObj.group(5) == 'ESTABLISHED':
                               if portaddress not in establish_count_outgoing.keys():
                                   establish_count_outgoing[portaddress] = 0
                               establish_count_outgoing[portaddress]  = establish_count_outgoing[portaddress] + 1
                           if matchObj.group(4) == 'TIME_WAIT':
                               if portaddress not in timewait_count_outgoing.keys():
                                   timewait_count_outgoing[portaddress] = 0
                               timewait_count_outgoing[portaddress]  =  timewait_count_outgoing[portaddress] + 1
                           if matchObj.group(4) == 'CLOSE_WAIT':
                               if portaddress not in closewait_count_outgoing.keys():
                                   closewait_count_outgoing[portaddress] = 0
                               closewait_count_outgoing[portaddress]  =  closewait_count_outgoing[portaddress] + 1

            flag = 0
         prev_file_time=file_start_time

   for port in portarray:
         port = str(port)
         i = 1
         j = 1
         k = 1
         plotlist = []
         for dufile in establish_incoming.values():
             matchObj = re.match(r".*_"+port+"$",dufile.name,re.M)
             if matchObj:
                plotlist.append((dufile.name, dufile.name.split('/')[-1]))
                dufile.close()
      
                if i%5 == 0:
                    if plotlist != []:
                       print "Generating plots for Establish Incoming "+port+" "+str(j)+" ."
                       Netstat_Incoming_Established = "Netstat_Incoming_Established_"+port+"_"+ str(j)
                       plotlib.plotfile(systemval,plotlist,\
                          'No of connections','Date & Time',Netstat_Incoming_Established)
                       j = j +1 
                       plotlist = []
                i = i +1
             if k - len(establish_incoming.keys()) == 0:
                if plotlist != []:
                   print "Generating plots for Establish Incoming "+port+" "+str(j)+" ."
                   Netstat_Incoming_Established = "Netstat_Incoming_Established_"+port+"_" + str(j)
                   plotlib.plotfile(systemval,plotlist,\
                      'No of connections','Date & Time',Netstat_Incoming_Established)
             k = k +1;

         i = 1
         j = 1
         k = 1
         plotlist = []
         for dufile in closewait_incoming.values():
             matchObj = re.match(r".*_"+port+"$",dufile.name,re.M)
             if matchObj:
                plotlist.append((dufile.name, dufile.name.split('/')[-1]))
                dufile.close()

                if i%5 == 0:
                    if plotlist != []:
                       print "Generating plots for Closewait Incoming "+port+" "+str(j)+" ."
                       Netstat_Incoming_Closewait = "Netstat_Incoming_Closewait_"+port+"_" + str(j)
                       plotlib.plotfile(systemval,plotlist,\
                           'No of connections','Date & Time',Netstat_Incoming_Closewait)
                       j = j +1
                       plotlist = []
                i = i +1
             if k - len(closewait_incoming.keys()) == 0:
                if plotlist != []:
                   print "Generating plots for Closewait Incoming "+port+" "+str(j)+" ."
                   Netstat_Incoming_Closewait = "Netstat_Incoming_Closewait_"+port+"_" + str(j)
                   plotlib.plotfile(systemval,plotlist,\
                       'No of connections','Date & Time',Netstat_Incoming_Closewait)
             k = k +1;

         i = 1
         j = 1
         k = 1
         plotlist = []
         for dufile in timewait_incoming.values():
             matchObj = re.match(r".*_"+port+"$",dufile.name,re.M)
             if matchObj:
                plotlist.append((dufile.name, dufile.name.split('/')[-1]))
                dufile.close()

                if i%5 == 0:
                    if plotlist != []:
                       print "Generating plots for Timewait Incoming "+port+" "+str(j)+" ."
                       Netstat_Incoming_Timewait = "Netstat_Incoming_Timewait_"+port+"_" + str(j)
                       plotlib.plotfile(systemval,plotlist,\
                           'No of connections','Date & Time',Netstat_Incoming_Timewait)
                       j = j +1
                       plotlist = []
                i = i +1
             if k - len(timewait_incoming.keys()) == 0:
                if plotlist != []:
                   print "Generating plots for Timewait Incoming "+port+" "+str(j)+" ."
                   Netstat_Incoming_Timewait = "Netstat_Incoming_Timewait_"+port+"_" + str(j)
                   plotlib.plotfile(systemval,plotlist,\
                       'No of connections','Date & Time',Netstat_Incoming_Timewait)
             k = k +1;

         i = 1
         j = 1
         k = 1
         plotlist = []
         for dufile in establish_outgoing.values():
             matchObj = re.match(r".*_"+port+"$",dufile.name,re.M)
             if matchObj:
                plotlist.append((dufile.name, dufile.name.split('/')[-1]))
                dufile.close()

                if i%5 == 0:
                    if plotlist != []:
                       print "Generating plots for Establish Outgoing "+port+" "+str(j)+" ."
                       Netstat_Outgoing_Established = "Netstat_Outgoing_Established_"+port+"_" + str(j)
                       plotlib.plotfile(systemval,plotlist,\
                           'No of connections','Date & Time',Netstat_Outgoing_Established)
                       j = j +1
                       plotlist = []
                i = i +1
             if k - len(establish_outgoing.keys()) == 0:
                if plotlist != []:
                   print "Generating plots for Establish Outgoing "+port+" "+str(j)+" ."
                   Netstat_Outgoing_Established = "Netstat_Outgoing_Established_"+port+"_" + str(j)
                   plotlib.plotfile(systemval,plotlist,\
                      'No of connections','Date & Time',Netstat_Outgoing_Established)
             k = k +1;

         i = 1
         j = 1
         k = 1
         plotlist = []
         for dufile in closewait_outgoing.values():
             matchObj = re.match(r".*_"+port+"$",dufile.name,re.M)
             if matchObj:
                plotlist.append((dufile.name, dufile.name.split('/')[-1]))
                dufile.close()
 
                if i%5 == 0:
                    if plotlist != []:
                       print "Generating plots for Closewait Outgoing "+port+" "+str(j)+" ."
                       Netstat_Outgoing_Closewait = "Netstat_Outgoing_Closewait_"+port+"_"  + str(j)
                       plotlib.plotfile(systemval,plotlist,\
                           'No of connections','Date & Time',Netstat_Outgoing_Closewait)
                       j = j +1
                       plotlist = []
                i = i +1
             if k - len(closewait_outgoing.keys()) == 0:
                if plotlist != []:
                   print "Generating plots for Closewait Outgoing "+port+" "+str(j)+" ."
                   Netstat_Outgoing_Closewait = "Netstat_Outgoing_Closewait_"+port+"_" + str(j)
                   plotlib.plotfile(systemval,plotlist,\
                      'No of connections','Date & Time',Netstat_Outgoing_Closewait)
             k = k +1;

         i = 1
         j = 1
         k = 1
         plotlist = []
         for dufile in timewait_outgoing.values():
             matchObj = re.match(r".*_"+port+"$",dufile.name,re.M)
             if matchObj:
                plotlist.append((dufile.name, dufile.name.split('/')[-1]))
                dufile.close()

                if i%5 == 0:
                    if plotlist != []:
                       print "Generating plots for Timewait Outgoing "+port+" "+str(j)+" ."
                       Netstat_Outgoing_Timewait = "Netstat_Outgoing_Timewait_"+port+"_" + str(j)
                       plotlib.plotfile(systemval,plotlist,\
                         'No of connections','Date & Time',Netstat_Outgoing_Timewait)
                       j = j +1
                       plotlist = []
                i = i +1
             if k - len(timewait_outgoing.keys()) == 0:
                if plotlist != []:
                   print "Generating plots for Timewait Outgoing "+port+" "+str(j)+" ."
                   Netstat_Outgoing_Timewait = "Netstat_Outgoing_Timewait_"+port+"_" + str(j)
                   plotlib.plotfile(systemval,plotlist,\
                      'No of connections','Date & Time',Netstat_Outgoing_Timewait)
             k = k +1;

print """
      Analysing iotop usage reports may take more time
"""
Status = raw_input('Do you wish to Continue[Y|N]:').strip('\n')
if Status != 'Y' and Status != 'y':
   print "Ignoring Analysing iotop usage reports"
   sys.exit()

#iotop usage plots
print "Analysing iotop usage reports."
iotop_files = [open(working_dir+'/'+x) for x in file_list if x[:12] == 'iotopoutput_']
iotopfilesRead = {}
iotopfilesWrite = {}
iotopfilesSwap = {}
iotopfilesIO = {}
newcount=0
dic = { "B" : 1, "K" : 1000, "M" : 1000000 }

for name in ProcessName:
  iotopfilesRead[name] = open(working_dir+"/IOTopRead_"+name+"",'a')
  iotopfilesWrite[name] = open(working_dir+"/IOTopWrite_"+name+"",'a')
  iotopfilesSwap[name] = open(working_dir+"/IOTopSwap_"+name+"",'a')
  iotopfilesIO[name] = open(working_dir+"/IOTopIO_"+name+"",'a')

ProcessNameTemp = '|'.join(ProcessName)
for iotop_file in iotop_files:
	iotop_file_temp = iotop_file.name
	t_start = iotop_file.name[-13:]
	t_file = iotop_file.name[:-14].split('/')[2]
    
	file_start_time = filetstamp_to_epoch(t_start)
	if not start_ctime:
             start_ctime = file_start_time
	offset = (file_start_time - start_ctime)/60.0

	if not prev_file_time:
             prev_file_time=file_start_time

	prevdiff = (file_start_time - prev_file_time)/60.0
	offset=0

	if prevdiff > rotate_interval:
             offset=prevdiff-rotate_interval

	count = 0
	previousindex = 0
	Capturestartline = commands.getoutput("grep -n \"Total DISK READ:\" "+iotop_file_temp+" | cut -d \":\" -f1").split('\n')
	if not Capturestartline:
	   continue 

	Capturestartline.append("-1")
	f = open(iotop_file_temp, "r")
	StartlinesArray = f.readlines()
	f.close()

	for index in Capturestartline:
	   if count == 0:
	      count = count + 1
	      previousindex = index
	      continue
	   if index == -1:
	      BlockLines = StartlinesArray[int(previousindex):]
	   else:
	      BlockLines = StartlinesArray[int(previousindex):int(index)]
	   if len(BlockLines) == 0:
		  continue					   
	   newval=newcount*System_poll_interval*60
	   newval += offset
	   newval += start_ctime
	   newval = time.strftime('%Y/%m/%d %H:%M:%S', time.localtime(newval))
	   newcount += 1
	   SumReadProcess = {}
	   SumWriteProcess = {}
	   SumSwapProcess = {}
	   SumIOProcess = {}
	   for blockline in BlockLines:
		     matchObj = re.match(r".*\s+(.*)\s+(B|M|K)\/s\s+(.*)\s+(B|M|K)\/s\s+(.*)\s+%\s+(.*)\s+%\s+("+ProcessNameTemp+")\s+.*",blockline,re.M)
		     if matchObj:
			    Read = float(matchObj.group(1))
			    ReadStr = str(matchObj.group(2))
			    write = float(matchObj.group(3))
			    writeStr = str(matchObj.group(4))
			    swap = float(matchObj.group(5))
			    io = float(matchObj.group(6))
			    name = str(matchObj.group(7))
			   
			    Readtemp = Read/dic[ReadStr];
			    writetemp = write/dic[writeStr];

			    if name in SumReadProcess.keys():
				   SumReadProcess[name] = SumReadProcess[name]+ Readtemp
				   SumWriteProcess[name] = SumWriteProcess[name]+ writetemp
				   SumSwapProcess[name] = SumSwapProcess[name]+ swap
				   SumIOProcess[name] = SumIOProcess[name]+ io
			    else:
				   SumReadProcess[name] = Readtemp 
				   SumWriteProcess[name] = writetemp
				   SumSwapProcess[name] = swap
				   SumIOProcess[name] = io
        
	   for name in ProcessName:
	      if name in SumReadProcess.keys():
			 print >> iotopfilesRead[name],newval,SumReadProcess[name]
			 print >> iotopfilesWrite[name],newval,SumWriteProcess[name]
			 print >> iotopfilesSwap[name],newval,SumSwapProcess[name]
			 print >> iotopfilesIO[name],newval,SumIOProcess[name]
	      else:
		     print >> iotopfilesRead[name],newval,0 
		     print >> iotopfilesWrite[name],newval,0 
		     print >> iotopfilesSwap[name],newval,0 
		     print >> iotopfilesIO[name],newval,0 
	   previousindex = index
	   count = count + 1
	prev_file_time=file_start_time 

i = 1
j = 1
plotlist = []
for dufile in iotopfilesRead.values():
	plotlist.append((dufile.name, dufile.name.split('/')[-1]))
	dufile.close()
	if i%5 == 0:
	   if plotlist != []:
	      print "Generating plots for IOTOP Read"
	      ReadBytes = "IOTOP_Read_Bytes_"+str(j)
	      plotlib.plotfile(systemval,plotlist,\
				'No of Read Bytes','Date & Time',ReadBytes)
	      j = j + 1 
	      plotlist = []
	i = i + 1

i = 1
j = 1
plotlist = []
for dufile in iotopfilesWrite.values():
	plotlist.append((dufile.name, dufile.name.split('/')[-1]))
	dufile.close()
	if i%5 == 0:
	   if plotlist != []:
	      print "Generating plots for IOTOP Write"
	      WriteBytes = "IOTOP_Write_Bytes_"+str(j)
	      plotlib.plotfile(systemval,plotlist,\
				'No of Write Bytes','Date & Time',WriteBytes)
	      j = j + 1 
	      plotlist = []
	i = i + 1

i = 1
j = 1
plotlist = []
for dufile in iotopfilesSwap.values():
	plotlist.append((dufile.name, dufile.name.split('/')[-1]))
	dufile.close()
	if i%5 == 0:
	   if plotlist != []:
	      print "Generating plots for IOTOP Swap"
	      SwapBytes = "IOTOP_Swap_Bytes_"+str(j)
	      plotlib.plotfile(systemval,plotlist,\
				'% of Swap Bytes','Date & Time',SwapBytes)
	      j = j + 1 
	      plotlist = []
	i = i + 1

i = 1
j = 1
plotlist = []
for dufile in iotopfilesIO.values():
	plotlist.append((dufile.name, dufile.name.split('/')[-1]))
	dufile.close()
	if i%5 == 0:
	   if plotlist != []:
	      print "Generating plots for IOTOP IO"
	      IOBytes = "IOTOP_IO_Bytes_"+str(j)
	      plotlib.plotfile(systemval,plotlist,\
				'% of IO Bytes','Date & Time',IOBytes)
	      j = j + 1 
	      plotlist = []
	i = i + 1

