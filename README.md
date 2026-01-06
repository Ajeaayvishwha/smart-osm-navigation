# Smart OSM Navigation System

The Smart OSM Navigation System is a Python-based navigation application that utilizes OpenStreetMap (OSM) data to compute optimal routes between locations. The system focuses on real-world map data processing, shortest path computation, and interactive route visualization.

## Objective
The main objective of this project is to design an intelligent navigation system that can identify the shortest path between two locations using graph-based algorithms while also estimating distance and travel time.

## Features
- Extracts real-world map data from OpenStreetMap
- Identifies the nearest graph nodes for given source and destination coordinates
- Computes the shortest path using Dijkstra’s Algorithm / A* Search
- Calculates total distance and Estimated Time of Arrival (ETA)
- Visualizes routes using an interactive web-based map interface
- Backend logic handled through a Flask API

## System Modules
- Graph Extraction Module – Retrieves and constructs graph data from OSM
- Nearest Node Identification Module – Maps input coordinates to closest graph nodes
- Shortest Path Computation Module – Calculates optimal routes
- ETA and Distance Calculation Module – Computes total distance and travel time
- Flask Backend API Module – Connects backend logic with frontend
- Frontend Visualization Module – Displays routes on an interactive map

## Technologies Used
- Python
- Flask
- OpenStreetMap (OSM)
- OSMnx
- NetworkX
- Graph Algorithms (Dijkstra / A*)
- HTML, CSS, JavaScript (for frontend visualization)

## How to Run
1. Clone the repository
2. Install required dependencies:
