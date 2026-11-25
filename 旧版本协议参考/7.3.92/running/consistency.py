"""Local geometry and totals checks; no network or protocol assumptions."""
import bisect
import math

EARTH_RADIUS_M = 6371000.0


def coordinate(lat, lon):
    if isinstance(lat, bool) or isinstance(lon, bool):
        raise ValueError("coordinates must be finite numbers")
    lat, lon = float(lat), float(lon)
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("coordinates are out of range")
    return lat, lon


def distance(a, b):
    lat1, lon1 = map(math.radians, coordinate(*a))
    lat2, lon2 = map(math.radians, coordinate(*b))
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return EARTH_RADIUS_M * 2 * math.asin(min(1.0, math.sqrt(max(0.0, h))))


def interpolate(a, b, fraction):
    if fraction <= 0:
        return a
    if fraction >= 1:
        return b
    angle = distance(a, b) / EARTH_RADIUS_M
    if angle < 1e-12:
        return a
    if abs(math.sin(angle)) < 1e-12:
        raise ValueError("antipodal route points cannot be interpolated")
    xyz = []
    for lat, lon in (a, b):
        lat, lon = math.radians(lat), math.radians(lon)
        xyz.append((math.cos(lat)*math.cos(lon), math.cos(lat)*math.sin(lon), math.sin(lat)))
    wa, wb = math.sin((1-fraction)*angle)/math.sin(angle), math.sin(fraction*angle)/math.sin(angle)
    x, y, z = (wa*xyz[0][i] + wb*xyz[1][i] for i in range(3))
    return math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))


def validate_totals(seconds, steps, start, stop, meters):
    if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds <= 0:
        raise ValueError("duration must be a positive integer")
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
        raise ValueError("steps must be a nonnegative integer")
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (start, stop)) or stop-start != seconds*1000:
        raise ValueError("timestamps do not match totalTime")
    if isinstance(meters, bool) or not isinstance(meters, (int, float)) or not math.isfinite(meters) or meters <= 0:
        raise ValueError("distance must be a finite positive number")


def sample_route(waypoints, meters, seconds, start, require_all=True):
    validate_totals(seconds, 0, start, start + seconds*1000, meters)
    route = []
    for point in waypoints:
        point = coordinate(*point)
        if not route or distance(route[-1], point) > 1e-6:
            route.append(point)
    if len(route) > 1 and distance(route[0], route[-1]) <= 1e-6:
        route.pop()
    if len(route) < 2:
        raise ValueError("at least two distinct route points are required")
    minimum = sum(distance(a, b) for a, b in zip(route, route[1:]))
    if require_all and meters + .001 < minimum:
        raise ValueError("target distance is too short to visit the supplied points")
    # Keep corners as samples so interpolation cannot cut across the route.
    vertices = [route[0]]
    cumulative = [0.0]
    edge = 0
    while cumulative[-1] < meters - 1e-8:
        a, b = route[edge % len(route)], route[(edge+1) % len(route)]
        length = distance(a, b)
        remaining = meters-cumulative[-1]
        if length >= remaining:
            vertices.append(interpolate(a, b, remaining/length))
            cumulative.append(float(meters))
        else:
            vertices.append(b)
            cumulative.append(cumulative[-1]+length)
        edge += 1
        if edge > 100000:
            raise ValueError("route has too many segments")
    duration_ms = seconds*1000
    samples = {}
    for elapsed in range(0, duration_ms, 3000):
        traveled = meters*elapsed/duration_ms
        index = min(len(vertices)-2, max(0, bisect.bisect_right(cumulative, traveled)-1))
        fraction = (traveled-cumulative[index])/(cumulative[index+1]-cumulative[index])
        samples[elapsed] = interpolate(vertices[index], vertices[index+1], fraction)
    corner_times = set()
    for point, traveled in zip(vertices, cumulative):
        elapsed = round(duration_ms*traveled/meters)
        if elapsed in corner_times:
            raise ValueError("route corners are too close for millisecond timestamps")
        corner_times.add(elapsed)
        samples[elapsed] = point
    return [(lat, lon, start+elapsed) for elapsed, (lat, lon) in sorted(samples.items())]


def check_track(points, meters, seconds, start, stop, fixed_points=()):
    validate_totals(seconds, 0, start, stop, meters)
    if len(points) < 2 or points[0].time != start or points[-1].time != stop:
        raise ValueError("track endpoints do not match run timestamps")
    for point in points:
        coordinate(point.lat, point.lon)
        if not isinstance(point.time, int) or not math.isfinite(point.speed) or point.speed < 0:
            raise ValueError("invalid track timestamp or speed")
    if any(a.time >= b.time for a, b in zip(points, points[1:])):
        raise ValueError("track timestamps must strictly increase")
    actual = sum(distance((a.lat, a.lon), (b.lat, b.lon)) for a, b in zip(points, points[1:]))
    if abs(actual-meters) > max(.1, meters*.0001):
        raise ValueError(f"track length {actual:.3f}m differs from totalDis {meters}m")
    for fixed in fixed_points:
        if not any(distance((fixed.lat, fixed.lon), (point.lat, point.lon)) <= .1 for point in points):
            raise ValueError("a checkpoint is missing from the track")
    return actual


def time_buckets(seconds, steps, start, stop, meters):
    validate_totals(seconds, steps, start, stop, meters)
    duration_ms = seconds*1000
    cents = round(meters*100)
    for begin in range(0, duration_ms, 10000):
        end = min(begin+10000, duration_ms)
        count = steps*end//duration_ms - steps*begin//duration_ms
        length = (cents*end//duration_ms - cents*begin//duration_ms)/100
        yield start+begin, start+end, count, length
