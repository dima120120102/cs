// Инициализация данных пользователя
let balance = 0;
let salesHistory = [];
let inventory = [];

let balanceAmount, depositForm, depositAmountInput, salesList, inventoryList, inventoryFilter, priceSort, sellAllBtn, tradeUrlInput;

// Базовый URL бэкенда
const BACKEND_URL = 'https://cs2cases.onrender.com';

// Получаем SteamID из localStorage
const steamId = localStorage.getItem('steamid');

// Загружаем Trade URL из localStorage
let tradeUrl = localStorage.getItem('tradeUrl') || '';

// DonationAlerts ссылка для оплаты
const DA_PAYMENT_LINK = 'https://www.donationalerts.com/r/cs2cases'; // Замените на вашу ссылку

// Подключение к SocketIO
const socket = io(BACKEND_URL);
socket.on('connect', () => {
    console.log('Подключено к серверу SocketIO');
});
socket.on('balance_update', (data) => {
    if (data.steam_id === steamId) {
        balance = data.balance;
        updateBalance();
        showBalanceChange(data.balance - balance, 'add');
        alert('Баланс пополнен через DonationAlerts!');
    }
});

// Сохраняем Trade URL
function saveTradeUrl() {
    if (!tradeUrlInput) return;
    tradeUrl = tradeUrlInput.value.trim();
    if (!tradeUrl) {
        alert('Пожалуйста, введите ваш Steam Trade URL!');
        return;
    }
    localStorage.setItem('tradeUrl', tradeUrl);
    alert('Trade URL сохранен!');
}

// Загружаем данные пользователя с сервера
async function loadUserData() {
    if (!steamId) {
        console.error('SteamID не найден');
        alert('Пожалуйста, войдите через Steam');
        window.location.href = 'index.html';
        return false;
    }

    try {
        const response = await fetch(`${BACKEND_URL}/api/user?steam_id=${steamId}`);
        if (response.ok) {
            const data = await response.json();
            balance = data.balance || 0;
            inventory = data.inventory || [];
            salesHistory = data.sales_history || [];
            return true;
        } else {
            throw new Error(`Ошибка: ${response.status}`);
        }
    } catch (error) {
        console.error('Ошибка загрузки:', error);
        alert('Ошибка загрузки данных');
        return false;
    }
}

