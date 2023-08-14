"""
 This script collects a bunch of system data and generates
 compressed reports. Another script (sysreport.py) reads this 
 data and creates plots.

 Parameters reported currently include - 
    (Statistics : report-filename)
    * Per process statistics                          : process_yymmdd_hhmmss
        -CPU Usage
        -Memory Usage 
        -Number of threads
    * Output of iostat -x (disk bandwidth statistics) : iostat_yymmdd_hhmmss
    * Disk usage (output of df -k)                    : disk_usage_yymmdd_hhmmss
    * ttstatus Output (output of ttstatus)               : ttstatus_yymmdd_hhmmss
    * Database capacity utlization (dssize output)    : dssize_yymmdd_hhmmss
    * Data directory listing (ls -l /Database)    : datadir_yymmdd_hhmmss
    * top sample output (top -b -n 2)                 : topout_yymmdd_hhmmss
    * Process wait state (ps -emo pid,ppid,cmd,wchan) : wchan_yymmdd_hhmmss
    * Netstat output (netstat -anpt) for media card   : netstat_yymmdd_hhmmss
    * Netstat output (netstat -anp) for other than media card   : netstat_yymmdd_hhmmss

 The timestamp in the file-name is the time at which the file was
 opened. Samples are added every sampling interval. The sampling interval
 is configurable.

 At the end of a rotation interval, all current files are archived and
 gzipped into a file with name reports_yymmdd_hhmmss.tgz. The time-stamp
 shows the time at which the files were archived.

 To analyze reports after a crash, copy the reports_...tgz files at around
 the time of the crash along with any of the individual files that could
 not be tarred up due to the crash. Use the time-stamp suffixes to identify
 files generated at around the time of the incident. 
 
 Use sysreport.py to generate plots.
"""

import sys
import os
import commands
import time
import os.path
import re
import array
sys.path.append('/DG/activeRelease/rtxlib/pytten')
sys.path.append('/DG/activeRelease/lib/pytten')
import traceback
import pyttenremote

if os.path.isfile('/etc/kodiakDG.conf'):      
   import pytten

##############################################
# CUSTOMIZABLE PARAMETERS
##############################################

# The following parameters can be modified to alter the
# behaviour of this script. In additions to the parameters
# in this section, you can also modify the monitored_data
# map at the end of the script to add new parameters that
# need to be monitored periodically.

# This script has to periodically obtain a list of process IDs
# that belong to a given process. This is a CPU intensive task.
# If you want accurate per process statistics, set this to 1 so
# that the script gets a PID listing at every sampling.
# If the processes being monitored are long lived and do not
# spawn new threads often, use a higher value like 10 so that
# the script updates the PIDs once in every 10 samplings.
update_samples = 1
# Log rotation interval in seconds. Default - 3600s = 1 hour
rotate_interval = 3600 
# Number of days for which log files have to be retained.
# The script will delete older log files to conserve disk space.
retain_days = 5
# Default sampling interval for process related snapshot - 120 seconds = 2 minutes
Process_poll_interval = 120
# Default sampling interval for DB snapshot -- 900 seconds = 15 minutes
DB_poll_interval = 900
# Default sampling interval for system related snapshot -- 240 seconds = 4 minutes
System_poll_interval = 240
# Measuring per process statistics can be CPU intensive.
# To avoid usage spikes, we stagger the process measurements
# so that the load is uniformly distributed. The default
# is to measure process parameters staggered by 2 seconds
# per process group.
stagger_delay = 2
# Set this to 0 to disable per process statistics.
process_monitoring = 1
# CPU Limit For which Thread Dump can be taken.
CPULimitForThresholdDump = 70
#Flag to specify to take Thread Dump  
ThreadDumpFlag = 0

# Default location for the monitor logs
monitor_log_directory = "/DGlogs/sysMonitorSnapshot"
OSBit = 32

# The names of processes for which process-specific monitoring
# is to be done. We will have CPU, memory and thread data for
# these processes.
process_sets = {
    'rtx':[
        'java',
        'timestenrepd',
        'timestensubd',
        'timestend',
        'ttcserver',
        'children(ArchiveLogs.sh)',
        'children(ttDGDBBackup)',
        'python2.6',
        'python2.7',
        'self',
        ],
    'ems':[
        'children(startxla.sh)',
        'children(startsm.sh)',
        'children(startnms.sh)',
        'children(ArchiveLogs.sh)',
        'children(ttDBBackup)',
        'rmiregistry',
        'Naming_Service',
	'kodiakDBMonitor',
        'timestenrepd',
        'timestensubd',
        'timestend',
        'ttcserver',
        'python2.6',
        'python2.7',
        'self',
        ]
    }

# The script depends on process counters to determine the
# CPU usage. The kernel reports two types of CPU times
# per thread/process -
# * The CPU time used by the thread/process
# * The CPU time used by all threads/processes spawned by it
# The time used by a spawned process is added to the parent
# only when it exits. In this script, we normally consider
# this time also. This increases the accurace of the CPU
# usage if the process spawns sub-tasks to complete small
# jobs. This can create problems however if the threads spawned
# execute for a couple of minutes and then terminate. In that
# case, CPU usage of the parent thread will show an abnormal
# spike in usage when the thread terminates and skew the
# usage calculations. This happens often with EMS processes.
# For monitoring EMS like processes this option should be set
# to 0.
add_child_data = 1

RTX = ''
EMS = ''
ReleaseVal = 6

##############################################
# CUSTOMIZABLE PARAMETERS - END
##############################################


