<?php
// Vectores de prueba de la tesis: entradas concretas y la salida EXACTA del código de producción (motor en
// bideplus/engine). Se ejecuta desde cualquier sitio; escribe vectores.json junto a este archivo.
declare(strict_types=1);
date_default_timezone_set('Europe/Madrid');

// La app con el motor dentro (bideplus/engine): por defecto, cuatro carpetas por encima de esta. BIDE_APP la cambia.
$sApp = getenv('BIDE_APP');
if (!$sApp) {
    $sApp = dirname(__DIR__, 4);
}
define('APP', $sApp);
require APP . '/api/autoload.php';

use Core\Config;
use Engine\Bizkaibus\PaceFactors;
use Engine\Bizkaibus\RealtimeMatcher;
use Engine\Bizkaibus\SegmentTimes;
use Engine\Bizkaibus\TripOffsets;
use Models\ServiceJourney;

Config::set('bus');

// Las funciones de calibración viven en un script de línea de órdenes: se cargan sin ejecutar su main().
$sTool = file_get_contents(APP . '/engine/bizkaibus/tools/realtime-backtest.php');
$sTool = preg_replace('/^<\?php\s*/', '', $sTool);
$sTool = preg_replace('/^declare\(strict_types=1\);\s*$/m', '', $sTool);
$sTool = preg_replace('/^require .*autoload\.php.;\s*$/m', '', $sTool);
// red.php (la red de la herramienta) se carga aquí: dentro de eval(), __DIR__ apuntaría a esta carpeta.
require_once APP . '/engine/bizkaibus/tools/red.php';
$sTool = preg_replace('/^require __DIR__ \. .\/red\.php.;\s*$/m', '', $sTool);
$sTool = preg_replace('/^use [^;]+;\s*$/m', '', $sTool);
$sTool = preg_replace('/^ini_set\([^;]+;\s*$/m', '', $sTool);
$sTool = preg_replace('/^main\(\$argv\);\s*$/m', '', $sTool);
eval('use Core\Config; use Core\Database; use Core\Http; use Models\ServiceJourney; use Engine\Bizkaibus\PaceFactors; use Engine\Bizkaibus\RealtimeMatcher; use Engine\Bizkaibus\SegmentTimes; use Engine\Bizkaibus\SiriVehicleMonitoringClient; use Engine\Bizkaibus\TripOffsets; ' . $sTool);

$aVectors = [];

// ---------- 1. Percentil (mediana baja) ----------
$aVectors['percentil'] = [
    ['valores' => [5, 1, 4, 2, 3], 'p' => 0.5, 'resultado' => percentile([5, 1, 4, 2, 3], 0.5)],
    ['valores' => [1, 2, 3, 4], 'p' => 0.5, 'resultado' => percentile([1, 2, 3, 4], 0.5)],
    ['valores' => [10, 20, 30, 40, 50, 60, 70, 80, 90, 100], 'p' => 0.9, 'resultado' => percentile([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], 0.9)],
];

// ---------- 2. Franja horaria ----------
$aVectors['franja'] = [];
foreach ([['2026-10-28', 28950], ['2026-10-28', 21599], ['2026-10-28', 21600], ['2026-10-31', 75600], ['2026-10-28', 90000], ['2026-11-01', 46800]] as [$sD, $iS]) {
    $aVectors['franja'][] = ['fecha' => $sD, 'segundos' => $iS, 'franja' => PaceFactors::bandFor($sD, $iS)];
}

// ---------- 3. Factor k ----------
$Pace = new PaceFactors(['global' => ['laborable.punta_manana' => 0.9, 'laborable.noche' => 0.4], 'lines' => ['3414' => ['laborable.punta_manana' => 1.35]]]);
$aVectors['factor_k'] = [
    ['linea' => '3414', 'fecha' => '2026-10-28', 'segundos' => 28950, 'k' => $Pace->factor('3414', '2026-10-28', 28950)],
    ['linea' => '9999', 'fecha' => '2026-10-28', 'segundos' => 28950, 'k' => $Pace->factor('9999', '2026-10-28', 28950)],
    ['linea' => '9999', 'fecha' => '2026-10-28', 'segundos' => 79200, 'k' => $Pace->factor('9999', '2026-10-28', 79200)],
    ['linea' => '9999', 'fecha' => '2026-10-28', 'segundos' => 50400, 'k' => $Pace->factor('9999', '2026-10-28', 50400)],
    // El número de línea, con o sin ceros a la izquierda (el feed escribe 03414; el horario, 3414).
    ['linea' => '03414', 'fecha' => '2026-10-28', 'segundos' => 28950, 'k' => $Pace->factor('03414', '2026-10-28', 28950)],
];

// ---------- 4. Proyección sobre un segmento ----------
$Project = new ReflectionMethod(RealtimeMatcher::class, 'projectOntoSegment');
$aVectors['proyeccion'] = [];
foreach ([
    [43.2601, -2.9250, ['lat' => 43.2600, 'lon' => -2.9300], ['lat' => 43.2600, 'lon' => -2.9200]],
    [43.2605, -2.9350, ['lat' => 43.2600, 'lon' => -2.9300], ['lat' => 43.2600, 'lon' => -2.9200]],
    [43.2600, -2.9300, ['lat' => 43.2600, 'lon' => -2.9300], ['lat' => 43.2600, 'lon' => -2.9300]],
] as [$dLat, $dLon, $aA, $aB]) {
    [$dF, $dD, $dL] = $Project->invoke(null, $dLat, $dLon, $aA, $aB);
    $aVectors['proyeccion'][] = ['bus' => [$dLat, $dLon], 'A' => $aA, 'B' => $aB, 'f' => $dF, 'distancia_m' => $dD, 'largo_m' => $dL];
}

