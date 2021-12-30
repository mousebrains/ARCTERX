# How I set up a Raspberry Pi for use on the ships of the ARCTERX pilot cruise in 2022
---
1. Create MicroSD card with Ubuntu server for a Raspberry Pi system. 
  - I used 21.10 64 bit server. 
  - To burn the MicroSD card I used the "Raspberry Pi Imager" application on my desktop.
2. Install the MicroSD in the Pi
3. Boot the Pi and get the IP address
4. Login to the Pi using `ssh ubuntu@IPAddr` using the default password *ubuntu*
5. You will have to change the default password on the initial login, then you will be logged out.
6. Execute the SetupPi/install0.sh script using the following to do the following on the new system:
using:
`ssh ubuntu@IPaddr:script to the new server via: `scp SetupPi/install0.sh ubuntu@IPAddr:`
7. Execute the 
7. Log back in using the new password.

7. Fully update the system using `sudo apt update`
8. Fully upgrade the system using `sudo apt upgrade`
9. Now reboot to have any new kernels become active using `sudo reboot`
10. Log back in.
11. Install fail2ban for security, `sudo apt install fail2ban`
12. Install ACL support, `sudo apt install acl`
13. Disable automatic updates and upgrades by changing both instances of **"1"** in /etc/apt/apt.conf/20auto-upgrades to **"0"**
14. Set the hostname using the command `sudo hostnamectl set-hostname YourNewHostname`
  - R/V Walton Smith primary, waltonsmith0
  - R/V Walton Smith backup, waltonsmith1
  - R/V Pelican primary, pelican0
  - R/V Pelican backup, pelican1
  - shore side test primary, pi4
  - shore side test backup, pi5
15. Enable zeroconf/bonjour via AVAHI-DAEMON, `sudo apt install avahi-daemon`
16. Add the sunrise group, `sudo addgroup sunrise`
17. Add the primary user via the commands
  - `sudo adduser pat`
  - `sudo usermod -aG sudo pat`
  - `sudo usermod -aG sunrise pat`
18. Logout of the ubuntu user
19. Logback in to the new user, *pat*
20. Delete the ubuntu user, `sudo deluser --remove-home ubuntu`
21. Create the Dropbox, Processed, and logs directories in ~pat, `mkdir Dropbox Processed logs`
22. Create the ssh key pair for talking to the shore side server, glidervm3, `ssh-keygen -b2048`
23. Create the ssh config file, *~/.ssh/config* with the following content:
<pre>
Host vm3 glidervm3 glidervm3.ceoas.oregonstate.edu
  Hostname glidervm3.ceoas.oregonstate.edu
  User pat
  IdentityFile ~/.ssh/id_rsa
  Compression yes
</pre>
25. Copy the new id to vm3, `ssh-copy-id -i ~/.ssh/id_rsa.pub vm3`
26. Do the initial rsync of Dropbox, `rsync --archive --compress --compress-level=22 --mkpath --copy-unsafe-links --delete-missing-args --delete --relative --stats vm3:Dropbox/ .`
27. Set up ACL for the home directory and Dropbox so other users in the group sunrise can see the home directory and modify Dropbox.
  - `setfacl --modify=group:sunrise:rX . Dropbox`
  - `setfacl --recursive --modify=group:sunrise:rwX Dropbox/* Processed Processed/*`
28. Install the websever, NGINX, and PHP support, `sudo apt install nginx php-fpm`
30. Install SAMBA for smb mounting for the ASVs and others `sudo apt install samba*`
31. Add a mount points for all users on all machines by adding *~/SUNRISE/SAMBA/forall.conf* to */etc/samba/smb.conf*
32. If on the waltonsmith0, create a mount point for Jasmine and the ASVs by:
  - Create the mount point if it does not exist for ASVs `mkdir /home/pat/Dropbox/WaltonSmith/asv`
  - Add *~/SUNRISE/SAMBA/ws.conf* to */etc/samba/smb.conf*
  - Create the SMB user with a known password, Sunrise, `sudo smbpasswd -a pat`
35. Restart samba, `sudo systemctl restart smbd`
36. Install the required PHP packages, `sudo apt install php-xml php-yaml`
37. Install the required python packages, 
  - `sudo apt install python3-pip python3-pandas`
  - `python3 -m pip install inotify-simple`
  - `python3 -m pip install libais`
38. Set up git
  - `cd ~`
  - `git config --global user.name "Pat Welch"`
  - `git config --global user.email pat@mousebrains.com`
  - `git config --global core.editor vim`
  - `git config --global pull.rebase false`
  - `git clone git@github.com:mousebrains/SUNRISE.git`
39. Modify the webserver configuration to point hat /home/pat/Dropbox and to run as user pat.
 - `cd ~/SUNRISE/nginx`
 - `make`
39. Install services using hostname discover method
  - `cd ~/SUNRISE`
  - `sudo ./install.services.py --discover`
40. Install the primary index.php
  - `cd ~/SUNRISE/html`
  - `make install`
44. To add a user use `~/SUNRISE/addUser` this sets up the user and group memberships
---
# For ship ops undo the shore side testing:
- `sudo rm /etc/ssh/sshd_config.d/osu_security.conf`
- `sudo rm /etc/ssh/banner.txt`
- `sudo rm /etc/motd`
- `sudo systemctl restart sshd`
- `sudo systemctl disable fail2ban`
- `sudo systemctl stop fail2ban`
