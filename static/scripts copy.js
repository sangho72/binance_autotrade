async function startBot() {
    console.log("Start Bot button clicked");  // 콘솔 로그 추가
    const response = await fetch('/start', { method: 'POST' });
    const result = await response.json();
    alert(result.message);
    updateStatus();
}

async function stopBot() {
    console.log("Stop Bot button clicked");  // 콘솔 로그 추가
    const response = await fetch('/stop', { method: 'POST' });
    const result = await response.json();
    alert(result.message);
    updateStatus();
}

async function resetBot() {
    console.log("Reset Bot button clicked");  // 콘솔 로그 추가
    const response = await fetch('/restart', { method: 'POST' });
    const result = await response.json();
    alert(result.message);
    updateStatus();
}
async function updateStatus() {
    const response = await fetch('/status');
    const result = await response.json();
    document.getElementById('status').innerText = `Bot Status: ${result.status}`;
    if (result.error) {
        document.getElementById('error').innerText = `Error: ${result.error}`;
    } else {
        document.getElementById('error').innerText = '';
    }
}
async function updateConfig(event) {
    event.preventDefault();
    const form = document.getElementById('config-form');
    const formData = new FormData(form);
    const response = await fetch('/config', {
        method: 'POST',
        body: formData
    });
    const result = await response.json();
    alert(result.message);
    loadConfig();  // 설정값을 다시 로드하여 화면에 표시
}

async function loadConfig() {
    const response = await fetch('/get_config');
    const result = await response.json();
    if (result.status === "success") {
        document.getElementById('coin_list').value = result.config.coin_list.join(',');
        document.getElementById('trade_rate').value = result.config.trade_rate;
        document.getElementById('target_leverage').value = result.config.target_leverage;
        document.getElementById('coin_list_display').innerText = `Coin List: ${result.config.coin_list.join(', ')}`;
    } else {
        alert("Error loading config: " + result.message);
    }
}


async function fetchLogs() {
    try {
        const response = await fetch('/logs');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const logs = await response.text();
        const terminalContent = document.getElementById('terminal_content');
        
        // 로그 타입별로 색상 지정
        const coloredLogs = logs.split('\n').map(line => {
            if (line.includes('[TRADE]')) {
                return `<span style="color: #4CAF50">${line}</span>`;
            } else if (line.includes('[BALANCE]')) {
                return `<span style="color: #2196F3">${line}</span>`;
            } else if (line.includes('[ERROR]')) {
                return `<span style="color: #f44336">${line}</span>`;
            } else if (line.includes('[WARNING]')) {
                return `<span style="color: #ff9800">${line}</span>`;
            }
            return line;
        }).join('\n');
        terminalContent.innerText = logs;
        terminalContent.scrollTop = terminalContent.scrollHeight;
    } catch (error) {
        console.error('Error fetching logs:', error);
    }
}

async function fetchData() {
    const response = await fetch('/data');
    const result = await response.json();
    if (result.status === "success") {
        displayBalanceData(result.balance_data);
        displayPositionData(result.position_data);
    } else {
        alert("Error loading data: " + result.message);
    }
}

function displayBalanceData(balanceData) {
    const table = document.getElementById('balance_data_table');
    table.innerHTML = '';  // 기존 테이블 내용 초기화

    // 테이블 헤더 추가
    const header = table.createTHead();
    const headerRow = header.insertRow(0);
    const headers = ['Wallet', 'Total', 'Free', 'Used', 'PNL'];
    headers.forEach((headerText, index) => {
        const cell = headerRow.insertCell(index);
        cell.outerHTML = `<th>${headerText}</th>`;
    });

    // 테이블 바디 추가
    const tbody = table.createTBody();
    const row = tbody.insertRow();
    row.insertCell(0).innerText = balanceData.wallet;
    row.insertCell(1).innerText = balanceData.total;
    row.insertCell(2).innerText = balanceData.free;
    row.insertCell(3).innerText = balanceData.used;
    row.insertCell(4).innerText = balanceData.PNL;
}

function displayPositionData(positionData) {
    const table = document.getElementById('position_data_table');
    table.innerHTML = '';  // 기존 테이블 내용 초기화

    // 테이블 헤더 추가
    const header = table.createTHead();
    const headerRow = header.insertRow(0);
    const headers = ['Symbol', 'Avg Price', 'Position Amount', 'Leverage', 'Unrealized Profit'];
    headers.forEach((headerText, index) => {
        const cell = headerRow.insertCell(index);
        cell.outerHTML = `<th>${headerText}</th>`;
    });

    // 테이블 바디 추가
    const tbody = table.createTBody();
    Object.keys(positionData).forEach(symbol => {
        const row = tbody.insertRow();
        const position = positionData[symbol];
        row.insertCell(0).innerText = symbol;
        row.insertCell(1).innerText = position.avg_price || '';
        row.insertCell(2).innerText = position.position_amount || '';
        row.insertCell(3).innerText = position.leverage || '';
        row.insertCell(4).innerText = position.unrealizedProfit || '';
    });
}

window.onload = function() {
    updateStatus();
    fetchLogs().then(() => {
        const terminalContent = document.getElementById('terminal_content');
        terminalContent.scrollTop = terminalContent.scrollHeight;  // 스크롤을 맨 아래로 이동
    });
    loadConfig();
    fetchData();
    setInterval(fetchLogs, 2000);  // 5초마다 로그 업데이트
    setInterval(fetchData, 2000);
};