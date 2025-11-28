import streamlit as st
from pymongo import MongoClient
import gridfs
from PIL import Image
import io
import numpy as np
import cv2

# --- Configuração da Página ---
st.set_page_config(page_title="Reconhecimento Facial (Lógica de Aula)", layout="wide")

# --- CSS FORÇADO PARA MÁSCARA (MANTIDO) ---
st.markdown("""
<style>
    div[data-testid="stCameraInput"] { text-align: center; margin: 0 auto; }
    div[data-testid="stCameraInput"] video { border-radius: 12px; }
    div[data-testid="stCameraInput"]::after {
        content: ""; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
        width: 280px; height: 350px;
        border: 5px dashed rgba(255, 255, 255, 0.9); border-radius: 40%;
        box-shadow: 0 0 0 2000px rgba(0, 0, 0, 0.7); pointer-events: none; z-index: 10;
    }
    div[data-testid="stCameraInput"] button { z-index: 20; position: relative; border-radius: 30px; }
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
        st.error(f"Erro de conexão com o banco: {e}")
        return None

client = init_connection()
if client:
    db = client['midias']
    fs = gridfs.GridFS(db)
else:
    st.stop()

# --- Estados da Sessão ---
if 'resultados' not in st.session_state:
    st.session_state['resultados'] = None
if 'foto_atual' not in st.session_state:
    st.session_state['foto_atual'] = None

# --- Funções de Processamento ---

def processar_imagem_aula(image, target_size=(200, 250)):
    img_gray = image.convert('L')
    img_resized = img_gray.resize(target_size)
    img_array = np.array(img_resized, dtype=np.int16)
    return img_array, img_resized

def calcular_diferenca_aula(img_usuario_array, img_banco_array):
    # Soma das Diferenças Absolutas (SAD)
    diferenca_abs = np.abs(img_banco_array - img_usuario_array)
    score_diferenca = np.sum(diferenca_abs)
    return score_diferenca

def calcular_similaridade_percentual(diferenca_score):
    """
    Converte o score bruto de diferença (SAD) em uma porcentagem estimada.
    CALIBRAÇÃO ATUALIZADA:
    O máximo teórico de diferença para 200x250 pixels é: 
    50.000 pixels * 255 (diferença máx por pixel) = 12.750.000.
    
    Ajustamos o divisor para 12.000.000 para ser um pouco mais tolerante.
    """
    max_diferenca_aceitavel = 12000000.0 
    
    # Inverte a lógica: Score 0 de diferença = 100% similaridade
    porcentagem = (1 - (diferenca_score / max_diferenca_aceitavel)) * 100
    
    # Garante que fique entre 0 e 100
    return max(0.0, min(100.0, porcentagem))

def encontrar_matches(foto_usuario_pil):
    resultados = []
    array_usuario, img_usuario_processada = processar_imagem_aula(foto_usuario_pil)
    
    todos_arquivos = list(fs.find())
    total = len(todos_arquivos)
    
    if total == 0: return [], img_usuario_processada

    progresso = st.progress(0)
    
    for i, grid_out in enumerate(todos_arquivos):
        try:
            bytes_img = grid_out.read()
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
            
        except Exception:
            continue
        
        if i % 5 == 0: progresso.progress((i + 1) / total)
    
    progresso.empty()
    # Ordena pela porcentagem maior (Descendente)
    resultados_ordenados = sorted(resultados, key=lambda x: x['porcentagem'], reverse=True)
    return resultados_ordenados, img_usuario_processada

def salvar_no_banco(nome, imagem_pil):
    try:
        buffer = io.BytesIO()
        imagem_pil.save(buffer, format='JPEG', quality=95)
        fs.put(buffer.getvalue(), filename=f"{nome}.jpg")
        st.toast(f"Salvo: {nome}.jpg", icon="💾")
        st.cache_resource.clear()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- Interface ---

st.title("Comparador Facial (Algoritmo da Aula)")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Captura")
    foto = st.camera_input("Tire a foto", label_visibility="collapsed")
    
    if foto:
        img_original = Image.open(foto)
        
        # Recorte Central Simples (Mantém a lógica manual)
        w, h = img_original.size
        target_ratio = 200/250
        current_ratio = w/h
        if current_ratio > target_ratio:
            new_w = h * target_ratio
            left = (w - new_w)/2
            img_crop = img_original.crop((left, 0, left + new_w, h))
        else:
            img_crop = img_original
            
        with st.spinner("Calculando similaridade..."):
            matches, img_proc = encontrar_matches(img_crop)
            st.session_state['resultados'] = matches
            st.session_state['foto_atual'] = img_proc

    if st.session_state['foto_atual']:
        st.image(st.session_state['foto_atual'], caption="Sua foto processada", width=150)
        with st.form("save"):
            nome = st.text_input("Nome do Usuário:")
            if st.form_submit_button("Salvar Imagem"):
                if nome: salvar_no_banco(nome, st.session_state['foto_atual'])
                else: st.warning("Digite um nome.")

with col2:
    st.subheader("Resultados")
    
    res = st.session_state['resultados']
    if res:
        qtde = st.slider("Quantidade de imagens:", 1, 10, 3)
        ordem = st.radio("Mostrar:", ["Mais Parecidas (Maior %)", "Menos Parecidas (Menor %)"], horizontal=True)
        
        lista_final = res[:qtde] if "Mais" in ordem else res[-qtde:][::-1]
        
        cols = st.columns(qtde)
        for i, item in enumerate(lista_final):
            with cols[i]:
                # Exibe Imagem
                st.image(item['imagem'], use_container_width=True)
                st.markdown(f"**{item['filename']}**")
                
                # Exibe Porcentagem Grande e Colorida (Azul/Verde/Vermelho)
                pct = item['porcentagem']
                
                if pct > 80:
                    cor = "#0066cc" # Azul forte
                elif pct > 60:
                    cor = "green"   # Verde
                else:
                    cor = "red"     # Vermelho
                
                st.markdown(f"""
                <h3 style='text-align: center; color: {cor}; margin:0;'>
                    {pct:.1f}%
                </h3>
                """, unsafe_allow_html=True)
                
                # Exibe Diferença Bruta (Pequeno)
                st.caption(f"Dif. Bruta: {item['diferenca']:,.0f}")
                
                # Barra de Progresso Visual
                st.progress(int(pct))
    else:
        st.info("Aguardando foto...")