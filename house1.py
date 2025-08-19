# app.py
# Streamlit web app: Intermediate ML project (Regression) — NO hardware required
# House Price Prediction with dark UI, optional per-region (Himachal Pradesh / Chandigarh) inputs,
# end-to-end: load → clean → train → evaluate → predict → save model.

import io
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import joblib
import json


from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge, Lasso

try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

# ------------------------------
# Page / Theme
# ------------------------------
st.set_page_config(
    page_title="House Price Predictor — Dark",
    page_icon="🏡",
    layout="wide",
)

# --- Applied a dark theme via CSS ---
DARK_CSS = """
<style>
:root {
  --bg: #0b0f14; /* deep navy */
  --surface: #131a22; /* card */
  --text: #e6edf3; /* primary text */
  --muted: #a8b3bd; /* secondary */
  --accent: #66d9ef; /* cyan */
  --accent2: #a78bfa; /* violet */
  --ok: #22c55e;
  --warn: #f59e0b;
  --err: #ef4444;
}
html, body, [class^="css"], .stApp {background: var(--bg) !important; color: var(--text) !important;}
.block-container {padding-top: 1.2rem;}
.stTextInput>div>div>input, .stNumberInput input, .stSelectbox>div>div>div>div {background: #0e141b !important; color: var(--text) !important; border: 1px solid #263241;}
.stButton>button {background: linear-gradient(135deg, var(--accent), var(--accent2)); color: #0b0f14; border: none; font-weight: 700;}
.stDownloadButton>button {background: #1f2937; color: var(--text); border: 1px solid #374151;}
.css-1xarl3l, .stMetric {background: var(--surface) !important; border-radius: 14px; padding: 1rem; border: 1px solid #1f2a37;}
.dataframe tbody tr:nth-child(odd) {background: #0f1620;}
.dataframe tbody tr:nth-child(even) {background: #0c1219;}
.dataframe td, .dataframe th {color: var(--text) !important;}
</style>
"""
st.markdown(DARK_CSS, unsafe_allow_html=True)


# ------------------------------
# Data Loading and Caching
# ------------------------------
MODEL_PATH = Path("house_price_model.joblib")
DATA_INFO_PATH = Path("data_info.json")

def read_csv_safely(file) -> pd.DataFrame:
    try:
        return pd.read_csv(file)
    except Exception as e:
        st.error(f"Failed to read CSV: {e}")
        return None

@st.cache_resource(show_spinner="Training model...")
def train_model(_df: pd.DataFrame, target_col: str, model_name: str):
    """Trains a model and returns the pipeline, metrics, and feature names."""
    if target_col not in _df.columns:
        st.error(f"Target column '{target_col}' not found in the uploaded file.")
        return None, None, None, None, None

    y = _df[target_col]
    X = _df.drop(columns=[target_col])

    numeric_features = X.select_dtypes(include=np.number).columns.tolist()
    categorical_features = X.select_dtypes(exclude=np.number).columns.tolist()

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Define preprocessing pipelines
    numeric_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler())
    ])
    categorical_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore"))
    ])
    preprocessor = ColumnTransformer(transformers=[
        ("num", numeric_transformer, numeric_features),
        ("cat", categorical_transformer, categorical_features)
    ])

    # Model selection
    models = {
        "LinearRegression": LinearRegression(),
        "Ridge": Ridge(alpha=1.0, random_state=42),
        "Lasso": Lasso(alpha=0.01, random_state=42),
        "RandomForest": RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1),
    }
    if HAS_XGB:
        models["XGBoost"] = XGBRegressor(objective="reg:squarederror", random_state=42, n_jobs=-1)

    model = models.get(model_name, RandomForestRegressor(n_estimators=100, random_state=42))
    
    # Create the full pipeline
    pipe = Pipeline(steps=[("preprocessor", preprocessor), ("model", model)])
    pipe.fit(X_train, y_train)

    # Evaluate the model
    preds = pipe.predict(X_test)
    metrics = {
        "MAE": mean_absolute_error(y_test, preds),
        "RMSE": np.sqrt(mean_squared_error(y_test, preds)), # <-- FIX APPLIED HERE
        "R²": r2_score(y_test, preds)
    }
    
    # Return everything needed for prediction and display
    return pipe, metrics, X_train.columns.tolist(), numeric_features, categorical_features

