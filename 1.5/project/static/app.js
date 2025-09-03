// Завантажити список товарів
async function fetchProducts() {
    try {
        const res = await fetch('/api/products');
        const products = await res.json();

        const list = document.getElementById('product-list');
        list.innerHTML = '';

        products.forEach(product => {
            const li = document.createElement('li');
            li.textContent = `${product.product_name} — ${product.quantity} шт.`;

            const deleteBtn = document.createElement('button');
            deleteBtn.textContent = 'Видалити';
            deleteBtn.onclick = () => deleteProduct(product.product_id);

            li.appendChild(deleteBtn);
            list.appendChild(li);
        });
    } catch (error) {
        console.error('Помилка при завантаженні товарів:', error);
    }
}

// Додати товар
document.getElementById('add-product-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const nameInput = document.getElementById('product_name');
    const quantityInput = document.getElementById('quantity');

    const product = {
        product_name: nameInput.value.trim(),
        quantity: parseInt(quantityInput.value)
    };

    if (!product.product_name || isNaN(product.quantity)) {
        alert('Будь ласка, введіть коректні дані.');
        return;
    }

    try {
        const res = await fetch('/api/products', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(product)
        });

        if (res.ok) {
            nameInput.value = '';
            quantityInput.value = '';
            fetchProducts();
        } else {
            const error = await res.json();
            alert(error.error || 'Помилка при додаванні товару.');
        }
    } catch (error) {
        console.error('Помилка:', error);
    }
});

// Видалити товар
async function deleteProduct(productId) {
    if (!confirm('Ви впевнені, що хочете видалити цей товар?')) return;

    try {
        const res = await fetch(`/api/products/${productId}`, {
            method: 'DELETE'
        });

        if (res.ok) {
            fetchProducts();
        } else {
            alert('Помилка при видаленні товару.');
        }
    } catch (error) {
        console.error('Помилка при видаленні:', error);
    }
}

// Початкове завантаження
fetchProducts();
