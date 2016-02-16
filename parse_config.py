#!/usr/bin/env python
import paramiko
from ssh_shell import *
import socket
import os
from subprocess import check_output
from subprocess import call
import smtplib
import multiprocessing
import cobra.mit.access
import cobra.mit.session
from cobra.internal.codec.jsoncodec import toJSONStr
from cobra.mit.request import DnQuery
from cobra.mit.request import ClassQuery

paramiko.util.log_to_file("paramiko.log", level=30)

def resolv(hostname):
    try:
        socket.gethostbyname(hostname)
        return True
    except:
        return False

def smail(text, smtp_to, smtp_from):
    from email.mime.text import MIMEText
    msg = MIMEText(text)
    msg['Subject'] = 'The Warnock Report'
    msg['From'] = smtp_from
    msg['To'] = smtp_to
    s = smtplib.SMTP('localhost')
    s.sendmail(smtp_from, [smtp_to], msg.as_string())
    s.quit()
    
def scrub(devicename, user, passw, file, outfile):
    try:
        device = SSHShell(devicename, user, passw, file)
        device.run_commands()
        file = open(outfile, 'w+')
        file.write("# " + devicename + " #")
        for output in device.command_output:
            file.write("\n###########" + '\n')
            file.write("# COMMAND ")
            file.write("\n###########" + '\n')        
            file.write(output)
        file.close()
        device.close()
    except:
        print "Error in scrub() for %s: %s" % (devicename, sys.exc_info()[0])

def check_dir(path):
    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        os.makedirs(directory)
        
def svn_checkin(user, password, emailto, emailfrom):
    status = check_output(["svn", "status", "config/"])
    success = True
    if status != '':
        if status[0] == '?' or 'M':
            if call(["svn", "add", "config", "--force", "--auto-props", "--parents", "--depth", "infinity", "--username", user, "--password", password, "--non-interactive", "--trust-server-cert", "--no-auth-cache"]) == 1:
                success = False
            if success:
                diff = check_output(["svn", "diff"])
                if diff != '':
                    smail(diff, emailto, emailfrom)
                success = call(["svn", "commit",  "config", "-m", "Config Updates", "--username", user, "--password", password, "--non-interactive", "--trust-server-cert", "--no-auth-cache"]) == 0
    return success

def svn_update(user, password):
    return call(["svn", "update", "--username", user, "--password", password, "--non-interactive", "--trust-server-cert", "--no-auth-cache"]) == 0


def get_full_aci_config(apic, user, password, outfile):
    try:
        url = "https://" + apic
        ls = cobra.mit.session.LoginSession(url, "apic:ACS\\" + user, password, secure=False, timeout=30) 
        md = cobra.mit.access.MoDirectory(ls)
        md.login()
    
        #Get tenant config
        cq = ClassQuery('fvTenant')
        cq.subtree = 'full'
        cq.propInclude= 'config-only'
        tenant_config = md.query(cq)
    
        #Infra config
        dq = DnQuery('uni/infra')
        dq.subtree = 'full'
        dq.propInclude = 'config-only'
        infra_config = md.query(dq)
    
        #Fabric config
        dq = DnQuery('uni/fabric')
        dq.subtree = 'full'
        dq.propInclude = 'config-only'
        fabric_config = md.query(dq)
    
        file = open(outfile, 'w+')
        file.write("# " + apic + " #")
        file.write("\n###########" + '\n')
        file.write("# TENANTS ")
        file.write("\n###########" + '\n')   
        for tenant in tenant_config:
            file.write(toJSONStr(tenant, prettyPrint=True))
    
        file.write("\n###########" + '\n')
        file.write("# Infra ")
        file.write("\n###########" + '\n')
        for infra in infra_config:
            file.write(toJSONStr(infra, prettyPrint=True))
        
        file.write("\n###########" + '\n')
        file.write("# Fabric ")
        file.write("\n###########" + '\n')
        for fabric in fabric_config:
            file.write(toJSONStr(fabric, prettyPrint=True))
    
        file.close()
    except:
        print "Error in get_full_aci_config() for %s: %s" % (apic, sys.exc_info()[0])
    

user = 'device_username'
svn_user = 'svn_username'
svn_passw = open('./svn_login').read().rstrip('\n')
passw = open('./login').read().rstrip('\n')
device_file = './devices.txt'

svn_update(svn_user, svn_passw)

threads = []
pool = multiprocessing.Pool(8)

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
                if device_type == 'ios':
                    if resolv(device[0]):
                        pool.apply_async(scrub, args=(device[0], user, passw, 'ios.txt', device_filename))
                elif device_type == 'f5':
                    if resolv(device[0]):
                        pool.apply_async(scrub, args=(device[0], user, passw, 'bigip.txt', device_filename))
                elif device_type == 'pa':
                    if resolv(device[0]):
                        pool.apply_async(scrub, args=(device[0], user, passw, 'pa.txt', device_filename))
                elif device_type == 'seamicro':
                    if resolv(device[0]):
                        pool.apply_async(scrub, args=(device[0], user, passw, 'seamicro.txt', device_filename))
                elif device_type == 'aci':
                    if resolv(device[0]):
                        pool.apply(get_full_aci_config, args=(device[0], user, passw, device_filename))
                elif device_type == 'nexos':
                    if resolv(device[0]):
                        pool.apply_async(scrub, args=(device[0], user, passw, 'nexos.txt', device_filename))
                else:
                    print 'else'
                    #do something

pool.close()
pool.join()
svn_checkin(svn_user, svn_passw)
