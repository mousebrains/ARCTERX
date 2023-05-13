<!DOCTYPE html>
<html lang="en">
<head>
<title>ARCTERX</title>
</head>
<body>
<ul>
<li><a href="SituationalAwareness">Situational Awareness Map</a></li>
<?php
if (is_dir("AVISO")) {
	echo "<li><a href='AVISO'>AVISO</a></li>\n";
}
?>
<li><a href='links.html'>Links</a></li>
<li><a href='Sync.ARCTERX/Shore/Papers'>Papers</a></li>
<li><a href='Sync.ARCTERX/Shore/Software'>Software</a></li>
<li><a href='Sync.ARCTERX/Ship'>Ship</a></li>
<li><a href='Sync.ARCTERX/Shore'>Shore</a></li>
<li><a href='typhoons.html'>Typhoons</a></li>
<li><a href='https://www.pacioos.hawaii.edu/voyager'>PacIOOS model</a></li>
<li><a href='https://vertmix.alaska.edu/atx2023.html'>APL-UW Epsilon PALAU 800 model</a></li>
<li><a href='https://www7320.nrlssc.navy.mil/NLIWI_WWW/EAS-SKII/EASNFS.html'>NRL model</a></li>
</ul>
<pre>
<?php
if (gethostname() != "arcterx") {
	echo "<div>";
	echo "<hr>";
	echo "<h3>Mounting shore to ship and ship to shore data</h3>";
	echo "Any of:";
	echo "<ul>";
	echo "<li>smb://arc2.local/ARCTERX</li>";
	echo "<li>smb://arc3.local/ARCTERX</li>";
	echo "<li>smb://arc1.local/ARCTERX</li>";
	echo "<li>smb://10.43.25.116/ARCTERX</li>";
	echo "<li>smb://10.43.25.115/ARCTERX</li>";
	echo "<li>smb://10.43.25.114/ARCTERX</li>";
	echo "</ul>";
	echo "</div>";
}
?>
</pre>
</body>
</html>
