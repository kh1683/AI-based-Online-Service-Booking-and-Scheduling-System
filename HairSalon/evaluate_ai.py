import os
import django
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# 1. Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HairSalon.settings')
django.setup()

from services.models import Booking
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error

def run_evaluation():
    print("Extracting historical booking data from database for AI performance evaluation...")
    
    # 2. Fetch all booking records and combine date and timeslot
    bookings = Booking.objects.all()
    if not bookings.exists():
        print("Error: No Booking data found in the database. Please ensure you have seeded/imported test data!")
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

    # 3. Partition datasets (take last 10 days for test set, previous days for train set)
    max_date = df['ds'].max()
    split_point = max_date - timedelta(days=10)
    
    train_df = df[df['ds'] <= split_point]
    test_df = df[df['ds'] > split_point]

    if train_df.empty or test_df.empty:
        print("Warning: Time span is not sufficient for a 10-day split. Using 80% train / 20% test split ratio instead.")
        split_idx = int(len(df) * 0.8)
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]

    print(f"Train set size: {len(train_df)} hourly slots | Test set size: {len(test_df)} hourly slots")

    # 4. Initialize and fit Prophet model
    print("Fitting and training AI model (Prophet)...")
    model = Prophet(yearly_seasonality=False, weekly_seasonality=True, daily_seasonality=True)
    model.fit(train_df)

    # 5. Predict customer traffic for the test set period
    print("Predicting customer traffic for the test period...")
    forecast = model.predict(test_df[['ds']])

    # 6. Extract ground truth (y) and predictions (yhat)
    y_true = test_df['y'].values
    y_pred = forecast['yhat'].values

    # 7. Compute academic evaluation metrics: MAE and RMSE
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))

    print("\n" + "="*40)
    print("      AI MODEL PERFORMANCE EVALUATION   ")
    print("="*40)
    print(f"  * Mean Absolute Error (MAE)  : {mae:.4f} (Customers/Hour)")
    print(f"  * Root Mean Squared Error (RMSE): {rmse:.4f}")
    print("="*40)
    print("Tip: Please record these two values for Chapter 5 of your thesis!\n")

if __name__ == '__main__':
    run_evaluation()
