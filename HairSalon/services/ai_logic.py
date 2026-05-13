import pandas as pd
from prophet import Prophet
from .models import Booking
from django.db.models import Count
from datetime import datetime, timedelta

def get_ai_forecast(salon_id):
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

    # 确保时间按小时对齐
    df['ds'] = df['ds'].dt.floor('h')
    df = df.groupby('ds')['y'].sum().reset_index()

    # 2. 初始化并训练模型
    model = Prophet(yearly_seasonality=False, weekly_seasonality=True, daily_seasonality=True)
    model.fit(df)

    # 预测未来一段时间
    future = model.make_future_dataframe(periods=48, freq='h') 
    forecast = model.predict(future)

    # 1. 过滤：只取今天或明天的未来数据
    predictions = forecast[forecast['ds'] > datetime.now().replace(tzinfo=None)]
    
    # 2. 核心修改：只取 10:00 到 19:00 (7 PM) 之间的数据
    predictions = predictions[predictions['ds'].dt.hour.between(10, 19)]
    
    # 3. 只取接下来的 10 个有效营业小时
    predictions = predictions.head(10)

    labels = [d.strftime('%H:00') for d in predictions['ds']]
    
    # 4. 这里的 yhat 是预测值，如果觉得太低，可以手动做个系数加成(可选)
    # values = [round(v * 3, 1) for v in predictions['yhat']] 
    values = [round(v, 2) for v in predictions['yhat']]
    
    return labels, values
