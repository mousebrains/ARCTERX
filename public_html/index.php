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
<li><a href='Sync/Shore/Papers'>Papers</a></li>
<li><a href='Sync/Shore/Software'>Software</a></li>
<li><a href='Sync/Ship'>Ship</a></li>
<li><a href='Sync/Shore'>Shore</a></li>
<li><a href='Sync/Processed'>Processed</a></li>
</ul>
<pre>
<?php
if (gethostname() != "arcterx.ceoas.oregonstate.edu") {
	echo "<div>";
	echo "<hr>";
	echo "<h3>SMB mount points</h3>";
	echo "Any of:";
	echo "<ul>";
	echo "<li>smb://pi10</li>";
	echo "<li>smb://shiphouse</li>";
	echo "</ul>";
	echo "</div>";
}
?>
</pre>
</body>
</html>
