"""
smart_navigation_osm.py
Simple Flask app that:
- downloads an OSM drive graph for a city/center
- exposes /route?start=lat,lon&end=lat,lon returning route coordinates + ETA + distance
- serves a minimal Leaflet UI at /
"""

from flask import Flask, request, jsonify, render_template_string
import osmnx as ox
import networkx as nx
import math
import threading

app = Flask(__name__)

# ---------- CONFIG ----------
# center point used to download OSM graph (change to your city)
CENTER_LAT = 12.9716   # default Bangalore center
CENTER_LON = 77.5946
DIST_METERS = 15000    # radius (meters) for graph extraction
MAX_GRAPH_NODES = 200000

# default travel speed (m/s) used for ETA if edge speed missing
DEFAULT_SPEED_MPS = 13.89  # ~50 km/h

# ---------- GLOBALS ----------
G = None
graph_lock = threading.Lock()

# ---------- HELPERS ----------
def load_graph(center_lat=CENTER_LAT, center_lon=CENTER_LON, dist=DIST_METERS):
    """Download OSM 'drive' network around center. Cache in global G."""
    global G
    with graph_lock:
        if G is None:
            print(f"Downloading OSM graph around {center_lat},{center_lon} dist={dist}m ...")
            # network_type 'drive' gives drivable roads
            G = ox.graph_from_point((center_lat, center_lon), dist=dist, network_type="drive")
            # simplify and ensure length attributes exist
            G = ox.add_edge_lengths(G)
            print("Graph downloaded: nodes=%d edges=%d" % (len(G.nodes), len(G.edges)))
        return G

def nearest_node(lat, lon):
    """Return nearest node id in G for given lat/lon."""
    Glocal = load_graph()
    # ox.nearest_nodes expects x=lon, y=lat
    return ox.distance.nearest_nodes(Glocal, X=lon, Y=lat)

def route_nodes_between(start_lat, start_lon, end_lat, end_lon):
    Glocal = load_graph()
    src = nearest_node(start_lat, start_lon)
    tgt = nearest_node(end_lat, end_lon)
    # compute shortest path by length (meters)
    route = nx.shortest_path(Glocal, src, tgt, weight="length")
    return route

def route_coords_from_nodes(route_nodes):
    Glocal = load_graph()
    coords = []
    for n in route_nodes:
        node = Glocal.nodes[n]
        # node['x'] = lon, node['y'] = lat
        coords.append([node['y'], node['x']])  # [lat, lon] for Leaflet easy use
    return coords

def route_length_meters(src_node, tgt_node):
    Glocal = load_graph()
    return nx.shortest_path_length(Glocal, src_node, tgt_node, weight="length")

def compute_eta_seconds(distance_meters):
    # naive ETA using default speed. Could be enhanced using edge maxspeed when available.
    if distance_meters <= 0:
        return 0
    return distance_meters / DEFAULT_SPEED_MPS

# ---------- FLASK ROUTES ----------
@app.route("/")
def index():
    # minimal Leaflet UI to demo routing
    return render_template_string("""
<!doctype html>
<html>
<head>
  <title>Smart OSM Navigation (demo)</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>body{margin:0} #map{position:absolute;left:0;top:0;bottom:0;width:75%} #panel{position:absolute;right:0;top:0;bottom:0;width:25%;padding:10px;overflow:auto;background:#f7f7f7}</style>
</head>
<body>
<div id="map"></div>
<div id="panel">
  <h3>Smart OSM Navigation (demo)</h3>
  <label>Origin (lat,lon)</label><br>
  <input id="origin" value="{{center_lat}}, {{center_lon}}" style="width:100%"><br><br>
  <label>Destination (lat,lon)</label><br>
  <input id="dest" value="{{center_lat-0.02}}, {{center_lon+0.02}}" style="width:100%"><br><br>
  <button id="btn">Compute Route</button>
  <hr>
  <div id="info"></div>
  <p style="font-size:12px;color:#666">Tip: click on map to copy coords into focused input</p>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
var map = L.map('map').setView([{{center_lat}}, {{center_lon}}], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19}).addTo(map);
var routeLayer = L.geoJSON().addTo(map);

map.on('click', function(e){
  // put coords into focused input
  var active = document.activeElement;
  if(active && (active.id==='origin' || active.id==='dest')) {
     active.value = e.latlng.lat.toFixed(6) + ", " + e.latlng.lng.toFixed(6);
  }
});

document.getElementById('btn').onclick = async function(){
  routeLayer.clearLayers();
  var o = document.getElementById('origin').value.trim();
  var d = document.getElementById('dest').value.trim();
  if(!o || !d) { alert('enter coords'); return; }
  try {
    var res = await fetch('/route?start='+encodeURIComponent(o)+'&end='+encodeURIComponent(d));
    var j = await res.json();
    if(j.error) {
      document.getElementById('info').innerText = 'Error: ' + j.error;
      return;
    }
    // draw polyline (route coords are [lat,lon])
    var poly = L.polyline(j.route_coords, {weight:4, color:'blue'}).addTo(map);
    map.fitBounds(poly.getBounds(), {padding:[50,50]});
    // add markers
    L.marker(j.route_coords[0]).addTo(map);
    L.marker(j.route_coords[j.route_coords.length-1]).addTo(map);
    document.getElementById('info').innerHTML =
       '<b>Distance:</b> ' + (j.distance_km.toFixed(3)) + ' km<br>' +
       '<b>ETA (min):</b> ' + (j.eta_min.toFixed(2)) + ' min';
  } catch(err){
    document.getElementById('info').innerText = 'Request failed: ' + err;
  }
}
</script>
</body>
</html>
    """, center_lat=CENTER_LAT, center_lon=CENTER_LON)

@app.route("/route")
def route_api():
    """
    Query params:
      start=lat,lon   (e.g. 12.97,77.59)
      end=lat,lon
    Returns JSON:
      { distance_km, eta_min, route_coords: [[lat,lon], ...] }
    """
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    if not start or not end:
        return jsonify({"error": "send start and end query params like start=lat,lon"}), 400
    try:
        s_lat, s_lon = [float(x.strip()) for x in start.split(",")]
        e_lat, e_lon = [float(x.strip()) for x in end.split(",")]
    except Exception as e:
        return jsonify({"error": "invalid coordinate format"}), 400

    try:
        Glocal = load_graph()
        src = nearest_node(s_lat, s_lon)
        tgt = nearest_node(e_lat, e_lon)
        # If src or tgt are far outside graph, we might want to reject; here we try anyway
        route_nodes = nx.shortest_path(Glocal, src, tgt, weight="length")
        # total length meters
        total_m = nx.shortest_path_length(Glocal, src, tgt, weight="length")
        eta_s = compute_eta_seconds(total_m)
        coords = route_coords_from_nodes(route_nodes)
        return jsonify({
            "distance_km": total_m/1000.0,
            "eta_min": eta_s/60.0,
            "route_coords": coords
        })
    except nx.NetworkXNoPath:
        return jsonify({"error": "no path found between those points (not connected in graph)"}), 404
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500

# ---------- START ----------
if __name__ == "__main__":
    # load graph on startup in background thread to reduce first-request delay
    t = threading.Thread(target=load_graph, args=(CENTER_LAT, CENTER_LON, DIST_METERS))
    t.daemon = True
    t.start()
    app.run(host="127.0.0.1", port=5000, debug=True)
