import json
import joblib
import pandas as pd
import numpy as np
from scipy import stats
import os
import boto3 
import traceback

# --- CONFIGURAÇÕES ---
TAXA_ATUALIZACAO_HZ = 20.0

# --- CARREGAMENTO DOS MODELOS ---
MODEL_PATH = os.environ.get('MODEL_PATH', '.') 

# Cliente MQTT (IoT Core)
# A região deve ser a mesma onde você criou a Lambda (ex: us-east-2)
iot_client = boto3.client('iot-data', region_name='us-east-2') 

try:
    print("Carregando modelos...")
    SCALER = joblib.load(os.path.join(MODEL_PATH, 'scaler_final.joblib'))
    MODEL = joblib.load(os.path.join(MODEL_PATH, 'xgboost_final.joblib'))
    ENCODER = joblib.load(os.path.join(MODEL_PATH, 'label_encoder_final.joblib'))
    print("Modelos carregados com sucesso.")
except Exception as e:
    print(f"ERRO FATAL ao carregar modelos: {e}")
    SCALER, MODEL, ENCODER = None, None, None

# --- FUNÇÕES DE PROCESSAMENTO ---

def extract_features_window(arr, fs=TAXA_ATUALIZACAO_HZ):
    """
    Extrai as 168 features estatísticas da janela de dados.
    """
    feats = {}
    axes = ['acc_x','acc_y','acc_z', 'gyro_x', 'gyro_y', 'gyro_z',
            'acc_vm', 'gyro_vm', 'jerk_x', 'jerk_y', 'jerk_z', 'jerk_vm']
    
    for i, ax in enumerate(axes):
        v = arr[:, i]
        # Domínio do Tempo
        feats[f'{ax}_mean'] = np.mean(v); feats[f'{ax}_std'] = np.std(v)
        feats[f'{ax}_var'] = np.var(v); feats[f'{ax}_min'] = np.min(v)
        feats[f'{ax}_max'] = np.max(v); feats[f'{ax}_median'] = np.median(v)
        feats[f'{ax}_rms'] = np.sqrt(np.mean(v**2)); feats[f'{ax}_energy'] = np.sum(v**2)
        feats[f'{ax}_iqr'] = np.subtract(*np.percentile(v, [75, 25]))
        feats[f'{ax}_skew'] = stats.skew(v); feats[f'{ax}_kurtosis'] = stats.kurtosis(v)
        
        # Zero Crossing
        if len(v) > 1: zc = ((v[:-1] * v[1:]) < 0).sum() / (len(v)-1)
        else: zc = 0.0
        feats[f'{ax}_zcross_rate'] = zc
        
        # Domínio da Frequência (FFT)
        try:
            fft = np.fft.rfft(v); mags = np.abs(fft); freqs = np.fft.rfftfreq(len(v), d=1.0/fs)
            if len(mags) > 1:
                idx = np.argmax(mags[1:]) + 1
                feats[f'{ax}_dom_freq'] = freqs[idx]; feats[f'{ax}_dom_mag'] = mags[idx]
            else: feats[f'{ax}_dom_freq'] = 0.0; feats[f'{ax}_dom_mag'] = 0.0
        except: feats[f'{ax}_dom_freq'] = 0.0; feats[f'{ax}_dom_mag'] = 0.0
    return feats

def lambda_handler(event, context):
    """
    Função principal executada pela AWS.
    """
    if not MODEL: return {'statusCode': 500, 'body': 'Modelos não carregados.'}
    
    prediction_label = "unknown"
    device_id = event.get('dev_id', 'unknown')
    
    try:
        # 1. Parseamento do JSON
        # O firmware já envia 'ax', 'ay', etc limpos de gravidade
        input_data = {
            'acc_x': event['ax'], 'acc_y': event['ay'], 'acc_z': event['az'],
            'gyro_x': event['gx'], 'gyro_y': event['gy'], 'gyro_z': event['gz']
        }
        df = pd.DataFrame(input_data)
        
        if len(df) < 10: return {'statusCode': 400, 'body': 'Dados insuficientes.'}

        # 2. Engenharia de Features (Calcular Vetores e Jerk)
        dt = 1.0 / TAXA_ATUALIZACAO_HZ
        
        # Magnitude (Agora sem gravidade, valores próximos de 0 se parado)
        df['acc_vm'] = np.sqrt(df['acc_x']**2 + df['acc_y']**2 + df['acc_z']**2)
        
        # --- Zero Motion Gate ---
        # Se a variação (std) for muito baixa, assume parado
        if df['acc_vm'].std() < 0.2:
            print(f"Zero Motion Gate ({device_id}): Veículo parado -> SLOW")
            prediction_label = 'slow'
        # ------------------------
        else:
            # Calcula Gyro VM e Jerks
            df['gyro_vm'] = np.sqrt(df['gyro_x']**2 + df['gyro_y']**2 + df['gyro_z']**2)
            for ax in ['x', 'y', 'z']:
                acc_col, jerk_col = f'acc_{ax}', f'jerk_{ax}'
                df[jerk_col] = np.concatenate(([0.0], np.diff(df[acc_col]) / dt))
            df['jerk_vm'] = np.sqrt(df['jerk_x']**2 + df['jerk_y']**2 + df['jerk_z']**2)


            # 3. Extrair Features
            cols_order = ['acc_x','acc_y','acc_z','gyro_x','gyro_y','gyro_z',
                          'acc_vm','gyro_vm','jerk_x','jerk_y','jerk_z','jerk_vm']
            
            # Converte para matriz numpy e extrai
            features_dict = extract_features_window(df[cols_order].values)
            
            # 4. Predição
            X_scaled = SCALER.transform(pd.DataFrame([features_dict]))
            prediction_idx = MODEL.predict(X_scaled)[0]
            prediction_label = ENCODER.inverse_transform([prediction_idx])[0]

        print(f"Predição para {device_id}: {prediction_label.upper()}")

        # 5. RETORNO VIA MQTT
        try:
            response_payload = json.dumps({
                "ts": event.get('ts', 0),
                "resultado": prediction_label 
            })
            
            TOPIC_RESPONSE = f"veiculos/{device_id}/resposta_IA"
            
            iot_client.publish(
                topic=TOPIC_RESPONSE,
                qos=0,
                payload=response_payload
            )
            print(f"Resposta enviada para: {TOPIC_RESPONSE}")
            
        except Exception as mqtt_err:
            print(f"ERRO ao publicar no MQTT: {mqtt_err}")

        return {
            'statusCode': 200,
            'device_id': device_id,
            'prediction': prediction_label
        }

    except Exception as e:
        print(f"ERRO GERAL: {e}")
        traceback.print_exc()
        return {'statusCode': 500, 'body': str(e)}