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
        self.api_key = st.secrets.get('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY no encontrada en los secrets de Streamlit")

        genai.configure(api_key=self.api_key)
        self.model = self._get_available_model()

    def _get_available_model(self):
        model_candidates = [
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ]
        for model_name in model_candidates:
            try:
                model = genai.GenerativeModel(model_name)
                logger.info(f"✅ Modelo '{model_name}' listo.")
                return model
            except Exception:
                continue
        raise Exception("No se pudo inicializar ningún modelo de Gemini.")

    def generate_daily_report(self, orders: list):
        """
        Genera un reporte diario analizando ventas en efectivo vs fiado.
        """
        if not self.model:
            return "### Error\nEl modelo de IA no está activo."
        if not orders:
            return "### Reporte Diario\nNo hubo movimientos registrados hoy."

        # Cálculos Financieros
        total_sales_value = 0.0
        cash_revenue = 0.0
        credit_revenue = 0.0 # Fiado
        total_transactions = len(orders)
        
        fiado_details = []

        item_sales = {}
        
        for order in orders:
            price = order.get('price', 0)
            if not isinstance(price, (int, float)): price = 0
            
            total_sales_value += price
            
            # Clasificación por tipo de pago
            payment_method = order.get('payment_method', 'efectivo')
            if payment_method == 'fiado':
                credit_revenue += price
                customer = order.get('customer_name', 'Desconocido')
                fiado_details.append(f"- {customer}: ${price:,.2f}")
            else:
                cash_revenue += price

            # Conteo de items
            for item in order.get('ingredients', []):
                item_name = item.get('name', 'N/A')
                quantity = item.get('quantity', 0)
                if isinstance(quantity, (int, float)) and quantity > 0:
                    item_sales[item_name] = item_sales.get(item_name, 0) + quantity

        top_selling_items = sorted(item_sales.items(), key=lambda x: x[1], reverse=True)[:10]

        # Prompt Estructurado
        prompt = f"""
        **Rol:** Eres el Consultor Financiero Senior de 'Rapi Tienda Acuarela'.
        
        **Objetivo:** Generar un reporte diario de ventas crítico y estratégico.

        **Datos Financieros del Día:**
        * **Ventas Totales (Bruto):** ${total_sales_value:,.2f}
        * **Dinero en Caja (Efectivo):** ${cash_revenue:,.2f}
        * **Cuentas por Cobrar (Fiado):** ${credit_revenue:,.2f}
        * **Total Transacciones:** {total_transactions}
        
        **Top Productos Vendidos:**
        {chr(10).join([f"    * {name}: {qty}" for name, qty in top_selling_items])}

        **Detalle de Créditos (Fiado):**
        {chr(10).join(fiado_details) if fiado_details else "    * No hubo ventas fiadas hoy."}

        **Instrucciones de Generación:**
        Analiza estos datos y escribe un reporte en Markdown que incluya:
        
        1.  **Resumen de Caja:** Compara lo que entró en efectivo vs lo que se fío. ¿Es saludable el nivel de crédito hoy?
        2.  **Análisis de Producto:** Comenta brevemente sobre los productos estrella.
        3.  **Alertas de Cobro:** Si hay fiados, menciona la importancia de gestionar esos cobros.
        4.  **Recomendación Estratégica:** Una acción concreta para mejorar mañana.
        
        **Firma Obligatoria:**
        ---
        *Reporte generado por:*
        **SAVA AI INTELLIGENCE**
        *Rapi Tienda Acuarela System*
        """

        try:
            response = self.model.generate_content(prompt)
            if response and response.text:
                return response.text
            return "### Error\nLa IA no generó respuesta."
        except Exception as e:
            return f"### Error\nFallo en análisis IA: {str(e)}"

    def analyze_image(self, image_pil: Image, description: str = ""):
        # (Se mantiene igual que la versión anterior, solo retornando el JSON)
        if not self.model: return json.dumps({"error": "Modelo inactivo."})
        try:
            prompt = f"""
            Analiza esta imagen de inventario. Contexto: "{description}"
            Salida JSON estricta con claves: elemento_identificado, cantidad_aproximada, estado_condicion, caracteristicas_distintivas, posible_categoria_de_inventario, marca_modelo_sugerido.
            """
            generation_config = {"response_mime_type": "application/json"}
            response = self.model.generate_content([prompt, image_pil], generation_config=generation_config)
            if response and response.text: return response.text
            return json.dumps({"error": "Respuesta vacía."})
        except Exception as e:
            return json.dumps({"error": str(e)})
