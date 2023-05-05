#! /bin/bash
#
# Copy the wh300 ob150nb
#
# April-2023, Pat Welch, pat@mousebrains.com

ADCP=/mnt/ship/TN417/adcp/proc
WH300=$ADCP/wh300/contour
OS75=$ADCP/os75nb/contour
LOG=/home/pat/logs/syncADCPs.log
CACHE=/home/pat/cache
TGT=/home/pat/Sync.ARCTERX/Ship/ADCP

echo >>$LOG
date >> $LOG
echo >>$LOG

/usr/bin/rsync \
	--temp-dir=$CACHE \
	--archive \
	--verbose \
	$WH300/allbins_depth.mat \
	$WH300/allbins_other.mat \
	$WH300/allbins_u.mat \
	$WH300/allbins_v.mat \
	$WH300/allbins_w.mat \
	$WH300/allbins_amp.mat \
	$WH300/*.nc \
	$TGT/wh300 \
	2>&1 >>$LOG

/usr/bin/rsync \
	--temp-dir=$CACHE \
	--archive \
	--verbose \
	$OS75/allbins_depth.mat \
	$OS75/allbins_other.mat \
	$OS75/allbins_u.mat \
	$OS75/allbins_v.mat \
	$OS75/allbins_w.mat \
	$OS75/allbins_amp.mat \
	$OS75/*.nc \
	$TGT/os75nb \
	2>&1 >>$LOG
