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
		$this->tables = array();

		$this->tables["ship"] =
			$db->prepare(
				"SELECT DISTINCT ON (id) 'ship' AS grp,id,t,lat,lon"
				. " FROM ship WHERE t>=? ORDER BY id,t DESC;"
			);

		$this->tables["drifter"] =
			$db->prepare(
				"SELECT DISTINCT ON (id) 'drifter' AS grp,id,t,lat,lon"
				. " FROM drifter"
				. " WHERE t>=? AND lat IS NOT NULL AND lon IS NOT NULL"
				. " ORDER BY id,t DESC;"
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

	function fetchData($tbl) {
		$stmt = $this->tables[$tbl];
		$latest = $this->latest[$tbl];
		if ($stmt->execute([$latest]) == false) {
                        array_push($this->errors, $stmt->errorInfo());
			return array();
		}
		$cache = $this->cache[$tbl];
		$a = array();
		while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
			$grp = $row["grp"];
			$id = $grp . "," . $row["id"];
			if (array_key_exists($id, $this->toDrop)) {
				continue;
			}
			$t = $row["t"];
			$latest = max($latest, $t);
			if (array_key_exists($id, $cache) && ($t <= $cache[$id])) {
				continue;
			}
			$cache[$id] = $t;
			$row["t"] = (new DateTimeImmutable($t))->getTimestamp();
			$row["lat"] = round((float) $row["lat"], 6);
			$row["lon"] = round((float) $row["lon"], 6);
			if (!array_key_exists($grp, $a)) {
				$a[$grp] = array();
			}
			unset($row["grp"]);
			array_push($a[$grp], $row);
		}
		$this->latest[$tbl] = $latest;
		$this->cache[$tbl] = $cache;
		return $a;
        } // fetchData

        function fetchInitial() {
		$this->errors = [];
		$a = array();

		foreach (array_keys($this->tables) AS $tbl) {
			$b = $this->fetchData($tbl);
			if (!empty($b)) {
				$a = array_merge($a, $b);
			}
		}

                if (!empty($this->errors)) {
                        $a['errors'] = $this->errors;
                        $this->errors = array();
		}
                return json_encode($a);
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

$db = new DB($dbName);

echo "data: " . $db->fetchInitial() . "\n\n";
$tPrev = time();

while (True) { # Wait forever
        if (ob_get_length()) {ob_flush();} // Flush output buffer
	flush();
	$notifications = $db->notifications($delay);
	if (empty($notifications)) {
		echo "data: " . json_encode([]) . "\n\n";
	} else {
		$tbl = $notifications["payload"];
		$data = $db->fetchData($tbl);
		if (empty($data)) {
			echo "data: " . json_encode([]) . "\n\n";
		} else {
			echo "data: " . json_encode($data) . "\n\n";
		}
        } // if
} // else
?>
