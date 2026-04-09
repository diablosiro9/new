from utils.enums import ProcessState  
import time 

class ProcessInstance: 
    def __init__(self):  
        self.pid = None  
        self.state = ProcessState.STOPPED  
        self.exited_flag = False  
        self.exit_code = None  
        self.start_time = None      
        self.retry_count = 0        
        self.stop_reason = None  
        self.pty_master_fd = None
        self.is_attachable = False  
        self.is_attached = False  

    def mark_started(self, pid): 
        self.pid = pid  
        self.state = ProcessState.RUNNING  
        self.exited_flag = False  
        self.start_time = time.time()  
        self.exit_code = None  

    def mark_exited(self, exit_code=None, manual=False):
        self.state = ProcessState.STOPPED 
        self.exited_flag = True 
        self.exit_code = exit_code  
        self.manual_stop = manual 