custom_parameter = ['update_samples','rotate_interval','retain_days','Process_poll_interval','stagger_delay','process_monitoring','monitor_log_directory','add_child_data','RTX','EMS','System_poll_interval','DB_poll_interval','CPULimitForThresholdDump','ThreadDumpFlag']

for keyparam in custom_parameter:
    string = keyparam
    if os.path.isfile('/DG/activeRelease/Tools/Fieldutils/customized_sysmonitor_parameter'):
       vars()[string] = commands.getoutput("grep -w "+keyparam+" /DG/activeRelease/Tools/Fieldutils/customized_sysmonitor_parameter|grep -v '#' |cut -f2 -d '='").strip()

update_samples  = int(update_samples)
rotate_interval = int(rotate_interval)
retain_days     = int(retain_days)
Process_poll_interval   = int(Process_poll_interval)
System_poll_interval   = int(System_poll_interval)
DB_poll_interval   = int(DB_poll_interval)
stagger_delay   = int(stagger_delay)
process_monitoring = int(process_monitoring)
CPULimitForThresholdDump = int(CPULimitForThresholdDump)
ThreadDumpFlag = int(ThreadDumpFlag)
add_child_data = int(add_child_data)

ReleaseValTemp=commands.getoutput("cat /etc/redhat-release | grep [7].[0-9]").strip()
if ReleaseValTemp != '':
   ReleaseVal = 7

if RTX != '':
    RTX = RTX.split(',')   
    for x in RTX: 
       process_sets["rtx"].append(x)
if EMS != '':
    EMS = EMS.split(',')
    for x in EMS:
       process_sets["ems"].append(x)

process_sets["rtx"] = set(process_sets["rtx"])
process_sets["rtx"] = list(process_sets["rtx"])
process_sets["ems"] = set(process_sets["ems"])
process_sets["ems"] = list(process_sets["ems"])
connectionstr = {}

#to write sysmonitor inforamation to respective log file,to avoid writing into log file if disk is full
def printlog(logfilename,logvalue):
    try:
        print >> log_manager.log_fd(logfilename),logvalue
    except:
        printlogt=0

def flushlog(flushlogname):
    try:
       log_manager.log_fd(flushlogname).flush() 
    except:
       printflusht=0

def db_fetch(query,dsn):
	LocalConn = getlocalconnection(dsn,0)
	try:
	   cur = LocalConn.cursor()
	   cur.execute(query)
	   return cur.fetchall()
	except (pyttenremote.DatabaseError,pytten.DatabaseError,Exception):
	   printlog('errors',"Process: %s."  % traceback.print_exc())
	   printlog('errors',"detail: Database connection failed for DSN %s" %dsn)
	   printlog('errors',"------------reconnect----------")
		  # Try a reconnect.
	   LocalConn = getlocalconnection(dsn,1)
	   connectionstr['Conn_%s' % dsn] = LocalConn
	   try:
	      cur = LocalConn.cursor()
	      cur.execute(query)
	      return cur.fetchall()
	   except:
	      printlog('errors',"After Re-Connect Featch detail: Database connection failed for DSN %s" %dsn)

def getlocalconnection(dsn, reconnect):
	if connectionstr.has_key('Conn_%s' % dsn) and reconnect == 0:
	   return connectionstr['Conn_%s' % dsn] 
	try:
	   printlog('errors',"After Re-Connect trying: Database connection failed for DSN %s" %dsn) 
	   if os.path.isfile('/etc/kodiakDG.conf'):      
	      local_connection = pytten.connect('DSN='+dsn)
	   else:
		  dsn = 'TTC_Server=127.0.0.1;TTC_Server_DSN='+dsn+';uid=timesten;pwd=public;tcp_port=53389'
		  local_connection = pyttenremote.connect(dsn)
	   return local_connection
	except:
          printlog('errors',"Reconnect detail: Database connection failed for DSN %s" %dsn)

def disconnectDB(Conn):
	    Conn.disconnect()

class LogManager:
    "A log-file allocator that allocates file-names and manages "
    "log rotation."

    def __init__(self):
        self.file_map = {}
        os.system('mkdir perfreports 2>/dev/null')

    def log_fd(self,name):
        "Returns a file object give a log-name. Log-name can be "
        "a word like 'topdata' in which case a file of the form "
        "topdata_yymmdd_hhmmss is returned."
        if self.file_map.has_key(name):
            return self.file_map[name]
        else:
            fd = open(self.get_log_name(name),'w')
            self.file_map[name] = fd
            return fd


    def get_log_name(self,name):
        return 'perfreports/'+name+time.strftime("_%y%m%d_%H%M%S")

    def rotate(self):
        "Called to close the current logs. Returns a list of "
        "names of the closed log files. Also deletes files from "
        "the perfreports directory that are older than retain-period."
        files_closed = []
        for file in self.file_map.values():
            files_closed.append(file.name)
            try:
                file.close()
            except:
                fileclosevar = 0
        self.file_map = {}
        # Remove files older than retain-period
        os.system('rm `find perfreports/ -mtime +%d 2>/dev/null` 2>/dev/null'\
            % retain_days)
        return files_closed

