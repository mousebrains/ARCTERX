<?php
header('Content-Type: text/event-stream');
header('Cache-Control: no-cache');
header('X-Accel-Buffering: no');

// Send to JSON formatted data representing
//   the controller's current,
//   the flow sensor's flow,
//   the number of stations turned on, and
//   the number of stations pending within the next 50-60 minutes

class DB {
        private $errors = array(); // Error stack
	private $toDrop = [
		// "WG,Ole" => 1,
		// "WG,Sven" => 1,
		// "WG,Stallion" => 1,
		// "WG,Ragnar" => 1,
	]; // Names to be ignored


	function __construct(string $dbName) {
                $db = new PDO("pgsql:dbname=$dbName;");
		$this->db = $db;
		// Prepare statements to fetch each table
		$this->initial = array();
		$this->tables = array();

		$this->initial["ship"] =
			$db->prepare(
				"SELECT 'ship' AS grp,id,t,lat,lon"
				. " FROM ship WHERE t>=? ORDER BY id,t DESC LIMIT ?;"
			);
		$this->tables["ship"] =
			$db->prepare(
				"SELECT DISTINCT ON (id) 'ship' AS grp,id,t,lat,lon"
				. " FROM ship WHERE t>=? ORDER BY id,t DESC;"
			);

		$this->initial["drifter"] =
			$db->prepare(
				"SELECT 'drifter' AS grp,id,t,lat,lon"
				. " FROM drifter"
				. " WHERE t>=? AND lat IS NOT NULL AND lon IS NOT NULL"
				. " ORDER BY id,t DESC LIMIT ?;"
			);
		$this->tables["drifter"] =
			$db->prepare(
				"SELECT DISTINCT ON (id) 'drifter' AS grp,id,t,lat,lon"
				. " FROM drifter"
				. " WHERE t>=? AND lat IS NOT NULL AND lon IS NOT NULL"
				. " ORDER BY id,t DESC;"
			);

		$this->initial["glider"] =
			$db->prepare(
				"SELECT grp,id,t,lat,lon"
				. " FROM glider"
				. " WHERE t>=?"
				. " ORDER BY grp,id,t DESC LIMIT ?;"
			);
		$this->tables["glider"] =
			$db->prepare(
				"SELECT DISTINCT ON (grp,id) grp,id,t,lat,lon"
				. " FROM glider"
				. " WHERE t>=?"
				. " ORDER BY grp,id,t DESC;"
			);

		$this->latest = array();
		$this->cache = array();

		$early = new DateTimeImmutable("yesterday", new DateTimeZone("UTC"));
		$early = $early->format("Y-m-d h:i:s+00");

		foreach (array_keys($this->tables) as $tbl) {
			$this->latest[$tbl] = $early;
			$this->cache[$tbl] = array();
			$db->exec("LISTEN " . $tbl . "_updated;");
		}
        }

        function notifications(int $dt) {
                $a = $this->db->pgsqlGetNotify(PDO::FETCH_ASSOC, $dt);
                if (!$a) return array();
                return ['channel' => $a['message'], 'payload' => $a['payload']];
        }

	function fetchRows($tbl, $stmt, $params) {
		if ($stmt->execute($params) == false) {
			array_push($this->errors, $stmt->errorInfo());
			return array();
		}

		$latest = array_key_exists($tbl, $this->latest) ? $this->latest[$tbl] : 
			"2000-01-01 00:00:00+00";
		$cache = $this->cache[$tbl];
		$a = array();
		while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
			$grp = $row["grp"];
			$id = $row["id"];
			$ident = $grp . "," . $id;
			if (array_key_exists($ident, $this->toDrop)) continue;
			$t = $row["t"];
			if (array_key_exists($ident, $cache) && ($cache[$ident] <= $t)) continue;
			if (!array_key_exists($ident, $cache)) $cache[$ident] = 0;
			if ($t > $cache[$ident]) { // Latest record for this ident
				$cache[$ident] = $t;
				$latest = max($latest, $t);
			}
			if (!array_key_exists($grp, $a)) $a[$grp] = array();
			if (!array_key_exists($id, $a[$grp])) $a[$grp][$id] = array();
			array_push($a[$grp][$id], [
				(new DateTimeImmutable($t))->getTimestamp(),
				round((float) $row["lat"], 6),
				round((float) $row["lon"], 6),
			]);
		} // while
		$this->cache[$tbl] = $cache;
		$t = date_sub(
			new DateTime($latest),
			DateInterval::createFromDateSTring("300 seconds"));
		$this->latest[$tbl] = $t->format("Y-m-d H:i:s+00");
		return $a;
	}

	function fetchData($tbl) {
		$b = $this->fetchRows($tbl, $this->tables[$tbl], [$this->latest[$tbl]]);
		if (!empty($this->errors)) {
                        $b["errors"] = $this->errors;
                        $this->errors = array();
		}
		return $b;
        } // fetchData

        function fetchInitial($hoursBack, $maxRows) {
		$this->errors = array();
		$b = array();

		$t0 = date("Y-m-d H:i:s+00", strtotime("-$hoursBack hours"));
		foreach (array_keys($this->initial) AS $tbl) {
			$this->latest[$tbl] = $t0;
			$a = $this->fetchRows($tbl, $this->initial[$tbl], [$t0, $maxRows]);
			if (!empty($a)) {
				$b = array_merge($b, $a);
			}
		}

                if (!empty($this->errors)) {
                        $b["errors"] = $this->errors;
                        $this->errors = array();
		}

                return $b;
        } // fetchInitial

        function exec($stmt) {
                if ($stmt->execute([]) == false) {
                        array_push($this->errors, $stmt->errorInfo());
                        return false;
                }
                return true;
	} // exec
} // DB

$delay = 55 * 1000; // 55 seconds between burps
$dbName = 'arcterx';
$hoursBack = 6; // Number of hours of data to fetch initially
$maxRows = 10000; // Maximum number of initial records for each table

$db = new DB($dbName);

$data = $db->fetchInitial($hoursBack, $maxRows);
if (!empty($data)) {
	echo "data: " . json_encode($data) . "\n\n";
}

$tPrev = time();

while (True) { # Wait forever
	try {
        	if (ob_get_length()) {ob_flush();} // Flush output buffer
		flush();
		$notifications = $db->notifications($delay);
		if (empty($notifications)) {
			echo "data: " . json_encode([]) . "\n\n";
		} else {
			$tbl = $notifications["payload"];
			$data = $db->fetchData($tbl);
			if (!empty($data)) {
				echo "data: " . json_encode($data) . "\n\n";
			}
		} // if notifications
	} catch (Exception $e) {
		echo "data: " . json_encode(["errors" => $e->getMessage()]) . "\n\n";
	}
} // else
?>