# ------------------------------
# Sidebar Controls
# ------------------------------
with st.sidebar:
    st.header("⚙️ Project Controls")
    
    uploaded_file = st.file_uploader("Upload your training CSV", type=["csv"])
    
    if uploaded_file:
        target_col = st.text_input("Enter the target column name", value="SalePrice")
        
        model_options = ["RandomForest", "LinearRegression", "Ridge", "Lasso"]
        if HAS_XGB:
            model_options.append("XGBoost")
        model_name = st.selectbox("Select a Model", model_options)

        if st.button("🚀 Train Model"):
            df = read_csv_safely(uploaded_file)
            if df is not None:
                pipe, metrics, features, num_feats, cat_feats = train_model(df, target_col, model_name)
                if pipe:
                    st.session_state["pipe"] = pipe
                    st.session_state["metrics"] = metrics
                    st.session_state["data_info"] = {
                        "features": features,
                        "num_feats": num_feats,
                        "cat_feats": cat_feats,
                        "target_col": target_col,
                    }
                    st.success("Model trained successfully!")

    st.markdown("---")
    
    if st.button("💾 Save Trained Model"):
        if "pipe" in st.session_state:
            joblib.dump(st.session_state["pipe"], MODEL_PATH)
            with open(DATA_INFO_PATH, 'w') as f:
                json.dump(st.session_state["data_info"], f)
            st.success(f"Model saved to `{MODEL_PATH}`")
        else:
            st.warning("No trained model to save. Please train a model first.")

    if st.button("📥 Load Saved Model"):
        if MODEL_PATH.exists() and DATA_INFO_PATH.exists():
            st.session_state["pipe"] = joblib.load(MODEL_PATH)
            with open(DATA_INFO_PATH, 'r') as f:
                st.session_state["data_info"] = json.load(f)
            st.success("Saved model loaded successfully!")
        else:
            st.error("No saved model found. Train and save a model first.")
            
    st.markdown("---")
    st.caption("Upload `train.csv` from the Kaggle House Prices competition to begin.")


# ------------------------------
# Main Page Display
# ------------------------------
st.title("🏡 House Price Predictor")
st.caption("An end-to-end ML regression project with Streamlit.")

if "pipe" not in st.session_state:
    st.info("Welcome! Please upload a dataset and train a model using the sidebar to get started.")
else:
    # Display metrics
    st.header("📊 Model Performance")
    metrics = st.session_state["metrics"]
    col1, col2, col3 = st.columns(3)
    col1.metric("Mean Absolute Error (MAE)", f"${metrics['MAE']:,.0f}")
    col2.metric("Root Mean Squared Error (RMSE)", f"${metrics['RMSE']:,.0f}")
    col3.metric("R² Score", f"{metrics['R²']:.3f}")
    
    st.markdown("---")

    # Prediction form
    st.header("🧮 Predict a House Price")
    
    # Retrieve feature lists from session state
    data_info = st.session_state["data_info"]
    features = data_info["features"]
    num_feats = data_info["num_feats"]
    cat_feats = data_info["cat_feats"]
    
    # Create a form for user inputs
    with st.form(key="prediction_form"):
        # We create inputs dynamically based on the dataset's columns
        st.write("Provide details for some key features to get a price estimate.")
        
        input_data = {}
        
        # A selection of important features from the Kaggle dataset
        form_cols = st.columns(3)
        with form_cols[0]:
            input_data["OverallQual"] = st.slider("Overall Quality (1-10)", 1, 10, 7)
            input_data["GrLivArea"] = st.number_input("Above Ground Living Area (sq ft)", min_value=500, max_value=5000, value=1500)
            input_data["GarageCars"] = st.slider("Garage Capacity (cars)", 0, 4, 2)
        with form_cols[1]:
            input_data["TotalBsmtSF"] = st.number_input("Basement Area (sq ft)", min_value=0, max_value=6000, value=1000)
            input_data["FullBath"] = st.slider("Full Bathrooms", 1, 4, 2)
            input_data["YearBuilt"] = st.number_input("Year Built", min_value=1800, max_value=2025, value=2005)
        with form_cols[2]:
            neighborhoods = ['CollgCr', 'Veenker', 'Crawfor', 'NoRidge', 'Mitchel', 'Somerst', 'NWAmes', 'OldTown', 'BrkSide', 'Sawyer', 'NAmes', 'SawyerW', 'IDOTRR', 'MeadowV', 'Edwards', 'Timber', 'Gilbert', 'StoneBr', 'ClearCr', 'NPkVill', 'Blmngtn', 'BrDale', 'SWISU', 'Blueste', 'NridgHt']
            input_data["Neighborhood"] = st.selectbox("Neighborhood", sorted(neighborhoods))
            
        predict_button = st.form_submit_button("Predict Price 💡")

    if predict_button:
        # Create a DataFrame for prediction
        X_pred = pd.DataFrame(columns=features, index=[0])
        
        # Populate with user inputs
        for key, value in input_data.items():
            if key in X_pred.columns:
                X_pred.loc[0, key] = value
        
        prediction = st.session_state["pipe"].predict(X_pred)
        
        st.subheader("🎉 Predicted Price")
        st.markdown(f"<div style='font-size:42px; font-weight:800; color: var(--ok);'>${prediction[0]:,.0f}</div>", unsafe_allow_html=True)

    # Display feature importances if available
    st.markdown("---")
    try:
        model = st.session_state["pipe"].named_steps["model"]
        if hasattr(model, "feature_importances_"):
            st.subheader("🔎 Top Feature Importances")
            
            preprocessor = st.session_state["pipe"].named_steps["preprocessor"]
            ohe_feature_names = preprocessor.named_transformers_["cat"].named_steps["onehot"].get_feature_names_out(cat_feats)
            final_feature_names = num_feats + list(ohe_feature_names)

            importances = pd.DataFrame({
                "feature": final_feature_names,
                "importance": model.feature_importances_
            }).sort_values("importance", ascending=False).head(15)
            
            st.dataframe(importances, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not display feature importances. Error: {e}")
