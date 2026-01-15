import firebase_admin
from firebase_admin import credentials, firestore
import json
import base64
import logging
from datetime import datetime, timezone
import streamlit as st
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Transaccional functions defined in the global scope ---
@firestore.transactional
def _complete_order_atomic(transaction, db, order_id):
    order_ref = db.collection('orders').document(order_id)
    order_snapshot = order_ref.get(transaction=transaction)
    if not order_snapshot.exists:
        raise ValueError("El pedido no existe.")
    order_data = order_snapshot.to_dict()
    items_to_update = []
    for ing in order_data.get('ingredients', []):
        item_ref = db.collection('inventory').document(ing['id'])
        item_snapshot = item_ref.get(transaction=transaction)
        if not item_snapshot.exists:
            raise ValueError(f"Ingrediente '{ing.get('name')}' no encontrado.")
        item_data = item_snapshot.to_dict()
        current_quantity = item_data.get('quantity', 0)
        if current_quantity < ing['quantity']:
            raise ValueError(f"Stock insuficiente para '{ing.get('name')}'.")
        new_quantity = current_quantity - ing['quantity']
        items_to_update.append({'ref': item_ref, 'new_quantity': new_quantity, 'item_data': item_data, 'ing_quantity': ing['quantity']})
    low_stock_alerts = []
    for item_update in items_to_update:
        transaction.update(item_update['ref'], {'quantity': item_update['new_quantity']})
        history_ref = item_update['ref'].collection('history').document()
        history_data = {"timestamp": datetime.now(timezone.utc), "type": "Venta (Pedido)", "quantity_change": -item_update['ing_quantity'], "details": f"Pedido ID: {order_id}"}
        transaction.set(history_ref, history_data)
        min_stock_alert = item_update['item_data'].get('min_stock_alert')
        if min_stock_alert and 0 < item_update['new_quantity'] <= min_stock_alert:
            low_stock_alerts.append(f"'{item_update['item_data'].get('name')}' ha alcanzado el umbral de stock mínimo ({item_update['new_quantity']}/{min_stock_alert}).")
    transaction.update(order_ref, {'status': 'completed', 'completed_at': datetime.now(timezone.utc)})
    return True, f"Pedido '{order_data.get('title')}' completado.", low_stock_alerts

@firestore.transactional
def _process_direct_sale_atomic(transaction, db, items_sold, sale_id, payment_data=None):
    # --- MODIFICACIÓN: Soporte para registro de venta y fiado ---
    items_to_update = []
    total_sale_amount = 0.0
    enriched_ingredients = []

    for sold_item in items_sold:
        item_ref = db.collection('inventory').document(sold_item['id'])
        item_snapshot = item_ref.get(transaction=transaction)
        if not item_snapshot.exists:
            raise ValueError(f"Producto '{sold_item.get('name')}' no encontrado.")
        item_data = item_snapshot.to_dict()
        current_quantity = item_data.get('quantity', 0)
        if current_quantity < sold_item['quantity']:
            raise ValueError(f"Stock insuficiente para '{sold_item.get('name')}'.")
        
        # Calcular precios para el registro de la orden
        sale_price = item_data.get('sale_price', 0.0)
        item_total = sale_price * sold_item['quantity']
        total_sale_amount += item_total
        
        new_quantity = current_quantity - sold_item['quantity']
        items_to_update.append({'ref': item_ref, 'new_quantity': new_quantity, 'item_data': item_data, 'sold_quantity': sold_item['quantity']})
        
        enriched_ingredients.append({
            'id': sold_item['id'],
            'name': item_data.get('name'),
            'quantity': sold_item['quantity'],
            'sale_price': sale_price
        })

    low_stock_alerts = []
    for item_update in items_to_update:
        transaction.update(item_update['ref'], {'quantity': item_update['new_quantity']})
        history_ref = item_update['ref'].collection('history').document()
        history_data = {"timestamp": datetime.now(timezone.utc), "type": "Venta Directa", "quantity_change": -item_update['sold_quantity'], "details": f"ID de Venta: {sale_id}"}
        transaction.set(history_ref, history_data)
        min_stock_alert = item_update['item_data'].get('min_stock_alert')
        if min_stock_alert and 0 < item_update['new_quantity'] <= min_stock_alert:
            low_stock_alerts.append(f"'{item_update['item_data'].get('name')}' ha alcanzado el umbral de stock mínimo ({item_update['new_quantity']}/{min_stock_alert}).")
    
    # --- NUEVO: Crear registro en 'orders' para reporte diario ---
    if payment_data is None:
        payment_data = {'method': 'efectivo', 'customer': 'Cliente General'}

    order_ref = db.collection('orders').document(sale_id)
    order_data = {
        'title': f"Venta Directa {sale_id.split('-')[-1]}",
        'price': total_sale_amount,
        'ingredients': enriched_ingredients,
        'status': 'completed',
        'timestamp': datetime.now(timezone.utc),
        'completed_at': datetime.now(timezone.utc),
        'payment_method': payment_data.get('method', 'efectivo'),
        'customer_name': payment_data.get('customer', 'Cliente General'),
        'is_direct_sale': True
    }
    transaction.set(order_ref, order_data)
    
    return True, f"Venta '{sale_id}' procesada y stock actualizado.", low_stock_alerts

