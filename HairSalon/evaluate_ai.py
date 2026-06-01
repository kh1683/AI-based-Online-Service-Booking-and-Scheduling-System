import sys
import os
import django
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Reconfigure stdout to support UTF-8 characters (emojis) on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 1. Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HairSalon.settings')
django.setup()

from services.models import Booking
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def run_advanced_evaluation():
    print("🚀 Extracting historical booking data for Advanced AI Metrics Evaluation...")
    
    # 2. Fetch all booking records and combine date and timeslot
    bookings = Booking.objects.all()
    if not bookings.exists():
        print("❌ Error: No booking data found in the database!")
        return

    data = []
    for b in bookings:
        dt = datetime.combine(b.booking_date, b.timeslot)
        dt_truncated = dt.replace(minute=0, second=0, microsecond=0)
        data.append(dt_truncated)

    # Convert to DataFrame and aggregate counts per hour
    df = pd.DataFrame({'ds': data})
    df = df.groupby('ds').size().reset_index(name='y')
    
    # Sort by date-time
    df = df.sort_values('ds').reset_index(drop=True)

    # 3. Train-Test Split (80% Train / 20% Test partition)
    max_date = df['ds'].max()
    split_point = max_date - timedelta(days=10)
    
    train_df = df[df['ds'] <= split_point]
    test_df = df[df['ds'] > split_point]

    if train_df.empty or test_df.empty:
        print("⚠️ Warning: Time span is not sufficient for a 10-day split. Using 80% train / 20% test split ratio instead.")
        split_idx = int(len(df) * 0.8)
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]

    print(f"📊 Dataset Partitioned -> Training Slots: {len(train_df)} hours | Testing Slots: {len(test_df)} hours")

    # 4. Model Training
    print("🤖 Training Prophet Model with Additive Seasonality components...")
    model = Prophet(yearly_seasonality=False, weekly_seasonality=True, daily_seasonality=True)
    model.fit(train_df)

    # 5. Prediction execution
    print("🔮 Forecasting traffic density vectors for the test window...")
    forecast = model.predict(test_df[['ds']])

    y_true = test_df['y'].values
    y_pred = forecast['yhat'].values

    # ==========================================
    # 🔥 6. COMPUTING ADVANCED EVALUATION METRICS
    # ==========================================
    
    # Metric A: MAE
    mae = mean_absolute_error(y_true, y_pred)
    
    # Metric B: RMSE
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    
    # Metric C: MAPE (Handles potential division-by-zero by replacing 0 actuals with a tiny epsilon)
    y_true_stable = np.where(y_true == 0, 1e-5, y_true)
    mape = np.mean(np.abs((y_true - y_pred) / y_true_stable)) * 100
    
    # Metric D: R-squared (R2) Score
    r2 = r2_score(y_true, y_pred)

    # ==========================================
    # 7. VISUAL DISPLAY OF RESULTS
    # ==========================================
    print("\n" + "="*50)
    print("      📊 EXTENDED AI MODEL EVALUATION MATRIX      ")
    print("="*50)
    print(f" 🔹 Mean Absolute Error (MAE)      : {mae:.4f} (Customers/Hour)")
    print(f" 🔹 Root Mean Squared Error (RMSE) : {rmse:.4f}")
    print(f" 🔹 Mean Absolute Pct Error (MAPE) : {mape:.2f}%")
    print(f" 🔹 R-squared Coefficient (R²)     : {r2:.4f}")
    print("="*50)
    print("💡 Academic Tip: Copy these 4 values directly into Chapter 5 of your thesis.\n")

if __name__ == '__main__':
    run_advanced_evaluation()
