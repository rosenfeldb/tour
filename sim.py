import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objects as go
import pandas as pd
import random
from collections import defaultdict

# Load dataset
file_path = "Travelers_Itineraries.tsv"
df = pd.read_csv(file_path, sep="\t")

# Process travel sequences
df_sorted = df.sort_values(by=["travelerNames", "travelIndex"])
memoryless_transitions = defaultdict(lambda: defaultdict(int))
path_based_transitions = defaultdict(lambda: defaultdict(int))
first_city_counts = defaultdict(int)
traveler_paths = {}

# Build transition probabilities and first city weights
for traveler, group in df_sorted.groupby("travelerNames"):
    places = group["placeOfVisit"].tolist()
    traveler_paths[tuple(places)] = traveler
    if places:
        first_city_counts[places[0]] += 1
    for i in range(len(places) - 1):
        current_place, next_place = places[i], places[i + 1]
        memoryless_transitions[current_place][next_place] += 1
        path_based_transitions[tuple(places[:i+1])][next_place] += 1

# Normalize probabilities
first_city_total = sum(first_city_counts.values())
first_city_probs = {city: count / first_city_total for city, count in first_city_counts.items()}
memoryless_probabilities = {
    place: {next_place: count / sum(transitions.values()) for next_place, count in transitions.items()}
    for place, transitions in memoryless_transitions.items()
}
path_based_probabilities = {
    path: {next_place: count / sum(transitions.values()) for next_place, count in transitions.items()}
    for path, transitions in path_based_transitions.items()
}

# Extract coordinates
df["latitude"] = df["coordinates"].str.split(",").str[0].astype(float)
df["longitude"] = df["coordinates"].str.split(",").str[1].astype(float)
place_coords = df.groupby("placeOfVisit")[["latitude", "longitude"]].mean().to_dict("index")

# Dash App Setup
app = dash.Dash(__name__)
app.layout = html.Div([
    dcc.Dropdown(
        id="mode-dropdown",
        options=[
            {"label": "Memoryless Mode", "value": "memoryless"},
            {"label": "Path-Based Mode", "value": "path-based"},
        ],
        value="memoryless",
        clearable=False,
        style={"width": "50%", "margin": "0 auto 10px auto"}
    ),
    html.Button("Start Simulation", id="start-btn", n_clicks=0, style={"display": "block", "margin": "0 auto 10px auto"}),
    dcc.Interval(id="interval-component", interval=2000, n_intervals=0, disabled=True),
    html.Div(id="travel-path", style={"border": "1px solid black", "padding": "5px", "min-height": "30px", "width": "80%", "margin": "0 auto 5px auto"}),
    dcc.Graph(id="travel-map", config={"scrollZoom": True}, style={"height": "85vh", "width": "100%"}),
    dcc.Store(id="path-memory", data={"visited": [], "current": None, "active": False, "mode": "memoryless"})
])

@app.callback(
    Output("interval-component", "disabled"),
    Output("travel-map", "figure"),
    Output("travel-path", "children"),
    Output("path-memory", "data"),
    Input("start-btn", "n_clicks"),
    Input("interval-component", "n_intervals"),
    State("mode-dropdown", "value"),
    State("path-memory", "data")
)
def update_simulation(n_clicks, n_intervals, mode, path_memory):
    fig = go.Figure()
    fig.update_layout(
        geo=dict(
            scope="europe",
            showland=True,
            landcolor="rgb(217, 217, 217)",
            center={"lat": 45, "lon": 10},
            projection_scale=2.5
        ),
        showlegend=False
    )
    
    if n_clicks == 0 and not path_memory["active"]:
        return True, fig, "Click 'Start Simulation' to begin.", path_memory
    
    if not path_memory["active"]:
        # Start a new simulation
        start_city = random.choices(list(first_city_probs.keys()), weights=first_city_probs.values())[0]
        path_memory = {"visited": [start_city], "current": start_city, "active": True, "mode": mode}
        return False, go.Figure(), "Simulation starting...", path_memory
    
    visited_places = path_memory["visited"]
    current_city = path_memory["current"]
    
    if mode == "memoryless":
        next_options = memoryless_probabilities.get(current_city, {})
    else:
        next_options = path_based_probabilities.get(tuple(visited_places), {})
    
    if not next_options:
        path_memory["active"] = False

        # Rebuild the final map before stopping
        final_fig = go.Figure()
        final_fig.update_layout(
            geo=dict(
                scope="europe",
                showland=True,
                landcolor="rgb(217, 217, 217)",
                center={"lat": 45, "lon": 10},
                projection_scale=2.5
            ),
            showlegend=False
        )
    
        for place in visited_places:
            if place in place_coords:
                final_fig.add_trace(go.Scattergeo(
                    lon=[place_coords[place]["longitude"]],
                    lat=[place_coords[place]["latitude"]],
                    mode="markers",
                    marker=dict(size=14, color="blue"),
                    name="Visited"
                ))

        if len(visited_places) > 1:
            line_lons = [place_coords[place]["longitude"] for place in visited_places if place in place_coords]
            line_lats = [place_coords[place]["latitude"] for place in visited_places if place in place_coords]

            final_fig.add_trace(go.Scattergeo(
                lon=line_lons,
                lat=line_lats,
                mode="lines+markers",
                line=dict(width=2, color="lightblue"),
                marker=dict(size=8, color="blue"),
                hoverinfo="none"
            ))


        if mode == "path-based":
            traveler_name = traveler_paths.get(tuple(visited_places), "Unknown Traveler")
            return True, final_fig, html.Div([
                html.P(f"Simulation complete! Traveler: {traveler_name}"),
                html.P(f"Travel Path: {' → '.join(visited_places)}")
            ]), path_memory
        return True, final_fig, "Simulation complete!", path_memory

    
    next_city = random.choices(list(next_options.keys()), weights=next_options.values())[0]
    visited_places.append(next_city)
    path_memory["current"] = next_city
    
    fig = go.Figure()
    fig.update_layout(
        geo=dict(
            scope="europe",
            showland=True,
            landcolor="rgb(217, 217, 217)",
            center={"lat": 45, "lon": 10},
            projection_scale=2.5
        ),
        showlegend=False
    )
    for place in visited_places:
        if place in place_coords:
            fig.add_trace(go.Scattergeo(
                lon=[place_coords[place]["longitude"]],
                lat=[place_coords[place]["latitude"]],
                mode="markers",
                marker=dict(size=14, color="blue"),
                name="Visited"
            ))
    
    if len(visited_places) > 1:
        fig.add_trace(go.Scattergeo(
            lon=[place_coords[place]["longitude"] for place in visited_places if place in place_coords],
            lat=[place_coords[place]["latitude"] for place in visited_places if place in place_coords],
            mode="lines",
            line=dict(width=2, color="lightblue"),
            hoverinfo="none"
        ))
    
    travel_path_text = " → ".join(visited_places)
    return False, fig, travel_path_text, path_memory

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run_server(debug=False, host="0.0.0.0", port=port)
    server = app.server
