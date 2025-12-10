import streamlit as st
import paho.mqtt.client as mqtt
import json
import pandas as pd
import plotly.graph_objects as go
import ssl
import time
import queue
from datetime import datetime

# ==============================================================================
# 1. CONFIGURAÇÕES DO SISTEMA
# ==============================================================================
AWS_ENDPOINT = "a3s3fmkum72xz8-ats.iot.us-east-2.amazonaws.com" 
PORT = 8883
TOPIC_DATA = "veiculos/+/eventos"
TOPIC_AI   = "veiculos/+/resposta_IA"

CA_PATH = "root-CA.pem"
CERT_PATH = "dashboard-cert.pem.crt"
KEY_PATH = "dashboard-private.pem.key"

MAX_SAMPLES = 500 

# ==============================================================================
# 2. CONFIGURAÇÃO DA PÁGINA E ESTILO
# ==============================================================================
st.set_page_config(page_title="TCC Telemetry AI", page_icon="🔥", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@300;500;700&display=swap');

    /* RESET GERAL */
    .stApp {
        background-color: #050505;
        background-image: radial-gradient(circle at 50% 50%, #1a1a1a 0%, #000000 100%);
    }
    
    * { font-family: 'Rajdhani', sans-serif; }
    h1, h2, h3, .big-font { font-family: 'Orbitron', sans-serif; letter-spacing: 2px; }

    /* HEADER */
    .header-container {
        display: flex; justify-content: space-between; align-items: center;
        padding: 10px 20px; border-bottom: 2px solid #00f2ff;
        box-shadow: 0 0 15px rgba(0, 242, 255, 0.3); margin-bottom: 20px;
        background: rgba(0,0,0,0.6);
    }
    
    /* ANIMATION */
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(0, 255, 65, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(0, 255, 65, 0); }
        100% { box-shadow: 0 0 0 0 rgba(0, 255, 65, 0); }
    }
    .live-indicator {
        width: 12px; height: 12px; background-color: #00ff41;
        border-radius: 50%; display: inline-block; margin-right: 8px;
        animation: pulse 2s infinite;
    }

    /* CARDS */
    .hud-card {
        background: rgba(20, 20, 30, 0.6);
        backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1); border-left: 4px solid #444;
        border-radius: 4px; padding: 15px; margin-bottom: 10px;
        transition: all 0.3s ease; position: relative; overflow: hidden;
    }
    .hud-value { 
        color: #fff; font-size: 24px; font-weight: 700; margin-top: 5px; 
        font-family: 'Orbitron'; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .hud-label { color: #888; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }

    /* Payload Monitor */
    .payload-box {
        background-color: #0d0d0d; border: 1px solid #333; color: #00f2ff;
        font-family: 'Courier New', monospace; font-size: 12px; padding: 10px;
        border-radius: 5px; height: 120px; overflow-y: auto;
    }

    /* Cores Específicas */
    .border-cyan { border-left-color: #00f2ff; } .text-cyan { color: #00f2ff; }
    .border-magenta { border-left-color: #ff00ff; } .text-magenta { color: #ff00ff; }
    .border-green { border-left-color: #00ff41; } .text-green { color: #00ff41; }
    .border-red { border-left-color: #ff002b; } .text-red { color: #ff002b; }

    .block-container { padding-top: 1rem; padding-bottom: 5rem; max-width: 100%; }
    header, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. GERENCIAMENTO DE ESTADO
# ==============================================================================
if 'trace_ax' not in st.session_state: st.session_state.trace_ax = [0] * MAX_SAMPLES
if 'trace_ay' not in st.session_state: st.session_state.trace_ay = [0] * MAX_SAMPLES
if 'trace_az' not in st.session_state: st.session_state.trace_az = [0] * MAX_SAMPLES
if 'trace_gx' not in st.session_state: st.session_state.trace_gx = [0] * MAX_SAMPLES
if 'trace_gy' not in st.session_state: st.session_state.trace_gy = [0] * MAX_SAMPLES
if 'trace_gz' not in st.session_state: st.session_state.trace_gz = [0] * MAX_SAMPLES

if 'full_session_data' not in st.session_state: st.session_state.full_session_data = []

if 'last_prediction' not in st.session_state: st.session_state.last_prediction = "AGUARDANDO..."
if 'dev_id' not in st.session_state: st.session_state.dev_id = "--"
if 'last_update' not in st.session_state: st.session_state.last_update = "OFFLINE"
if 'raw_event' not in st.session_state: st.session_state.raw_event = {}
if 'raw_ai' not in st.session_state: st.session_state.raw_ai = {}

@st.cache_resource
def get_msg_queue(): return queue.Queue()
msg_queue = get_msg_queue()

# ==============================================================================
# 4. PROCESSAMENTO DE DADOS (COM TRAVA ANTI-DUPLICIDADE)
# ==============================================================================
def process_queue():
    updated = False
    try:
        while not msg_queue.empty():
            msg = msg_queue.get_nowait()
            data = msg['payload']
            topic = msg['topic']
            updated = True
            
            st.session_state.last_update = datetime.now().strftime("%H:%M:%S")
            
            if "eventos" in topic:
                st.session_state.raw_event = data
                st.session_state.dev_id = data.get('dev_id', 'N/A')
                ts = data.get('ts', 0)

                # --- TRAVA DE DUPLICIDADE ---
                # Se o timestamp for igual ao último salvo, ignora o pacote.
                if st.session_state.full_session_data:
                    if ts == st.session_state.full_session_data[-1].get("timestamp_device", 0):
                        continue # Pula processamento
                
                ax, ay, az = data.get('ax', []), data.get('ay', []), data.get('az', [])
                gx, gy, gz = data.get('gx', []), data.get('gy', []), data.get('gz', [])
                
                # Atualiza Buffers Gráficos
                if isinstance(ax, list):
                    st.session_state.trace_ax.extend(ax)
                    st.session_state.trace_ay.extend(ay)
                    st.session_state.trace_az.extend(az)
                    st.session_state.trace_ax = st.session_state.trace_ax[-MAX_SAMPLES:]
                    st.session_state.trace_ay = st.session_state.trace_ay[-MAX_SAMPLES:]
                    st.session_state.trace_az = st.session_state.trace_az[-MAX_SAMPLES:]

                if isinstance(gx, list):
                    st.session_state.trace_gx.extend(gx)
                    st.session_state.trace_gy.extend(gy)
                    st.session_state.trace_gz.extend(gz)
                    st.session_state.trace_gx = st.session_state.trace_gx[-MAX_SAMPLES:]
                    st.session_state.trace_gy = st.session_state.trace_gy[-MAX_SAMPLES:]
                    st.session_state.trace_gz = st.session_state.trace_gz[-MAX_SAMPLES:]

                # Gravação CSV (Nova Linha)
                max_val = max(ax) if ax else 0
                new_row = {
                    "timestamp_device": ts,
                    "horario_chegada": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "device_id": st.session_state.dev_id,
                    "ax_list": str(ax), "ay_list": str(ay), "az_list": str(az),
                    "gx_list": str(gx), "gy_list": str(gy), "gz_list": str(gz),
                    "pico_acc": max_val,
                    "predicao_ia": "Processando..."
                }
                st.session_state.full_session_data.append(new_row)

            elif "resposta_IA" in topic:
                st.session_state.raw_ai = data
                resultado = data.get("resultado", "ERRO").upper()
                st.session_state.last_prediction = resultado
                
                # Atualiza a última linha com a resposta da IA
                if st.session_state.full_session_data:
                    st.session_state.full_session_data[-1]["predicao_ia"] = resultado

    except Exception as e: pass
    return updated

# ==============================================================================
# 5. CONEXÃO MQTT
# ==============================================================================
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        client.subscribe(TOPIC_DATA)
        client.subscribe(TOPIC_AI)

def on_message(client, userdata, msg):
    try:
        msg_queue.put({"topic": msg.topic, "payload": json.loads(msg.payload.decode())})
    except: pass

@st.cache_resource
def start_mqtt():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="Dash_Final_Clean")
    client.tls_set(ca_certs=CA_PATH, certfile=CERT_PATH, keyfile=KEY_PATH, tls_version=ssl.PROTOCOL_TLSv1_2)
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(AWS_ENDPOINT, PORT, 60)
        client.loop_start()
        return client
    except: return None

_ = start_mqtt()

# ==============================================================================
# 6. LAYOUT E RENDERIZAÇÃO
# ==============================================================================
process_queue()

# --- HEADER ---
st.markdown(f"""
<div class="header-container">
    <div class="header-title">
        <span style="color:#888; font-size:0.7em;">PROJECT //</span> TCC TELEMETRY<span style="color:#00f2ff;">.AI</span>
    </div>
    <div style="display:flex; align-items:center; font-family:'Orbitron'; color:#fff;">
        <span class="live-indicator"></span> SYSTEM ONLINE
        <span style="margin-left:20px; color:#555;">|</span>
        <span style="margin-left:20px; color:#00f2ff;">{st.session_state.last_update}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# --- KPIS / CARDS ---
pred = st.session_state.last_prediction
status_style = {"color": "text-cyan", "border": "border-cyan", "icon": "💠"}
if "AGGRESSIVE" in pred: status_style = {"color": "text-red", "border": "border-red", "icon": "☢️"}
elif "NORMAL" in pred: status_style = {"color": "text-green", "border": "border-green", "icon": "🟢"}
elif "SLOW" in pred: status_style = {"color": "text-magenta", "border": "border-magenta", "icon": "🐌"}

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""<div class="hud-card {status_style['border']}"><div class="hud-label">AI PREDICTION</div>
    <div class="hud-value {status_style['color']}">{status_style['icon']} {pred}</div></div>""", unsafe_allow_html=True)
with col2:
    st.markdown(f"""<div class="hud-card border-cyan"><div class="hud-label">DEVICE ID</div>
    <div class="hud-value" title="{st.session_state.dev_id}">{st.session_state.dev_id}</div></div>""", unsafe_allow_html=True)
with col3:
    pico = max(st.session_state.trace_ax[-10:]) if st.session_state.trace_ax else 0
    st.markdown(f"""<div class="hud-card border-magenta"><div class="hud-label">INSTANT PICO X</div>
    <div class="hud-value text-magenta">{pico:.2f} m/s²</div></div>""", unsafe_allow_html=True)
with col4:
    st.markdown(f"""<div class="hud-card border-green"><div class="hud-label">SESSION LOGS</div>
    <div class="hud-value text-green">{len(st.session_state.full_session_data)} <span style="font-size:16px">pkts</span></div></div>""", unsafe_allow_html=True)

# --- GRÁFICOS (VERTICAL) ---
def create_neon_chart(title, x, y, z):
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=x, mode='lines', name='Eixo X', line=dict(color='#00f2ff', width=2)))
    fig.add_trace(go.Scatter(y=y, mode='lines', name='Eixo Y', line=dict(color='#ff00ff', width=2)))
    fig.add_trace(go.Scatter(y=z, mode='lines', name='Eixo Z', line=dict(color='#ffe600', width=2)))
    
    fig.update_layout(
        title=dict(text=title, font=dict(family="Orbitron", size=14, color="#aaa")),
        template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,10,10,0.5)',
        height=380,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=True, gridcolor='#222', range=[-20, 20]),
        legend=dict(orientation="h", y=1.1, x=1, bgcolor="rgba(0,0,0,0)")
    )
    return fig

st.plotly_chart(create_neon_chart("ACELERÔMETRO (m/s²)", st.session_state.trace_ax, st.session_state.trace_ay, st.session_state.trace_az), use_container_width=True)
st.plotly_chart(create_neon_chart("GIROSCÓPIO (deg/s)", st.session_state.trace_gx, st.session_state.trace_gy, st.session_state.trace_gz), use_container_width=True)

# --- ÁREA DE CONTROLE E EXPORTAÇÃO ---
st.markdown("---")
col_actions, col_monitor1, col_monitor2 = st.columns([1, 2, 2])

with col_actions:
    st.markdown('<div class="hud-label">SESSION CONTROL</div>', unsafe_allow_html=True)
    st.write("")
    
    if st.session_state.full_session_data:
        df_export = pd.DataFrame(st.session_state.full_session_data)
        csv = df_export.to_csv(index=False).encode('utf-8')
        
        # Botão de Download Único
        st.download_button(
            label="💾 DOWNLOAD CSV", data=csv,
            file_name=f"telemetry_log.csv", # Nome estático para evitar re-render loop
            mime="text/csv", type="primary"
        )
    else:
        st.button("💾 NO DATA", disabled=True)

    st.write("")
    if st.button("🗑️ NOVA SESSÃO"):
        st.session_state.full_session_data = []
        st.session_state.trace_ax = [0] * MAX_SAMPLES
        st.session_state.trace_ay = [0] * MAX_SAMPLES
        st.session_state.trace_az = [0] * MAX_SAMPLES
        st.session_state.trace_gx = [0] * MAX_SAMPLES
        st.session_state.trace_gy = [0] * MAX_SAMPLES
        st.session_state.trace_gz = [0] * MAX_SAMPLES
        st.rerun()

with col_monitor1:
    st.markdown('<div class="hud-label">RAW: EVENTOS</div>', unsafe_allow_html=True)
    st.markdown(f"""<div class="payload-box">{json.dumps(st.session_state.raw_event, indent=2)}</div>""", unsafe_allow_html=True)

with col_monitor2:
    st.markdown('<div class="hud-label">RAW: RESPOSTA IA</div>', unsafe_allow_html=True)
    st.markdown(f"""<div class="payload-box">{json.dumps(st.session_state.raw_ai, indent=2)}</div>""", unsafe_allow_html=True)

time.sleep(1)
st.rerun()