def firestore_retry(func):
    def wrapper(*args, **kwargs):
        max_retries = 3
        delay = 1
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying...")
                time.sleep(delay)
                delay *= 2
        logger.error(f"All retries failed for {func.__name__}.")
        raise
    return wrapper

class FirebaseManager:
    _app_initialized = False

    def __init__(self):
        self.db = None
        self._initialize_firebase()
    
    def _initialize_firebase(self):
        if not self._app_initialized:
            try:
                creds_base64 = st.secrets.get('FIREBASE_SERVICE_ACCOUNT_BASE64')
                if not creds_base64:
                    raise ValueError("Secret 'FIREBASE_SERVICE_ACCOUNT_BASE64' not found.")
                creds_json_str = base64.b64decode(creds_base64).decode('utf-8')
                creds_dict = json.loads(creds_json_str)
                cred = credentials.Certificate(creds_dict)
                if not firebase_admin._apps:
                    firebase_admin.initialize_app(cred)
                    logger.info("Firebase App initialized successfully.")
                self.__class__._app_initialized = True
            except Exception as e:
                logger.error(f"Fatal error initializing Firebase: {e}")
                st.error(f"Could not connect to the database. Please check secrets and configuration. Error: {e}")
                raise
        self.db = firestore.client()

    @firestore_retry
    def save_inventory_item(self, data, custom_id, is_new=False, details=None):
        doc_ref = self.db.collection('inventory').document(custom_id)
        doc_ref.set(data, merge=True)
        history_type = "Stock Inicial" if is_new else "Ajuste Manual"
        details = details or ("Item created in the system." if is_new else "Item updated manually.")
        history_data = {
            "timestamp": datetime.now(timezone.utc), "type": history_type,
            "quantity_change": data.get('quantity'), "details": details
        }
        doc_ref.collection('history').add(history_data)
        logger.info(f"Inventory item saved/updated: {custom_id}")
    
    # --- FUNCIÓN DE ELIMINACIÓN OPTIMIZADA (Limpia historial) ---
    def delete_inventory_item(self, doc_id):
        try:
            doc_ref = self.db.collection('inventory').document(doc_id)
            
            # 1. Eliminar subcolección 'history' (Limpieza profunda)
            # Nota: Esto se hace en lotes pequeños para evitar problemas de memoria
            self._delete_collection_batch(doc_ref.collection('history'), batch_size=20)
            
            # 2. Eliminar el documento principal
            doc_ref.delete()
            logger.info(f"Inventory item {doc_id} and history deleted.")
        except Exception as e:
            logger.error(f"Error deleting inventory item {doc_id}: {e}")
            raise e

    def _delete_collection_batch(self, coll_ref, batch_size):
        """Helper para borrar subcolecciones"""
        docs = list(coll_ref.limit(batch_size).stream())
        deleted = 0
        if len(docs) > 0:
            batch = self.db.batch()
            for doc in docs:
                batch.delete(doc.reference)
            batch.commit()
            deleted = len(docs)
            
        if deleted >= batch_size:
            return self._delete_collection_batch(coll_ref, batch_size)

    @firestore_retry
    def get_inventory_item_details(self, doc_id):
        doc = self.db.collection('inventory').document(doc_id).get()
        if doc.exists:
            item = doc.to_dict(); item['id'] = doc.id
            return item
        return None

    @firestore_retry
    def get_all_inventory_items(self):
        docs = self.db.collection('inventory').stream()
        items = [dict(item.to_dict(), **{'id': item.id}) for item in docs]
        return sorted(items, key=lambda x: x.get('name', '').lower())

    @firestore_retry
    def create_order(self, order_data):
        enriched_ingredients = []
        for ing in order_data['ingredients']:
            item_details = self.get_inventory_item_details(ing['id'])
            if item_details:
                ing['purchase_price'] = item_details.get('purchase_price', 0)
                ing['sale_price'] = item_details.get('sale_price', 0)
            enriched_ingredients.append(ing)
        order_data['ingredients'] = enriched_ingredients
        self.db.collection('orders').add(order_data)
        logger.info("New order created with enriched price data.")

    @firestore_retry
    def get_order_count(self):
        return self.db.collection('orders').count().get()[0][0].value

    @firestore_retry
    def get_orders(self, status=None):
        query = self.db.collection('orders')
        if status:
            query = query.where(filter=firestore.FieldFilter('status', '==', status))
        docs = query.stream()
        orders = []
        for doc in docs:
            order = doc.to_dict(); order['id'] = doc.id
            ts = order.get('timestamp')
            if isinstance(ts, datetime):
                order['timestamp_obj'] = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
            else:
                order['timestamp_obj'] = datetime.min.replace(tzinfo=timezone.utc)
            orders.append(order)
        return sorted(orders, key=lambda x: x['timestamp_obj'], reverse=True)
    
    @firestore_retry
    def get_orders_in_date_range(self, start_date, end_date):
        """Fetches completed orders within a specific date range."""
        query = self.db.collection('orders').where(
            filter=firestore.FieldFilter('status', '==', 'completed')
        ).where(
            filter=firestore.FieldFilter('completed_at', '>=', start_date)
        ).where(
            filter=firestore.FieldFilter('completed_at', '<', end_date)
        )
        docs = query.stream()
        orders = []
        for doc in docs:
            order = doc.to_dict(); order['id'] = doc.id
            orders.append(order)
        return orders

    @firestore_retry
    def cancel_order(self, order_id):
        self.db.collection('orders').document(order_id).delete()
        logger.info(f"Order {order_id} cancelled.")

    def complete_order(self, order_id):
        try:
            transaction = self.db.transaction()
            return _complete_order_atomic(transaction, self.db, order_id)
        except Exception as e:
            logger.error(f"Transaction failed for order {order_id}: {e}")
            return False, f"Transaction error: {str(e)}", []
            
    def process_direct_sale(self, items_sold, sale_id, payment_data=None):
        try:
            transaction = self.db.transaction()
            # --- MODIFICACIÓN: Pasamos payment_data ---
            return _process_direct_sale_atomic(transaction, self.db, items_sold, sale_id, payment_data)
        except Exception as e:
            logger.error(f"Transaction failed for direct sale {sale_id}: {e}")
            return False, f"Transaction error: {str(e)}", []

    @firestore_retry
    def add_supplier(self, supplier_data):
        self.db.collection('suppliers').add(supplier_data)
        logger.info("New supplier added.")

    @firestore_retry
    def get_all_suppliers(self):
        docs = self.db.collection('suppliers').stream()
        return sorted([dict(s.to_dict(), **{'id': s.id}) for s in docs], key=lambda x: x.get('name', '').lower())