// ---------- 5. Cubos de largo y respaldo por largo ----------
$aVectors['cubo_largo'] = [];
foreach ([0, 299.9, 300, 999.9, 1000, 1499.9, 1500, 2999.9, 3000, 12000] as $dM) {
    $aVectors['cubo_largo'][] = ['metros' => $dM, 'cubo' => SegmentTimes::lengthBucket($dM)];
}
$Ratios = new SegmentTimes(['segments' => ['X>Y' => ['n' => 2, 'all' => 1]], 'lengthRatios' => ['2' => ['all' => 0.769, 'laborable.punta_manana' => 0.811], '4' => ['all' => 2.0], '5' => ['all' => 0.1]]]);
$aVectors['respaldo_largo'] = [
    ['horario_s' => 120, 'metros' => 800, 'franja' => 'laborable.punta_manana', 'segundos' => $Ratios->fallbackSeconds(120.0, 800.0, 'laborable.punta_manana')],
    ['horario_s' => 120, 'metros' => 800, 'franja' => 'fin_semana.noche', 'segundos' => $Ratios->fallbackSeconds(120.0, 800.0, 'fin_semana.noche')],
    ['horario_s' => 300, 'metros' => 2000, 'franja' => 'laborable.manana', 'segundos' => $Ratios->fallbackSeconds(300.0, 2000.0, 'laborable.manana')],
    ['horario_s' => 300, 'metros' => 5000, 'franja' => 'laborable.manana', 'segundos' => $Ratios->fallbackSeconds(300.0, 5000.0, 'laborable.manana')],
    ['horario_s' => 300, 'metros' => 100, 'franja' => 'laborable.manana', 'segundos' => $Ratios->fallbackSeconds(300.0, 100.0, 'laborable.manana')],
    ['horario_s' => 300, 'metros' => null, 'franja' => 'laborable.manana', 'segundos' => $Ratios->fallbackSeconds(300.0, null, 'laborable.manana')],
];

// ---------- 6. Tiempos por tramo (fitSegments) ----------
$aSeg = [];
$AddSample = function (string $sFrom, string $sTo, string $sTrack, string $sBand, float $dActual) use (&$aSeg) {
    $aSeg[] = ['track' => $sTrack, 'band' => $sBand, 'from' => $sFrom, 'to' => $sTo, 'actual' => $dActual];
};
// Tramo A>B: 2 buses en punta de la mañana (90, 100) y 6 a mediodía (58..64): la franja escasa se acerca a «todas horas».
$AddSample('A', 'B', 'b1', 'laborable.punta_manana', 90);
$AddSample('A', 'B', 'b2', 'laborable.punta_manana', 100);
foreach ([60, 58, 62, 64, 59, 61] as $i => $dSeconds) {
    $AddSample('A', 'B', 'm' . $i, 'laborable.mediodia', $dSeconds);
}
// Tramo B>C: un solo bus: no se aprende (mínimo 2).
$AddSample('B', 'C', 'b1', 'laborable.punta_manana', 75);
// Tramo C>D: 3 buses, todos en la misma franja: no se guarda «todas horas».
foreach ([200, 210, 190] as $i => $dSeconds) {
    $AddSample('C', 'D', 'c' . $i, 'laborable.noche', $dSeconds);
}
// Mismo bus dos veces en el tramo D>E: cuenta una vez (el último valor visto).
$AddSample('D', 'E', 'd1', 'laborable.manana', 50);
$AddSample('D', 'E', 'd1', 'laborable.manana', 70);
$AddSample('D', 'E', 'd2', 'laborable.manana', 60);
$aVectors['tiempos_tramo'] = ['muestras' => $aSeg, 'resultado' => fitSegments($aSeg)];

// ---------- 7. Factor k calibrado (shrunkFactor) ----------
$MakeTracks = function (array $aRatios): array {
    $aTracks = [];
    foreach ($aRatios as $i => $dR) {
        $aTracks['t' . $i] = [['actualRemaining' => 600 * $dR, 'scheduledRemaining' => 600]];
    }
    return $aTracks;
};
$aVectors['k_calibrado'] = [];
foreach ([[0.80, 0.82, 0.84, 0.86, 0.88, 0.90, 0.92, 0.94], array_fill(0, 40, 0.85), [1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.2, 2.3, 2.4, 2.5]] as $aR) {
    $aVectors['k_calibrado'][] = ['cocientes_por_bus' => $aR, 'k' => shrunkFactor($MakeTracks($aR))];
}
// Un bus con varias muestras: su cociente es suma(real)/suma(horario), no la media de cocientes.
$aVectors['k_un_bus'] = ['muestras' => [[100, 200], [300, 200]], 'k_sin_encoger' => (100 + 300) / (200 + 200)];

// ---------- 8. Hora real de paso (actualPassingTime) ----------
$aTrack = [['t' => 28900, 'sched' => 28880], ['t' => 28960, 'sched' => 28940], ['t' => 29020, 'sched' => 29030]];
$aVectors['paso_real'] = [
    ['pista' => $aTrack, 'llegada_programada' => 28950, 'paso_real' => actualPassingTime($aTrack, 28950)],
    ['pista' => $aTrack, 'llegada_programada' => 28800, 'paso_real' => actualPassingTime($aTrack, 28800)],
];

// ---------- 9. Aclarado de muestras de ritmo (thinSamples) ----------
$aMany = [];
for ($i = 0; $i < 100; $i++) {
    $aMany[] = ['track' => 'x', 'i' => $i];
}
$aVectors['aclarado'] = ['n' => 100, 'tope' => MAX_SAMPLES_PER_TRACK, 'indices' => array_column(thinSamples($aMany), 'i')];

