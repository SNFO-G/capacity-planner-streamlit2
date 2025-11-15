
import streamlit as st
import pandas as pd
import altair as alt

from cap_planner_app.model_core import load_baseline, compute_allocation

st.set_page_config(page_title="Capacity Planner", layout="wide")

st.title("Production Capacity Planner")
st.caption("Upload updated CSVs or use the baseline files to calculate allocations, line utilization, and fill rates.")

st.sidebar.header("Inputs")
st.sidebar.write("You can either use the built in baseline data or upload new CSV files for any of the inputs.")

# Load baseline data from package
rates_base, calendar_base, demand_base = load_baseline()

def read_or_default(uploaded, default_df, name):
    if uploaded is not None:
        try:
            return pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"Could not read {name} CSV: {e}")
            return default_df
    return default_df

calendar_file = st.sidebar.file_uploader("Calendar CSV", type="csv", key="calendar")
demand_file = st.sidebar.file_uploader("Demand CSV", type="csv", key="demand")
rates_file = st.sidebar.file_uploader("Rates CSV", type="csv", key="rates")

use_baseline = st.sidebar.checkbox("Always use baseline files", value=False)

if use_baseline:
    cal = calendar_base.copy()
    dem = demand_base.copy()
    rates = rates_base.copy()
else:
    cal = read_or_default(calendar_file, calendar_base, "calendar")
    dem = read_or_default(demand_file, demand_base, "demand")
    rates = read_or_default(rates_file, rates_base, "rates")

run_clicked = st.button("Run optimization")

if not run_clicked:
    st.info("Upload files if needed and click 'Run optimization' to generate results.")
else:
    with st.spinner("Running optimization..."):
        alloc_df, util_df, fill_df, meta = compute_allocation(rates, cal, dem)

    st.success("Optimization complete.")

    products = meta.get("products", [])
    lines = meta.get("lines", [])
    months = meta.get("months", [])

    # Summary metrics
    st.subheader("Highlights")
    c1, c2, c3 = st.columns(3)

    total_mt = alloc_df["MT"].sum() if not alloc_df.empty else 0.0
    c1.metric("Total production (MT)", f"{total_mt:,.1f}")

    if "Utilization" in util_df.columns and not util_df.empty:
        avg_util = util_df["Utilization"].mean()
        c2.metric("Average line utilization", f"{avg_util * 100:,.1f}%")
    else:
        c2.metric("Average line utilization", "n/a")

    if "Fill_Rate" in fill_df.columns and not fill_df.empty:
        avg_fill = fill_df["Fill_Rate"].dropna().mean()
        c3.metric("Average demand coverage", f"{avg_fill * 100:,.1f}%")
    else:
        c3.metric("Average demand coverage", "n/a")

    st.markdown("---")

    # Allocations
    st.subheader("Allocations")
    if not alloc_df.empty:
        prod_opts = ["All"] + sorted(alloc_df["PRODUCT"].dropna().unique().tolist())
        sel_prod = st.selectbox("Filter by product", prod_opts, key="alloc_filter")
        if sel_prod != "All":
            alloc_view = alloc_df[alloc_df["PRODUCT"] == sel_prod]
        else:
            alloc_view = alloc_df

        st.dataframe(alloc_view, use_container_width=True)

        if not alloc_view.empty:
            chart_alloc = alt.Chart(alloc_view).mark_bar().encode(
                x="Month:N",
                y="sum(MT):Q",
                color="PRODUCT:N",
                tooltip=list(alloc_view.columns)
            ).properties(height=260)
            st.altair_chart(chart_alloc, use_container_width=True)
    else:
        st.write("No allocation results.")

    st.markdown("---")

    # Line utilization
    st.subheader("Line utilization")
    if not util_df.empty:
        line_opts = ["All"] + sorted(util_df["Line"].dropna().unique().tolist())
        sel_line = st.selectbox("Filter by line", line_opts, key="util_filter")
        if sel_line != "All":
            util_view = util_df[util_df["Line"] == sel_line]
        else:
            util_view = util_df

        st.dataframe(util_view, use_container_width=True)

        if not util_view.empty and "Utilization" in util_view.columns:
            chart_util = alt.Chart(util_view).mark_bar().encode(
                x="Month:N",
                y=alt.Y("Utilization:Q", axis=alt.Axis(format="%", title="Utilization")),
                color="Line:N",
                tooltip=list(util_view.columns)
            ).properties(height=260)
            st.altair_chart(chart_util, use_container_width=True)
    else:
        st.write("No utilization results.")

    st.markdown("---")

    # Fill rates
    st.subheader("Fill rates")
    if not fill_df.empty:
        prod_opts2 = ["All"] + sorted(fill_df["PRODUCT"].dropna().unique().tolist())
        sel_prod2 = st.selectbox("Filter by product", prod_opts2, key="fill_filter")
        if sel_prod2 != "All":
            fill_view = fill_df[fill_df["PRODUCT"] == sel_prod2]
        else:
            fill_view = fill_df

        st.dataframe(fill_view, use_container_width=True)

        if not fill_view.empty and "Fill_Rate" in fill_view.columns:
            group = fill_view.dropna(subset=["Fill_Rate"]).groupby("PRODUCT", as_index=False)["Fill_Rate"].mean()
            group = group.sort_values("Fill_Rate").head(5)
            chart_fill = alt.Chart(group).mark_bar().encode(
                x="PRODUCT:N",
                y=alt.Y("Fill_Rate:Q", axis=alt.Axis(format="%", title="Avg fill rate")),
                tooltip=[ "PRODUCT", alt.Tooltip("Fill_Rate:Q", format=".1%") ]
            ).properties(height=260, title="Service risk view (lowest average fill rates)")
            st.altair_chart(chart_fill, use_container_width=True)
    else:
        st.write("No fill rate results.")
