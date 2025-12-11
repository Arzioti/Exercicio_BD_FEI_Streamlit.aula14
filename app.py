import streamlit as st
from pymongo import MongoClient
import gridfs
from PIL import Image
import io
import numpy as np
import cv2

# --- Configuração da Página (OBRIGATÓRIO SER A PRIMEIRA LINHA) ---
st.set_page_config(page_title="Reconhecimento Facial", layout="wide", initial_sidebar_state="collapsed")

# --- CSS SUPREMO PARA MOBILE (CORRIGIDO V5 - NUCLEAR) ---
st.markdown("""
<style>
    /* 1. RESET TOTAL DA PÁGINA */
    .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
        overflow: hidden !important;
    }
    
    header, footer, #MainMenu { display: none !important; }
    
    .stApp {
        background-color: black;
    }

    /* 2. FORÇA BRUTA NO VIDEO (V5) */
    
    /* Container Principal: Fixo na tela */
    div[data-testid="stCameraInput"] {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 85vh !important;
        z-index: 1 !important;
        background-color: black !important;
    }

    /* Força TODOS os containers internos (Pai e Avô do vídeo) a ocuparem 100% */
    div[data-testid="stCameraInput"] > div,
    div[data-testid="stCameraInput"] > div > div {
        height: 100% !important;
        width: 100% !important;
        aspect-ratio: unset !important; /* Mata o cálculo de proporção */
        padding-bottom: 0 !important;
        margin-bottom: 0 !important;
    }

    /* O Elemento de Vídeo em si - A regra suprema */
    /* Usamos seletores genéricos dentro do input para garantir que pegue */
    div[data-testid="stCameraInput"] video {
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        width: 100% !important;
        height: 100% !important;
        
        /* O segredo: min-height força o vídeo a ignorar o redimensionamento do JS */
        min-height: 85vh !important; 
        min-width: 100vw !important;
        
        object-fit: cover !important; /* Garante que preencha tudo (zoom) */
        z-index: 2 !important;
    }

    /* 3. MÁSCARA GUIA (ROSTO) */
    div[data-testid="stCameraInput"]::after {
        content: ""; 
        position: absolute; 
        top: 45%; 
        left: 50%; 
        transform: translate(-50%, -50%);
        width: 70vw; 
        height: 45vh; 
        border: 4px dashed rgba(255, 255, 255, 0.6); 
        border-radius: 50%; 
        box-shadow: 0 0 0 100vmax rgba(0, 0, 0, 0.5); /* Sombra gigante */
        pointer-events: none; 
        z-index: 50; /* Acima do vídeo */
    }

    /* 4. BOTÃO DE CAPTURA */
    div[data-testid="stCameraInput"] button { 
        position: absolute !important; 
        bottom: 5vh !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 100 !important; /* Bem acima de tudo */
        width: 80px !important; 
        height: 80px !important;
        border-radius: 50% !important;
        background-color: #ff4444 !important;
        border: 4px solid white !important;
        color: transparent !important;
    }
    
    div[data-testid="stCameraInput"] button:active {
        transform: translateX(-50%) scale(0.9) !important;
        background-color: #cc0000 !important;
    }

    /* Esconde textos auxiliares */
    div[data-testid="stCameraInput"] small { display: none !important; }

    /* Área de Resultados */
    .resultados-container {
        margin-top: 85vh !important;
        position: relative;
        z-index: 200;
        background-color: #0e1117;
        padding: 20px;
        min-height: 50vh;
        border-top-left-radius: 20px;
        border-top-right-radius: 20px;
    }
    
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

# --- Cache e Estados da Sessão ---
if 'resultados' not in st.session_state:
    st.session_state['resultados'] = None
if 'foto_atual' not in st.session_state:
    st.session_state['foto_atual'] = None
if 'ultimo_buffer_foto' not in st.session_state:
    st.session_state['ultimo_buffer_foto'] = None 

# --- Funções Matemáticas e de Processamento ---

def processar_imagem_aula(image, target_size=(200, 250)):
    # Converte para Cinza e Redimensiona
    img_gray = image.convert('L')
    img_resized = img_gray.resize(target_size)
    # Usa int16 para permitir subtração negativa no cálculo da diferença
    img_array = np.array(img_resized, dtype=np.int16)
    return img_array, img_resized

def calcular_diferenca_aula(img_usuario_array, img_banco_array):
    # Soma das Diferenças Absolutas (SAD)
    diferenca_abs = np.abs(img_banco_array - img_usuario_array)
    score_diferenca = np.sum(diferenca_abs)
    return score_diferenca

def calcular_similaridade_percentual(diferenca_score):
    # Calibração: 8 milhões como limite máximo aceitável para separar bem
    max_diferenca_aceitavel = 8000000.0 
    porcentagem = (1 - (diferenca_score / max_diferenca_aceitavel)) * 100
    return max(0.0, min(100.0, porcentagem))

def encontrar_matches(foto_usuario_pil):
    resultados = []
    array_usuario, img_usuario_processada = processar_imagem_aula(foto_usuario_pil)
    
    try:
        todos_arquivos = list(fs.find())
        if not todos_arquivos:
            return [], img_usuario_processada # Retorna vazio se não houver imagens
    except:
        return [], img_usuario_processada
    
    # Processa todas as imagens do banco
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
            
    # Ordena: Maior porcentagem primeiro
    resultados_ordenados = sorted(resultados, key=lambda x: x['porcentagem'], reverse=True)
    return resultados_ordenados, img_usuario_processada

def salvar_no_banco(nome, imagem_pil):
    try:
        buffer = io.BytesIO()
        imagem_pil.save(buffer, format='JPEG', quality=95)
        fs.put(buffer.getvalue(), filename=f"{nome}.jpg")
        st.toast(f"Salvo: {nome}.jpg", icon="💾")
        st.cache_resource.clear()
        st.session_state['ultimo_buffer_foto'] = None # Força reprocessar na próxima
    except Exception as e:
        st.error(f"Erro: {e}")

# --- Interface Principal (Mobile First) ---

# Container vazio apenas para segurar o lugar, já que o CSS posiciona tudo como fixed
placeholder_cam = st.empty()

with placeholder_cam:
    foto = st.camera_input("Tire a foto", label_visibility="collapsed")

# Lógica de Cache Inteligente: Só processa se a foto mudou
if foto:
    bytes_foto_atual = foto.getvalue()
    
    if bytes_foto_atual != st.session_state['ultimo_buffer_foto']:
        img_original = Image.open(foto)
        
        # Crop Inteligente (Centralizado)
        w, h = img_original.size
        target_ratio = 200/250
        current_ratio = w/h
        
        if current_ratio > target_ratio:
            new_w = h * target_ratio
            left = (w - new_w)/2
            img_crop = img_original.crop((left, 0, left + new_w, h))
        else:
            new_h = w / target_ratio
            top = (h - new_h)/2
            img_crop = img_original.crop((0, top, w, top + new_h))
        
        with st.spinner("Analisando..."):
            matches, img_proc = encontrar_matches(img_crop)
            st.session_state['resultados'] = matches
            st.session_state['foto_atual'] = img_proc
            st.session_state['ultimo_buffer_foto'] = bytes_foto_atual

# --- Exibição dos Resultados ---
if st.session_state['foto_atual']:
    # Classe CSS específica para empurrar o conteúdo para baixo da câmera fixa
    st.markdown("<div class='resultados-container'>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📊 Comparação", "💾 Salvar"])
    
    with tab1:
        res = st.session_state['resultados']
        if res:
            # Controles Rápidos
            c1, c2 = st.columns([1, 1])
            with c1: 
                qtde = st.selectbox("Quantidade:", [3, 6, 9, 12], index=0)
            with c2: 
                ordem = st.radio("Mostrar:", ["Mais Parecidas", "Menos Parecidas"], horizontal=True)
            
            # Filtra a lista (instantâneo, sem reprocessar imagem)
            if "Mais" in ordem:
                lista_final = res[:qtde]
            else:
                lista_final = res[-qtde:][::-1]
            
            # Grid
            cols = st.columns(3)
            for i, item in enumerate(lista_final):
                with cols[i % 3]:
                    st.image(item['imagem'], use_container_width=True)
                    pct = item['porcentagem']
                    
                    # Cores
                    cor = "green" if pct >= 60 else "red"
                    
                    st.markdown(f"<h3 style='text-align:center; color:{cor}; margin:0; font-size: 18px;'>{pct:.0f}%</h3>", unsafe_allow_html=True)
                    st.caption(f"{item['filename']}")
        else:
            st.warning("Banco de dados vazio.")

    with tab2:
        col_img, col_input = st.columns([1, 2])
        with col_img:
            st.image(st.session_state['foto_atual'], use_container_width=True, caption="Sua Foto")
        with col_input:
            with st.form("salvar_foto"):
                nome_input = st.text_input("Nome da pessoa:")
                if st.form_submit_button("Salvar no Banco", use_container_width=True):
                    if nome_input:
                        salvar_no_banco(nome_input, st.session_state['foto_atual'])
                    else:
                        st.warning("Escreva um nome.")

    st.markdown("</div>", unsafe_allow_html=True)