# app.py
# Streamlit Web App for Himachal Pradesh House Price Prediction

import io
from pathlib import Path
import json
import numpy as np
import pandas as pd
import streamlit as st
import joblib
from datetime import datetime

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor

# ------------------------------
# Page Configuration and Theme
# ------------------------------
st.set_page_config(
    page_title="Himachal Pradesh House Price Predictor",
    page_icon="🏔️",
    layout="wide",
)

# A dark theme to make the app visually appealing
DARK_CSS = """
<style>
:root {
  --bg: #0b0f14; --surface: #131a22; --text: #e6edf3; --muted: #a8b3bd;
  --accent: #66d9ef; --accent2: #a78bfa; --ok: #22c55e;
}
html, body, [class^="css"], .stApp {background: var(--bg) !important; color: var(--text) !important;}
.block-container {padding-top: 1.2rem;}
.stTextInput>div>div>input, .stNumberInput input, .stSelectbox>div>div>div>div {
    background: #0e141b !important; color: var(--text) !important; border: 1px solid #263241;
}
.stButton>button {
    background: linear-gradient(135deg, var(--accent), var(--accent2)); color: #0b0f14; border: none; font-weight: 700;
}
.stDownloadButton>button {background: #1f2937; color: var(--text); border: 1px solid #374151;}
.stMetric {background: var(--surface) !important; border-radius: 14px; padding: 1rem; border: 1px solid #1f2a37;}
</style>
"""
st.markdown(DARK_CSS, unsafe_allow_html=True)


# ------------------------------
# Himachal Pradesh Specific Data
# ------------------------------
HP_DATA = {
    "districts": ["Shimla", "Manali", "Kasauli", "Dharamshala", "Kullu", "Solan", "Mandi", "Kangra"],
    # These are placeholder multipliers. For a real project, these would be derived from market data.
    "district_multipliers": {
        "Kasauli": 1.25, "Manali": 1.22, "Shimla": 1.18, "Solan": 1.12,
        "Kullu": 1.10, "Dharamshala": 1.08, "Kangra": 1.05, "Mandi": 0.98,
    },
    "notes": (
        "This tool provides a price estimate based on a general model, adjusted for "
        "different districts in Himachal Pradesh. Prices in hilly regions are heavily "
        "influenced by factors like view, accessibility, and proximity to tourist hubs."
    )
}

# ------------------------------
# Core ML Functions (Training and Loading)
# ------------------------------
MODEL_PATH = Path("hp_house_price_model.joblib")
DATA_INFO_PATH = Path("hp_data_info.json")

def read_csv_safely(file) -> pd.DataFrame:
    try:
        return pd.read_csv(file)
    except Exception as e:
        st.error(f"Failed to read CSV: {e}")
        return None

