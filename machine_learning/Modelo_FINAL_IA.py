"""
Script de Treinamento FINAL (XGBoost Simples Otimizado)

1. Usa a arquitetura "XGBoost Simples" (vencedora do teste A/B).
2. Carrega 100% dos dados.
3. Escala e balanceia (SMOTE) os dados.
4. Usa OPTUNA para encontrar os MELHORES hiperparâmetros (busca de 50 tentativas).
5. Treina o modelo final com os parâmetros campeões.
6. Salva os 3 artefatos finais para produção/implantação.

Requer: pip install optuna
"""

import os
import glob
import json
import warnings
import numpy as np
import pandas as pd
from scipy import signal, stats
from tqdm import tqdm
import joblib
import sys
from time import time
import optuna # <-- NOVO

# Modelos
from xgboost import XGBClassifier

# Pré-processamento e Métricas
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import f1_score
from imblearn.over_sampling import SMOTE

# --- Configurações Globais ---
TARGET_FS = 20.0
WINDOW_SIZE = 50
WINDOW_STEP = 10
GRAVITY_CUTOFF_HZ = 0.5
RANDOM_STATE = 42

# Número de tentativas de otimização do Optuna
N_OPTUNA_TRIALS = 50
# Validação cruzada DENTRO de cada tentativa do Optuna
N_OPTUNA_CV_SPLITS = 3 

# Nomes dos arquivos de saída FINAIS
SCALER_PATH = "scaler_final.joblib"
LABEL_ENCODER_PATH = "label_encoder_final.joblib"
MODEL_PATH = "xgboost_final.joblib"
FEATURE_COLUMNS_PATH = "feature_columns_final.json"

# --- Funções de Carregamento e Normalização (Helpers) ---
# (Colapsei as funções auxiliares aqui para economizar espaço)
# (Elas são idênticas às do script anterior)
def detect_and_normalize_df(df, fpath):
    MAP_D1_MERGED={'time':'time','session':'session','acc_x':'acc_x','acc_y':'acc_y','acc_z':'acc_z','gyro_x':'gyro_x','gyro_y':'gyro_y','gyro_z':'gyro_z','label':'label'}
    MAP_D3={'time':'time','session':'session','accel_x':'acc_x','accel_y':'acc_y','accel_z':'acc_z','label':'label','roll':'gyro_x','pitch':'gyro_y','yaw':'gyro_z'}
    MAP_D24={'Timestamp':'time','AccX':'acc_x','AccY':'acc_y','AccZ':'acc_z','Class':'label','GyroX':'gyro_x','GyroY':'gyro_y','GyroZ':'gyro_z'}
    colmap={}
    fname=os.path.basename(fpath).lower()
    target_map={}
    if 'dataset1_merged' in fname:
        target_map=MAP_D1_MERGED
    elif 'dataset3' in fname:
        target_map=MAP_D3
    elif 'dataset2' in fname or 'dataset4' in fname:
        target_map=MAP_D24
    else:
        target_map={'accel_x':'acc_x','accel_y':'acc_y','accel_z':'acc_z','AccX':'acc_x','AccY':'acc_y','AccZ':'acc_z','acc_x':'acc_x','roll':'gyro_x','pitch':'gyro_y','yaw':'gyro_z','GyroX':'gyro_x','GyroY':'gyro_y','GyroZ':'gyro_z','gyro_x':'gyro_x','label':'label','Class':'label','session':'session','time':'time','timestamp':'time','Timestamp':'time'}
    inv_map={}
    for k,v in target_map.items():
        inv_map.setdefault(v,[]).append(k)
    df_cols_original={c:c for c in df.columns}
    df_cols_lower={c.lower():c for c in df.columns}
    def find_original_col(novo_nome):
        original_names=inv_map.get(novo_nome,[])
        for original_name in original_names:
            if original_name in df_cols_original:
                return df_cols_original[original_name]
            if original_name.lower() in df_cols_lower:
                return df_cols_lower[original_name.lower()]
        if novo_nome in df_cols_original:return df_cols_original[novo_nome]
        if novo_nome in df_cols_lower:return df_cols_lower[novo_nome]
        return None
    for axis in['acc_x','acc_y','acc_z','gyro_x','gyro_y','gyro_z']:colmap[axis]=find_original_col(axis)
    colmap['label']=find_original_col('label');colmap['time']=find_original_col('time');colmap['session']=find_original_col('session')
    norm=pd.DataFrame()
    if colmap['time'] is not None:
        raw=df[colmap['time']]
        try:
            tdt=pd.to_datetime(raw,errors='coerce')
            if tdt.notna().sum()>5 and tdt.isna().sum()<(len(tdt)/2):
                norm['time_seconds']=(tdt.astype('int64')/1e9).values.astype(float)
            else:
                raise ValueError("Não é datetime, tentar numérico")
        except Exception:
            try:
                tnum=pd.to_numeric(raw,errors='coerce')
                if tnum.notna().sum()==0 or(tnum.nunique()<2):
                    raise ValueError("Time column is constant or non-numeric, using fake time")
                tmax=np.nanmax(tnum);t=tnum.astype(float)
                if tmax>1e18:t=t/1e9
                elif tmax>1e15:t=t/1e6
                elif tmax>1e12:t=t/1e3
                norm['time_seconds']=t
            except Exception:
                norm['time_seconds']=np.arange(len(df)).astype(float)/TARGET_FS
    else:
        norm['time_seconds']=np.arange(len(df)).astype(float)/TARGET_FS
    if 'dataset1_merged' not in fname and'time_seconds'in norm.columns:
        norm['time_seconds']=norm['time_seconds']-norm['time_seconds'].min()
    for axis in['acc_x','acc_y','acc_z','gyro_x','gyro_y','gyro_z']:
        col=colmap.get(axis)
        if col is not None and col in df.columns:
            try:
                norm[axis]=pd.to_numeric(df[col],errors='coerce')
                if norm[axis].isna().all()and df[col].dtype=='object':
                    norm[axis]=pd.to_numeric(df[col].str.replace(',','.'),errors='coerce')
            except Exception:norm[axis]=np.nan
        else:
            if'gyro'in axis:norm[axis]=0.0
            else:norm[axis]=np.nan
    if colmap.get('label')is not None and colmap['label']in df.columns:norm['label']=df[colmap['label']].astype(str).str.lower()
    else:norm['label']='unknown'
    if colmap.get('session')is not None and colmap['session']in df.columns:norm['session']=df[colmap['session']].astype(str)
    else:norm['session']=os.path.basename(fpath)
    norm=norm.sort_values('time_seconds',na_position='last').reset_index(drop=True)
    norm=norm.dropna(subset=['acc_x','acc_y','acc_z'])
    return norm
