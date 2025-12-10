import time
import csv
import datetime
import json 
import numpy as np
import pandas as pd
import joblib
from collections import deque
import matplotlib.pyplot as plt
from scipy import signal, stats
import sys
import os
# Certifique-se de que o arquivo ac_shared_memory.py está na mesma pasta
from ac_shared_memory import AssettoCorsaSharedMemory

# ==============================================================================
# 1. CONFIGURAÇÕES
# ==============================================================================
TRIGGER_THRESHOLD_MS2 = 3.0       
SAMPLES_TOTAL = 50                
PRE_EVENT_SAMPLES = 24            
POST_EVENT_SAMPLES = 25           
HEARTBEAT_INTERVAL_SEC = 2 * 60   

G_PARA_MS2 = 9.80665
TAXA_ATUALIZACAO_HZ = 20.0        
INTERVALO_SCRIPT = 1.0 / TAXA_ATUALIZACAO_HZ
GRAVITY_CUTOFF_HZ = 0.5           

# Configuração de Latência
LATENCIA_LTE_SEC = 1.0  # Simula 1 segundo de delay de upload

# Cores
class Colors:
    HEADER = '\033[95m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log(msg, tipo="INFO"):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {tipo}: {msg}")

# ==============================================================================
# 2. SETUP DO RELATÓRIO
# ==============================================================================
print(f"{Colors.HEADER}--- CONFIGURAÇÃO DO TESTE DE TCC (MODO LOCAL + LATÊNCIA) ---{Colors.ENDC}")
CENARIO_TESTE = input("Digite o NOME DO CENÁRIO (ex: Volta_LTE_Ruim): ").strip().replace(" ", "_")
if not CENARIO_TESTE: CENARIO_TESTE = "Teste_Simulacao_LTE"

nome_arquivo_csv = f"DADOS_TCC_{CENARIO_TESTE}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

log("AWS está DESATIVADA. Rodando localmente com SIMULAÇÃO DE LATÊNCIA.", "AVISO")

# ==============================================================================
# 3. CARREGAMENTO IA
# ==============================================================================
try:
    SCALER = joblib.load('scaler_final.joblib')
    MODEL = joblib.load('xgboost_final.joblib')
    ENCODER = joblib.load('label_encoder_final.joblib')
    log("IA Carregada.", "SISTEMA")
except Exception as e:
    log(f"Erro ao carregar IA: {e}", "ERRO")
    exit()

# ==============================================================================
# 4. FUNÇÕES IA
# ==============================================================================
def remove_gravity(df, fs=TAXA_ATUALIZACAO_HZ, cutoff_hz=GRAVITY_CUTOFF_HZ):
    b, a = signal.butter(2, cutoff_hz / (0.5*fs), btype='low', analog=False)
    df_out = df.copy()
    for axis in ['acc_x','acc_y','acc_z']:
        try:
            g = signal.filtfilt(b, a, df[axis].values)
            df_out[axis] = df[axis].values - g
        except:
            df_out[axis] = df[axis].values - np.mean(df[axis].values)
    return df_out

def extract_features_window(arr, fs=TAXA_ATUALIZACAO_HZ):
    feats = {}
    axes = ['acc_x','acc_y','acc_z', 'gyro_x', 'gyro_y', 'gyro_z',
            'acc_vm', 'gyro_vm', 'jerk_x', 'jerk_y', 'jerk_z', 'jerk_vm']
    for i, ax in enumerate(axes):
        v = arr[:, i]
        feats[f'{ax}_mean'] = float(np.mean(v))
        feats[f'{ax}_std']  = float(np.std(v))
        feats[f'{ax}_var']  = float(np.var(v))
        feats[f'{ax}_min']  = float(np.min(v))
        feats[f'{ax}_max']  = float(np.max(v))
        feats[f'{ax}_median'] = float(np.median(v))
        feats[f'{ax}_rms'] = float(np.sqrt(np.mean(v**2)))
        feats[f'{ax}_energy'] = float(np.sum(v**2))
        feats[f'{ax}_iqr'] = float(np.subtract(*np.percentile(v, [75, 25])))
        feats[f'{ax}_skew'] = float(stats.skew(v))
        feats[f'{ax}_kurtosis'] = float(stats.kurtosis(v))
        
        if len(v) > 1: zc = ((v[:-1] * v[1:]) < 0).sum() / (len(v)-1)
        else: zc = 0.0
        feats[f'{ax}_zcross_rate'] = float(zc)
        
        try:
            fft = np.fft.rfft(v); mags = np.abs(fft); freqs = np.fft.rfftfreq(len(v), d=1.0/fs)
            if len(mags) > 1:
                idx = np.argmax(mags[1:]) + 1
                feats[f'{ax}_dom_freq'] = float(freqs[idx])
                feats[f'{ax}_dom_mag'] = float(mags[idx])
            else:
                feats[f'{ax}_dom_freq'] = 0.0; feats[f'{ax}_dom_mag'] = 0.0
        except:
            feats[f'{ax}_dom_freq'] = 0.0; feats[f'{ax}_dom_mag'] = 0.0
    return feats