def get_children(pname, shell_script=1):
    "This function is used to track processes that have been spawned "
    "from a shell script. It can also be used to track all child processes "
    "of a given pid (if shell_script is 0, pname is assumed to be a PID file). "
    "A list of PIDs of children, grandchildren, great-grandchildren, ... is "
    "returned. Note that the list contains PIDs are strings."
    track_pid = None
    if shell_script:
        print pname
    else:
        # Get the PID of the process to be tracked from file.
        try:
            track_pid = open(pname).readline().strip()
        except:
            print "Could not open", pname
            return []
    # Get all process IDs along with their parent process IDs
    # and file-names.
    out = commands.getoutput('ps -emo pid,ppid,cmd')
    out = out.split('\n')[1:]
    # out is now a list of 'pid, ppid, fname'
    # Construct graph of processes
    # pid_map will have process-ID as the key. The value will
    # be a list of the key's child process-IDs.
    pid_map = {}
    for line in out:
        lsplit = line.split()
        # Get the PID, PPID and command name
        # from the ps listing
        pid,ppid,cmd = lsplit[0:3]
        if shell_script:
            if re.search(pname,line):
                # Get the PID of the shell script.
                # This is the PID we need to track.
                track_pid = pid
        # Populate the PID map. Each PID key will have a list
        # of its children as the value.
        if pid_map.has_key(ppid):
            pid_map[ppid].append(pid)
        else:
            pid_map[ppid] = [pid]
    if not track_pid:
        # We could not locate the process we were supposed to
        # track.
        return []
    # Now that we have a graph that maps a PID to it's 
    # immediate descendants, we need to get all of the tracked PIDs
    # children, grand-children and so on.
    pid_list = []
    def process_node(pid):
        'Function to recursively track down all descendants of a PID'
        pid_list.append(pid)
        if pid_map.has_key(pid):
            for child_pid in pid_map[pid]:
                process_node(child_pid)
    # Call the private function to populate pid_list
    process_node(track_pid)
    # We are done!
    return pid_list

class ThreadData:
    "Contains data pertaining to a single thread. The last recorded "\
    "CPU usage percentage, recording time and last recorded CPU time "\
    "are stored."

    def __init__(self,num_processors):
        self.num_processors = num_processors
        self.count_total = 0
        self.last_record_time = 0
        self.percentage = 0
        self.thread_count = 0
        
    def update(self,reading_time,procline):
        "Updates the thread's usage values using the supplied reading-time "\
        "and line from the thread's stat file."

        # Fields 14,15,16 and 17 contain the CPU usage times.
        if add_child_data:
            time_data = [int(x) for x in procline[13:17]]
        else:
            time_data = [int(x) for x in procline[13:15]]

        self.thread_count = int(procline[19])

        total = 0
        for val in time_data:
            total += val
        if self.last_record_time == 0:
            # First reading - usage percentage cannot be calculated now.
            self.last_record_time = reading_time
            self.count_total = total
        elif reading_time != self.last_record_time:
            # Get the time difference in the recording interval and calculate
            # the thread's CPU usage percentage.
            diff = total - self.count_total
            if diff < 0:
               diff = 0 
            self.percentage = diff/(reading_time - self.last_record_time)/\
                self.num_processors
            # Store the new total and the reading for the next calculation.
            self.last_record_time = reading_time
            self.count_total = total

