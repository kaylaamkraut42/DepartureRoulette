import pandas as pd
import duckdb
from pathlib import Path

df = pd.read_csv("Airline_Delay_Cause.csv")

def carrier_names():
    carrier_names = df['carrier_name'].unique().tolist()
    return carrier_names

def airport_names(carrier_name):
    df_filtered = df[df["carrier_name"] == carrier_name]
    airport_names = df_filtered["airport_name"].unique().tolist()
    return airport_names

def _filtered_data(carrier_name, airport_name=None, month=None, year=None):
    mask = df["carrier_name"] == carrier_name
    for column, value in (("airport_name", airport_name), ("month", month), ("year", year)):
        if value is not None:
            mask &= df[column] == value
    return df.loc[mask]


def summary(carrier_name, airport_name=None, month=None, year=None):
    filtered_row = _filtered_data(carrier_name, airport_name, month, year)

    if filtered_row.empty:
        return None

    arrived_flight_count = filtered_row["arr_flights"].sum()
    arrived_delay_count = filtered_row["arr_del15"].sum()
    delay_rate = arrived_delay_count / arrived_flight_count if arrived_flight_count > 0 else 0.0
    return arrived_flight_count, arrived_delay_count, delay_rate

def get_month_name(month_num):
    months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sept','Oct','Nov','Dec']
    return months[month_num-1]


def delay_causes(carrier_name, airport_name=None, month=None, year=None):
    cause_columns = {
        "carrier_ct": "Airline",
        "weather_ct": "Weather",
        "nas_ct": "National aviation system",
        "security_ct": "Security",
        "late_aircraft_ct": "Late arriving aircraft",
    }
    selected = _filtered_data(carrier_name, airport_name, month, year)[list(cause_columns)]
    counts = selected.sum().rename(index=cause_columns)
    causes = counts.rename_axis("Cause").reset_index(name="Delayed flights")
    causes = causes.loc[causes["Delayed flights"] > 0].copy()
    total = causes["Delayed flights"].sum()
    causes["Share"] = causes["Delayed flights"] / total if total > 0 else 0.0
    return causes

def get_airport_code(airport_name):
    df_filtered = df[df["airport_name"] == airport_name]
    row = df_filtered.iloc[0]
    return row['airport']

def return_delays_df():
    delays = duckdb.sql("""
        SELECT carrier_name, SUM(arr_del15) AS total_delays
        FROM df
        GROUP BY carrier_name
        ORDER BY total_delays DESC
    """).df()
    return delays


def annual_airport_delays(year, carrier_name=None):
    selected = df.loc[df["year"] == year]
    if carrier_name is not None:
        selected = selected.loc[selected["carrier_name"] == carrier_name]
    selected = selected.copy()
    selected["airport_name"] = selected["airport_name"].fillna(selected["airport"])
    totals = selected.groupby(["airport", "airport_name"], as_index=False).agg(
        total_flights=("arr_flights", "sum"),
        delayed_flights=("arr_del15", "sum"),
    )
    totals["delay_rate"] = (
        totals["delayed_flights"].div(totals["total_flights"].where(totals["total_flights"] > 0))
        .fillna(0) * 100
    )
    coordinates = pd.read_csv(Path(__file__).with_name("airport_coordinates.csv"))
    return totals.merge(coordinates, on="airport", how="left", validate="many_to_one").sort_values(
        ["delayed_flights", "airport"], ascending=[False, True]
    ).reset_index(drop=True)
