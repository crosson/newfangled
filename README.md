# newfangled
## Why
This was hastily built as an ad-hoc rancid replacement for configuration backups that would work regardless of the vendor.

## How

Newfangled runs in a cron. The cron calls the parse_config.py command. This bit of python code iterates through a list of devices with instructions on what OS to expect and which commands to run. I have adde things like F5, NEXOS, IOS or PA(Palo Alto) but you can easily add more so long as your device supports SSH and has some generic show commands. I also added a function for Cisco ACI to pull a full config with a rest call. Unlike Rancid instead of placing a router.db in each subfolder populated with that sites devices all devices for newfangled are stored in a single file called devices.txt. Organize the file how you see fit using comment lines as a means for documenting and organizing the devices.txt file.  The program will autobuild the folder tree placing the configurations of devices into their respctive folders. The end result is a subtree of folders similar to Rancid. Also unlike rancid it is very easy to change what commands are run on the remote systems. It is also very easy to exclude certain lines which is great for avoiding noise. The program was originally intended to be used with SVN. It will checkin your latest configuration backups and email you a DIFF of the latest changes.

Due to the simplicity of targeting spcific hosts and ease of dictating commands on the remote system this program could easily be morfed into a mass configuration push script. We have a forked version of this which we use for massive device updates. Think like NTP, DNS, or usernames. Items that are the same on multiple devices that you can update at once.

## Setup

1. Clone the project to a folder on a server where
2. Create your login files and passwords
  * These files should be protected to your cron user only, similar to rancid. These files store the passwords required to login into your network equipment as well as check in configuration changes.
  * add your svn user's password to the 'svn_login' file. Make sure its permissions are safely set.
  * Add your device users passwrod to the 'login' file. Make sure its permissions are safely set.
  * The svn username and device username are found in parse_config.py starting at line 124. 
3. The project was originaly built with SVN. You will want to make a new SVN repository in this folder and setup your SVN user for checking in new backed up configuration.
4. Add a single device to the device.txt file commenting out the rest. Set whatver commands you wish to run on the associated devices OS txt file.
5. Run parse_config.py and validate that you can scrape config from a device.
6. Populate the devices file with your devices. We run this on about 100 devices and it doesn't take longer than a few minutes to run. Much faster than rancid.

## Disclaimer

We built this in a bind and in a panic due to inefficiencies with Rancid. It obviously could be improved. Feel free to take the code and use it to your benefit.