import streamlit as st
from AggregrationLayer import AggregationLayer

# ----- Aggregation Layer Functions / Setup -----

aggLayer = AggregationLayer()

# relevant_content = aggLayer.extract_relevant_page_content(page_content="", image="")
gps_coordinate_guess = aggLayer.geoclip_inference(image_path="./images/i1.jpg")


# ===============================================


# run with steamlit run app.py

# st.set_page_config(layout="wide")

# st.title("GeoInference Enhancement Pipeline")

print(gps_coordinate_guess)