// ---------- 10. Corrección por viaje (TripOffsets) ----------
// Un viaje con datos propios en laborable y en fin de semana, su línea con valor en una franja y el valor por franja.
$aTripTable = [
    'trips' => ['9999|S0|S4|28800|5' => ['laborable' => [20, 40, 60], 'fin_semana' => [-30, 0, 30]]],
    'lines' => ['L2' => ['laborable.punta_manana' => 15]],
    'global' => ['laborable.punta_manana' => 25, 'fin_semana.noche' => -10],
];
$Trips = new TripOffsets($aTripTable);
$aVectors['correccion_viaje'] = [
    'tabla' => $aTripTable,
    'clave' => TripOffsets::key('9999', 'S0', 'S4', 28800, 5),
    'tercios' => array_map(fn(array $aCase) => [$aCase[0], $aCase[1], TripOffsets::part($aCase[0], $aCase[1])], [[0, 5], [1, 5], [2, 5], [3, 5], [4, 5], [1, 3], [2, 3], [9, 5], [0, 0]]),
    'dia_servicio' => array_map(fn(array $aCase) => [$aCase[0], $aCase[1], TripOffsets::serviceDate($aCase[0], $aCase[1])], [['2026-10-12', true], ['2026-10-12', false], ['2026-10-17', true], ['2026-11-01', true], ['2026-12-08', true]]),
    'consultas' => [],
];
foreach ([
    ['9999|S0|S4|28800|5', '9999', '2026-10-28', 28800, 4, 5],
    ['9999|S0|S4|28800|5', '9999', '2026-10-28', 28800, 2, 5],
    ['9999|S0|S4|28800|5', '9999', '2026-10-31', 28800, 1, 5],
    ['L2|A|B|28800|3', 'L2', '2026-10-28', 28800, 1, 3],
    ['L2|A|B|72000|3', 'L2', '2026-10-31', 72000, 1, 3],
    ['L3|A|B|28800|3', 'L3', '2026-10-28', 28800, 1, 3],
    ['L3|A|B|50400|3', 'L3', '2026-10-28', 50400, 1, 3],
    // La misma consulta con el número de línea escrito como en el feed, con un cero delante.
    ['09999|S0|S4|28800|5', '09999', '2026-10-28', 28800, 4, 5],
] as [$sKey, $sLine, $sDate, $iDeparture, $iIndex, $iCount]) {
    $aVectors['correccion_viaje']['consultas'][] = ['clave' => $sKey, 'linea' => $sLine, 'fecha' => $sDate, 'salida' => $iDeparture, 'indice' => $iIndex, 'paradas' => $iCount, 'segundos' => $Trips->seconds($sKey, $sLine, $sDate, $iDeparture, $iIndex, $iCount)];
}

// ---------- 11. Calibración de la corrección por viaje (fitTripOffsets) ----------
// Desvíos (hora real menos capa 3 sin corregir) de dos viajes de la línea L1 y uno de la L2. El de 2 000 s se recorta a
// 900; el 12 de octubre es festivo y cuenta como fin de semana (su «serviceDate» es el domingo de esa semana).
$aTripResiduals = [];
$AddResidual = function (string $sDate, string $sServiceDate, string $sTrip, string $sLine, int $iDeparture, int $iIndex, int $iCount, float $dError) use (&$aTripResiduals) {
    $aTripResiduals[] = ['date' => $sDate, 'serviceDate' => $sServiceDate, 'trip' => $sTrip, 'line' => $sLine, 'departure' => $iDeparture, 'index' => $iIndex, 'count' => $iCount, 'error' => $dError];
};
$AddResidual('2026-10-26', '2026-10-26', 'L1|A|D|28800|4', 'L1', 28800, 1, 4, 100);
$AddResidual('2026-10-26', '2026-10-26', 'L1|A|D|28800|4', 'L1', 28800, 2, 4, 160);
$AddResidual('2026-10-26', '2026-10-26', 'L1|A|D|28800|4', 'L1', 28800, 3, 4, 220);
$AddResidual('2026-10-27', '2026-10-27', 'L1|A|D|28800|4', 'L1', 28800, 1, 4, 140);
$AddResidual('2026-10-27', '2026-10-27', 'L1|A|D|28800|4', 'L1', 28800, 3, 4, 2000);
$AddResidual('2026-10-26', '2026-10-26', 'L1|A|D|32400|4', 'L1', 32400, 2, 4, -60);
$AddResidual('2026-10-31', '2026-10-31', 'L1|A|D|32400|4', 'L1', 32400, 1, 4, 30);
$AddResidual('2026-10-12', '2026-10-18', 'L1|A|D|32400|4', 'L1', 32400, 3, 4, 50);
$AddResidual('2026-10-26', '2026-10-26', 'L2|X|Y|61200|6', 'L2', 61200, 5, 6, 300);
// Con el percentil de partida, 0,4 (en producción lo elige cada noche la recalibración).
$aVectors['calibracion_viaje'] = ['desvios' => $aTripResiduals, 'resultado' => fitTripOffsets($aTripResiduals, 0.4)];

// ---------- 12. El emparejador completo sobre un viaje sintético ----------
// Viaje 9999-101: 5 paradas en línea recta hacia el este a lo largo del paralelo 43,26 (Bilbao). Distancias reales.
const LAT = 43.2600;
const LON0 = -2.9300;
$dMPerDegLon = cos(deg2rad(LAT)) * 111320;
$aDist = [0, 400, 1000, 2500, 3200];
$aArr = [28800, 28890, 29010, 29310, 29430];
$aDep = [28800, 28890, 29010, 29310, 29430];