class ProcessData:
    "Maintains data for an entire process (all threads of the process)."

    def __init__(self,num_processors,name,procps_patched):
        self.num_processors = num_processors
        self.name = name
        self.procps_patched = procps_patched
        # Map of the thread PID and it's ThreadData structure
        self.thread_data = {}
        self.main_thread_id = None
        # Process VM size and RSS
        self.vmsize = 0
        self.FDCount = 0
        self.rss = 0
        self.private_writable_mem = 0
        self.reading_time = 0
        self.total_percentage = 0
        self.threadscount = 0
        # Stores the number of CPU usage updates done for the process.
        # Used to trigger periodic PID updates for the process.
        self.updates = 0
        # Get all PIDs of the threads of this process and create the
        # thread-data structures for them
        self.update_pids()

    def update_pids(self):
        "Gets the PIDs of the threads belonging to the process. Creates "\
        "thread-data structures for tracking new threads. Deletes tracking "\
        "structures for threads that have died."
        # Use pgrep to get the PIDs of the threads. More efficient than
        # scanning the entire procfs files ourselves.
        if self.name == 'self':
            pids = [os.getpid()]
        elif self.name.find('children(') != -1:
            # Extract the name of the shell script
            shell_script_name = self.name.split('(')[1][:-1]
            # Get all children, grandchildren, ...
            pids = get_children(shell_script_name)
          
            try:
                pids = [int(x) for x in pids]
            except:
                pids = []
        elif self.name.find('pidfile(') != -1:
            pid_file_name = self.name.split('(')[1][:-1]
            pids = get_children(pid_file_name, 0)
            try:
                pids = [int(x) for x in pids]
            except:
                pids = []
	elif self.name.find('proc(') != -1:
	    pid_file_name = self.name.split('(')[1][:-1]
	    try:
	        pids = [int(x) for x in\
		    commands.getoutput("ps -ef | grep "+pid_file_name+" | grep -v grep | awk '{print $2}'").split()]
	    except:
		pids = []
        else:
		if OSBit == "64":
                	pids = [int(x) for x in \
                    		commands.getoutput("pgrep %s" % (self.name[0:15])).split()]
		else:
                	pids = [int(x) for x in \
                    		commands.getoutput("ps -mC %s --no-headers | "\
                    		"awk '{print $1}'" % (self.name)).split()]
        if len(pids) == 0:
             printlog('errors',"Process: %s. No threads found."  % self.name)    
             self.main_thread_id = -1
        else:
            if add_child_data:
                # Use the last thread-ID in the list for mapping the
                # the memory usage of the process. This is done since
                # many RTX processes have a dummy outer process to
                # communicate with the platform.
                self.main_thread_id = pids[-1]
            else:
                # In this mode we are monitoring a process that has
                # many short-lived threads. It's better to use one
                # of the IDs at the beginning for getting memory usage.
                if len(pids) > 1:
                    self.main_thread_id = pids[1]
                else:
                    self.main_thread_id = pids[0]
        existing_threads = self.thread_data.keys()[:]
        # Find threads which have died and remove their thread_data entries
        for thread_id in existing_threads:
            if pids.count(thread_id) == 0:
                try:
                    del self.thread_data[thread_id]
                except:
                    pass
        # Create ThreadData for new PIDs (PIDs that don't have a thread-data
        # structure in the map)
        for pid in pids:
            if not self.thread_data.has_key(pid):
                self.thread_data[pid] = ThreadData(self.num_processors)

    def update_data(self):
        # Increment the update-count. For every 10 updates, check if there
        # are any changes in the PIDs of the threads belonging to the process.
        self.reading_time = time.time()
        self.updates += 1
        if self.updates % update_samples == 0:
            self.update_pids()
        if self.main_thread_id == -1:
            self.total_percentage = 0
            self.private_writable_mem = 0
            self.rss = 0
            self.vmsize = 0
            self.FDCount = 0
            return
        # Update the thread data
        total_percentage = 0
        lthreads = 0
        for pid in self.thread_data.keys():
            # For each thread belonging to the process, read the
            # procfs stats for the thread and pass the data to the
            # thread-data class to update the thread's usage data.
            try:
                f = open('/proc/%d/stat' % pid)
                times = f.readline().split()
            except:
                continue
            self.thread_data[pid].update(self.reading_time,times)
            total_percentage += self.thread_data[pid].percentage

            lthreads += self.thread_data[pid].thread_count
        self.total_percentage = total_percentage
        self.threadscount=lthreads
	
        # Get the private writable memory available to the process.
        # This will be a better indication of the memory used by the 
        # process rather than the RSS or Size values in the proc file-system
        matchObj = re.match( r'.*children\(.*', self.name, re.M)
        if matchObj:
           self.private_writable_mem = 0
           for pid in self.thread_data.keys():
               pvtmemperpid = commands.getoutput\
                   ("(pmap -d %d 2>/dev/null || pmap %d 2>/dev/null) "\
                   "| egrep 'writ[e]?able/private' "\
                   "| awk -Fate: '{print $2}' | awk -FK '{print $1}'" %\
                   (pid,pid))
               try:
                  pvtmemperpid = int(pvtmemperpid)
               except:
                  pvtmemperpid = 0
               self.private_writable_mem = self.private_writable_mem + pvtmemperpid
        else:
           self.private_writable_mem = commands.getoutput\
               ("(pmap -d %d 2>/dev/null || pmap %d 2>/dev/null) "\
               "| egrep 'writ[e]?able/private' "\
               "| awk -Fate: '{print $2}' | awk -FK '{print $1}'" %\
               (self.main_thread_id, self.main_thread_id))
        try:
            self.private_writable_mem = int(self.private_writable_mem)
        except:
             printlog('errors',"Main thread (ID:%d) of process %s appears to have died." %  (self.main_thread_id, self.name))
             self.private_writable_mem = -1
        # Get the VmSize and VmRSS values
        try:
            # Get this from the status file of the last thread belonging
            # to the process. The memory usage figures need not be added
            # up. They will be same for all the threads.
            self.vmsize = 0
            self.rss = 0
            self.FDCount = 0
            matchObj = re.match( r'.*children\(.*', self.name, re.M)
            if matchObj:
               pidarray = self.thread_data.keys()
            else:
               pidarray = [ self.main_thread_id ]

            for pid in pidarray:
               self.FDCountTemp = commands.getoutput('ls -l /proc/%s/fd | wc -l' % pid)
               self.FDCountTemp = int(self.FDCountTemp)
               self.FDCount = self.FDCountTemp + self.FDCount
               f = open('/proc/%d/status' % pid)
               lines = f.readlines()
               for line in lines:
                   if line.find('VmSize')==0:
                       count,unit = line.split(':')[1].split()
                       count = int(count)
                       unit = unit.strip()
                       if unit == 'kB':
                          count *= 1000
                       vmsizeperpid = count/1000
                       self.vmsize = self.vmsize + vmsizeperpid
                   if line.find('VmRSS')==0:
                       count,unit = line.split(':')[1].split()
                       count = int(count)
                       unit = unit.strip()
                       if unit == 'kB':
                          count *= 1000
                       rsssizeperpid = count/1000
                       self.rss = self.rss + rsssizeperpid
        except:
            pass
     
    def get_stats(self):
        "Returns a printable line containing the reading time, process name, "\
        "memory statistics, overall CPU usage and the CPU usage breakup for "
        "the threads belonging to the process."
        # Compose the process level statistics.
        length = len(self.thread_data)
        if length > 1: 
          length = length - 1
        retstr = 'time:%f, name:%s, pvt-wr-mem: %d kB, cpu: %.3f, '\
            'rss: %d kB, vmsize: %d kB, threads: %d, ctime: %s, fdcount: %d' % \
            (self.reading_time,self.name,self.private_writable_mem,\
            self.total_percentage, self.rss, self.vmsize,
            self.threadscount, time.ctime(self.reading_time),self.FDCount)
       
        return retstr

    def GetThreadHeapDump(self):
        "Get heap Dump and Thread Dump for Java Related process."
        JavaHome=os.environ.get("JAVAHOME32")
        matchObj = re.match( r'.*(tomcat_instance|xdmstartup|activemq).*', self.name, re.M)
        if matchObj and self.total_percentage >= CPULimitForThresholdDump and ThreadDumpFlag == 1:
            printlog('ThreadDump',commands.getoutput("/DG/activeRelease/Tools/Fieldutils/ThreadDumpSnapshot.sh '"+self.name+"'"))
            flushlog('ThreadDump');

