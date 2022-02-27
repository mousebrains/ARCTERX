# These are the steps I take to install a fresh system on a Raspberry Pi for a Mapserver

***GeoServer***
- Download the latest GeoServer Stable Web Archive, war, from [GeoServer](http://geoserver.org)
- Unzip the *zip* file. You'll need to copy the war file to the new server later.

***Setup new Raspberry Pi server***

- Create a fresh MicroSD card with Ubuntu Server. I use the the 
[Raspberry Pi Imager](https://www.raspberrypi.com/software/)
and installed Ubuntu Server 21.10
- Install the MicroSD card in the Raspberry Pi, boot, and obtain the IPV4 address.
- `ssh ubuntu@ipAddr` log into the Pi with the password ***ubuntu***. You will be required to change your password, then logged out.
- `ssh-copy-id ubuntu@ipAddr` to copy your ssh credentials to the new pi with the new password.
- `ssh ubuntu@ipAddr log into the Pi. You should not need a password now.
- `sudo apt update` update the software repository list.
- `sudo apt upgrade` download and upgrade updated software packages.
- `sudo apt autoremove` remove unneeded software packages.
- `sudo hostnamectl set-hostname rrmap` to set the hostname to rrmap
- `sudo apt install avahi-daemon` to enable Zero-Config and access via rrmap.local
- `sudo apt install nginx` to install the latest nginx webserver. 
- `sudo apt install tomcat9` to install the latest Tomcat webserver.
- `sudo reboot` to reboot the system and use the updated packages.
- Copy the GeoServer war file to the Pi server, `scp *.war ubuntu@rrmap.local:` where \*.war is the GeoServer war file from the GeoServer zip file you downloaded
- Copy geoserver file in the Git repository to the Pi server using `scip geoserver ubuntu@rrmap.local:`
- `ssh ubuntu@rrmap.local` log back into the Pi.
- `sudo cp geoserver.war /var/lib/tomcat9/webapps` to install GeoServer under Tomcat
- After a few seconds Tomcat will have unpacked geoserver and it will be available in a web browser at **http://rrmap.local:8080/geoserver**
 - Login to geoserver using username *admin* and password *geoserver*
 - Got to "Users, Groups, Roles -> Users/Groups" then click on username *admin* Change the admin password to a non-default password you'll remember, *ARCTERX* 
 - To add a layer do the following:
  - Upload your layer into a directory for user ubuntu:rrmap.local, for example: geoserver/layerName

Copy `gliderwms0.ceoas.oregonstate.edu:/var/www/html/maps /var/www/html/maps` This is ~18GB