def processar_pacote_ia(lista_amostras):
    cols = ['time', 'acc_x', 'acc_y', 'acc_z', 'gyro_x', 'gyro_y', 'gyro_z']
    df = pd.DataFrame(lista_amostras, columns=cols)
    
    dt = 1.0 / TAXA_ATUALIZACAO_HZ
    df['acc_vm'] = np.sqrt(df['acc_x']**2 + df['acc_y']**2 + df['acc_z']**2)
    df['gyro_vm'] = np.sqrt(df['gyro_x']**2 + df['gyro_y']**2 + df['gyro_z']**2)
    for ax in ['x', 'y', 'z']:
        df[f'jerk_{ax}'] = np.concatenate(([0.0], np.diff(df[f'acc_{ax}']) / dt))
    df['jerk_vm'] = np.sqrt(df['jerk_x']**2 + df['jerk_y']**2 + df['jerk_z']**2)

    df_filt = remove_gravity(df)
    
    feature_cols = ['acc_x','acc_y','acc_z','gyro_x','gyro_y','gyro_z',
                    'acc_vm','gyro_vm','jerk_x','jerk_y','jerk_z','jerk_vm']
    arr_window = df_filt[feature_cols].values
    features_dict = extract_features_window(arr_window)
    
    X_scaled = SCALER.transform(pd.DataFrame([features_dict]))
    y_pred_idx = MODEL.predict(X_scaled)
    resultado = ENCODER.inverse_transform(y_pred_idx)[0]
    
    return resultado

# ==============================================================================
# 5. LOOP PRINCIPAL
# ==============================================================================

pre_event_buffer = deque(maxlen=PRE_EVENT_SAMPLES)
current_event_list = []
event_in_progress = False
samples_collected = 0
last_heartbeat = time.time()
packet_count = 0

# Preparar CSV
arquivo_csv = open(nome_arquivo_csv, 'w', newline='')
writer = csv.writer(arquivo_csv)
writer.writerow(['cenario', 'packet_id', 'tipo_pacote', 'predicao_ia', 'timestamp_real', 'acc_x', 'acc_y', 'acc_z', 'gyro_x', 'gyro_y', 'gyro_z'])

ac = AssettoCorsaSharedMemory()
log(f"Iniciando gravação em: {nome_arquivo_csv}", "CSV")
log("Vá para a pista! (GIROSCÓPIO ZERADO | LATÊNCIA LTE ATIVA)", "AC")

RAD_TO_DEG = 180.0 / np.pi 

try:
    while True:
        start = time.time()
        phy = ac.get_physics()
        
        if phy and phy.packetId > 0:
            ts = time.time()
            ax = phy.accG[0] * G_PARA_MS2
            ay = phy.accG[1] * G_PARA_MS2
            az = phy.accG[2] * G_PARA_MS2
            
            # Giroscópio Zerado
            gx = 0.0
            gy = 0.0
            gz = 0.0
            
            sample = [ts, ax, ay, az, gx, gy, gz]
            
            triggered = (abs(ax) > TRIGGER_THRESHOLD_MS2) or (abs(az) > TRIGGER_THRESHOLD_MS2)
            
            if event_in_progress:
                current_event_list.append(sample)
                samples_collected += 1
                
                if samples_collected >= POST_EVENT_SAMPLES:
                    packet_count += 1
                    
                    # 1. Processa IA
                    res = processar_pacote_ia(current_event_list)
                    cor = Colors.FAIL if res == 'aggressive' else Colors.GREEN
                    print(f"📦 PCT #{packet_count} | {CENARIO_TESTE} | IA: {cor}{res.upper()}{Colors.ENDC}")
                    
                    # 2. Grava CSV
                    for s in current_event_list:
                        writer.writerow([CENARIO_TESTE, packet_count, 'EVENTO', res] + s)
                    arquivo_csv.flush()
                    
                    # 3. SIMULAÇÃO DE LATÊNCIA LTE (Bloqueante)
                    # O script para aqui, simulando o tempo de upload do pacote
                    log(f"Simulando upload LTE... ({LATENCIA_LTE_SEC}s)", "REDE")
                    time.sleep(LATENCIA_LTE_SEC) 
                    
                    event_in_progress = False
                    current_event_list = []
                    last_heartbeat = time.time()
            
            else:
                if triggered:
                    event_in_progress = True
                    samples_collected = 0
                    current_event_list = list(pre_event_buffer)
                    current_event_list.append(sample)
                else:
                    pre_event_buffer.append(sample)
                    
                    if (time.time() - last_heartbeat) > HEARTBEAT_INTERVAL_SEC:
                        if len(pre_event_buffer) == PRE_EVENT_SAMPLES:
                            hb = list(pre_event_buffer)
                            while len(hb) < SAMPLES_TOTAL: hb.append(sample)
                            
                            packet_count += 1
                            res_hb = processar_pacote_ia(hb)
                            print(f"💓 Heartbeat processado. IA: {res_hb}")
                            
                            for s in hb:
                                writer.writerow([CENARIO_TESTE, packet_count, 'HEARTBEAT', res_hb] + s)
                            arquivo_csv.flush()
                            
                            # Simulação de Latência no Heartbeat também
                            log(f"Enviando Heartbeat LTE... ({LATENCIA_LTE_SEC}s)", "REDE")
                            time.sleep(LATENCIA_LTE_SEC)
                            
                            last_heartbeat = time.time()
        else:
            time.sleep(1)

        elapsed = time.time() - start
        if elapsed < INTERVALO_SCRIPT: time.sleep(INTERVALO_SCRIPT - elapsed)

except KeyboardInterrupt:
    print("\nFim do teste.")
finally:
    ac.close()
    arquivo_csv.close()