#! /bin/bash
#
# Copy the wh300 ob150nb
#
# April-2023, Pat Welch, pat@mousebrains.com

/home/pat/ARCTERX/CruiseSync/syncADCP.py \
	--output=~/Sync.ARCTERX/Ship/ADCP/wh300 \
	--ADCP=/mnt/ship/TN417/adcp/proc/wh300/contour \
	--logfile=/home/pat/logs/syncADCPwh300.log \
	--verbose

/home/pat/ARCTERX/CruiseSync/syncADCP.py \
	--output=~/Sync.ARCTERX/Ship/ADCP/os75nb \
	--ADCP=/mnt/ship/TN417/adcp/proc/os75nb/contour \
	--logfile=/home/pat/logs/syncADCPos75nb.log \
	--verbose
