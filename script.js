document.addEventListener('DOMContentLoaded', () => {
    // Инициализация Web App
    Telegram.WebApp.ready();
    Telegram.WebApp.expand(); // Разворачиваем Web App на весь экран

    const userStarsElement = document.getElementById('user-stars');
    const spinButton = document.getElementById('spin-button');
    const spinCostElement = document.getElementById('spin-cost');
    const wheelElement = document.getElementById('wheel');
    const winnableItemsGrid = document.getElementById('winnable-items-grid');
    const demoModeToggle = document.getElementById('demo-mode-toggle');

    let currentUserStars = 0;
    let currentCaseData = {}; // Здесь будут храниться данные о текущем выбранном кейсе

    // Функция для получения данных от бота (например, при инициализации или по запросу)
    function getUserData() {
        // В реальном приложении бот может передавать initial_data при открытии Web App,
        // или Web App может запросить данные.
        // Сейчас просто эмулируем получение данных.
        // Более сложный вариант: Telegram.WebApp.sendData(JSON.stringify({action: 'request_user_data'}));
        // И бот отвечает через Telegram.WebApp.onEvent('mainButtonClicked', ...)
        
        // Пример получения звезд из URL (если бот их туда положит)
        const urlParams = new URLSearchParams(window.location.search);
        const stars = parseInt(urlParams.get('stars')) || 0;
        const caseId = urlParams.get('case'); // Получаем ID кейса из URL

        currentUserStars = stars;
        userStarsElement.textContent = currentUserStars;

        if (caseId) {
            // В идеале, бот должен передавать ВСЕ данные о кейсе (items, weights, name и т.д.)
            // Сейчас для примера возьмем данные из `bot.py` и передадим их сюда
            // через URL-параметры (это НЕ лучший способ для больших данных, но для старта пойдет).
            // Лучше: Telegram.WebApp.initDataUnsafe или запрос к боту через sendData/onEvent
            
            try {
                const itemsJson = urlParams.get('items');
                if (itemsJson) {
                    currentCaseData = {
                        id: caseId,
                        items: JSON.parse(itemsJson)
                    };
                    renderWinnableItems(currentCaseData.items);
                    renderWheelItems(currentCaseData.items); // Рендерим элементы колеса
                    // Обновляем стоимость кручения
                    const caseCost = urlParams.get('cost'); // Если бот передает стоимость
                    if (caseCost) {
                        spinCostElement.textContent = caseCost;
                    } else {
                         // По умолчанию для бесплатного кейса 0, для других может быть жестко прописано
                        spinCostElement.textContent = caseId === 'free_case' ? '0' : '25'; 
                    }
                } else {
                    console.warn("No items data in URL for case:", caseId);
                    // Загрузить дефолтные данные или запросить у бота
                }
            } catch (e) {
                console.error("Error parsing case items from URL:", e);
            }
        }
    }

    // Рендеринг секции "Вы можете выиграть..."
    function renderWinnableItems(items) {
        winnableItemsGrid.innerHTML = ''; // Очищаем
        if (!items || items.length === 0) {
            winnableItemsGrid.innerHTML = '<p style="text-align: center; width: 100%;">Нет предметов для отображения.</p>';
            return;
        }

        const totalWeight = items.reduce((sum, item) => sum + item.weight, 0);

        items.forEach(item => {
            const itemDiv = document.createElement('div');
            itemDiv.classList.add('winnable-item');

            const img = document.createElement('img');
            // Здесь вам нужно будет использовать реальные пути к изображениям ваших предметов
            // Например: img.src = `images/${item.name.toLowerCase().replace(/\s/g, '_')}.png`;
            // Для звезд можно так:
            if (typeof item.value === 'number') { // Если это звезды
                 img.src = `images/star_icon.png`; // Используем иконку звезды
                 img.alt = `${item.value} звезд`;
            } else { // Если это предмет/NFT
                 img.src = `images/${item.value}.png`; // Предполагаем, что имя файла соответствует value
                 img.alt = item.name;
            }
           

            const percentSpan = document.createElement('span');
            percentSpan.classList.add('item-percent');
            const percentage = (item.weight / totalWeight * 100).toFixed(2);
            percentSpan.textContent = `${percentage}%`;

            const valueSpan = document.createElement('span');
            valueSpan.classList.add('item-value');
            valueSpan.textContent = typeof item.value === 'number' ? `${item.value} ⭐` : item.name;

            itemDiv.appendChild(img);
            itemDiv.appendChild(percentSpan);
            itemDiv.appendChild(valueSpan);

            winnableItemsGrid.appendChild(itemDiv);
        });
    }

    // Рендеринг элементов колеса (просто повторяем несколько элементов)
    function renderWheelItems(items) {
        wheelElement.innerHTML = '';
        if (!items || items.length === 0) return;

        // Для демонстрации, просто дублируем первые несколько элементов
        const displayItems = items.slice(0, 5); // Отобразим первые 5 элементов

        displayItems.forEach(item => {
            const itemDiv = document.createElement('div');
            itemDiv.classList.add('wheel-item');

            const img = document.createElement('img');
            if (typeof item.value === 'number') {
                 img.src = `images/star_icon.png`;
                 img.alt = `${item.value} звезд`;
            } else {
                 img.src = `images/${item.value}.png`;
                 img.alt = item.name;
            }

            const valueSpan = document.createElement('span');
            valueSpan.textContent = typeof item.value === 'number' ? `${item.value} ⭐` : item.name;

            itemDiv.appendChild(img);
            itemDiv.appendChild(valueSpan);
            wheelElement.appendChild(itemDiv);
        });
    }


    // Обработка клика на кнопку "Мне повезёт!"
    spinButton.addEventListener('click', () => {
        // Здесь будет логика для спина колеса и выбора случайного предмета
        // Для примера, просто выбираем случайный предмет и отправляем боту

        if (!currentCaseData.items || currentCaseData.items.length === 0) {
            Telegram.WebApp.showAlert('Невозможно крутить: нет данных о предметах кейса.');
            return;
        }

        const totalWeight = currentCaseData.items.reduce((sum, item) => sum + item.weight, 0);
        let randomNum = Math.random() * totalWeight;
        let selectedItem = null;

        for (const item of currentCaseData.items) {
            if (randomNum < item.weight) {
                selectedItem = item;
                break;
            }
            randomNum -= item.weight;
        }

        if (selectedItem) {
            Telegram.WebApp.showAlert(`Вы выиграли: ${selectedItem.name}!`);
            // Отправляем результат боту
            Telegram.WebApp.sendData(JSON.stringify({
                action: 'case_result',
                item_name: typeof selectedItem.value === 'number' ? selectedItem.value : selectedItem.name // Отправляем значение или имя
            }));
            // В идеале здесь должна быть анимация колеса, а потом уже отправка результата
        } else {
            Telegram.WebApp.showAlert('Ошибка при определении выигрыша.');
        }

        // В демо-режиме, не списываем звезды
        if (!demoModeToggle.checked && currentCaseData.cost > 0) {
            // Здесь должна быть логика проверки баланса и списания звезд.
            // Сейчас это делает бот при нажатии на "Крутить" в самом боте.
            // Если Web App отвечает за списание, то нужно отправить update_stars боту.
            // Telegram.WebApp.sendData(JSON.stringify({ action: 'update_stars', amount: -currentCaseData.cost }));
        }

        // Закрываем Web App после кручения, чтобы показать сообщение бота
        // Telegram.WebApp.close(); 
    });

    // Обработка переключения демо-режима (для функционала, если он будет)
    demoModeToggle.addEventListener('change', (event) => {
        if (event.target.checked) {
            console.log("Демо режим включен");
            spinButton.textContent = "Мне повезёт! (ДЕМО)";
            spinCostElement.style.display = 'none'; // Скрыть стоимость в демо-режиме
        } else {
            console.log("Демо режим выключен");
            spinButton.textContent = "Мне повезёт!";
            spinCostElement.style.display = 'inline'; // Показать стоимость
            spinCostElement.textContent = currentCaseData.cost || '0'; // Вернуть актуальную стоимость
        }
    });

    // Обработчики для навигационных кнопок (пока просто скрытие/показ секций)
    document.getElementById('nav-play').addEventListener('click', () => {
        document.getElementById('case-view').style.display = 'block';
        document.getElementById('upgrades-view').style.display = 'none';
        document.querySelectorAll('.nav-button').forEach(btn => btn.classList.remove('active'));
        document.getElementById('nav-play').classList.add('active');
    });

    // Добавьте обработчики для других кнопок (Лидеры, Лотереи, Профиль, Апгрейды)
    // Например, для апгрейдов:
    // document.getElementById('nav-upgrades').addEventListener('click', () => {
    //     document.getElementById('case-view').style.display = 'none';
    //     document.getElementById('upgrades-view').style.display = 'block';
    //     // Обновить активную кнопку навигации
    // });
    
    // Инициализируем данные при загрузке Web App
    getUserData();
});