class ProcReader:
    "Contains a collection of processes being monitored for CPU and "\
    "memory usage."

    def __init__(self,num_processors,process_names,procps_patched):
        self.num_processors = num_processors
        self.process_names = [x for x in process_names if x[0] != '-']
        # Create the process data collecting class instance for each process
        self.processes = {}
        for process_name in self.process_names:
            self.processes[process_name] = ProcessData(self.num_processors,\
                process_name,procps_patched)
        self.current_process = 0
        self.num_processes = len(self.process_names)

    def update_data(self):
        "Updates statistics for each process and prints a line containing the "\
        "current data."
        process_data = self.processes.values()[self.current_process]
        process_data.update_data()
        printlog('processinfo',process_data.get_stats())    
        flushlog('processinfo');
        process_data.GetThreadHeapDump();
        
        self.current_process += 1
        if self.current_process == self.num_processes:
            self.current_process = 0

def get_cpu_info():
    "Gets the CPU model name and the number of processors on the system. "\
    "Returns (number of processors (int), model string)."
    model_name = ''
    num_processors = 0
    f = open('/proc/cpuinfo')
    lines = f.readlines()
    for line in lines:
        if line.find('model name') == 0:
            model_name = line.split(':')[1].strip()
        elif line.find('processor') == 0:
            num_processors += 1
    return num_processors,model_name

def start_continuous_data_monitoring(monitored_data,flag):
    log_file_names = []
    for data_file in monitored_data.keys():
        if data_file == 'heapinfo':
		   if HEAPFLAG == 0:
                      continue 
		   os.system('/DG/activeRelease/Tools/Fieldutils/heaprun.sh stop')
        else:
		   os.system('pkill -f "%s"' % monitored_data[data_file])
        log_file_name = log_manager.get_log_name(data_file)
        log_file_names.append(log_file_name)
        Actfilename = os.path.basename(log_file_name);
        if flag == 1:
           if data_file == 'heapinfo':
                       os.system(monitored_data[data_file]+' %s'%Actfilename)
           else:
                       os.system(monitored_data[data_file]+' > %s&'%log_file_name)
    return log_file_names
        
def get_system_type():
    # Check the type of system we are running on:
    # RTX, EMS
    # If command-line parameters are specified, use them
    retval = ''
    if len(sys.argv) > 1:
        if sys.argv.count('--ems') != 0:
            retval = 'ems'
        if sys.argv.count('--rtx') != 0:
            retval = 'rtx'
    else:
        # No command-line, let's check.
        if os.path.exists('/etc/kodiakEMS.conf'):
            retval = 'ems'
    # Assume RTX if none of the conditions are satisfied.
    if retval == '':
        retval = 'rtx'
    return retval

def get_rtx_dsn():
    pttid = commands.getoutput('cat /etc/kodiakDG.conf | grep \'\\<PTTSERVERID\'')
    try:
        pttid = pttid.split('=')[1].strip()
        dsn = 'DG_'+pttid
    except:
        printlog('monitor_log','Failed to get PTT server ID')
        dsn = ''
    return dsn


## get process list from startup.txt file
def getRTXProcList():
	proclist=commands.getoutput("awk -F, '{print $1}' /DG/activeRelease/dat/startup.txt 2>>/dev/null | awk -F= '{print $2}' | sed 's/ *\" *//g'")
	try:
		rtxplist=proclist.split()
	except:
            printlog('monitor_log','Failed to get RTX process list from startup.txt file')
	    rtxplist = []

	return rtxplist

def GetNewDBConection():
	for i in range(1,7):
		sds=('%s_%d') % (pttid,i)
		Key = 'Conn_'+ sds
    		if os.path.isfile( ('/Database/%s.ds0') % (sds) ):
                    if Key not in connectionstr:
                       ConnStr = getlocalconnection(sds,0)
                       connectionstr['Conn_%s' % sds] = ConnStr
                       DBSnapshot['ttlogholds_%s' % sds]='call ttbookmark; call ttlogholds;select to_char(sysdate),NAME,to_char(VALUE),to_char(SYS1),to_char(SYS2) from sys.systemstats'
                       DBSnapshot['DBSysMon_%s' % sds]='select * from sys.monitor'
                       DBSnapshot['dssize_%s' % sds]="select concat('PERM_ALLOCATED_SIZE=',to_char(PERM_ALLOCATED_SIZE)),concat('PERM_IN_USE_SIZE=',to_char(PERM_IN_USE_SIZE)),concat('PERM_IN_USE_HIGH_WATER=',to_char(PERM_IN_USE_HIGH_WATER)),concat('TEMP_ALLOCATED_SIZE=',to_char(TEMP_ALLOCATED_SIZE)),concat('TEMP_IN_USE_SIZE=',to_char(TEMP_IN_USE_SIZE)),concat('TEMP_IN_USE_HIGH_WATER=',to_char(TEMP_IN_USE_HIGH_WATER)),concat('LOG_BUFFER_WAITS=',to_char(LOG_BUFFER_WAITS)) from sys.monitor"
                       monitored_data['repadmin_%s' % sds]=('echo Date:;date;export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:'+\
                          '/opt/TimesTen/kodiak/lib;'+\
                          ' /opt/TimesTen/kodiak/bin/ttRepAdmin -dsn %s -receiver list') % (sds)
    		else:
                    if Key in connectionstr:
                       del connectionstr[Key]
                       del DBSnapshot['ttlogholds_%s' % sds]
                       del DBSnapshot['DBSysMon_%s' % sds]
                       del DBSnapshot['dssize_%s' % sds]
                       del monitored_data['repadmin_%s' % sds]
	