@st.cache_resource(show_spinner="Training model...")
def train_model(_df: pd.DataFrame, target_col: str):
    """Trains a RandomForest model and returns the pipeline, metrics, and feature names."""
    if target_col not in _df.columns:
        st.error(f"Target column '{target_col}' not found in the uploaded file.")
        return None, None, None
    
    y = _df[target_col]
    X = _df.drop(columns=[target_col])
    
    numeric_features = X.select_dtypes(include=np.number).columns.tolist()
    categorical_features = X.select_dtypes(exclude=np.number).columns.tolist()

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    preprocessor = ColumnTransformer(transformers=[
        ("num", Pipeline(steps=[("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), numeric_features),
        ("cat", Pipeline(steps=[("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical_features)
    ])
    
    pipe = Pipeline(steps=[("preprocessor", preprocessor), ("model", RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1))])
    pipe.fit(X_train, y_train)

    preds = pipe.predict(X_test)
    metrics = {
        "MAE": mean_absolute_error(y_test, preds),
        "RMSE": np.sqrt(mean_squared_error(y_test, preds)),
        "R²": r2_score(y_test, preds)
    }
    
    data_info = {"features": X_train.columns.tolist(), "num_feats": numeric_features, "cat_feats": categorical_features}
    return pipe, metrics, data_info

# ------------------------------
# Sidebar Controls
# ------------------------------
with st.sidebar:
    st.header("⚙️ Project Controls")
    uploaded_file = st.file_uploader("Upload Training Data (CSV)", type=["csv"])
    
    if uploaded_file:
        target_col = st.text_input("Enter Target Column Name", value="SalePrice")
        if st.button("🚀 Train Model"):
            df = read_csv_safely(uploaded_file)
            if df is not None:
                pipe, metrics, data_info = train_model(df, target_col)
                if pipe:
                    st.session_state.update({"pipe": pipe, "metrics": metrics, "data_info": data_info})
                    st.success("Model trained successfully!")

    st.markdown("---")
    if st.button("💾 Save Trained Model"):
        if "pipe" in st.session_state:
            joblib.dump(st.session_state["pipe"], MODEL_PATH)
            with open(DATA_INFO_PATH, 'w') as f:
                json.dump(st.session_state["data_info"], f)
            st.success(f"Model saved to `{MODEL_PATH}`")
        else:
            st.warning("No model to save. Please train one first.")

    if st.button("📥 Load Saved Model"):
        if MODEL_PATH.exists() and DATA_INFO_PATH.exists():
            st.session_state["pipe"] = joblib.load(MODEL_PATH)
            with open(DATA_INFO_PATH, 'r') as f:
                st.session_state["data_info"] = json.load(f)
            st.success("Saved model loaded successfully!")
        else:
            st.error("No saved model found.")
    
    st.markdown("---")
    st.info("Note: The underlying model is generic. Upload a dataset like Kaggle's House Prices `train.csv` to enable predictions.")

# ------------------------------
# Main Page Display
# ------------------------------
st.title("🏔️ Himachal Pradesh House Price Predictor")
st.caption(HP_DATA["notes"])

if "pipe" not in st.session_state:
    st.warning("Please train or load a model using the sidebar to enable the prediction form.")
else:
    st.markdown("---")
    st.header("🧮 Predict a House Price in Himachal Pradesh")
    
    data_info = st.session_state["data_info"]
    
    with st.form(key="prediction_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            district = st.selectbox("Select District", HP_DATA["districts"])
            area_sqft = c1.number_input("Area (sq ft)", min_value=300, max_value=10000, value=1500, step=100)
        with c2:
            bedrooms = st.slider("Bedrooms (BHK)", 1, 10, 3)
            bathrooms = st.slider("Bathrooms", 1, 8, 2)
        with c3:
            property_age = st.number_input("Property Age (years)", 0, 100, 10)
            view_quality = st.select_slider("View Quality", ["Basic", "Average", "Good", "Excellent"], value="Good")
        
        predict_button = st.form_submit_button("Predict Price 💡")

    if predict_button:
        # --- Smart Mapping from HP-specific inputs to generic model features ---
        # This allows using a generic model (like one trained on Kaggle's dataset)
        # with inputs that make sense for Himachal Pradesh.
        
        # 1. Map View Quality to Overall Quality (a common feature in house price datasets)
        view_to_qual_map = {"Basic": 3, "Average": 5, "Good": 7, "Excellent": 9}
        overall_qual = view_to_qual_map[view_quality]

        # 2. Create the feature row for the model
        model_features = data_info["features"]
        X_pred = pd.DataFrame(columns=model_features, index=[0])
        
        # Populate the row with our mapped data, letting the pipeline handle missing values
        input_mappings = {
            "GrLivArea": area_sqft,       # Above-ground living area
            "OverallQual": overall_qual,  # Overall material and finish quality
            "YearBuilt": datetime.now().year - property_age,
            "FullBath": bathrooms,
            "TotRmsAbvGrd": bedrooms + 2, # Estimate total rooms from bedrooms
        }
        
        for feature, value in input_mappings.items():
            if feature in X_pred.columns:
                X_pred.loc[0, feature] = value
        
        # 3. Make prediction and apply district multiplier
        base_pred = st.session_state["pipe"].predict(X_pred)
        district_multiplier = HP_DATA["district_multipliers"].get(district, 1.0)
        final_pred = base_pred * district_multiplier * 50  # Final scaling factor for display in INR

        st.success("Prediction Complete!")
        pcol1, pcol2 = st.columns([2, 1])
        with pcol1:
            st.subheader("🏷️ Estimated Property Value")
            st.markdown(f"<div style='font-size:42px;font-weight:800; color: var(--ok);'>₹ {final_pred:,.0f}</div>", unsafe_allow_html=True)
        with pcol2:
            st.metric("Base Model Output", f"{base_pred:,.0f}")
            st.metric("District Multiplier", f"×{district_multiplier:.2f} for {district}")

# ------------------------------
# Downloadable Data Template
# ------------------------------
st.markdown("---")
st.subheader("⬇️ Downloads")

# A template that matches the intuitive Himachal-specific input form
template_df = pd.DataFrame([{
    "area_sqft": 1500, "bedrooms": 3, "bathrooms": 2, "property_age": 10,
    "view_quality": "Good", "district": "Shimla", "SalePrice": 7500000
}])
buf = io.StringIO()
template_df.to_csv(buf, index=False)
st.download_button("Download Data Template (for HP)", buf.getvalue(), file_name="hp_house_price_template.csv", mime="text/csv")