def resample_to_fs(df,target_fs=TARGET_FS):
    t0=df['time_seconds'].values
    if len(t0)<2:return pd.DataFrame()
    start,end=t0[0],t0[-1]
    new_t=np.arange(start,end,1.0/target_fs)
    if len(new_t)<2:return pd.DataFrame()
    res=pd.DataFrame({'time_seconds':new_t})
    for axis in['acc_x','acc_y','acc_z','gyro_x','gyro_y','gyro_z']:
        if axis in df.columns and pd.to_numeric(df[axis],errors='coerce').notna().any():
            y=df[axis].values
            res[axis]=np.interp(new_t,t0,y)
        else:
            res[axis]=0.0
    idx=np.searchsorted(t0,new_t,side='right')-1
    idx[idx<0]=0
    res['label']=df['label'].values[idx]
    res['session']=df['session'].values[idx]
    return res
def remove_gravity(df,fs=TARGET_FS,cutoff_hz=GRAVITY_CUTOFF_HZ):
    b,a=signal.butter(2,cutoff_hz/(0.5*fs),btype='low',analog=False)
    df_out=df.copy()
    for axis in['acc_x','acc_y','acc_z']:
        if axis not in df_out.columns:
            continue
        try:
            if len(df[axis].values)>10:
                g=signal.filtfilt(b,a,df[axis].values)
                df_out[axis]=df[axis].values-g
            else:
                df_out[axis]=df[axis].values-np.mean(df[axis].values)
        except Exception as e:
            df_out[axis]=df[axis].values-np.mean(df[axis].values)
    return df_out
