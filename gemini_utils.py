import google.generativeai as genai
import logging
from PIL import Image
import streamlit as st
import json
from datetime import datetime, timezone
import google.api_core.exceptions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiUtils:
    def __init__(self):
        """
        Initializes the Gemini client by finding the best available model.
        """
        self.api_key = st.secrets.get('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY no encontrada en los secrets de Streamlit")

        genai.configure(api_key=self.api_key)
        self.model = self._get_available_model()

    def _get_available_model(self):
        """
        Intenta inicializar el mejor modelo de Gemini disponible de la lista proporcionada.
        """
        # Lista de modelos priorizada, AHORA INCLUYE el modelo experimental.
        model_candidates = [
            "gemini-2.0-flash-exp",       # Modelo experimental más reciente (prioridad 1)
            "gemini-1.5-flash-latest",    # Versión más reciente y rápida de 1.5
            "gemini-1.5-pro-latest",      # Versión Pro más reciente de 1.5
            "gemini-1.5-flash",           # Modelo Flash básico
            "gemini-1.5-pro",             # Modelo Pro básico
        ]

        for model_name in model_candidates:
            try:
                model = genai.GenerativeModel(model_name)
                logger.info(f"✅ Modelo de Gemini '{model_name}' inicializado con éxito.")
                return model
            except google.api_core.exceptions.NotFound:
                 logger.warning(f"⚠️ Modelo '{model_name}' no encontrado (NotFound).")
                 continue
            except Exception as e:
                logger.warning(f"⚠️ Modelo '{model_name}' no disponible o no compatible: {e}")
                continue

        raise Exception("No se pudo inicializar ningún modelo de Gemini compatible de la lista.")


    def generate_daily_report(self, orders: list):
        """
        Generates a daily sales report as a Markdown string with recommendations.
        """
        if not self.model:
            return "### Error\nEl modelo de texto no está inicializado."
        if not orders:
            return "### Reporte Diario\nNo hubo ventas completadas hoy para generar un reporte."

        total_revenue = sum(o.get('price', 0) for o in orders if isinstance(o.get('price'), (int, float)))
        total_orders = len(orders)

        item_sales = {}
        for order in orders:
            for item in order.get('ingredients', []):
                item_name = item.get('name', 'N/A')
                quantity = item.get('quantity', 0)
                if isinstance(quantity, (int, float)) and quantity > 0:
                    item_sales[item_name] = item_sales.get(item_name, 0) + quantity

        top_selling_items = sorted(item_sales.items(), key=lambda x: x[1], reverse=True)

        prompt = f"""
        **Actúa como un analista de negocios experto para una tienda.**

        **Fecha del Reporte:** {datetime.now(timezone.utc).strftime('%d de %B de %Y')}

        **Datos de Ventas del Día:**
        * **Ingresos Totales:** ${total_revenue:,.2f}
        * **Número de Pedidos:** {total_orders}
        * **Artículos Vendidos (Nombre: Cantidad):**
        """
        for name, qty in top_selling_items:
            prompt += f"    * {name}: {qty}\n"

        prompt += """
        **Tu Tarea:**
        Basado en los datos de ventas de hoy, escribe un reporte conciso y accionable en formato Markdown. El reporte debe incluir:
        1.  Un **Resumen Ejecutivo** de una o dos frases.
        2.  Una sección de **Observaciones Clave** con 2-3 puntos importantes.
        3.  Una sección de **Recomendaciones Estratégicas** con 2-3 acciones claras.
        4.  Al final del todo, incluye la siguiente firma:
            
            ---
            *Elaborado por:*
            **Joseph Javier Sánchez Acuña**
            *CEO - SAVA SOFTWARE FOR ENGINEERING*

        **IMPORTANTE:** Tu única salida debe ser el texto del reporte en formato Markdown. No incluyas nada más.
        """

        try:
            response = self.model.generate_content(prompt)
            if response and response.text:
                return response.text
            else:
                logger.error("La IA no devolvió una respuesta de texto válida.")
                return "### Error\nLa IA no devolvió una respuesta válida."

        except Exception as e:
            logger.error(f"Error crítico durante la generación de reporte con Gemini: {e}")
            error_message = str(e)
            if "API key not valid" in error_message:
                return "### Error\nLa API Key de Gemini no es válida. Verifícala en los secretos."
            return f"### Error\nNo se pudo generar el reporte: {error_message}"


    def analyze_image(self, image_pil: Image, description: str = ""):
        """
        Analiza una imagen y devuelve una respuesta JSON estructurada y limpia.
        """
        if not self.model:
            return json.dumps({"error": "El modelo de Gemini no está inicializado."})

        try:
            prompt = f"""
            Analiza esta imagen de un objeto de inventario.
            Descripción adicional del sistema de detección: "{description}"

            Actúa como un experto catalogador. Tu única salida debe ser un objeto JSON válido con estas claves:
            - "elemento_identificado": (string) El nombre específico y descriptivo del objeto.
            - "cantidad_aproximada": (integer) El número de unidades que ves. Si es solo uno, pon 1.
            - "estado_condicion": (string) La condición aparente (ej: "Nuevo en empaque", "Usado", "Componente").
            - "caracteristicas_distintivas": (string) Lista separada por comas de características visuales clave.
            - "posible_categoria_de_inventario": (string) La categoría más lógica (ej: "Electrónicos", "Ferretería").
            - "marca_modelo_sugerido": (string) Si es visible, marca y/o modelo (ej: "Sony XM4"). Si no, "No visible".

            IMPORTANTE: Responde solo con el objeto JSON válido, sin texto adicional ni marcas ```json.
            """
            
            generation_config = {
                "response_mime_type": "application/json",
            }
            response = self.model.generate_content([prompt, image_pil], generation_config=generation_config)

            if response and response.text:
                report_data = json.loads(response.text)
                if "elemento_identificado" in report_data:
                    return response.text
                else:
                    logger.warning("El JSON de análisis de imagen está incompleto.")
                    return json.dumps({"error": "JSON de imagen incompleto.", "raw_response": response.text})
            else:
                return json.dumps({"error": "Respuesta de imagen inválida."})

        except json.JSONDecodeError:
            raw_response = response.text if 'response' in locals() and hasattr(response, 'text') else "No response text available."
            logger.error("La IA no devolvió un formato JSON válido para la imagen.")
            return json.dumps({"error": "JSON de imagen mal formado.", "raw_response": raw_response})
        except Exception as e:
            logger.error(f"Error crítico durante el análisis de imagen con Gemini: {e}")
            return json.dumps({"error": f"No se pudo contactar al servicio de IA para imagen: {str(e)}"})

