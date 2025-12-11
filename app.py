import streamlit as st
from pymongo import MongoClient
import gridfs
from PIL import Image, ImageOps
import io
import numpy as np

# --- Configuração da Página (OBRIGATÓRIO SER A PRIMEIRA LINHA) ---
st.set_page_config(page_title="Reconhecimento Facial", layout="wide", initial_sidebar_state="collapsed")

# --- CSS V15 - PADRÃO BANCO DE DADOS (SEM ZOOM) ---
st.markdown("""
<style>
    /* 1. RESET BÁSICO */
    .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
    }
    
    header, footer, #MainMenu { display: none !important; }
    
    .stApp {
        background-color: black;
    }

    /* 2. CÂMERA FULL SCREEN (SEM DISTORÇÃO) */
    div[data-testid="stCameraInput"] {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        z-index: 10 !important;
        background-color: black !important;
    }

    div[data-testid="stCameraInput"] > div {
        height: 100vh !important;
        width: 100vw !important;
        aspect-ratio: unset !important;
    }

    div[data-testid="stCameraInput"] video {
        width: 100vw !important;
        height: 100vh !important;
        object-fit: cover !important;
        min-height: 100vh !important;
        object-position: center !important; /* CENTRO EXATO */
    }

    /* 3. MÁSCARA GUIA (CENTRALIZADA 50%) */
    div[data-testid="stCameraInput"]::after {
        content: ""; 
        position: absolute; 
        
        /* Centralizado para alinhar com o crop matemático */
        top: 50%; 
        left: 50%; 
        transform: translate(-50%, -50%);
        
        width: 280px; 
        height: 380px; 
        
        border: 3px dashed rgba(255, 255, 255, 0.5); 
        border-radius: 50%; 
        box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.5); 
        pointer-events: none; 
        z-index: 20; 
    }

    /* 4. BOTÃO DE CAPTURA */
    div[data-testid="stCameraInput"] button { 
        position: absolute !important; 
        bottom: 50px !important; 
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 30 !important; 
        width: 80px !important; 
        height: 80px !important;
        border-radius: 50% !important;
        background-color: #ff4444 !important;
        border: 4px solid white !important;
        color: transparent !important;
    }
    
    /* 5. TELA DE RESULTADOS */
    .resultados-wrapper {
        background-color: #0e1117;
        min-height: 100vh;
        padding: 20px;
        padding-top: 40px;
        display: flex;
        flex-direction: column;
        align-items: center;
        overflow-y: auto !important;
    }
    
    .stRadio label, .stSelectbox label, p, h3 {
        color: white !important;
    }

    small { display: none !important; }
    
</style>
""", unsafe_allow_html=True)

# --- Conexão MongoDB ---
URI = "mongodb+srv://antoniocjunior61_db_user:MP86bA8RrKUcVwc0@cluster0.xnstoor.mongodb.net/?appName=Cluster0"