def sliding_windows(df,win_size=WINDOW_SIZE,step=WINDOW_STEP,label_by='majority'):
    X,Y,S=[],[],[]
    n=len(df)
    dt=1.0/TARGET_FS
    for col in['acc_x','acc_y','acc_z','gyro_x','gyro_y','gyro_z']:
        if col not in df.columns:
            df[col]=0.0
    df['acc_vm']=np.sqrt(df['acc_x']**2+df['acc_y']**2+df['acc_z']**2)
    df['gyro_vm']=np.sqrt(df['gyro_x']**2+df['gyro_y']**2+df['gyro_z']**2)
    df['jerk_x']=np.concatenate(([0.0],np.diff(df['acc_x'])/dt))
    df['jerk_y']=np.concatenate(([0.0],np.diff(df['acc_y'])/dt))
    df['jerk_z']=np.concatenate(([0.0],np.diff(df['acc_z'])/dt))
    df['jerk_vm']=np.sqrt(df['jerk_x']**2+df['jerk_y']**2+df['jerk_z']**2)
    feature_channels=['acc_x','acc_y','acc_z','gyro_x','gyro_y','gyro_z','acc_vm','gyro_vm','jerk_x','jerk_y','jerk_z','jerk_vm']
    for start in range(0,n-win_size+1,step):
        w=df.iloc[start:start+win_size]
        arr=w[feature_channels].values
        try:
            mode_vals=pd.Series(w['label'].values).mode()
            if len(mode_vals)>0:lab=str(mode_vals.iloc[0])
            else:lab=str(w['label'].values[win_size//2])
        except Exception:
            lab=str(w['label'].values[win_size//2])
        X.append(arr);Y.append(lab);S.append(w['session'].values[0])
    return np.array(X),np.array(Y),np.array(S)
def extract_features_window(arr,fs=TARGET_FS):
    feats={}
    axes=['acc_x','acc_y','acc_z','gyro_x','gyro_y','gyro_z','acc_vm','gyro_vm','jerk_x','jerk_y','jerk_z','jerk_vm']
    win_size=arr.shape[0]
    for i,ax in enumerate(axes):
        v=arr[:,i]
        feats[f'{ax}_mean']=np.mean(v);feats[f'{ax}_std']=np.std(v)
        feats[f'{ax}_var']=np.var(v);feats[f'{ax}_min']=np.min(v)
        feats[f'{ax}_max']=np.max(v);feats[f'{ax}_median']=np.median(v)
        feats[f'{ax}_rms']=np.sqrt(np.mean(v**2));feats[f'{ax}_energy']=np.sum(v**2)
        feats[f'{ax}_iqr']=np.subtract(*np.percentile(v,[75,25]))
        feats[f'{ax}_skew']=stats.skew(v);feats[f'{ax}_kurtosis']=stats.kurtosis(v)
        if len(v)>1:zc=((v[:-1]*v[1:])<0).sum()/(len(v)-1)
        else:zc=0.0
        feats[f'{ax}_zcross_rate']=zc
        try:
            fft=np.fft.rfft(v);mags=np.abs(fft);freqs=np.fft.rfftfreq(len(v),d=1.0/fs)
            if len(mags)>1:
                idx=np.argmax(mags[1:])+1
                feats[f'{ax}_dom_freq']=freqs[idx];feats[f'{ax}_dom_mag']=mags[idx]
            else:
                feats[f'{ax}_dom_freq']=0.0;feats[f'{ax}_dom_mag']=0.0
        except Exception:
            feats[f'{ax}_dom_freq']=0.0;feats[f'{ax}_dom_mag']=0.0
    return feats
def extract_features(X_windows,fs=TARGET_FS):
    feat_list=[]
    for w in X_windows:
        feat_list.append(extract_features_window(w,fs=fs))
    return pd.DataFrame(feat_list)

# --- Função de Carregamento Principal ---

def load_and_extract_features(csv_dir, target_fs=TARGET_FS):
    all_features_list = []
    all_labels_list = []
    
    print("\n[INFO] Carregando e processando arquivos CSV...")
    csv_paths = glob.glob(os.path.join(csv_dir, "*.csv"))
    
    ignore_list = ['dados.csv', 'mobd_imu_labeled.csv', 'dataset1.csv']
    
    for fpath in tqdm(csv_paths, desc="Arquivos CSV"):
        fname_lower = os.path.basename(fpath).lower()
        
        is_ignored = any(ignored in fname_lower for ignored in ignore_list)
        is_output_file = fname_lower.startswith('features_ensemble') or fname_lower.startswith('xgboost_final')
        
        if is_ignored or (is_output_file and 'dataset1_merged.csv' not in fname_lower):
            continue
                
        try:
            try: 
                df = pd.read_csv(fpath)
            except (pd.errors.ParserError, UnicodeDecodeError): 
                df = pd.read_csv(fpath, sep=';', encoding='latin1')
        except Exception as e:
            print(f"   [AVISO] Falha ao ler {fpath}: {e}")
            continue
        
        if df.empty: 
            continue
            
        nd = detect_and_normalize_df(df, fpath)
        if len(nd) < 2: 
            continue

        unique_sessions = nd['session'].unique()

        for session_id in unique_sessions:
            df_session = nd[nd['session'] == session_id].copy()
            df_session = df_session.sort_values('time_seconds').reset_index(drop=True)
            if len(df_session) < 2: continue
            
            rd = resample_to_fs(df_session, target_fs=target_fs)
            if len(rd) < WINDOW_SIZE: continue
                
            rd = remove_gravity(rd, fs=target_fs, cutoff_hz=GRAVITY_CUTOFF_HZ)
            Xw, Yw, Sw = sliding_windows(rd, win_size=WINDOW_SIZE, step=WINDOW_STEP, label_by='majority')
            if len(Xw) == 0: continue
                
            feats = extract_features(Xw, fs=target_fs)
            all_features_list.append(feats)
            all_labels_list.append(Yw)
            
    if not all_features_list:
        raise RuntimeError("Nenhum dado processado. Verifique os CSVs.")
        
    X_full = pd.concat(all_features_list, ignore_index=True)
    y_full = np.concatenate(all_labels_list)

    print(f"\n[INFO] Amostras antes do filtro: {len(y_full)}")
    print(f"[INFO] Classes originais: {np.unique(y_full)}")
    classes_desejadas = ['normal', 'aggressive', 'slow']
    y_series = pd.Series(y_full); mask = y_series.isin(classes_desejadas)
    
    X_full = X_full[mask].reset_index(drop=True)
    y_full = y_full[mask]
    
    print(f"[INFO] Amostras retidas: {len(y_full)}")
    print(f"[INFO] Classes retidas: {np.unique(y_full)}")
    
    if len(y_full) == 0:
        raise RuntimeError("Nenhuma amostra restou após filtrar.")
    
    X_full = X_full.fillna(0.0); X_full = X_full.replace([np.inf, -np.inf], 0.0)
    
    return X_full, y_full

# --- Função de Otimização (Optuna) ---

def objective(trial, X_res, y_res):
    """
    Função 'objetivo' que o Optuna tentará maximizar.
    Ela testa um conjunto de hiperparâmetros usando validação cruzada.
    """
    
    # 1. Definição do espaço de busca de hiperparâmetros
    param = {
        'objective': 'multi:softmax',
        'num_class': 3,
        'eval_metric': 'mlogloss',
        'n_estimators': trial.suggest_int('n_estimators', 200, 1000, step=100),
        'max_depth': trial.suggest_int('max_depth', 4, 12),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'gamma': trial.suggest_float('gamma', 0.0, 5.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 5.0),
        'reg_lambda': trial.suggest_float('reg_lambda', 0.0, 5.0),
        'random_state': RANDOM_STATE,
        'n_jobs': -1
    }
    
    # 2. Instancia o modelo com os parâmetros da tentativa (trial)
    model = XGBClassifier(**param, use_label_encoder=False)
    
    # 3. Avalia o modelo usando validação cruzada (para um score robusto)
    # Usamos os dados já balanceados (X_res, y_res) para a busca
    skf = StratifiedKFold(n_splits=N_OPTUNA_CV_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    
    scores = cross_val_score(model, X_res, y_res, cv=skf, scoring='f1_macro', n_jobs=-1)
    
    # 4. Retorna a média do F1-Macro
    return np.mean(scores)


# --- Ponto de Entrada Principal ---

def main(csv_dir):
    """
    Função principal para orquestrar o pipeline de treinamento final.
    """
    warnings.filterwarnings('ignore', category=UserWarning)
    
    try:
        t_start = time()
        
        # --- 1. Carregar e Processar Dados ---
        X_full, y_full = load_and_extract_features(csv_dir, target_fs=TARGET_FS)
        
        # --- 2. Salvar Colunas de Features ---
        feature_columns_list = X_full.columns.tolist()
        with open(FEATURE_COLUMNS_PATH, 'w') as f:
            json.dump(feature_columns_list, f)
        print(f"\n[INFO] Lista de features ({len(feature_columns_list)} colunas) salva em: {FEATURE_COLUMNS_PATH}")

        # --- 3. Codificar Labels (e salvar) ---
        le = LabelEncoder()
        y_full_enc = le.fit_transform(y_full)
        joblib.dump(le, LABEL_ENCODER_PATH)
        print(f"[INFO] LabelEncoder salvo em: {LABEL_ENCODER_PATH}")
        
        # --- 4. Escalar Features (e salvar) ---
        # IMPORTANTE: Scaler é treinado nos dados originais (NÃO balanceados)
        scaler = StandardScaler()
        X_full_s = scaler.fit_transform(X_full)
        joblib.dump(scaler, SCALER_PATH)
        print(f"[INFO] Scaler (treinado em {len(X_full_s)} amostras) salvo em: {SCALER_PATH}")
        
        # --- 5. Balancear Dados (SMOTE) ---
        # Agora aplicamos SMOTE nos dados escalados para treinar
        print(f"\n[INFO] Aplicando SMOTE... (Contagem antes: {np.bincount(y_full_enc)})")
        try:
            min_class = np.min(np.bincount(y_full_enc))
            k_n = min(5, min_class - 1) if min_class > 1 else 1
            smote = SMOTE(random_state=RANDOM_STATE, k_neighbors=k_n)
            X_res, y_res = smote.fit_resample(X_full_s, y_full_enc)
            print(f"[INFO] SMOTE concluído. (Contagem depois: {np.bincount(y_res)})")
        except Exception as e:
            print(f"[ERRO] SMOTE falhou: {e}. Abortando.")
            sys.exit(1)
            
        # --- 6. Otimização com Optuna ---
        print(f"\n[INFO] Iniciando otimização com Optuna ({N_OPTUNA_TRIALS} tentativas)...")
        t_optuna_start = time()
        
        # Cria um "estudo" do Optuna, com o objetivo de maximizar o score
        study = optuna.create_study(direction='maximize')
        
        # Passa os dados balanceados (X_res, y_res) para a função 'objective'
        study.optimize(lambda trial: objective(trial, X_res, y_res), n_trials=N_OPTUNA_TRIALS, show_progress_bar=True)
        
        print(f"[INFO] Otimização concluída em {time() - t_optuna_start:.2f}s.")
        
        # --- 7. Exibir Resultados da Otimização ---
        best_params = study.best_params
        best_score = study.best_value
        
        print("\n" + "="*50)
        print("      OTIMIZAÇÃO DO MODELO FINAL CONCLUÍDA")
        print("="*50)
        print(f"Melhor F1-Macro (média de {N_OPTUNA_CV_SPLITS}-Folds): {best_score:.4f}")
        print("\nMelhores Hiperparâmetros Encontrados:")
        print(json.dumps(best_params, indent=4))
        
        # --- 8. Treinar e Salvar Modelo Final ---
        print("\n[INFO] Treinando o modelo XGBoost_final com os melhores parâmetros...")
        
        # Adiciona parâmetros fixos aos melhores encontrados
        final_params = {
            **best_params,
            'objective': 'multi:softmax',
            'num_class': 3,
            'eval_metric': 'mlogloss',
            'random_state': RANDOM_STATE,
            'n_jobs': -1,
            'use_label_encoder': False
        }
        
        model_final = XGBClassifier(**final_params)
        model_final.fit(X_res, y_res) # Treina em 100% dos dados balanceados
        
        joblib.dump(model_final, MODEL_PATH)
        print(f"[INFO] Modelo final salvo em: {MODEL_PATH}")

        print("\n" + "="*50)
        print(f"PIPELINE FINAL CONCLUÍDO (Tempo Total: {time() - t_start:.2f}s)")
        print("Artefatos salvos e prontos para implantação:")
        print(f"1. {MODEL_PATH} (Modelo XGBoost)")
        print(f"2. {SCALER_PATH} (Padronizador)")
        print(f"3. {LABEL_ENCODER_PATH} (Codificador de Labels)")
        print(f"4. {FEATURE_COLUMNS_PATH} (Lista de Colunas)")
        
    except Exception as e:
        print(f"\n[ERRO GERAL] Ocorreu uma exceção: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Script de Treinamento Final (XGBoost Otimizado com Optuna).")
    parser.add_argument('--csv_dir', required=False, default='.', help="Diretório contendo os CSVs (padrão: '.').")
    args = parser.parse_args()
    
    # Desabilitar logs verbosos do Optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    
    print(f"[INFO] Usando diretório de CSVs: {args.csv_dir}")
    main(csv_dir=args.csv_dir)
