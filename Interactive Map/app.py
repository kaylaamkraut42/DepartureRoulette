import streamlit as st
import altair as alt
import folium
import streamlit.components.v1 as components
from html import escape
from helpers import *

"""This is a streamlit application. To run enter streamlit run app.py"""

st.title("Airline Delays")

with st.sidebar:
    carrier = st.selectbox(
        "Airline Carrier",
        carrier_names()
    )
    view = st.radio("View", ["Monthly by airport", "Annual airline summary"])
    year = st.number_input(
        "Year",
        min_value = 2023,
        max_value = 2026,
        step = 1
    )
    airport = None
    month = None
    if view == "Monthly by airport":
        airport = st.selectbox("Airport", airport_names(carrier))
        month = st.number_input("Month", min_value=1, max_value=12, step=1)

with st.container(border = True):
    if view == "Monthly by airport":
        period = f"{get_month_name(month)}, {year}"
        selection = f"{carrier} arriving at {get_airport_code(airport)} in {period}"
    else:
        selection = f"{carrier} across all airports in {year}"
        st.caption("Annual totals include all available months in the selected year.")
    result = summary(carrier, airport, month, year)
    
    if result is None:
        st.warning(f"No data available for {selection}.")
    else:
        arrived_count, delay_count, delay_rate = result
        st.write(f"Delay statistics for {selection}")
        col1, col2 = st.columns(2)

        with col1:
            st.metric("Total Flights", arrived_count)

        with col2:
            st.metric("Delayed Flights", delay_count)

        st.write(f"Percentage of flights arriving ≥ 15 minutes: {delay_rate*100:.1f}%")

        st.progress(delay_rate)

        st.subheader("Delay causes")
        causes = delay_causes(carrier, airport, month, year)
        if causes.empty:
            st.info("No delay causes recorded for this selection.")
        else:
            chart = alt.Chart(causes).encode(
                theta=alt.Theta("Delayed flights:Q", stack=True),
                color=alt.Color("Cause:N", title="Delay cause"),
                order=alt.Order("Cause:N"),
                tooltip=[
                    alt.Tooltip("Cause:N", title="Delay cause"),
                    alt.Tooltip("Delayed flights:Q", format=".2f"),
                    alt.Tooltip("Share:Q", format=".1%"),
                ],
            )
            donut = chart.mark_arc(innerRadius=75, outerRadius=130)
            labels = chart.mark_text(radius=105).encode(
                text=alt.Text("Share:Q", format=".0%"),
                color=alt.value("white"),
            )
            st.altair_chart((donut + labels).properties(height=320), use_container_width=True)
            st.caption(
                "Share of recorded delay causes for the current selection. "
                "Counts may be fractional when a flight has multiple causes."
            )

st.subheader(f"Airport delays in {year}")
map_scope = st.radio("Map airlines", ["All airlines", "Selected airline"], horizontal=True)
st.caption(
    "Annual totals use all available months, regardless of the monthly filter. "
    "Larger circles mean more arrivals delayed by at least 15 minutes. "
    "Pan, zoom, and hover over an airport to explore."
)
try:
    airports = annual_airport_delays(year, carrier if map_scope == "Selected airline" else None)
except (OSError, ValueError) as exc:
    st.error(f"Unable to load airport map coordinates: {exc}")
else:
    if airports.empty:
        st.info("No airport data available for this year and airline selection.")
    else:
        mapped = airports.dropna(subset=["latitude", "longitude"]).copy()
        missing = len(airports) - len(mapped)
        if missing:
            st.info(f"{missing} airports have no coordinates; they are included in the table below.")
        if not mapped.empty:
            maximum = mapped["delayed_flights"].max()
            mapped["radius"] = (mapped["delayed_flights"] / maximum) ** 0.5 * 35 if maximum > 0 else 3
            mapped = mapped.sort_values("radius", ascending=False)
            airport_map = folium.Map(
                location=[39, -98], zoom_start=3,
                tiles="OpenStreetMap", height=500,
            )
            airport_map.get_root().html.add_child(folium.Element("""
                <div style="position:fixed; bottom:25px; left:12px; z-index:1000;
                            background:white; color:#222; padding:12px 16px;
                            border:1px solid #ccc; border-radius:6px;
                            box-shadow:0 1px 5px #999; font-size:13px;
                            max-width:280px; pointer-events:none;">
                    <b>Airport delay counts</b><br>
                    Bigger circle = more delayed flights<br>
                    <span style="font-size:12px;">Number of arrivals delayed 15+ minutes</span>
                </div>
            """))
            for row in mapped.itertuples(index=False):
                details = (
                    f"<b>{escape(str(row.airport))}: {escape(str(row.airport_name))}</b><br>"
                    f"Total flights: {row.total_flights:,.0f}<br>"
                    f"Delayed flights: {row.delayed_flights:,.0f}<br>"
                    f"Delay rate: {row.delay_rate:.1f}%"
                )
                folium.CircleMarker(
                    location=[row.latitude, row.longitude],
                    radius=max(3, float(row.radius)),
                    color="#dc4b2d", weight=1,
                    fill=True, fill_color="#dc4b2d", fill_opacity=0.65,
                    tooltip=folium.Tooltip(details),
                    popup=folium.Popup(details, max_width=350),
                ).add_to(airport_map)
            components.html(airport_map.get_root().render(), height=520)
        st.dataframe(
            airports[["airport", "airport_name", "total_flights", "delayed_flights", "delay_rate"]]
            .rename(columns={"airport": "Airport", "airport_name": "Airport name",
                             "total_flights": "Total flights", "delayed_flights": "Delayed flights",
                             "delay_rate": "Delay rate (%)"}),
            hide_index=True,
        )
        st.caption("Airport coordinates: [OurAirports](https://ourairports.com/data/) (public domain).")
