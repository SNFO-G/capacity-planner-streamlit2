# Capacity Planner Streamlit App

This repository contains a Streamlit web application that runs the production capacity model.

## How to run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

The app uses the baseline CSV files in `cap_planner_app/data` by default, and also allows uploading updated Calendar, Demand and Rates CSVs.
