"""
Strava Activity Trends - Streamlit App

Shows trends over time (distance, pace, elevation) across ALL your Strava
activity types, using data pulled live from the Strava API.

Run with:
    streamlit run app.py

Credentials can be provided either:
  1. In the sidebar at runtime, or
  2. In a .streamlit/secrets.toml file:

        [strava]
        client_id = "12345"
        client_secret = "abc123..."
        refresh_token = "def456..."

Get client_id/client_secret from https://www.strava.com/settings/api
Get refresh_token by running get_refresh_token.py once.
"""

import time
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st
import plotly.express as px


STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"

st.set_page_config(page_title="Strava Trends", page_icon="🏃", layout="wide")


# ---------- Credentials ----------
def get_credentials():
    secrets_strava = st.secrets.get("strava", {}) if hasattr(st, "secrets") else {}

    st.sidebar.header("Strava API Credentials")
    client_id = st.sidebar.text_input(
        "Client ID", value=secrets_strava.get("client_id", "")
    )
    client_secret = st.sidebar.text_input(
        "Client Secret", value=secrets_strava.get("client_secret", ""), type="password"
    )
    refresh_token = st.sidebar.text_input(
        "Refresh Token", value=secrets_strava.get("refresh_token", ""), type="password"
    )

    st.sidebar.caption(
        "Don't have a refresh token yet? Run `get_refresh_token.py` once "
        "from your terminal to generate one."
    )
    return client_id, client_secret, refresh_token


# ---------- API calls ----------
@st.cache_data(ttl=3000, show_spinner=False)
def get_access_token(client_id, client_secret, refresh_token):
    resp = requests.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


@st.cache_data(ttl=900, show_spinner=False)
def fetch_all_activities(access_token, after_epoch):
    headers = {"Authorization": f"Bearer {access_token}"}
    activities = []
    page = 1
    per_page = 200

    while True:
        resp = requests.get(
            STRAVA_ACTIVITIES_URL,
            headers=headers,
            params={"after": after_epoch, "page": page, "per_page": per_page},
        )
        print(resp.status_code)
        print(resp.text)
        resp.raise_for_status()
        batch = resp.json()

        if not batch:
            break
        activities.extend(batch)
        page += 1
        if len(batch) < per_page:
            break
        time.sleep(0.2)  # be nice to Strava's rate limits

    return activities


def activities_to_dataframe(activities):
    if not activities:
        return pd.DataFrame()

    df = pd.json_normalize(activities)
    keep = [
        "name",
        "type",
        "sport_type",
        "start_date_local",
        "distance",
        "moving_time",
        "elapsed_time",
        "total_elevation_gain",
        "average_speed",
        "average_heartrate",
        "kudos_count",
    ]
    keep = [c for c in keep if c in df.columns]
    df = df[keep].copy()

    df["start_date_local"] = pd.to_datetime(df["start_date_local"])
    df["distance_km"] = df["distance"] / 1000
    df["distance_mi"] = df["distance"] / 1609.34
    df["moving_time_min"] = df["moving_time"] / 60

    # Pace: minutes per km, guard against divide-by-zero
    df["pace_min_per_km"] = df.apply(
        lambda r: (r["moving_time_min"] / r["distance_km"])
        if r["distance_km"] > 0
        else None,
        axis=1,
    )
    df["pace_min_per_mi"] = df.apply(
        lambda r: (r["moving_time_min"] / r["distance_mi"])
        if r["distance_mi"] > 0
        else None,
        axis=1,
    )

    return df.sort_values("start_date_local")


