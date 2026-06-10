import pandas as pd
from prophet import Prophet
from .models import Booking
from django.db.models import Count
from datetime import datetime, timedelta
import holidays

def generate_future_features(future_datetime_str):
    """
    根据用户想要预订的未来任意时间（比如下个月），生成模型需要的特征
    future_datetime_str 格式: '2026-07-15 14:00:00'
    """
    dt = pd.to_datetime(future_datetime_str)
    
    # 1. 基础时间特征
    hour = dt.hour
    day_of_week = dt.dayofweek
    day_of_month = dt.day
    is_weekend = 1 if day_of_week in [5, 6] else 0
    
    # 2. 自动判断马来西亚/本地公共假期 (以马来西亚假期为例)
    my_holidays = holidays.Malaysia(years=dt.year)
    is_holiday = 1 if dt in my_holidays else 0
    
    # 3. 组合成模型特征向量
    feature_vector = [[hour, day_of_week, day_of_month, is_weekend, is_holiday]]
    
    return feature_vector

def get_ai_forecast(salon_id, target_date_str=None):
    # 1. 提取历史数据
    raw_data = Booking.objects.filter(salon_id=salon_id) \
        .values('booking_date', 'timeslot') \
        .annotate(y=Count('id')) \
        .order_by('booking_date', 'timeslot')

    if len(raw_data) < 10:  # 如果数据太少，无法训练
        return None

    df = pd.DataFrame(list(raw_data))
    
    # 将 booking_date 和 timeslot 结合成一个 ds
    df['ds'] = df.apply(lambda row: datetime.combine(row['booking_date'], row['timeslot']), axis=1)

    # 确保 ds 这一列是不带时区的（Prophet 的要求）
    df['ds'] = df['ds'].dt.tz_localize(None)

    # 确保时间按小时对齐并聚合
    df['ds'] = df['ds'].dt.floor('h')
    df_raw = df.groupby('ds')['y'].sum().reset_index()

    if not df_raw.empty:
        # Create a complete hourly range from min to max date to fill in missing hours with 0
        min_date = df_raw['ds'].min()
        max_date = df_raw['ds'].max()
        all_hours = pd.date_range(start=min_date, end=max_date, freq='h')
        
        df = pd.DataFrame({'ds': all_hours})
        df = pd.merge(df, df_raw, on='ds', how='left').fillna({'y': 0})
        df['y'] = df['y'].astype(int)
    else:
        df = df_raw

    # 2. 初始化并训练模型，并添加马来西亚公共假期
    model = Prophet(yearly_seasonality=False, weekly_seasonality=True, daily_seasonality=True)
    model.add_country_holidays(country_name='MY')
    model.fit(df)

    # 3. 预测未来时间段 (支持针对特定的未来日期进行预测)
    if target_date_str:
        try:
            from datetime import time as dt_time
            target_dt = datetime.strptime(target_date_str, '%Y-%m-%d')
            future_hours = [datetime.combine(target_dt.date(), dt_time(hour, 0)) for hour in range(10, 20)]
            future = pd.DataFrame({'ds': future_hours})
        except Exception:
            future = model.make_future_dataframe(periods=48, freq='h')
    else:
        future = model.make_future_dataframe(periods=48, freq='h')
        
    forecast = model.predict(future)

    # Clip forecast predictions to >= 0 since customer booking count cannot be negative
    forecast['yhat'] = forecast['yhat'].clip(lower=0)

    # 4. 根据输入模式进行过滤
    if target_date_str:
        predictions = forecast
    else:
        predictions = forecast[forecast['ds'] > datetime.now().replace(tzinfo=None)]
        predictions = predictions[predictions['ds'].dt.hour.between(10, 19)]
        predictions = predictions.head(10)

    # 用第一个预测点测试/打印出提取出的特征向量，展示特征解析功能正常工作
    if not predictions.empty:
        sample_time_str = predictions.iloc[0]['ds'].strftime('%Y-%m-%d %H:%M:%S')
        features = generate_future_features(sample_time_str)
        print(f"[AI Prediction Feature Check] Time: {sample_time_str} | Feature Vector: {features}")

    labels = [d.strftime('%H:00') for d in predictions['ds']]
    values = [round(v, 2) for v in predictions['yhat']]
    
    return labels, values

def get_optimal_time_slots(salon_id, selected_date_str=None):
    """根据 AI 预测，推荐当天最空闲（效率最高）的 3 个营业时段"""
    import os
    import joblib
    from django.conf import settings

    model_path = os.path.join(settings.BASE_DIR, 'trained_model.pkl')
    
    if selected_date_str and os.path.exists(model_path):
        try:
            # 加载重新训练好的、聪明的模型
            model = joblib.load(model_path)
            base_date = pd.to_datetime(selected_date_str)
            
            # 营业时间：10:00 AM - 07:00 PM (10:00 to 19:00 inclusive)
            business_hours = range(10, 20) 
            predicted_traffic = {}
            
            # 动态为这一天的每一个小时生成特征，让模型预测
            for hour in business_hours:
                day_of_week = base_date.dayofweek
                day_of_month = base_date.day
                is_weekend = 1 if day_of_week in [5, 6] else 0
                
                # 构建当前小时的特征输入
                X_future = pd.DataFrame([[hour, day_of_week, day_of_month, is_weekend]], 
                                        columns=['hour', 'day_of_week', 'day_of_month', 'is_weekend'])
                
                pred_density = model.predict(X_future)[0]
                predicted_traffic[hour] = max(0, pred_density)
            
            # 最优推荐算法逻辑：找出预测客流量最低（最空闲）的前 3 个小时
            optimal_hours = sorted(predicted_traffic, key=predicted_traffic.get)[:3]
            optimal_slots = [f"{h:02d}:00" for h in optimal_hours]
            return optimal_slots
        except Exception as e:
            # Fallback to Prophet in case of error
            print(f"Error predicting with RandomForest: {e}")
            pass

    # ==================== Prophet Fallback ====================
    # 1. 跑一遍 Prophet 拿到预测数据 (传入目标日期)
    forecast_data = get_ai_forecast(salon_id, selected_date_str)
    
    if not forecast_data:
        # 如果历史数据不足，给出默认的营业时间推荐（比如早上的黄金时段）
        return ['10:00', '11:00', '15:00']
    
    labels, values = forecast_data
    
    # 2. 将时间和预测值组合成字典或 DataFrame
    slots = [{"time": label, "load": val} for label, val in zip(labels, values)]
    
    # 3. 按负载（Load）从低到高排序 —— 负载越低，对商家效率越好，客户等待时间越短
    slots_sorted = sorted(slots, key=lambda x: x['load'])
    
    # 4. 选出负载最低的 3 个时段作为“智能推荐”
    optimal_slots = [slot['time'] for slot in slots_sorted[:3]]
    
    # 如果预测到的时段不足 3 个，用默认时段补齐
    default_backups = ['10:00', '11:00', '15:00']
    for backup in default_backups:
        if len(optimal_slots) >= 3:
            break
        if backup not in optimal_slots:
            optimal_slots.append(backup)
            
    return optimal_slots[:3]


