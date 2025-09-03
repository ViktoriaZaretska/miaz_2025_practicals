from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
import psycopg2

# Завантаження змінних з .env
load_dotenv()

# Ініціалізація Flask-додатку
app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Отримання параметрів підключення до БД з .env
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Функція для підключення до БД
def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

# Головна сторінка (UI)
@app.route('/')
def index():
    return render_template('index.html')

# API: Отримати всі товари
@app.route('/api/products', methods=['GET'])
def get_products():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT product_id, product_name, quantity FROM products ORDER BY product_id;")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    products = [{"product_id": r[0], "product_name": r[1], "quantity": r[2]} for r in rows]
    return jsonify(products)

# API: Додати новий товар
@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.json
    name = data.get("product_name")
    quantity = data.get("quantity")

    if not name or quantity is None:
        return jsonify({"error": "Invalid data"}), 400

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO products (product_name, quantity) VALUES (%s, %s) RETURNING product_id;",
                (name, quantity))
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"product_id": new_id, "product_name": name, "quantity": quantity}), 201

# API: Видалити товар за ID
@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE product_id = %s RETURNING product_id;", (product_id,))
    deleted = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if deleted:
        return jsonify({"message": "Product deleted"}), 200
    else:
        return jsonify({"error": "Product not found"}), 404

# Запуск сервера
if __name__ == '__main__':
    app.run(debug=True)