# ---------- App ----------
def main():
    st.title("🏃 Strava Activity Trends")
    st.caption("Distance, pace, and elevation trends across all your activities.")

    client_id, client_secret, refresh_token = get_credentials()

    if not (client_id and client_secret and refresh_token):
        st.info(
            "Enter your Strava Client ID, Client Secret, and Refresh Token in the "
            "sidebar to get started. See the README for setup steps."
        )
        return

    st.sidebar.divider()
    lookback_days = st.sidebar.slider(
        "How far back to load?", min_value=30, max_value=1825, value=365, step=30
    )
    unit = st.sidebar.radio("Units", ["Kilometers", "Miles"], horizontal=True)
    rolling_window = st.sidebar.slider(
        "Trend smoothing (rolling avg, # activities)", 1, 20, 5
    )

    try:
        access_token = get_access_token(client_id, client_secret, refresh_token)
    except requests.HTTPError as e:
        st.error(f"Could not authenticate with Strava: {e}")
        return

    after_epoch = int((datetime.now() - timedelta(days=lookback_days)).timestamp())

    with st.spinner("Fetching activities from Strava..."):
        try:
            raw_activities = fetch_all_activities(access_token, after_epoch)
        except requests.HTTPError as e:
            st.error(f"Error fetching activities: {e}")
            return

    df = activities_to_dataframe(raw_activities)

    if df.empty:
        st.warning("No activities found in this date range.")
        return

    # Activity type filter
    all_types = sorted(df["type"].unique().tolist())
    selected_types = st.multiselect(
        "Filter by activity type", options=all_types, default=all_types
    )
    df = df[df["type"].isin(selected_types)]

    if df.empty:
        st.warning("No activities match the selected filters.")
        return

    dist_col = "distance_km" if unit == "Kilometers" else "distance_mi"
    dist_label = "km" if unit == "Kilometers" else "mi"
    pace_col = "pace_min_per_km" if unit == "Kilometers" else "pace_min_per_mi"
    pace_label = f"min/{dist_label}"

    df[f"{dist_col}_roll"] = df[dist_col].rolling(rolling_window, min_periods=1).mean()
    df[f"{pace_col}_roll"] = df[pace_col].rolling(rolling_window, min_periods=1).mean()
    df["elevation_roll"] = (
        df["total_elevation_gain"].rolling(rolling_window, min_periods=1).mean()
    )

    # ---------- Summary metrics ----------
    st.subheader("Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Activities", len(df))
    c2.metric(f"Total Distance ({dist_label})", f"{df[dist_col].sum():,.1f}")
    c3.metric("Total Moving Time (hrs)", f"{df['moving_time_min'].sum() / 60:,.1f}")
    c4.metric(
        "Total Elevation Gain (m)", f"{df['total_elevation_gain'].sum():,.0f}"
    )

    st.divider()

    # ---------- Trend charts ----------
    st.subheader("Distance Over Time")
    fig_dist = px.scatter(
        df,
        x="start_date_local",
        y=dist_col,
        color="type",
        opacity=0.5,
        labels={"start_date_local": "Date", dist_col: f"Distance ({dist_label})"},
    )
    fig_dist.add_scatter(
        x=df["start_date_local"],
        y=df[f"{dist_col}_roll"],
        mode="lines",
        name=f"Rolling avg ({rolling_window})",
        line=dict(width=3),
    )
    st.plotly_chart(fig_dist, use_container_width=True)

    st.subheader("Pace Over Time")
    pace_df = df.dropna(subset=[pace_col])
    fig_pace = px.scatter(
        pace_df,
        x="start_date_local",
        y=pace_col,
        color="type",
        opacity=0.5,
        labels={"start_date_local": "Date", pace_col: f"Pace ({pace_label})"},
    )
    fig_pace.add_scatter(
        x=pace_df["start_date_local"],
        y=pace_df[f"{pace_col}_roll"],
        mode="lines",
        name=f"Rolling avg ({rolling_window})",
        line=dict(width=3),
    )
    fig_pace.update_yaxes(autorange="reversed")  # lower pace = faster, show at top
    st.plotly_chart(fig_pace, use_container_width=True)

    st.subheader("Elevation Gain Over Time")
    fig_elev = px.scatter(
        df,
        x="start_date_local",
        y="total_elevation_gain",
        color="type",
        opacity=0.5,
        labels={"start_date_local": "Date", "total_elevation_gain": "Elevation Gain (m)"},
    )
    fig_elev.add_scatter(
        x=df["start_date_local"],
        y=df["elevation_roll"],
        mode="lines",
        name=f"Rolling avg ({rolling_window})",
        line=dict(width=3),
    )
    st.plotly_chart(fig_elev, use_container_width=True)

    st.divider()
    st.subheader("Raw Activities")
    display_cols = [
        "start_date_local",
        "name",
        "type",
        dist_col,
        "moving_time_min",
        pace_col,
        "total_elevation_gain",
    ]
    st.dataframe(
        df[display_cols].sort_values("start_date_local", ascending=False),
        use_container_width=True,
        hide_index=True,
    )


if __name__ == "__main__":
    main()

