import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objects as go
import pandas as pd
from collections import defaultdict

# Load dataset
file_path = "Travelers_Itineraries.tsv"
df = pd.read_csv(file_path, sep="\t")

# Process travel sequences
df_sorted = df.sort_values(by=["travelerNames", "travelIndex"])
transition_paths = defaultdict(lambda: defaultdict(int))
memoryless_transitions = defaultdict(lambda: defaultdict(int))

# Build transition paths based on complete travel history
for traveler, group in df_sorted.groupby("travelerNames"):
    places = group["placeOfVisit"].tolist()
    for i in range(len(places) - 1):
        prev_cities = tuple(places[:i+1])  # Track entire past sequence
        next_city = places[i + 1]
        if prev_cities not in transition_paths:
            transition_paths[prev_cities] = defaultdict(int)
        transition_paths[prev_cities][next_city] += 1

        # Build memoryless transitions (only considers direct connections)
        memoryless_transitions[places[i]][next_city] += 1

# Extract coordinates
df["latitude"] = df["coordinates"].str.split(",").str[0].astype(float)
df["longitude"] = df["coordinates"].str.split(",").str[1].astype(float)
place_coords = df.groupby("placeOfVisit")[["latitude", "longitude"]].mean().to_dict("index")

# Sort places alphabetically for dropdown
sorted_places = sorted(df["placeOfVisit"].unique())

# Dash App Setup
app = dash.Dash(__name__)
app.layout = html.Div([
    html.Div([
        dcc.Dropdown(
            id="mode-dropdown",
            options=[
                {"label": "Memoryless Mode", "value": "memoryless"},
                {"label": "Path-Based Mode", "value": "path-based"},
            ],
            value="memoryless",
            clearable=False,
            style={"width": "48%", "display": "inline-block", "margin-right": "2%"}
        ),
        dcc.Dropdown(
            id="city-dropdown",
            options=[{"label": city, "value": city} for city in sorted_places],
            placeholder="Select a city to start",
            style={"width": "48%", "display": "inline-block"}
        ),
    ], style={"width": "100%", "text-align": "center", "margin-bottom": "5px"}),

    html.Div(id="travel-path", style={"border": "1px solid black", "padding": "5px", "min-height": "30px", "width": "80%", "margin": "0 auto 5px auto"}),

    dcc.Graph(id="travel-map", config={"scrollZoom": True}, style={"height": "85vh", "width": "100%"}),

    dcc.Store(id="path-memory", data={"visited": [], "current": None})
])

@app.callback(
    Output("travel-map", "figure"),
    Output("path-memory", "data"),
    Output("travel-path", "children"),
    Input("city-dropdown", "value"),
    Input("travel-map", "clickData"),
    State("mode-dropdown", "value"),
    State("path-memory", "data")
)
def update_map(selected_start_city, clickData, mode, path_memory):
    if not selected_start_city:
        return go.Figure(), path_memory, "Select a city to begin your journey."

    visited_places = path_memory["visited"]
    current_city = path_memory["current"] or selected_start_city

    if not visited_places:
        visited_places.append(selected_start_city)

    if clickData and "points" in clickData:
        try:
            clicked_city = clickData["points"][0].get("text", "").split(" (")[0]
            if mode == "path-based":
                prev_cities_tuple = tuple(visited_places)
                next_destinations = transition_paths.get(prev_cities_tuple, {})
            else:
                next_destinations = memoryless_transitions.get(current_city, {})

            if clicked_city in next_destinations:
                visited_places.append(clicked_city)
                current_city = clicked_city
        except (IndexError, AttributeError, KeyError):
            pass

    fig = go.Figure()
    for place in visited_places:
        if place in place_coords:
            fig.add_trace(go.Scattergeo(
                lon=[place_coords[place]["longitude"]],
                lat=[place_coords[place]["latitude"]],
                mode="markers",
                marker=dict(size=14, color="blue"),
                name="Visited"
            ))

    if mode == "path-based" and len(visited_places) > 1:
        fig.add_trace(go.Scattergeo(
            lon=[place_coords[place]["longitude"] for place in visited_places if place in place_coords],
            lat=[place_coords[place]["latitude"] for place in visited_places if place in place_coords],
            mode="lines",
            line=dict(width=2, color="lightblue"),
            hoverinfo="none"
        ))

    next_destinations = memoryless_transitions.get(current_city, {}) if mode == "memoryless" else transition_paths.get(tuple(visited_places), {})
    total_transitions = sum(next_destinations.values())
    top_destinations = sorted(next_destinations.items(), key=lambda x: x[1], reverse=True)[:5]

    for place, count in top_destinations:
        probability = (count / total_transitions) * 100 if total_transitions > 0 else 0
        if place in place_coords:
            fig.add_trace(go.Scattergeo(
                lon=[place_coords[place]["longitude"]],
                lat=[place_coords[place]["latitude"]],
                text=[f"{place} ({probability:.1f}%, {count})"],
                mode="markers+text",
                marker=dict(size=8 + (probability / 5), color="orange"),
                textposition="top center"
            ))
            fig.add_trace(go.Scattergeo(
                lon=[place_coords[current_city]["longitude"], place_coords[place]["longitude"]],
                lat=[place_coords[current_city]["latitude"], place_coords[place]["latitude"]],
                mode="lines",
                line=dict(width=3, color="gray"),
                hoverinfo="none"
            ))

    fig.update_layout(
        geo=dict(
            scope="europe",
            showland=True,
            landcolor="rgb(217, 217, 217)",
            center={"lat": 42, "lon": 12},
            projection_scale=7.5
        ),
        showlegend=False
    )

    travel_path_text = " → ".join(visited_places)
    return fig, {"visited": visited_places, "current": current_city}, travel_path_text

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run_server(debug=False, host="0.0.0.0", port=port)
    server = app.server