function viaje(bool $bShape, array|null $aArrOver = null, bool $bHoliday = false): PDO
{
    global $aDist, $aArr, $aDep, $dMPerDegLon;
    $aA = $aArrOver ?? $aArr;
    $aD = $aArrOver ?? $aDep;
    $Pdo = new PDO('sqlite::memory:');
    $Pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    $Pdo->exec('
        CREATE TABLE stops (id TEXT PRIMARY KEY, name TEXT, name_normalized TEXT, area TEXT DEFAULT \'\', area_normalized TEXT DEFAULT \'\', lat REAL, lon REAL, station_id TEXT, platform_label TEXT);
        CREATE TABLE service_journeys (id TEXT PRIMARY KEY, line_id TEXT, journey_pattern_id TEXT, trip_number TEXT, calendar_id TEXT, first_departure_seconds INTEGER, shape_id TEXT);
        CREATE TABLE passing_times (service_journey_id TEXT, seq_order INTEGER, stop_id TEXT, arrival_seconds INTEGER, departure_seconds INTEGER, dist_m REAL);
        CREATE TABLE trip_aliases (trip_id TEXT PRIMARY KEY, service_journey_id TEXT);
    ');
    if ($bShape) {
        $Pdo->exec('CREATE TABLE shapes (id TEXT PRIMARY KEY, points TEXT)');
    }
    $aPoints = [];
    foreach ($aDist as $i => $dM) {
        $dLon = LON0 + $dM / $dMPerDegLon;
        $Pdo->prepare('INSERT INTO stops (id, name, name_normalized, lat, lon) VALUES (?, ?, ?, ?, ?)')->execute(['S' . $i, 'S' . $i, 's' . $i, LAT, $dLon]);
        $Pdo->prepare('INSERT INTO passing_times VALUES (?, ?, ?, ?, ?, ?)')->execute(['J', $i + 1, 'S' . $i, $aA[$i], $aD[$i], $dM]);
        $aPoints[] = [LAT, $dLon, $dM];
    }
    $Pdo->exec("INSERT INTO service_journeys VALUES ('J', '9999', 'P', '101', 'C', 28800, 'SH')");
    $Pdo->exec("INSERT INTO trip_aliases VALUES ('trp_A9999_101_X_28800', 'J')");
    if ($bShape) {
        $Pdo->prepare('INSERT INTO shapes VALUES (?, ?)')->execute(['SH', json_encode($aPoints)]);
    }
    // Festivo: ese día circula por excepción un calendario de solo domingo.
    if ($bHoliday) {
        $Pdo->exec("
            CREATE TABLE service_calendars (id TEXT PRIMARY KEY, from_date TEXT, to_date TEXT, weekday_mask INTEGER);
            CREATE TABLE service_calendar_exceptions (calendar_id TEXT, date TEXT, available INTEGER);
            INSERT INTO service_calendars VALUES ('D', '2026-01-01', '2026-12-31', 64);
            INSERT INTO service_calendar_exceptions VALUES ('D', '" . FECHA . "', 1);
        ");
    }
    return $Pdo;
}

$Segments = new SegmentTimes([
    'segments' => [
        'S0>S1' => ['n' => 10, 'all' => 100, 'laborable.punta_manana' => 110],
        'S1>S2' => ['n' => 6, 'all' => 150, 'laborable.punta_manana' => 140],
    ],
    'lengthRatios' => ['4' => ['all' => 0.64, 'laborable.punta_manana' => 0.668], '2' => ['all' => 0.769, 'laborable.punta_manana' => 0.811]],
]);
$PaceK = new PaceFactors(['global' => ['laborable.punta_manana' => 0.9]]);
const FECHA = '2026-10-28';

function entrada(array $aOver): array
{
    return $aOver + [
        'tripRef' => 'trp_A9999_101_X_28800', 'lineId' => '9999', 'departureSeconds' => 28800, 'delaySeconds' => 0,
        'vehicleRef' => 'V1', 'currentStopId' => 'S2', 'order' => 3,
        'lat' => null, 'lon' => null, 'locationSeconds' => null, 'recordedSeconds' => null,
    ];
}
function fila(int $iStop, array $aArrUse): array
{
    return ['service_journey_id' => 'J', 'line_id' => '9999', 'trip_number' => '101', 'first_departure_seconds' => 28800, 'arrival_seconds' => $aArrUse[$iStop], 'stop_seq' => $iStop + 1];
}
function escenario(string $sNombre, array|null $aEntry = null, int $iNow = 28980, bool $bShape = true, array|null $aArrOver = null, SegmentTimes|null $Seg = null, TripOffsets|null $Trips = null, bool $bHoliday = false): array
{
    global $Segments, $PaceK, $aArr;
    $aArrUse = $aArrOver ?? $aArr;
    $aMap = [];
    if ($aEntry !== null) {
        $aMap = ['9999|101' => [$aEntry]];
    }
    $Matcher = new RealtimeMatcher($aMap, new ServiceJourney(viaje($bShape, $aArrOver, $bHoliday)), $iNow, $PaceK, FECHA, $Seg ?? $Segments, $Trips);
    $aOut = ['escenario' => $sNombre, 'ahora' => $iNow, 'entrada' => $aEntry, 'trazado' => $bShape, 'correccion_viaje' => $Trips !== null, 'festivo' => $bHoliday];
    if ($aEntry !== null) {
        $aOut['posicion'] = $Matcher->positionFor('J', $aEntry);
    }
    $aOut['paradas'] = [];
    foreach ($aArrUse as $i => $iA) {
        $aR = $Matcher->enrich([fila($i, $aArrUse)])[0];
        $aOut['paradas'][] = ['parada' => 'S' . $i, 'hora_publicada' => $iA, 'estado' => $aR['status'], 'llegada_estimada' => $aR['etaSeconds'], 'retraso_s' => $aR['delaySeconds']];
    }
    return $aOut;
}

$LonAt = fn(float $dM) => LON0 + $dM / $dMPerDegLon;
$aVectors['viaje'] = ['paradas' => array_map(fn($i) => ['id' => 'S' . $i, 'lat' => LAT, 'lon' => $LonAt((float)$aDist[$i]), 'dist_m' => $aDist[$i], 'llegada' => $aArr[$i], 'salida' => $aDep[$i]], array_keys($aDist)),
    'tramos_aprendidos' => ['S0>S1' => ['n' => 10, 'all' => 100, 'laborable.punta_manana' => 110], 'S1>S2' => ['n' => 6, 'all' => 150, 'laborable.punta_manana' => 140]],
    'proporciones' => ['4' => ['all' => 0.64, 'laborable.punta_manana' => 0.668], '2' => ['all' => 0.769, 'laborable.punta_manana' => 0.811]],
    'k' => ['laborable.punta_manana' => 0.9], 'fecha' => FECHA];
$dNorth11 = 0.0001; // ~11 m al norte del recorrido
$aVectors['escenarios'] = [
    escenario('Capa 1: GPS a 700 m, 11 m del trazado', entrada(['lat' => LAT + $dNorth11, 'lon' => $LonAt(700), 'locationSeconds' => 28950, 'recordedSeconds' => 28950])),
    escenario('Capa 1 sin trazado: proyección sobre la recta entre paradas', entrada(['lat' => LAT + $dNorth11, 'lon' => $LonAt(700), 'locationSeconds' => 28950, 'recordedSeconds' => 28950]), 28980, false),
    escenario('GPS a 60 m del trazado: no se usa (pasillo de 50 m); capa 2', entrada(['lat' => LAT + 60 / 111320, 'lon' => $LonAt(700), 'locationSeconds' => 28950, 'recordedSeconds' => 28950])),
    escenario('Capa 2: sin GPS, próxima parada S2 y hora del dato', entrada(['recordedSeconds' => 28950])),
    escenario('GPS y parada registrada discrepan más de 6 min: capa 3', entrada(['lat' => LAT + $dNorth11, 'lon' => $LonAt(2800), 'locationSeconds' => 29400, 'recordedSeconds' => 29400]), 29420),
    escenario('Capa 3: ningún dato del bus, antes de salir', null, 28700),
    escenario('Capa 3: ningún dato, el horario corregido ya pasó', null, 29600),
    escenario('Capa 3: horario publicado muy lento, el bus probablemente ya pasó', null, 31200, true, [28800, 28890, 29010, 30810, 30930], new SegmentTimes(['segments' => ['S0>S1' => ['n' => 9, 'laborable.punta_manana' => 110], 'S1>S2' => ['n' => 9, 'laborable.punta_manana' => 140], 'S2>S3' => ['n' => 9, 'laborable.punta_manana' => 240], 'S3>S4' => ['n' => 9, 'laborable.punta_manana' => 100]]])),
    escenario('Dato GPS de hace más de 10 min: no se usa', entrada(['lat' => LAT + $dNorth11, 'lon' => $LonAt(700), 'locationSeconds' => 28300, 'recordedSeconds' => 28300]), 28980),
    escenario('Capa 3 con la corrección por viaje de la tabla 10, antes de salir', null, 28700, true, null, null, $Trips),
    escenario('Capa 3 con corrección por viaje en un festivo: tramos y corrección de fin de semana', null, 28700, true, null, null, $Trips, true),
    escenario('Capa 1 en la primera parada: el bus espera 10 min antes de salir; llegada de la capa 3', entrada(['lat' => LAT + $dNorth11, 'lon' => $LonAt(0), 'locationSeconds' => 28200, 'recordedSeconds' => 28200, 'order' => 2, 'currentStopId' => 'S1']), 28210),
    escenario('Esperando a 600 m de la primera parada antes de salir: no se sitúa', entrada(['lat' => LAT + 600 / 111320, 'lon' => $LonAt(0), 'locationSeconds' => 28200, 'recordedSeconds' => 28200, 'order' => 2, 'currentStopId' => 'S1']), 28210),
    escenario('Llegando: la llegada a S2 ya pasó hace 80 s sin confirmar el paso; «0 min»', entrada(['lat' => LAT + $dNorth11, 'lon' => $LonAt(700), 'locationSeconds' => 28950, 'recordedSeconds' => 28950]), 29100),
    escenario('GPS 50 m pasada S2 y el feed aún en S2: no se da por pasada (regla de 150 m)', entrada(['lat' => LAT + $dNorth11, 'lon' => $LonAt(1050), 'locationSeconds' => 29020, 'recordedSeconds' => 29020]), 29040),
    escenario('Llegando hace más de 3 min sin confirmar el paso: «puede que ya haya pasado»', entrada(['lat' => LAT + $dNorth11, 'lon' => $LonAt(700), 'locationSeconds' => 28950, 'recordedSeconds' => 28950]), 29320),
];


// ---------- 17. Viajes que pasan de medianoche (RealtimeMatcher::daysAgo y vehiclesOfDay) ----------
// Un bus es de un viaje de ayer si su salida queda más de 12 h por delante de ahora; sus horas se cuentan entonces desde
// la medianoche de ayer (las 00:30 son las 24:30), y un dato sin hora de hoy no cuenta.
$aVectors['dia_del_viaje'] = ['casos' => []];
foreach ([[84600, 1800], [87000, 1800], [28800, 28980], [600, 85800], [45000, 1800], [45001, 1800]] as [$iDep, $iNow]) {
    $aVectors['dia_del_viaje']['casos'][] = ['salida' => $iDep, 'ahora' => $iNow, 'dias_atras' => RealtimeMatcher::daysAgo(['departureSeconds' => $iDep], $iNow)];
}
$aMidnightMap = [
    '9999|201' => [['tripRef' => 'trp_A9999_201_X_84600', 'departureSeconds' => 84600, 'vehicleRef' => 'V7', 'order' => 9, 'locationSeconds' => 1700, 'recordedSeconds' => 1710]],
    '9999|202' => [['tripRef' => 'trp_A9999_202_X_87000', 'departureSeconds' => 87000, 'vehicleRef' => 'V8', 'order' => 2, 'locationSeconds' => null, 'recordedSeconds' => 1750]],
    '9999|203' => [['tripRef' => 'trp_A9999_203_X_83000', 'departureSeconds' => 83000, 'vehicleRef' => 'V9', 'order' => 20]],
    '9999|101' => [['tripRef' => 'trp_A9999_101_X_1500', 'departureSeconds' => 1500, 'vehicleRef' => 'V1', 'order' => 2, 'locationSeconds' => 1790, 'recordedSeconds' => 1790]],
];
$aVectors['dia_del_viaje']['feed'] = $aMidnightMap;
$aVectors['dia_del_viaje']['ahora'] = 1800;
$aVectors['dia_del_viaje']['de_ayer'] = RealtimeMatcher::vehiclesOfDay($aMidnightMap, 1800, 1);
$aVectors['dia_del_viaje']['de_hoy'] = RealtimeMatcher::vehiclesOfDay($aMidnightMap, 1800, 0);

// ---------- 18. Buses que faltan en una lectura del feed (FeedMemory::withHeld) ----------
// Se sigue usando el último dato de un bus que falta, hasta 180 s, si su viaje no lo lleva ya otro bus y el bus no
// aparece en otro viaje.
$aHeldNow = ['9999|101' => [['tripRef' => 'trp_A9999_101_X_28800', 'vehicleRef' => 'V1', 'order' => 3, 'locationSeconds' => 29000]],
    '9999|102' => [['tripRef' => 'trp_A9999_102_X_30000', 'vehicleRef' => 'V3', 'order' => 1, 'locationSeconds' => 29000]]];
$aHeldPrevious = [
    '9999|101' => [['tripRef' => 'trp_A9999_101_X_28800', 'vehicleRef' => 'V9', 'order' => 2, 'locationSeconds' => 28950]],
    '9999|103' => [['tripRef' => 'trp_A9999_103_X_27000', 'vehicleRef' => 'V2', 'order' => 7, 'locationSeconds' => 28900]],
    '9999|104' => [['tripRef' => 'trp_A9999_104_X_27600', 'vehicleRef' => 'V4', 'order' => 5, 'locationSeconds' => 28800]],
    '9999|105' => [['tripRef' => 'trp_A9999_105_X_27600', 'vehicleRef' => 'V5', 'order' => 4, 'locationSeconds' => null, 'recordedSeconds' => 28830]],
    '9999|106' => [['tripRef' => 'trp_A9999_106_X_27600', 'vehicleRef' => 'V3', 'order' => 6, 'locationSeconds' => 28990]],
    '9999|107' => [['tripRef' => 'trp_A9999_107_X_27600', 'vehicleRef' => 'V6', 'order' => 6]],
    '9999|108' => [['tripRef' => 'trp_A9999_108_X_27600', 'vehicleRef' => 'V10', 'order' => 6, 'locationSeconds' => 29050]],
    '9999|109' => [['tripRef' => 'trp_A9999_109_X_27600', 'vehicleRef' => '', 'order' => 6, 'locationSeconds' => 29000]],
    '9999|110' => [['tripRef' => 'trp_A9999_110_X_27600', 'vehicleRef' => 'V11', 'order' => 3, 'locationSeconds' => 28820]],
];
$aVectors['buses_retenidos'] = ['feed' => $aHeldNow, 'anterior' => $aHeldPrevious, 'ahora' => 29010,
    'resultado' => \Engine\Bizkaibus\FeedMemory::withHeld($aHeldNow, $aHeldPrevious, 29010)];

// ---------- 19. Emparejado de cada bus del feed con su viaje del horario (RealtimeMatcher::lookup) ----------
// Primero por la referencia exacta del viaje (tabla trip_aliases); si no, por línea y número de viaje con la salida a
// 180 s o menos, la más cercana, sin reutilizar un bus que ya está emparejado exactamente con otro viaje.
function emparejado(string $sNombre, array $aEntries, string $sJourney, int $iDeparture = 28800): array
{
    $Matcher = new RealtimeMatcher(['9999|101' => $aEntries], new ServiceJourney(viaje(true)), 28980, null, FECHA, new SegmentTimes(), new TripOffsets());
    $aFound = $Matcher->lookup('9999', '101', $iDeparture, $sJourney);
    return ['caso' => $sNombre, 'buses' => $aEntries, 'viaje' => $sJourney, 'salida' => $iDeparture, 'bus' => $aFound['vehicleRef'] ?? null];
}
$aExact = ['tripRef' => 'trp_A9999_101_X_28800', 'departureSeconds' => 28800, 'vehicleRef' => 'VE'];
$aVectors['emparejado'] = [
    'alias' => ['trp_A9999_101_X_28800' => 'J'],
    'casos' => [
        emparejado('Referencia exacta', [['tripRef' => 'trp_A9999_101_Y_28700', 'departureSeconds' => 28800, 'vehicleRef' => 'VO'], $aExact], 'J'),
        emparejado('Sin referencia exacta: salida a 120 s', [['tripRef' => 'trp_A9999_101_Y_28920', 'departureSeconds' => 28920, 'vehicleRef' => 'VA']], 'J'),
        emparejado('Sin referencia exacta: salida a 180 s justos', [['tripRef' => 'trp_A9999_101_Y_28980', 'departureSeconds' => 28980, 'vehicleRef' => 'VA']], 'J'),
        emparejado('Sin referencia exacta: salida a 200 s, no se empareja', [['tripRef' => 'trp_A9999_101_Y_29000', 'departureSeconds' => 29000, 'vehicleRef' => 'VA']], 'J'),
        emparejado('Dos candidatos: el de salida más cercana', [['tripRef' => 'trp_A9999_101_Y_28650', 'departureSeconds' => 28650, 'vehicleRef' => 'VA'], ['tripRef' => 'trp_A9999_101_Y_28860', 'departureSeconds' => 28860, 'vehicleRef' => 'VB']], 'J'),
        emparejado('Otro viaje con la misma línea y número: el bus emparejado con J no se reutiliza', [$aExact], 'K', 28800),
        emparejado('Otro viaje: se usa el bus sin referencia exacta', [$aExact, ['tripRef' => 'trp_A9999_101_Y_28800', 'departureSeconds' => 28800, 'vehicleRef' => 'VC']], 'K', 28800),
    ],
];

// ---------- 20. Lectura del feed SIRI (SiriVehicleMonitoringClient::parse) ----------
$sSiri = '<?xml version="1.0" encoding="UTF-8"?>
<Siri xmlns="http://www.siri.org.uk/siri" version="2.0"><ServiceDelivery><VehicleMonitoringDelivery>
<VehicleActivity><RecordedAtTime>2026-10-28T08:02:40+01:00</RecordedAtTime><MonitoredVehicleJourney>
<VehicleJourneyRef>trp_A0651_737_ABC1_28500</VehicleJourneyRef><Delay>PT2M30S</Delay><VehicleRef>4021</VehicleRef>
<VehicleLocation><Longitude>-2.93</Longitude><Latitude>43.26</Latitude></VehicleLocation>
<LocationRecordedAtTime>2026-10-28T07:02:30Z</LocationRecordedAtTime>
<MonitoredCall><StopPointRef>0356</StopPointRef><Order>5</Order></MonitoredCall></MonitoredVehicleJourney></VehicleActivity>
<VehicleActivity><RecordedAtTime>2026-10-28T08:03:00+01:00</RecordedAtTime><MonitoredVehicleJourney>
<VehicleJourneyRef>trp_A3414_12_X_29100</VehicleJourneyRef><Delay>-PT45S</Delay><VehicleRef>4100</VehicleRef>
<MonitoredCall><StopPointRef>1201</StopPointRef><VisitNumber>2</VisitNumber></MonitoredCall></MonitoredVehicleJourney></VehicleActivity>
<VehicleActivity><RecordedAtTime>2026-10-27T23:59:00+01:00</RecordedAtTime><MonitoredVehicleJourney>
<VehicleJourneyRef>trp_A0651_801_ABC1_84000</VehicleJourneyRef><VehicleRef>4022</VehicleRef>
<VehicleLocation><Longitude>-2.95</Longitude><Latitude>43.25</Latitude></VehicleLocation>
<MonitoredCall><StopPointRef>0400</StopPointRef><Order>30</Order></MonitoredCall></MonitoredVehicleJourney></VehicleActivity>
<VehicleActivity><MonitoredVehicleJourney><VehicleJourneyRef>otro_formato_1</VehicleJourneyRef></MonitoredVehicleJourney></VehicleActivity>
</VehicleMonitoringDelivery></ServiceDelivery></Siri>';
$aVectors['lectura_feed'] = ['xml' => $sSiri, 'hoy' => FECHA, 'resultado' => \Engine\Bizkaibus\SiriVehicleMonitoringClient::parse($sSiri, FECHA)];

// ---------- 21. Registro de pasos (PassageLog) ----------
// Cada minuto se guarda, por referencia de viaje, «orden de la próxima parada:hora del dato»; al leer, por viaje del
// horario se queda el orden mayor de sus referencias. Con él, una parada de orden menor ya está pasada.
$aPassMap = ['9999|101' => [['tripRef' => 'trp_A9999_101_X_28800', 'order' => 3, 'recordedSeconds' => 29000, 'locationSeconds' => 28990],
    ['tripRef' => 'trp_A9999_101_Y_28800', 'order' => 2, 'recordedSeconds' => null, 'locationSeconds' => 28900]],
    '9999|102' => [['tripRef' => 'trp_A9999_102_X_30000', 'order' => null, 'recordedSeconds' => 29000], ['tripRef' => '', 'order' => 1, 'recordedSeconds' => 29000],
    ['tripRef' => 'trp_A9999_102_Z_30000', 'order' => 4, 'recordedSeconds' => null, 'locationSeconds' => null]]];
$aVectors['registro_pasos'] = [
    'feed' => $aPassMap,
    'campos' => \Engine\Bizkaibus\PassageLog::fields($aPassMap),
    'campos_paradas' => \Engine\Bizkaibus\PassageLog::stopFields($aPassMap),
    'lectura' => ['viaje_de_cada_campo' => ['J', 'J', 'K', 'K'], 'valores' => ['3:29000', '5:29100', null, 'mal'],
        'resultado' => \Engine\Bizkaibus\PassageLog::merge(['J', 'J', 'K', 'K'], ['3:29000', '5:29100', null, 'mal'])],
    'historial' => ['hash' => ['trp_A1#3' => '29000', 'trp_A1#1' => '28800', 'trp_A2#2' => '30000', 'mal' => '1', 'trp_A1#4' => 'x'],
        'resultado' => \Engine\Bizkaibus\PassageLog::stopsFromHash(['trp_A1#3' => '29000', 'trp_A1#1' => '28800', 'trp_A2#2' => '30000', 'mal' => '1', 'trp_A1#4' => 'x'])],
];

// Escenario: el viaje ya no está en el feed, pero el registro dice que se vio con la próxima parada S3 (orden 4) a
// las 29 300: S0, S1 y S2 están pasadas; S3 y S4 siguen con la capa 3.
function escenarioPasos(string $sNombre, array $aPassage, int $iNow): array
{
    global $Segments, $PaceK, $aArr;
    $Matcher = new RealtimeMatcher([], new ServiceJourney(viaje(true)), $iNow, $PaceK, FECHA, $Segments, null);
    $Matcher->setPassageLoader(fn(array $aIds) => ['J' => $aPassage]);
    $aOut = ['escenario' => $sNombre, 'ahora' => $iNow, 'paso_registrado' => $aPassage, 'paradas' => []];
    foreach ($aArr as $i => $iA) {
        $aR = $Matcher->enrich([fila($i, $aArr)])[0];
        $aOut['paradas'][] = ['parada' => 'S' . $i, 'hora_publicada' => $iA, 'estado' => $aR['status'], 'llegada_estimada' => $aR['etaSeconds'], 'retraso_s' => $aR['delaySeconds']];
    }
    return $aOut;
}
$aVectors['escenarios_pasos'] = [
    escenarioPasos('Sin bus en el feed; el registro lo vio con la próxima parada S3', ['order' => 4, 'seconds' => 29300], 29400),
    escenarioPasos('El paso registrado es posterior a ahora: la hora mostrada es ahora', ['order' => 2, 'seconds' => 29000], 28990),
];

// ---------- 22. Retraso que se muestra del bus (displayDelayMinutes y displayDelaySeconds) ----------
$Display = new RealtimeMatcher([], null, 28980, $PaceK, FECHA, $Segments, null);
$aVectors['retraso_mostrado'] = ['minutos' => []];
foreach ([null, 29, 30, 31, 89, 90, -29, -30, -31, -90, 2700, 2701, -2701] as $iDelay) {
    $aVectors['retraso_mostrado']['minutos'][] = ['segundos' => $iDelay, 'minutos' => $Display->displayDelayMinutes($iDelay)];
}
$aVectors['retraso_mostrado']['buses'] = [];
foreach ([
    ['Con GPS: el retraso en la próxima parada', entrada(['lat' => LAT + $dNorth11, 'lon' => $LonAt(700), 'locationSeconds' => 28950, 'recordedSeconds' => 28950]), 28980],
    ['Sin GPS: el retraso de la parada registrada', entrada(['recordedSeconds' => 28950]), 28980],
    ['Dato GPS viejo y sin hora de la lectura: 0', entrada(['lat' => LAT + $dNorth11, 'lon' => $LonAt(700), 'locationSeconds' => 28300]), 28980],
] as [$sName, $aEntry, $iNow]) {
    $Matcher = new RealtimeMatcher(['9999|101' => [$aEntry]], new ServiceJourney(viaje(true)), $iNow, $PaceK, FECHA, $Segments, null);
    $aVectors['retraso_mostrado']['buses'][] = ['caso' => $sName, 'entrada' => $aEntry, 'ahora' => $iNow,
        'retraso_actual_s' => $Matcher->currentDelaySeconds('J', $aEntry), 'retraso_mostrado_s' => $Matcher->displayDelaySeconds('J', $aEntry)];
}

// ---------- 23. Elección nocturna del percentil de la corrección por viaje ----------
// Se aprende con los días anteriores y se prueba en el último: queda el percentil que más acierta a ±2 min y, con
// empate, el de menos error medio (calibrateTrips). Errores con fitTripOffsets y tripOffsetErrors del motor.
$aRankResiduals = [];
$aErrorsByDay = ['2026-10-26' => [150, 340, 50, 320, 40], '2026-10-27' => [290, 190, 380, 60, 210], '2026-10-28' => [-70, 30, 120, 330, 240], '2026-10-29' => [250, 0, 210, -70, -100]];
foreach ($aErrorsByDay as $sDay => $aErrs) {
    foreach ($aErrs as $iIdx => $iErr) {
        $aRankResiduals[] = ['date' => $sDay, 'serviceDate' => $sDay, 'trip' => 'L1|A|D|28800|6', 'line' => 'L1', 'departure' => 28800, 'index' => 1 + $iIdx, 'count' => 6, 'error' => (float)$iErr];
    }
}
$aTrainR = array_values(array_filter($aRankResiduals, fn($a) => $a['date'] < '2026-10-29'));
$aTestR = array_values(array_filter($aRankResiduals, fn($a) => $a['date'] >= '2026-10-29'));
$aPerRank = [];
$dChosen = TRIP_OFFSET_RANKS[0];
$aBestR = null;
foreach (TRIP_OFFSET_RANKS as $dCand) {
    $aE = tripOffsetErrors($aTestR, fitTripOffsets($aTrainR, $dCand));
    $aPerRank[] = ['percentil' => $dCand, 'error_medio_s' => $aE[1], 'a_2_min' => $aE[3]];
    if ($aBestR === null || [$aE[3], -$aE[1]] > [$aBestR[3], -$aBestR[1]]) {
        $aBestR = $aE;
        $dChosen = $dCand;
    }
}
$aVectors['eleccion_percentil'] = ['candidatos' => TRIP_OFFSET_RANKS, 'desvios' => $aRankResiduals, 'primer_dia_de_prueba' => '2026-10-29',
    'por_percentil' => $aPerRank, 'elegido' => $dChosen, 'sin_corregir' => ['error_medio_s' => $aBestR[0], 'a_2_min' => $aBestR[2]],
    // La tabla nueva solo se escribe si baja el error medio de los días de prueba.
    'se_escribe' => $aBestR[1] < $aBestR[0]];

file_put_contents(__DIR__ . '/vectores.json', json_encode($aVectors, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_PRESERVE_ZERO_FRACTION) . "\n");
echo json_encode($aVectors, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_PRESERVE_ZERO_FRACTION), "\n";