def check_system_configuration():
    processors, model_name = get_cpu_info()
    printlog('monitor_log',model_name)
    
    printlog('monitor_log',"Processors: "+str(processors)+"")
    # Our results also depend on the version of the process
    # monitoring tools on the system.
    procps_version = commands.getoutput('rpm -q procps').strip()
    printlog('monitor_log',procps_version)
    matchObj = re.match( r'procps', procps_version, re.M)
    if matchObj:
        return 0, processors
    else:
        return 1, processors

if __name__ == "__main__":
    # Procedure to run as a daemon process.
    # Change to our working directory first.
    # Fork now.
    if len(sys.argv) > 1:
        monitor_log_directory = sys.argv[1]
    print "Reports will be logged to:", monitor_log_directory
    
    countsys = 0
   
    if os.fork(): 
        # Parent process exits here.
        os._exit(0)
    # Child process - make session leader. 
    os.setsid()
    # Detach from the console by closing stdin,
    # stdout and stderr.

    for fd in range(3):
        os.close(fd)
    # Set std input/output/error to /dev/null.
    os.open('/dev/null', os.O_RDONLY)
    os.open('/dev/null', os.O_WRONLY)
    os.open('/dev/null', os.O_WRONLY)
    # Done. Fork again. 
   
    if os.fork():
        # Parent exits here.
        os._exit(0)
    # From here on, the child process is detached
    # from the console.
    os.system('mkdir -p %s' % monitor_log_directory)
    # Change our working directory. All relative paths will now
    # be relative to this directory.
    os.chdir(monitor_log_directory)
    # Create a logmanager instance 
    log_manager = LogManager()
    ########
    # Determine system type.
    ########
  
    flag = 0
    MEDIAFLAG=0
    HEAPFLAG=0

    PROCESSORS = commands.getoutput("cat /proc/cpuinfo | grep processor | wc -l").strip()
    
    card = {1:'UNKNOWN',2:'Pr RTX',3:'Store RTX',4:'Red RTX',5:'RG',6:'LS',7:'NS',8:'BP',9:'LNS',10:'NSBP',11:'LSBP',12:'LNSBP',13:'LI',14:'PTM Server',15:'Sec RTX',16:'GEO RG',17:'VSMS',18:'PBC',19:'POIP-FE',20:'WSC',21:'Red VSMS',22:'Red LS',23:'Red NS',24:'Red BP',25:'Red LI',26:'GSMS GW',27:'Red GSMS GW',28:'UNKNOWN',29:'GC Client Reg',30:'SIP GW',31:'Red SIP GW',32:'POC',33:'Geo POC',34:'OMA Presence',35:'Geo OMA Presence',36:'XDM',37:'Geo XDM',38:'Ser POC Media',39:'Red POC Media',40:'LICCC',41:'Ser POC Messaging',42:'Red POC Messaging',43:'NNI GW',44:'NNI GW Signalling Container',45:'NNI GW Registrar Container',46:'NNI GW Webserver Container',47:'NNI GW TE Container',48:'NNI GW SM Container',49:'NNI GW Broker Container',102:'Remote Log Server'}

    hostname  = commands.getoutput("hostname").strip()

    if os.path.isfile('/etc/kodiakDG.conf'):
       Pttserverid= os.environ.get("PTTSERVERID")
       LOCAL_IP_ADDRESS = os.environ.get("LOCAL_IP_ADDRESS")
       localdsn = 'DG_'+Pttserverid
       LocalConn = getlocalconnection(localdsn,0)
       cardtype = db_fetch("select SignalingCardType from DG.SignalingCardInfo S,DG.SignalingCardAddlInfo SA where S.SignalingCardID=SA.SignalingCardID and S.IPAddress = '%s'" % LOCAL_IP_ADDRESS,localdsn)
       matchObj = re.match( r'.*\((\d+).*', str(cardtype), re.M)
       if matchObj:
          if matchObj.group(1) == '':
             cardval = 'UNKNOWN'
          else:
             val = int(matchObj.group(1))
             if val in card.keys():
                cardval = card[val] 
                if val == 38 or val == 39:
                   MEDIAFLAG=1
                if val == 36 or val == 37 or val == 20 or val == 41 or val == 42 or val == 46:
                   HEAPFLAG=1
             else:
                cardval = 'UNKNOWN'
       else:
          cardval = 'UNKNOWN'
    elif os.path.isfile('/etc/kodiakEMS.conf'):
       cardval = 'EMS'
       localdsn = 'EMSDSN'
       LocalConn = getlocalconnection(localdsn,0)
       LOCAL_IP_ADDRESS = os.environ.get("EMSIP")
    else:
       cardval = 'UNKNOWN'

    connectionstr['Conn_%s' % localdsn] = LocalConn
    temp = commands.getoutput("/usr/local/bin/reg_read")
    temp = temp.split('\n') 
    arr=[]
