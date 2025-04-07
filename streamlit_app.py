import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import datetime

# Use caching to speed up file loading
@st.cache_data
def load_station_data(file):
    df = pd.read_csv(file)
    # Ensure valid coordinates are present
    df = df.dropna(subset=['LatitudeMeasure', 'LongitudeMeasure'])
    return df

@st.cache_data
def load_narrowresult_data(file):
    df = pd.read_csv(file)
    # Convert dates and measurement values
    df['ActivityStartDate'] = pd.to_datetime(df['ActivityStartDate'], errors='coerce')
    df['ResultMeasureValue'] = pd.to_numeric(df['ResultMeasureValue'], errors='coerce')
    # Remove rows with missing or invalid date/measurement info
    df = df.dropna(subset=['ActivityStartDate', 'ResultMeasureValue'])
    return df

# App title and instructions
st.title("Contaminant Analysis and Mapping")
st.write(
    "Upload the station database and the narrow result database. "
    "Then select a contaminant, set the measurement and date ranges, "
    "and view the map and trend plot for the selected contaminant."
)

# Sidebar file uploaders for both CSV databases
st.sidebar.header("Upload Databases")
station_file = st.sidebar.file_uploader("Upload Station Database (CSV)", type=["csv"])
narrowresult_file = st.sidebar.file_uploader("Upload Narrow Result Database (CSV)", type=["csv"])

if station_file is not None and narrowresult_file is not None:
    # Load data
    station_df = load_station_data(station_file)
    narrowresult_df = load_narrowresult_data(narrowresult_file)

    # --- Data Cleaning (Optional but Recommended) ---
    station_df["MonitoringLocationIdentifier"] = station_df["MonitoringLocationIdentifier"].str.strip().str.lower()
    narrowresult_df["MonitoringLocationIdentifier"] = narrowresult_df["MonitoringLocationIdentifier"].str.strip().str.lower()

    st.sidebar.header("Contaminant and Filter Options")
    # Get unique contaminants from the narrowresult database
    contaminants = narrowresult_df["CharacteristicName"].unique()
    selected_contaminant = st.sidebar.selectbox("Select Contaminant", contaminants)

    # Filter narrowresult data for the chosen contaminant
    filtered_initial = narrowresult_df[narrowresult_df["CharacteristicName"] == selected_contaminant]
    if filtered_initial.empty:
        st.error("No records found for the selected contaminant.")
    else:
        # Define measurement value range
        min_value = float(filtered_initial["ResultMeasureValue"].min())
        max_value = float(filtered_initial["ResultMeasureValue"].max())
        measurement_range = st.sidebar.slider(
            "Select Measurement Value Range",
            min_value=min_value, max_value=max_value,
            value=(min_value, max_value)
        )

        # Define date range (convert to date objects)
        min_date = filtered_initial["ActivityStartDate"].min().date()
        max_date = filtered_initial["ActivityStartDate"].max().date()
        date_range = st.sidebar.date_input(
            "Select Date Range", value=(min_date, max_date),
            min_value=min_date, max_value=max_date
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = min_date
            end_date = max_date

        # Filter narrowresult data by contaminant, measurement range, and date range
        mask = (
            (narrowresult_df["CharacteristicName"] == selected_contaminant) &
            (narrowresult_df["ResultMeasureValue"] >= measurement_range[0]) &
            (narrowresult_df["ResultMeasureValue"] <= measurement_range[1]) &
            (narrowresult_df["ActivityStartDate"].dt.date >= start_date) &
            (narrowresult_df["ActivityStartDate"].dt.date <= end_date)
        )
        filtered_df = narrowresult_df[mask]

        st.subheader("Filtered Data Overview")
        st.write(f"Total records: {len(filtered_df)}")

        # Get unique station names from the filtered narrowresult data
        station_names = filtered_df["MonitoringLocationIdentifier"].unique()
        # Filter station_df for these stations
        filtered_stations = station_df[station_df["MonitoringLocationIdentifier"].isin(station_names)].copy()
        filtered_stations["LatitudeMeasure"] = pd.to_numeric(filtered_stations["LatitudeMeasure"], errors='coerce')
        filtered_stations["LongitudeMeasure"] = pd.to_numeric(filtered_stations["LongitudeMeasure"], errors='coerce')
        filtered_stations = filtered_stations.dropna(subset=['LatitudeMeasure', 'LongitudeMeasure'])

        st.subheader("Map of Stations (Based on Selected Characteristic)")
        if not filtered_stations.empty:
            # Compute center of the map for filtered stations
            center_lat_filtered = filtered_stations["LatitudeMeasure"].mean()
            center_lon_filtered = filtered_stations["LongitudeMeasure"].mean()
            m_filtered = folium.Map(location=[center_lat_filtered, center_lon_filtered], zoom_start=6)
            # Add markers for each station
            for _, row in filtered_stations.iterrows():
                folium.Marker(
                    location=[row["LatitudeMeasure"], row["LongitudeMeasure"]],
                    popup=row["MonitoringLocationIdentifier"]
                ).add_to(m_filtered)
            # Display the map using streamlit-folium
            st_folium(m_filtered, width=700, height=500, key="filtered_map") # Added a key
        else:
            st.write("No stations found with the selected criteria for this characteristic.")

        st.subheader("Trend Over Time")
        # Create a time-series plot for the selected contaminant, grouped by station
        fig, ax = plt.subplots(figsize=(12, 6))
        for site, group in filtered_df.groupby("MonitoringLocationIdentifier"):
            group_sorted = group.sort_values("ActivityStartDate")
            ax.plot(
                group_sorted["ActivityStartDate"],
                group_sorted["ResultMeasureValue"],
                marker="o", label=site
            )
        ax.set_xlabel("Time")
        ax.set_ylabel("Measured Value")
        ax.set_title(f"Trend Over Time for {selected_contaminant}")
        ax.legend(title="Station", bbox_to_anchor=(1.05, 1), loc="upper left")
        plt.tight_layout()
        st.pyplot(fig)
else:
    st.info("Please upload both databases (CSV files) in the sidebar to continue.")