@st.cache_resource
def init_connection():
    try:
        client = MongoClient(URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        return client
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

client = init_connection()

if client:
    db = client['midias']
    fs = gridfs.GridFS(db)
else:
    st.stop()

# --- Estados ---
if 'camera_key' not in st.session_state:
    st.session_state.camera_key = 0
if 'resultados' not in st.session_state:
    st.session_state['resultados'] = None
if 'foto_atual' not in st.session_state:
    st.session_state['foto_atual'] = None

def resetar_app():
    st.session_state['resultados'] = None
    st.session_state['foto_atual'] = None
    st.session_state.camera_key += 1
    st.rerun()

# --- Processamento ---
def processar_imagem_aula(image, target_size=(200, 250)):
    img_gray = image.convert('L')
    img_resized = img_gray.resize(target_size)
    img_array = np.array(img_resized, dtype=np.int16)
    return img_array, img_resized

def calcular_diferenca_aula(img_usuario_array, img_banco_array):
    diferenca_abs = np.abs(img_banco_array - img_usuario_array)
    score_diferenca = np.sum(diferenca_abs)
    return score_diferenca

def calcular_similaridade_percentual(diferenca_score):
    max_diferenca_aceitavel = 8000000.0 
    porcentagem = (1 - (diferenca_score / max_diferenca_aceitavel)) * 100
    return max(0.0, min(100.0, porcentagem))

def encontrar_matches(foto_usuario_pil):
    resultados = []
    array_usuario, img_usuario_processada = processar_imagem_aula(foto_usuario_pil)
    
    try:
        todos_arquivos = list(fs.find())
        if not todos_arquivos:
            return [], img_usuario_processada
    except:
        return [], img_usuario_processada
    
    for grid_out in todos_arquivos:
        try:
            bytes_img = grid_out.read()
            if not bytes_img: continue
            img_banco_pil = Image.open(io.BytesIO(bytes_img))
            array_banco, img_banco_processada = processar_imagem_aula(img_banco_pil)
            diferenca = calcular_diferenca_aula(array_usuario, array_banco)
            porcentagem = calcular_similaridade_percentual(diferenca)
            resultados.append({
                'filename': grid_out.filename,
                'diferenca': diferenca,
                'porcentagem': porcentagem,
                'imagem': img_banco_processada
            })
        except:
            continue
            
    resultados_ordenados = sorted(resultados, key=lambda x: x['porcentagem'], reverse=True)
    return resultados_ordenados, img_usuario_processada

def salvar_no_banco(nome, imagem_pil):
    try:
        buffer = io.BytesIO()
        imagem_pil.save(buffer, format='JPEG', quality=95)
        fs.put(buffer.getvalue(), filename=f"{nome}.jpg")
        st.toast(f"Salvo: {nome}.jpg", icon="💾")
        import time
        time.sleep(1.5)
        resetar_app()
    except Exception as e:
        st.error(f"Erro: {e}")

# --- LÓGICA PRINCIPAL ---

if st.session_state['foto_atual'] is None:
    # === TELA 1: CÂMERA ===
    foto = st.camera_input("Tire a foto", label_visibility="collapsed", key=f"cam_{st.session_state.camera_key}")
    
    if foto:
        st.markdown("""<style>div[data-testid="stCameraInput"] { display: none !important; }</style>""", unsafe_allow_html=True)
        
        with st.status("Processando...", expanded=True) as status:
            img_original = Image.open(foto)
            img_original = ImageOps.exif_transpose(img_original)
            
            # --- CROP MAXIMIZADO (SEM ZOOM EXCESSIVO) ---
            # Objetivo: Manter o máximo da imagem original, apenas ajustando a proporção para 4:5 (0.8)
            # Isso garante que se você enquadrou o rosto na tela, ele vai aparecer na foto.
            
            w, h = img_original.size
            img_ratio = w / h
            target_ratio = 200 / 250 # 0.8
            
            if img_ratio > target_ratio:
                # Imagem é mais "gorda" que o alvo (ex: PC ou Horizontal)
                # Cortamos as laterais, mantemos a altura total
                new_w = h * target_ratio
                left = (w - new_w) / 2
                img_crop = img_original.crop((left, 0, left + new_w, h))
            else:
                # Imagem é mais "alta" que o alvo (ex: Celular Vertical 9:16)
                # Cortamos o excesso de topo e base, mantemos a largura total.
                # Como a máscara está no CENTRO, o corte centralizado é perfeito.
                new_h = w / target_ratio
                top = (h - new_h) / 2
                img_crop = img_original.crop((0, top, w, top + new_h))
            
            matches, img_proc = encontrar_matches(img_crop)
            
            st.session_state['resultados'] = matches
            st.session_state['foto_atual'] = img_proc
            
            status.update(label="Pronto!", state="complete", expanded=False)
        st.rerun()

else:
    # === TELA 2: RESULTADOS ===
    st.markdown("""
        <style>
            .block-container { overflow: auto !important; }
            div[data-testid="stCameraInput"] { display: none !important; }
            .stApp { background-color: #0e1117 !important; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='resultados-wrapper'>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>Análise Concluída</h3>", unsafe_allow_html=True)
    
    # Exibe a foto analisada maior para conferência
    st.image(st.session_state['foto_atual'], caption="Sua Foto (Padrão Banco)", width=200)
    
    st.divider()
    
    res = st.session_state['resultados']
    if res:
        c_f1, c_f2 = st.columns([1, 1])
        with c_f1: qtde = st.selectbox("Qtd:", [3, 6, 9], index=0)
        with c_f2: ordem = st.radio("Ver:", ["Mais Parecidas", "Menos Parecidas"], horizontal=True)
        
        lista = res[:qtde] if "Mais" in ordem else res[-qtde:][::-1]
        
        cols = st.columns(3)
        for i, item in enumerate(lista):
            with cols[i % 3]:
                st.image(item['imagem'], use_container_width=True)
                pct = item['porcentagem']
                cor = "#00ff00" if pct >= 60 else "#ff4444"
                st.markdown(f"<div style='text-align:center; color:{cor}; font-weight:bold;'>{pct:.0f}%</div>", unsafe_allow_html=True)
                st.caption(f"{item['filename']}")
    else:
        st.info("Banco vazio.")

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 Nova Foto", use_container_width=True, type="primary"):
            resetar_app()
    with c2:
        with st.popover("💾 Salvar", use_container_width=True):
            nome = st.text_input("Nome:")
            if st.button("Confirmar"):
                if nome: salvar_no_banco(nome, st.session_state['foto_atual'])
                else: st.warning("Nome vazio")
    
    st.markdown("</div>", unsafe_allow_html=True)