// Сохраняем данные пользователя на сервере
async function saveUserData() {
    if (!steamId) return;

    try {
        const response = await fetch(`${BACKEND_URL}/api/user/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                steam_id: steamId,
                balance: balance,
                inventory: inventory,
                sales_history: salesHistory
            })
        });
        if (!response.ok) throw new Error(`Ошибка: ${response.status}`);
    } catch (error) {
        console.error('Ошибка сохранения:', error);
        alert('Ошибка сохранения данных');
    }
}

// Отправка предмета в Steam
async function sendToSteam(item) {
    if (!tradeUrl) {
        alert('Пожалуйста, введите ваш Steam Trade URL!');
        return;
    }

    try {
        const response = await fetch(`${BACKEND_URL}/api/send-to-steam`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                steam_id: steamId,
                trade_url: tradeUrl,
                item: item
            })
        });

        if (response.ok) {
            alert('Предмет отправлен в Steam!');
            inventory = inventory.filter(i => i !== item);
            await saveUserData();
            displayInventory();
        } else {
            throw new Error(`Ошибка: ${response.status}`);
        }
    } catch (error) {
        console.error('Ошибка отправки:', error);
        alert('Ошибка при отправке в Steam');
    }
}

// Обновляем отображение баланса
function updateBalance() {
    if (!balanceAmount) return;
    balanceAmount.textContent = balance.toFixed(2);
}

// Показать анимацию изменения баланса
function showBalanceChange(amount, type) {
    if (!balanceAmount) return;
    const changeElement = document.createElement('div');
    changeElement.className = `balance-change ${type}`;
    changeElement.textContent = `${type === 'add' ? '+' : '-'}${Math.abs(amount).toFixed(2)} ₽`;
    balanceAmount.parentElement.appendChild(changeElement);
    setTimeout(() => changeElement.remove(), 2000);
}

// Показать форму пополнения
function showDepositForm() {
    if (!depositForm) return;
    depositForm.style.display = 'block';
}

// Скрыть форму пополнения
function hideDepositForm() {
    if (!depositForm || !depositAmountInput) return;
    depositForm.style.display = 'none';
    depositAmountInput.value = '';
}

// Пополнить баланс через DonationAlerts
function deposit() {
    const amount = parseInt(depositAmountInput.value);
    if (isNaN(amount) || amount <= 0) {
        alert('Введите корректную сумму!');
        return;
    }
    alert(`Перейдите по ссылке и отправьте ${amount} ₽ с вашим SteamID (${steamId}) в имени доната.`);
    window.open(`${DA_PAYMENT_LINK}?amount=${amount}&steamid=${steamId}`, '_blank');
    hideDepositForm();
}

// Продать предмет из инвентаря
async function sellFromInventory(item) {
    const price = item.price;
    balance += price;
    showBalanceChange(price, 'add');
    updateBalance();

    salesHistory.push(item);
    inventory = inventory.filter(i => i !== item);

    displayInventory();
    displaySalesHistory();
    updateSellAllButton();
    await saveUserData();
}

// Продать все предметы
async function sellAllItems() {
    if (inventory.length === 0) {
        alert('В инвентаре нет предметов!');
        return;
    }

    let totalAmount = inventory.reduce((sum, item) => sum + item.price, 0);
    if (!confirm(`Продать все ${inventory.length} предметов за ${totalAmount} ₽?`)) return;

    salesHistory = [...salesHistory, ...inventory];
    balance += totalAmount;
    showBalanceChange(totalAmount, 'add');
    updateBalance();

    inventory = [];
    displayInventory();
    displaySalesHistory();
    updateSellAllButton();
    await saveUserData();
}

// Обновляем кнопку "Продать все"
function updateSellAllButton() {
    if (!sellAllBtn) return;
    sellAllBtn.disabled = inventory.length === 0;
    sellAllBtn.style.opacity = inventory.length === 0 ? '0.7' : '1';
}

// Отобразить историю продаж
function displaySalesHistory() {
    if (!salesList) return;
    salesList.innerHTML = '';
    salesHistory.forEach((item, index) => {
        const itemCard = document.createElement('div');
        itemCard.className = 'item-card';
        itemCard.innerHTML = `
            <img src="${item.image}" alt="${item.name}">
            <div>${item.name}</div>
            <div class="price">${item.price} ₽</div>
        `;
        itemCard.style.animationDelay = `${index * 0.1}s`;
        salesList.appendChild(itemCard);
    });
}

// Отобразить инвентарь
function displayInventory(filter = '', sort = 'default') {
    if (!inventoryList) return;
    inventoryList.innerHTML = '';

    let filteredInventory = inventory.filter(item =>
        item.name.toLowerCase().includes(filter.toLowerCase())
    );

    if (sort === 'cheap-first') {
        filteredInventory.sort((a, b) => a.price - b.price);
    } else if (sort === 'expensive-first') {
        filteredInventory.sort((a, b) => b.price - a.price);
    }

    filteredInventory.forEach((item, index) => {
        const itemCard = document.createElement('div');
        itemCard.className = 'item-card';
        itemCard.innerHTML = `
            <img src="${item.image}" alt="${item.name}">
            <div>${item.name}</div>
            <div class="price">${item.price} ₽</div>
            <button onclick="sellFromInventory(${JSON.stringify(item).replace(/"/g, '"')})">Продать</button>
            <button onclick="sendToSteam(${JSON.stringify(item).replace(/"/g, '"')})" style="background-color: #2196F3; margin-top: 5px;">Отправить в Steam</button>
        `;
        itemCard.style.animationDelay = `${index * 0.1}s`;
        inventoryList.appendChild(itemCard);
    });

    updateSellAllButton();
}

// Фильтрация и сортировка инвентаря
function filterInventory() {
    if (!inventoryFilter || !priceSort) return;
    const filterValue = inventoryFilter.value;
    const sortValue = priceSort.value;
    displayInventory(filterValue, sortValue);
}

// Переключение темы
function toggleTheme() {
    const body = document.body;
    const themeButton = document.querySelector('.theme-toggle');
    if (!themeButton) return;
    body.classList.toggle('dark-mode');
    const isDarkMode = body.classList.contains('dark-mode');
    localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
    themeButton.textContent = isDarkMode ? 'Светлый режим' : 'Темный режим';
}

// При загрузке страницы
document.addEventListener('DOMContentLoaded', async () => {
    balanceAmount = document.getElementById('balanceAmount');
    depositForm = document.getElementById('depositForm');
    depositAmountInput = document.getElementById('depositAmount');
    salesList = document.getElementById('salesList');
    inventoryList = document.getElementById('inventoryList');
    inventoryFilter = document.getElementById('inventoryFilter');
    priceSort = document.getElementById('priceSort');
    sellAllBtn = document.getElementById('sellAllBtn');
    tradeUrlInput = document.getElementById('tradeUrl');

    const requiredElements = { balanceAmount, depositForm, depositAmountInput, salesList, inventoryList, inventoryFilter, priceSort, sellAllBtn, tradeUrlInput };
    for (const [key, value] of Object.entries(requiredElements)) {
        if (!value) {
            console.error(`Элемент ${key} не найден`);
            alert(`Ошибка: элемент ${key} не найден`);
            return;
        }
    }

    tradeUrlInput.value = tradeUrl;

    const savedTheme = localStorage.getItem('theme');
    const body = document.body;
    const themeButton = document.querySelector('.theme-toggle');
    if (themeButton) {
        if (savedTheme === 'dark') {
            body.classList.add('dark-mode');
            themeButton.textContent = 'Светлый режим';
        } else {
            body.classList.remove('dark-mode');
            themeButton.textContent = 'Темный режим';
        }
    }

    const userDataLoaded = await loadUserData();
    if (!userDataLoaded) return;

    if (sellAllBtn) sellAllBtn.addEventListener('click', sellAllItems);

    updateBalance();
    displaySalesHistory();
    displayInventory();
});