#read line into array
    for line in temp:
        arr.append(line)
    for val in arr:
        matchObj = re.match( r'Blade ID is\s*(.*)', val, re.M)
        if matchObj:
           if matchObj.group(1) != '':
              hardwaretype = matchObj.group(1)
              if hardwaretype == 'cp6010':
                 hardwaretype = 'Proc200'
              elif hardwaretype == 'cp6014':
                 hardwaretype = 'Proc300'
              else:
                 hardwaretype = 'UNKNOWN' 
              flag = 1
              break

    if flag == 0 or ReleaseVal == 7:
       hardwaretype = 'VIRTUAL'

    OSBit = commands.getoutput("/bin/uname -m 2>> /dev/null | sed -e 's/x86_64/64/g' 2>> /dev/null")


    pttid = None
    try:
        # Try to infer the system type.
        sys_type = get_system_type()
        sys_types = sys_type.split('-')
	

        if len(sys_types) == 1:
            process_set = process_sets[sys_type]
        else:
            process_set = []
            for sys_type in sys_types:
                for process in process_sets[sys_type]:
                    if process_set.count(process) == 0:
                        process_set.append(process) 

	## get process list from startup.txt file for RTX
	if 'rtx' in sys_types:
		proclist_startup = getRTXProcList()
		for proc in proclist_startup:
			if proc == 'tomcat_instance1' or proc == 'tomcat_instance2' or proc == 'tomcat_instance3' or proc == 'tomcat_instance4': 
				proc='children('+proc+'.+catalina.sh)'
			if proc == 'xdmstartup.sh' or proc == 'consulstartup.sh' or proc == 'consultemplatestartup.sh' or proc == 'syslogproxy.sh' or proc == 'activemq': 
				proc='children('+proc+')'
			if proc == 'smpp':
				proc='proc('+proc+')'
			if process_set.count(proc) == 0:
				process_set.append(proc)

        if sys_type in ('ems'):
            pttid = 'emsdsn'
        if sys_type in ('ems'):
            # EMS processes spawn short-lived child processes
            # that screw up CPU usage data. So don't consider
            # child process counters.
            add_child_data = 0
        
        ####
        # Get information on the hardware configuration.
        # Can be useful when interpreting the results.
        ####
        procps_patched, processors = check_system_configuration()

        # For RTX systems, get the PTT-ID
        if not pttid:
            pttid = get_rtx_dsn()
        printlog('monitor_log',"Database DSN:"+pttid+"")
        printlog('monitor_log','Starting monitoring loop.') 
        flushlog('monitor_log');              
       
        reader = ProcReader(processors,process_set,procps_patched)
        # Main loop. Invokes the process monitor periodically and rotates the
        # logs.

        #######################################################
        # Customize the following map if you want to monitor
        # any new system parameter. The format is:
        # 'logfilename':'shell command'
        # This list is for commands that are to be run once
        # per sampling interval. Customize the next map for
        # parameters that need continuous monitoring.
        ########################################################
       
        monitored_data = {
            'disk_usage':'echo Date:;date;df -Pk',
            'ttstatus':'echo Date:;date;ttstatus',
            'Memory_usage':'echo Date:;date;cat /proc/meminfo',
            'repadmin':('echo Date:;date;export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:'+\
                    '/opt/TimesTen/kodiak/lib;'+\
                    ' /opt/TimesTen/kodiak/bin/ttRepAdmin -dsn %s -receiver list') % (pttid),
            'datadir':'echo Date:;date;ls -l /Database',
            'wchan':'ps -emo pid,ppid,cmd,wchan ',
        }
  
        if MEDIAFLAG == 1:
           monitored_data['netstat'] = 'echo Date:;date;netstat -anp'
        else:
           monitored_data['netstat'] = 'echo Date:;date;netstat -anpt'
          
        DBSnapshot = {
            'ttlogholds':'call ttbookmark; call ttlogholds;select to_char(sysdate),NAME,to_char(VALUE),to_char(SYS1),to_char(SYS2) from sys.systemstats',
            'DBSysMon':'select * from sys.monitor',
            'dssize':"select concat('PERM_ALLOCATED_SIZE=',to_char(PERM_ALLOCATED_SIZE)),concat('PERM_IN_USE_SIZE=',to_char(PERM_IN_USE_SIZE)),concat('PERM_IN_USE_HIGH_WATER=',to_char(PERM_IN_USE_HIGH_WATER)),concat('TEMP_ALLOCATED_SIZE=',to_char(TEMP_ALLOCATED_SIZE)),concat('TEMP_IN_USE_SIZE=',to_char(TEMP_IN_USE_SIZE)),concat('TEMP_IN_USE_HIGH_WATER=',to_char(TEMP_IN_USE_HIGH_WATER)),concat('LOG_BUFFER_WAITS=',to_char(LOG_BUFFER_WAITS)) from sys.monitor"
		}

        GetNewDBConection()
			
        #######################################################
        # Customize the following map if you want to monitor
        # any new system parameter continously. For example
        # running sar or iostat for a single sample does not
        # give meaningful data. These commands should run over
        # multiple sampling intervals.
        # The format is:
        # 'logfilename':'shell command'
        ########################################################
        monitored_data_continuous = {
            'iostat':'iostat -x -d %d' % System_poll_interval,
            'topoutput':'top -b -d %d' % System_poll_interval,
            'iotopoutput':'iotop -b -d %d' % System_poll_interval,
            'sar':'sar -u -r -S -W -B -n DEV %d' % System_poll_interval,
            'heapinfo':'/DG/activeRelease/Tools/Fieldutils/heaprun.sh start'
        }
        if ReleaseVal == 7: 
           monitored_data_continuous['Dockerinfo'] = '/DG/activeRelease/Tools/Fieldutils/DockerSnapshot.sh %d %d' %(System_poll_interval,processors)

        GetNewDBConection()
        continuous_data_files = start_continuous_data_monitoring\
            (monitored_data_continuous,1)
        secs_from_prev_rotate = 0
        Systemtime = time.time()
        DBtime = Systemtime 
        while 1:
            # Record beginning of sampling interval
            t1 = time.time()
            if t1 - Systemtime >= System_poll_interval or countsys == 0 or t1 - Systemtime < 0:
			    GetNewDBConection()
			    for log_file in monitored_data.keys():
					printlog(""+log_file+"",commands.getoutput(monitored_data[log_file]))                   
					flushlog(""+log_file+"");
			    Systemtime = t1

            if t1 - DBtime >= DB_poll_interval or countsys == 0 or t1 - DBtime < 0:
			    GetNewDBConection()
			    for DBProcess in DBSnapshot.keys():
				    TempDBProcess = DBProcess.split('_DG')
				    if len(TempDBProcess) == 1:
					      Tempdsn = localdsn
				    else:   
					      Tempdsn = 'DG'+TempDBProcess[1]
				    QueryTemp = DBSnapshot[DBProcess].split(';')
				    printlog(""+DBProcess+"",commands.getoutput('echo Date:;date'))
				    for query in QueryTemp:
				       result = db_fetch(query,Tempdsn)
				       if result == None:
				           continue
				       for output in result:
				           printlog(""+DBProcess+"",output)
				       flushlog(""+DBProcess+"");
			    DBtime = t1

            # Take readings for each process with the stagger delay
            if process_monitoring:
                for i in range(len(process_set)):
                    reader.update_data()
                    time.sleep(stagger_delay)
            # Record end of sampling interval.
            t2 = time.time()
            # Sleep for the remaining period of the poll interval
            if countsys == 0:
               printlog('systemstat',"LOCAL_IP_ADDRESS "+LOCAL_IP_ADDRESS+"")
               printlog('systemstat',"HOSTNAME "+hostname+"")
               printlog('systemstat',"CARD_TYPE "+cardval+"")
               printlog('systemstat',"HARDWARE_TYPE "+hardwaretype+"")
               printlog('systemstat',"rotate_interval "+str(rotate_interval)+"")
               printlog('systemstat',"Process_poll_interval "+str(Process_poll_interval)+"")
               printlog('systemstat',"DB_poll_interval "+str(DB_poll_interval)+"")
               printlog('systemstat',"System_poll_interval "+str(System_poll_interval)+"")
               printlog('systemstat',"PROCESSORS "+str(PROCESSORS)+"")
               printlog('systemstat',"RELEASEVER "+str(ReleaseVal)+"")
               flushlog('systemstat');
               
            countsys = countsys + 1 
            if (t2 - t1) < Process_poll_interval and t2 - t1 > 0:
                time.sleep(Process_poll_interval - (t2-t1))
            else:
                # If we took longer than the poll interval to
                # collect data, log an error. Can happen when
                # the system is heavily loaded.
                printlog('errors',"Data collection time exceeded poll interval. t2-t1='"+str((t2-t1))+"") 
                printlog('errors','This could be due to heavy load on the system.')
            secs_from_prev_rotate += Process_poll_interval
            if secs_from_prev_rotate >= rotate_interval:
                # Close all open log files.
                secs_from_prev_rotate = 0
                countsys = 0
                closed_continuous_data_files = continuous_data_files[:]
                GetNewDBConection()
                continuous_data_files = \
                    start_continuous_data_monitoring(monitored_data_continuous,1)
                # This also checks for stale reports to be deleted.

                files_closed = log_manager.rotate()
                # Tar the closed files now.
                archive_list = ''
                for file_name in files_closed:
                    archive_list += file_name + ' '
                archive_list += ' '.join(closed_continuous_data_files) 
                try:
                   os.system(('/bin/nice -n +19 tar -vczf %s.tgz '+archive_list) % \
                       log_manager.get_log_name('reports'))
                except:
                   tarvar = 0 
                os.system('rm -f '+archive_list)

    except KeyboardInterrupt:
        for process in monitored_data_continuous.keys():
            os.system('pkill -f "%s"' % monitored_data_continuous[process])
            os.system('pkill top')
            os.system('pkill iotop')
            os.system('pkill iostat')
            os.system('pkill sar')
            os.system('sh /DG/activeRelease/Tools/Fieldutils/heaprun.sh stop')
            for connection in connectionstr:
               disconnectDB(connection)
            disconnectDB(LocalConn)

        closed_continuous_data_files = continuous_data_files[:]
        continuous_data_files = \
            start_continuous_data_monitoring(monitored_data_continuous,0)
        # This also checks for stale reports to be deleted.

    	files_closed = log_manager.rotate()
        # Tar the closed files now.
        archive_list = ''
        for file_name in files_closed:
              archive_list += file_name + ' '
        archive_list += ' '.join(closed_continuous_data_files) 
        try:
              os.system(('/bin/nice -n +19 tar -vczf %s.tgz '+archive_list) % \
                   log_manager.get_log_name('reports'))
        except:
              tarvar = 0 
        os.system('rm -f '+archive_list)
        
    except:
        printlog('errors','Unknown exception. Logging backtrace.')    
        import traceback
        traceback.print_exc(20, printlog('errors',''))
