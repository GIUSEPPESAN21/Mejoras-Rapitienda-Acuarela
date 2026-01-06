Gestor de Inventario y Pedidos con Streamlit
Esta es una aplicación web interactiva para la gestión de inventarios y el procesamiento de pedidos, construida íntegramente en Python utilizando la librería Streamlit.

La aplicación permite a los usuarios:

Añadir y actualizar items en el inventario.

Crear nuevos pedidos especificando un título, precio e ingredientes requeridos del inventario.

Visualizar pedidos en proceso y marcarlos como "completados", lo que descuenta automáticamente el stock de los ingredientes correspondientes.

Cancelar pedidos en proceso.

Ver un historial de pedidos completados.

Consultar un informe financiero con el total de ventas y un resumen del inventario final.

Descargar un reporte del inventario actual en formato PDF.

Esta versión es una adaptación de una aplicación originalmente desarrollada con Flask y una interfaz HTML/JavaScript.

Estructura del Proyecto
app.py: El script principal de Python que contiene toda la lógica de la aplicación y la definición de la interfaz de usuario con Streamlit.

requirements.txt: El archivo que lista todas las dependencias de Python necesarias para ejecutar el proyecto.

Cómo Ejecutar la Aplicación Localmente
Sigue estos pasos para poner en marcha la aplicación en tu máquina local.

Clonar el Repositorio:

git clone <URL-de-tu-repositorio-en-GitHub>
cd <nombre-del-repositorio>

Crear y Activar un Entorno Virtual (Recomendado):
Esto aísla las dependencias de tu proyecto.

# Crear el entorno
python3 -m venv venv

# Activar en macOS/Linux
source venv/bin/activate

# Activar en Windows
.\venv\Scripts\activate

Instalar las Dependencias:
El archivo requirements.txt contiene todas las librerías necesarias.

pip install -r requirements.txt

Ejecutar la Aplicación Streamlit:
Una vez instaladas las dependencias, ejecuta el siguiente comando en tu terminal:

streamlit run app.py

Streamlit iniciará un servidor local y abrirá la aplicación automáticamente en tu navegador web.

Despliegue en Streamlit Community Cloud
Esta aplicación está lista para ser desplegada gratuitamente en la plataforma de Streamlit.

Sube tu código a un repositorio público en GitHub. Asegúrate de que los archivos app.py y requirements.txt estén en la raíz del repositorio.

Regístrate en Streamlit Community Cloud usando tu cuenta de GitHub.

Desplegar la aplicación:

Desde tu panel de control, haz clic en "New app".

Selecciona el repositorio de GitHub que acabas de subir.

Asegúrate de que la rama (main o master) y el archivo principal (app.py) estén correctamente seleccionados.

Haz clic en "Deploy!".

Streamlit se encargará del resto, instalando las dependencias y poniendo tu aplicación en línea para que puedas compartirla con una URL pública.
