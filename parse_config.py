#!/usr/bin/env python
import socket
import os
from subprocess import check_output
from subprocess import call
import smtplib
import multiprocessing
import requests
import sys
from optparse import OptionParser
import paramiko
from ssh_shell import *

"""Backup Configuration

The following fields populate the variables required to run. Typically you only need to update the user field. This is the user that logs into devices
and runs the desired commands. Make sure the login file has an updated set of credentials. Also make sure the login file is locked down to the service
account used to run the backups.
"""


parser = OptionParser()
parser.add_option("-d", "--devices", action="store", dest="device_file", type="string", help="Devices file name")
parser.add_option("--mail-from", action="store", dest="MAIL_FROM", type="string", help="For send mail. Mail from field")
parser.add_option("--mail-to", action="store", dest="MAIL_TO", type="string", help="For send mail. Mail to field")

options, args = parser.parse_args()

device_file = ''
if options.device_file:
    device_file = options.device_file
else:
    parser.error('Devices file not given')

if "NETCONFIG_USERNAME" in os.environ:
    user = os.environ["NETCONFIG_USERNAME"]
else:
    raise Exception('Missing environmental variable NETCONFIG_USERNAME')                             #username used to log into devices

passw = ''
if "NETCONFIG_PASSWORD" in os.environ:
    passw = os.environ["NETCONFIG_PASSWORD"]
else:
    raise Exception('Missing environmental variable NETCONFIG_PASSWORD')

MAIL_FROM = False
MAIL_TO = False
if options.MAIL_FROM:
    MAIL_FROM = options.MAIL_FROM
if options.MAIL_TO:
    MAIL_TO = options.MAIL_TO

paramiko.util.log_to_file("paramiko.log", level=30)

def write_file(text, outfile):
    f = open(outfile, 'w+')
    f.write(text.replace("\r", ""))
    f.close()

def can_resolv(hostname):
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return False

def smail(text, smtp_to, smtp_from):
    from email.mime.text import MIMEText
    msg = MIMEText(text)
    msg['Subject'] = 'Latest Backup Diffs'
    msg['From'] = smtp_from
    msg['To'] = smtp_to
    s = smtplib.SMTP('localhost')
    try:
        s.sendmail(smtp_from, [smtp_to], msg.as_string())
    except smtplib.SMTPSenderRefused:
        text = 'The configuration diffs are too large to fit in an email. The following devices have been updated.\n'
        text += check_output(["svn", "status"])
        msg = MIMEText(text)
        msg['Subject'] = 'Latest Backup Diffs'
        msg['From'] = smtp_from
        msg['To'] = smtp_to
        s = smtplib.SMTP('localhost')
        try:
            s.sendmail(smtp_from, [smtp_to], msg.as_string())
        except:
            pass
    s.quit()

"""scrub

scrub is the function that ssh's into a device and runs the desired list of commands. It writes the output of each command into a file.
"""
def scrub(devicename, user, passw, file, outfile):
    try:
        device = SSHShell(devicename, user, passw, file)
        device.exec_commands()
        file = open(outfile, 'w+')
        file.write("# " + devicename + " #")
        for output in device.command_output:
            file.write("\n###########" + '\n')
            file.write("# COMMAND ")
            file.write("\n###########" + '\n')        
            file.write(output.replace("\r", ""))
        file.close()
        device.close()
    except:
        print "Error in scrub() for %s: %s" % (devicename, sys.exc_info()[0])

def check_dir(path):
    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        os.makedirs(directory)

def git_diff(smtp_from=False, smtp_to=False):
    diff = check_output(["git", "diff"])
    if diff != '':
        try:
            if smtp_to and smtp_from:
                smail(diff, smtp_to, smtp_from)
            else:
                print diff
        except:
            print "Could not email diff in git_diff(): %s" % (sys.exc_info()[0])

""" git_commit_push()

git_commit_push updates the git repository. By default it blindly git adds all files in the config folder. If there has been no change to the file nothing
will get added. Only altered configurations are updated. 
"""
def git_commit_push():
    success = True
    git_diff(MAIL_FROM, MAIL_TO)
    if call(["git", "add", "config/*"]) == 1:
        success = False
    if call(["git", "commit", "-a", "-m", "Config Updates"]) == 1:
        success = False
    if call(["git", "push"]) == 1:
        success = False
    return success
    
def git_pull():
    success = True
    if call(["git", "pull"]) == 1:
        success = False
    return success
        
def svn_checkin(user, password, smtp_from=False, smtp_to=False):
    status = check_output(["svn", "status", "config/"])
    success = True
    if status != '':
        if status[0] == '?' or 'M':
            if call(["svn", "add", "config", "--force", "--auto-props", "--parents", "--depth", "infinity", "--username", user, "--password", password, 
                     "--non-interactive", "--trust-server-cert", "--no-auth-cache"]) == 1:
                success = False
            if success:
                diff = check_output(["svn", "diff"])
                if diff != '':
                    if smtp_to and smtp_from:
                        smail(diff, smtp_to, smtp_from)
                    else:
                        print diff
                success = call(["svn", "commit", "config", "-m", "Config Updates", "--username", user, "--password", password, "--non-interactive", 
                                "--trust-server-cert", "--no-auth-cache"]) == 0
    return success

def svn_update(user, password):
    return call(["svn", "update", "--username", user, "--password", password, "--non-interactive", "--trust-server-cert", "--no-auth-cache"]) == 0

def get_full_asa_config(asa, user, password, outfile):
    url = "https://" + asa
    r = requests.get(url + "/admin/exec/show%20run", auth=(user, password), verify=False)
    write_file(r.text, outfile)

""" git_pull the latest updates
We  run git pull here to fetch a fresh update of the devices.txt and or type files. In this way new devices can be added in the repository locally by other
users. Before we start iterating through devices the repository will be fully updated including any new devices added.
    
NOTE: # Git is now managed directly by the Jenkins job
"""
#git_pull()   # Git is now managed directly by the Jenkins job

threads = []
pool = multiprocessing.Pool(8)

"""Device iteration

For each device in the devices file we will scrub config.
"""
for device in open(device_file, 'r'):
    if not device.strip()[0] == '#':
        device = device.strip().split(':')
        if len(device) == 4:
            device_type = device[1]
            device_location = device[2]
            location_path = './config/' + device_location + '/'
            check_dir(location_path)
            device_filename = location_path + device[0] + '.txt'
            if device[3] == 'up':
                type_file = "type/" + device_type + ".txt"
                if os.path.isfile(type_file):
                    if can_resolv(device[0]):
                        pool.apply_async(scrub, args=(device[0], user, passw, type_file, device_filename))
                    else:
                        print 'Unable to resolve' + device[0]
                else:
                    print 'unmatched type for device ' + device[0]

pool.close()
pool.join()
#git_commit_push()   # Git is now managed directly by the Jenkins job
