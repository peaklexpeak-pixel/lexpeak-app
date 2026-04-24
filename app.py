import streamlit as st
from streamlit_mic_recorder import mic_recorder
from streamlit_gsheets import GSheetsConnection
import openai
import pandas as pd
import os
import json

# Configuración de página
st.set_page_config(page_title="Lexpeak - AI Oral Assessment", layout="wide")

# --- CONEXIONES ---
# Intentamos obtener la llave de los Secrets de Streamlit
if "OPENAI_API_KEY" in st.secrets:
    openai_key = st.secrets["OPENAI_API_KEY"]
else:
    openai_key = "TU_LLAVE_AQUI" # Solo como respaldo

client = openai.OpenAI(api_key=openai_key)
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNCIONES DE BASE DE DATOS ---
def get_data(worksheet):
    return conn.read(worksheet=worksheet, ttl=0).dropna(how="all")

def save_data(worksheet, new_row):
    df_actual = get_data(worksheet)
    df_final = pd.concat([df_actual, pd.DataFrame([new_row])], ignore_index=True)
    conn.update(worksheet=worksheet, data=df_final)

def calificar_audio(archivo_audio):
    transcript = client.audio.transcriptions.create(model="whisper-1", file=archivo_audio)
    texto = transcript.text
    prompt = f"""Califica este texto de inglés: "{texto}". 
    Puntúa de 2.5 a 12.5 en: Pronunciation, Fluency, Grammar, Vocabulary. 
    Total debe ser suma de los 4 (10-50). Responde SOLO JSON:
    {{"pronunciation":0, "fluency":0, "grammar":0, "vocabulary":0, "total":0}}"""
    
    res = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    return json.loads(res.choices[0].message.content)

# --- INTERFAZ LEXPEAK ---
st.title("🚀 Lexpeak")
menu = ["Estudiantes", "Profesores", "Super Admin"]
choice = st.sidebar.selectbox("Selecciona Perfil", menu)

# --- SECCIÓN ESTUDIANTES ---
if choice == "Estudiantes":
    st.header("Área de Práctica")
    codigo = st.text_input("Código de Actividad:")
    nombre = st.text_input("Tu Nombre Completo:")
    
    df_acts = get_data("Actividades")
    if codigo in df_acts["ActivityCode"].values:
        act_info = df_acts[df_acts["ActivityCode"] == codigo].iloc[0]
        st.info(f"Actividad de: {act_info['Teacher']} \n\n Tarea: {act_info['Description']}")
        audio = mic_recorder(start_prompt="⏺️ Empezar Grabación", stop_prompt="⏹️ Detener y Enviar")
        if audio:
            with st.spinner("Lexpeak está analizando tu voz..."):
                with open("temp.mp3", "wb") as f: f.write(audio['bytes'])
                notas = calificar_audio(open("temp.mp3", "rb"))
                nueva_nota = {
                    "Student": nombre, "ActivityCode": codigo, "Teacher": act_info['Teacher'],
                    "Pronunciation": notas['pronunciation'], "Fluency": notas['fluency'],
                    "Grammar": notas['grammar'], "Vocabulary": notas['vocabulary'], "Total": notas['total']
                }
                save_data("Notas", nueva_nota)
                st.success("¡Excelente! Tu calificación ha sido enviada.")
    elif codigo:
        st.error("Código de actividad no válido.")

# --- SECCIÓN PROFESORES ---
elif choice == "Profesores":
    st.header("Acceso para Docentes")
    user = st.text_input("Usuario:")
    pw = st.text_input("Contraseña:", type="password")
    df_profes = get_data("Profesores")
    if user in df_profes["Username"].values:
        real_pw = df_profes[df_profes["Username"] == user]["Password"].values[0]
        if pw == str(real_pw):
            sub_menu = st.tabs(["Mis Notas", "Crear Actividad"])
            with sub_menu[0]:
                df_notas = get_data("Notas")
                st.dataframe(df_notas[df_notas["Teacher"] == user])
            with sub_menu[1]:
                nuevo_cod = st.text_input("Crea un código (ej: UNIT1):")
                desc = st.text_area("Instrucciones:")
                if st.button("Publicar Actividad"):
                    save_data("Actividades", {"Teacher": user, "ActivityCode": nuevo_cod, "Description": desc})
                    st.success("Actividad creada.")
        else: st.error("Contraseña incorrecta")

# --- SECCIÓN SUPER ADMIN ---
elif choice == "Super Admin":
    admin_pw = st.text_input("Master Password:", type="password")
    if admin_pw == "lexpeak2025":
        st.header("Gestión de Profesores")
        new_prof = st.text_input("Nombre del Profesor:")
        new_user = st.text_input("Usuario:")
        new_pass = st.text_input("Contraseña:")
        if st.button("Dar de alta Profesor"):
            save_data("Profesores", {"Username": new_user, "Password": new_pass, "Name": new_prof})
            st.success(f"Profesor {new_prof} agregado.")
