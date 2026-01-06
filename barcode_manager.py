import logging
from firebase_utils import FirebaseManager

# Configuración del logger para este módulo
logger = logging.getLogger(__name__)

class BarcodeManager:
    """
    Gestiona toda la lógica de negocio relacionada con el escaneo de códigos de barras,
    actuando como intermediario entre la interfaz de usuario y la base de datos.
    """
    def __init__(self, firebase_manager: FirebaseManager):
        """
        Inicializa el gestor con una instancia del manejador de Firebase.

        Args:
            firebase_manager (FirebaseManager): Instancia para interactuar con Firestore.
        """
        self.db = firebase_manager

    def handle_inventory_scan(self, barcode: str):
        """
        Procesa un código de barras escaneado en el modo de gestión de inventario.
        Verifica si el producto existe y devuelve su estado.

        Args:
            barcode (str): El código de barras escaneado.

        Returns:
            dict: Un diccionario con el estado y los datos pertinentes.
        """
        if not barcode:
            return {'status': 'error', 'message': 'El código de barras no puede estar vacío.'}
        
        try:
            item = self.db.get_inventory_item_details(barcode)
            if item:
                logger.info(f"Producto encontrado para el código '{barcode}': {item['name']}")
                return {'status': 'found', 'item': item}
            else:
                logger.info(f"Producto no encontrado para el código '{barcode}'.")
                return {'status': 'not_found', 'barcode': barcode}
        except Exception as e:
            logger.error(f"Error al procesar el escaneo de inventario para '{barcode}': {e}")
            return {'status': 'error', 'message': str(e)}

    def add_item_to_sale(self, barcode: str, current_sale_items: list):
        """
        Añade un artículo a una venta rápida (Punto de Venta) o incrementa su cantidad.

        Args:
            barcode (str): El código de barras del producto.
            current_sale_items (list): La lista de artículos en la venta actual.

        Returns:
            tuple: (list, dict) La lista de venta actualizada y un mensaje de estado.
        """
        if not barcode:
            return current_sale_items, {'status': 'error', 'message': 'El código de barras no puede estar vacío.'}

        try:
            item_data = self.db.get_inventory_item_details(barcode)
            if not item_data:
                return current_sale_items, {'status': 'error', 'message': f"Producto con código '{barcode}' no encontrado."}

            if item_data.get('quantity', 0) <= 0:
                 return current_sale_items, {'status': 'warning', 'message': f"¡Stock agotado para '{item_data['name']}'!"}

            existing_item = next((item for item in current_sale_items if item['id'] == barcode), None)
            
            if existing_item:
                if item_data.get('quantity', 0) > existing_item['quantity']:
                    existing_item['quantity'] += 1
                    msg = {'status': 'success', 'message': f"'{item_data['name']}' (+1). Total: {existing_item['quantity']}"}
                else:
                    msg = {'status': 'warning', 'message': f"No hay más stock disponible para '{item_data['name']}'."}
            else:
                new_item = {
                    'id': item_data['id'], 'name': item_data['name'],
                    'sale_price': item_data.get('sale_price', 0),
                    'purchase_price': item_data.get('purchase_price', 0),
                    'quantity': 1
                }
                current_sale_items.append(new_item)
                msg = {'status': 'success', 'message': f"'{item_data['name']}' añadido a la venta."}
            
            return current_sale_items, msg

        except Exception as e:
            logger.error(f"Error al añadir artículo a la venta '{barcode}': {e}")
            return current_sale_items, {'status': 'error', 'message': str(e)}
            
    # --- NUEVA FUNCIÓN DE APOYO PARA PEDIDOS ---
    def add_item_to_order_list(self, item_to_add: dict, current_order_items: list, quantity_to_add: int):
        """
        Añade un artículo a la lista de un pedido o incrementa su cantidad si ya existe.

        Args:
            item_to_add (dict): Los datos del producto a añadir.
            current_order_items (list): La lista actual de artículos del pedido.
            quantity_to_add (int): La cantidad de unidades a añadir.

        Returns:
            tuple: (list, dict) La lista de pedido actualizada y un mensaje de estado.
        """
        try:
            if not item_to_add:
                 return current_order_items, {'status': 'error', 'message': 'Producto no válido.'}

            # Validar que haya stock suficiente
            if item_to_add.get('quantity', 0) < quantity_to_add:
                return current_order_items, {'status': 'warning', 'message': f"Stock insuficiente para '{item_to_add['name']}'. Disponible: {item_to_add.get('quantity', 0)}"}

            existing_item = next((item for item in current_order_items if item['id'] == item_to_add['id']), None)

            if existing_item:
                # Si ya existe, suma la nueva cantidad
                new_total_quantity = existing_item['order_quantity'] + quantity_to_add
                if item_to_add.get('quantity', 0) < new_total_quantity:
                    return current_order_items, {'status': 'warning', 'message': f"No puedes añadir {quantity_to_add} más. Stock total: {item_to_add.get('quantity', 0)}, ya en pedido: {existing_item['order_quantity']}"}
                
                existing_item['order_quantity'] = new_total_quantity
                msg = {'status': 'success', 'message': f"Cantidad de '{item_to_add['name']}' actualizada a {new_total_quantity}."}
            else:
                # Si es nuevo, lo añade a la lista
                new_order_item = item_to_add.copy()
                new_order_item['order_quantity'] = quantity_to_add
                current_order_items.append(new_order_item)
                msg = {'status': 'success', 'message': f"'{item_to_add['name']}' añadido al pedido."}
            
            return current_order_items, msg
        except Exception as e:
            logger.error(f"Error al añadir artículo al pedido: {e}")
            return current_order_items, {'status': 'error', 'message': str(e)}

