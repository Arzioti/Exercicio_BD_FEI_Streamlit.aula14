import streamlit as st
from pymongo import MongoClient
import gridfs
from PIL import Image
import io

# Conexão com o MongoDB Atlas
uri = "mongodb+srv://antoniocjunior61_db_user:MP86bA8RrKUcVwc0@cluster0.xnstoor.mongodb.net/?appName=Cluster0"
client = MongoClient(uri)
db = client['midias']
fs = gridfs.GridFS(db)

st.title("Visualizador de Imagens do GridFS")

# Buscar todos os arquivos armazenados no GridFS
arquivos = list(fs.find())

if not arquivos:
    st.warning("Nenhuma imagem encontrada no GridFS.")
else:
    st.write(f"Total de imagens armazenadas: {len(arquivos)}")

    # Exibir imagens em colunas
    cols = st.columns(3)  # 3 imagens por linha
    for i, arquivo in enumerate(arquivos):
        dados = arquivo.read()
        imagem = Image.open(io.BytesIO(dados))

        with cols[i % 3]:
            st.image(imagem, caption=arquivo.filename, use_container_width=True)
            st.download_button(
                label="Baixar",
                data=dados,
                file_name=arquivo.filename,
                mime="image/jpeg"
            )