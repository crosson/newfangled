import paramiko
import time

class SSHShell(object):
    def __init__(self, device, user, passw, commandfile = None):
        self.device = device
        self.user = user
        self.passw = passw
        self.ssh = self.connect(device, user, passw)
        #self.chan = self.ssh.invoke_shell()
        self.command_file = commandfile
        self.command_list = []
        if self.command_file:
            self.read_commands(self.command_file)
        self.command_output = []
        #self.prompt = self.get_prompt()
        
    def connect(self, device, user, passw):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(device, username = user, password = passw, allow_agent=False, look_for_keys=False)
        return ssh
    
    def exec_commands(self):
        """exec_commands()
        
        There are two options for running commands in SSHShell. exec_commands or run_commands(). exec_commands manages recieves and buffering for you and
        has generally found more reliable. Some legacy devices misbehave and require a more granular approach. run_commands() can be used in that case.
        exec_commamnds reads the command file and executes those commands. It stores the responses in the command_output array.
        
        While the command files are built at the time the object is created commands are not run until told to do so with this function.
        """ 
        text = ''
        for command_dict in self.command_list:
            ssh = self.connect(self.device, self.user, self.passw)
            stdin, text_stream, stderr = ssh.exec_command(command_dict['command'])
            recieve_text = text_stream.read()
            if command_dict['exclude']:
                for item in command_dict['exclude']:
                    recieve_text = self.exclude(recieve_text, item)
            self.command_output.append(recieve_text)
            ssh.close()
    
    def get_prompt(self):
        self.chan.send('\r\r\r')
        prompt = ''
        loop = True
        timeout = 5
        while loop & (timeout > 0):
            if self.chan.recv_ready():
                text = self.chan.recv(65536)
                prompt = text.split("\n")[-1]
                if len(prompt) > 0:
                    loop = False
            else:
                timeout -= 1
                time.sleep(1)
        return prompt
        
    def read_commands(self, filename):
        with open(filename) as file:
            for line in file:
                if '#' not in line[0]:
                    l = line.split('!')
                    command = l[0].strip()
                    exclude = []
                    if len(l) > 1:
                        for item in range(1, len(l)):
                            exclude.append(l[item].strip())
                    command_d = {'command' : command, 'exclude' : exclude}
                    self.command_list.append(command_d)
    
    def run_commands(self):
        """run_commands()
    
        There are two options for running commands in SSHShell. exec_commands or run_commands(). run_commands() offers a legacy and more granular approach
        to sending and recieving data over channels. However, as a result, some devices like IOS become hard to manage and responses can become inconsistent.
        run_commands parses the same command files. It manually sends the commands and listens for responses. It tries to be patient and piece together the
        response text stream.
        
        While the command files are built at the time the object is created commands are not run until told to do so with this function.
        """
        self.prompt = self.get_prompt()
        for command_dict in self.command_list:
            self.command_output.append(self.talk(command_dict))
                    
    def read_chan(self, buffer_size = 65536, timeout = 20):
        text = ''
        loop = True
        timeout_reset = timeout
        while loop & (timeout > 0):
            if self.chan.recv_ready():
                timeout = timeout_reset
                text_stream = self.chan.recv(buffer_size)
                if text_stream.split('\n')[-1] == self.prompt:
                    loop = False
                text += text_stream
            else:
                timeout -= 1
                time.sleep(1)
        return text
        
    def clear_buffer(self):
        if self.chan.recv_ready():
            self.chan.recv(65536)
        return self.chan.recv_ready()
        
    def talk(self, command_dict):
        self.clear_buffer()
        self.chan.send(command_dict['command'] + '\n')
        text = self.read_chan()
        if command_dict['exclude']:
            for item in command_dict['exclude']:
                text = self.exclude(text, item)
        return text
        
    def exclude(self, text, excluded):
        new_text = ''
        for line in text.rstrip().split('\n'):
            if excluded not in line:
                new_text += line + '\n'
        return new_text
        
    def close(self):
        self.ssh.close()