// static/scripts.js

let candlestickSeries = null;
let chart = null;
let currentSymbol = null;

// 봇 제어 함수
async function startBot1() {
    try {
        const response = await fetch('/start', { method: 'POST' });
        const result = await response.json();
        if (result.status === 'success') {
            showNotification('Bot started successfully', 'success');
        } else {
            showNotification('Failed to start bot: ' + result.message, 'error');
        }
        updateStatus();
    } catch (error) {
        showNotification('Error starting bot: ' + error.message, 'error');
    }
}

async function stopBot1() {
    try {
        const response = await fetch('/stop', { method: 'POST' });
        const result = await response.json();
        if (result.status === 'success') {
            showNotification('Bot stopped successfully', 'success');
            updateStatus();
        } else {
            showNotification('Failed to stop bot: ' + result.message, 'error');
        }
    } catch (error) {
        showNotification('Error stopping bot: ' + error.message, 'error');
    }
}

async function startBot() {
    try {
        const response = await fetch('/start', { method: 'POST' });
        const result = await response.json();
        if (result.status === 'success') {
            showNotification(result.message, 'success');
        } else {
            showNotification('Failed to start bot: ' + result.message, 'error');
        }
        updateStatus();
    } catch (error) {
        showNotification('Error starting bot: ' + error.message, 'error');
    }
}

async function stopBot() {
    try {
        const response = await fetch('/stop', { method: 'POST' });
        const result = await response.json();
        if (result.status === 'success') {
            showNotification(result.message, 'success');
        } else {
            showNotification('Failed to stop bot: ' + result.message, 'error');
        }
        updateStatus();
    } catch (error) {
        showNotification('Error stopping bot: ' + error.message, 'error');
    }
}

async function restartBot() {
    try {
        const response = await fetch('/restart', { method: 'POST' });
        const result = await response.json();
        if (result.status === 'success') {
            showNotification(result.message, 'success');
        } else {
            showNotification('Failed to restart bot: ' + result.message, 'error');
        }
        updateStatus();
    } catch (error) {
        showNotification('Error restarting bot: ' + error.message, 'error');
    }
}

// 상태 업데이트 함수
async function updateStatus() {
    try {
        const response = await fetch('/status');
        const result = await response.json();
        const statusBadge = document.getElementById('bot_status');
        if (result.status === 'running') {
            statusBadge.textContent = 'Active';
            statusBadge.classList.remove('status-inactive');
            statusBadge.classList.add('status-active');
        } else {
            statusBadge.textContent = 'Inactive';
            statusBadge.classList.remove('status-active');
            statusBadge.classList.add('status-inactive');
        }
    } catch (error) {
        console.error('Status update failed:', error);
        const statusBadge = document.getElementById('bot_status');
        statusBadge.textContent = 'Inactive';
        statusBadge.classList.remove('status-active');
        statusBadge.classList.add('status-inactive');
    }
}

// 데이터 가져오기 함수
async function fetchData() {
    try {
        const response = await fetch('/data');
        const result = await response.json();
        if (result.status === 'success') {
            updateBalanceDisplay(result.balance_data);
            updatePositionDisplay(result.position_data);
            // updateCoinList(); // 포지션 데이터가 업데이트될 때 코인 목록도 갱신
        }
    } catch (error) {
        console.error('Data fetch failed:', error);
    }
}

// 잔고 정보 업데이트
function updateBalanceDisplay(balanceData) {
    if (balanceData) {
        document.getElementById('total_balance').textContent = `${parseFloat(balanceData.wallet).toFixed(2)} USDT`;
        document.getElementById('available_balance').textContent = `${parseFloat(balanceData.free).toFixed(2)} USDT`;
        document.getElementById('PNL').textContent = `${parseFloat(balanceData.pnl).toFixed(2)} USDT`;
    }
}


function updatePositionDisplay(positionData) {
    const positionInfo = document.getElementById('position_info');
    let html = `
        <div class="position-header grid grid-cols-6 gap-2 border-b pb-2 mb-2 text-sm font-semibold text-gray-300">
            <div>Symbol</div>
            <div>Size</div>
            <div>Entry Price</div>
            <div>Margin</div>
            <div>PNL (ROI %)</div>
            <div>Market status</div>
        </div>
    `;
    const entries = Object.entries(positionData);
    if (entries.length === 0) {
        html += '<p class="text-sm text-gray-400">No positions available</p>';
    } else {
        const sortedEntries = entries.sort((a, b) => Math.abs(parseFloat(b[1].position_amount) || 0) - Math.abs(parseFloat(a[1].position_amount) || 0));
        sortedEntries.forEach(([symbol, position]) => {
            const positionAmount = parseFloat(position.position_amount) || 0;
            const entryPrice = parseFloat(position.avg_price) || 0;
            const leverage = parseFloat(position.leverage) || 1;
            const unrealizedPnl = parseFloat(position.unrealized_profit) || 0;
            const initialMargin = leverage !== 0 ? Math.abs((positionAmount * entryPrice) / leverage) : 0;
            const pnlPercentage = initialMargin !== 0 ? (unrealizedPnl / initialMargin * 100).toFixed(2) : "0.00";
            const pnlColor = unrealizedPnl >= 0 ? 'text-green-400' : 'text-red-400';
            const isLong = positionAmount > 0;
            const symbolColor = isLong ? 'text-green-400' : 'text-red-400';
            const sizeColor = isLong ? 'text-green-400' : 'text-red-400';
            let marketStatusClass = '';
            switch(position.market_status) {
                case 'Strong_Trend_Up': marketStatusClass = 'bg-green-600'; break;
                case 'Rising': marketStatusClass = 'bg-green-400'; break;
                case 'Sideways_Or_Weak_Trend': marketStatusClass = 'bg-yellow-500'; break;
                case 'Falling': marketStatusClass = 'bg-red-400'; break;
                case 'Strong_Trend_Down': marketStatusClass = 'bg-red-600'; break;
                default: marketStatusClass = 'bg-gray-500';
            }
            const marketStatusText = position.market_status ? position.market_status.replace(/_/g, ' ').replace('Or', '/') : 'Unknown';
            html += `
                <div class="position-row grid grid-cols-6 gap-2 items-center py-2 border-b text-sm">
                    <div class="${symbolColor} symbol-clickable" onclick="updateChart('${symbol}')">${symbol}</div>
                    <div class="${sizeColor}">${positionAmount.toFixed(3)}</div>
                    <div>${entryPrice.toFixed(4)}</div>
                    <div>${initialMargin.toFixed(2)} USDT</div>
                    <div class="${pnlColor}">${unrealizedPnl.toFixed(2)} USDT (${pnlPercentage}%)</div>
                    <div class="market-badge ${marketStatusClass} text-xs py-1 px-2 rounded">${marketStatusText}</div>
                </div>
            `;
            // 첫 번째 심벌을 기본으로 설정
            if (!currentSymbol) currentSymbol = symbol;
        });
    }
    positionInfo.innerHTML = html;
}

// 로그 가져오기 함수
async function fetchLogs() {
    try {
        const response = await fetch('/logs');
        const data = await response.json();
        if (data.status === 'success') {
            const terminalContent = document.getElementById('terminal_content');
            if (terminalContent) {
                let html = '';
                data.logs.forEach(log => {
                    let logClass = '';
                    switch(log.category) {
                        case 'trade': logClass = 'log-trade'; break;
                        case 'balance': logClass = 'log-balance'; break;
                        case 'system': logClass = 'log-system'; break;
                    }
                    if (log.level >= 40) logClass += ' log-error';
                    else if (log.level == 30) logClass += ' log-warning';
                    html += `
                        <div class="${logClass} text-sm py-1">
                            <span class="log-timestamp">${new Date(log.timestamp).toLocaleString()}</span>
                            <span class="ml-2">${log.message}</span>
                        </div>
                    `;
                });
                terminalContent.innerHTML = html;
                terminalContent.scrollTop = terminalContent.scrollHeight; // 최신 로그로 스크롤
            }
        } else {
            console.error('Failed to fetch logs:', data.message);
        }
    } catch (error) {
        console.error('Log fetch failed:', error);
    }
}

// 알림 표시 함수
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 p-4 rounded shadow-lg ${
        type === 'success' ? 'bg-green-500' :
        type === 'error' ? 'bg-red-500' :
        'bg-blue-500'
    } text-white`;
    notification.textContent = message;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 3000);
}


function loadChart() {
    const chartContainer = document.getElementById('chart_container');
    if (chart) {
        chart.remove();
        chart = null;
        candlestickSeries = null;
    }
    if (chartContainer && typeof LightweightCharts !== 'undefined') {
        chart = LightweightCharts.createChart(chartContainer, {
            width: chartContainer.clientWidth,
            height: 400,
            timeScale: { 
                timeVisible: true, 
                secondsVisible: false,
            },
            layout: { backgroundColor: '#1a1a1a', textColor: '#d1d4dc' },
            grid: { vertLines: { color: '#333' }, horzLines: { color: '#333' } },
        });
        candlestickSeries = chart.addCandlestickSeries({
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderVisible: false,
            wickUpColor: '#26a69a',
            wickDownColor: '#ef5350',
            priceFormat: {
                type: 'price',
                precision: 4, // 소수점 아래 4자리로 고정 (필요 시 조정)
                minMove: 0.0001 // 최소 가격 단위 설정
            }
        });
        console.log('Chart initialized successfully');
        if (currentSymbol) updateChart(currentSymbol);
    } else {
        console.error('Chart container or LightweightCharts not found');
    }
}

async function updateChart1(symbol) {
    currentSymbol = symbol;
    if (!symbol || !candlestickSeries) {
        console.log('No symbol selected or candlestickSeries not initialized');
        return;
    }
    try {
        const response = await fetch(`/coin_data/${symbol}?interval=1m`);
        const data = await response.json();
        if (data.status === 'success' && data.data.length > 0) {
            candlestickSeries.setData(data.data);
            chart.timeScale().fitContent();
            console.log(`Chart updated for ${symbol} with ${data.data.length} candles`);
        } else {
            console.warn('No candle data available or fetch failed:', data.message);
        }
    } catch (error) {
        console.error('Error fetching candle data:', error);
    }
}

async function updateChart(symbol) {
    currentSymbol = symbol;
    if (!symbol || !candlestickSeries) {
        console.log('No symbol selected or candlestickSeries not initialized');
        return;
    }
    try {
        const response = await fetch(`/coin_data/${symbol}?interval=1m`);
        const data = await response.json();
        if (data.status === 'success' && data.data.length > 0) {
            candlestickSeries.setData(data.data);
            chart.timeScale().fitContent();
            // 선택된 심벌 표시
            document.getElementById('selected_symbol').textContent = `선택된 코인: ${symbol}`;
            document.getElementById('selected_symbol').classList.add('text-gray-100');
            console.log(`Chart updated for ${symbol} with ${data.data.length} candles`);
        } else {
            console.warn('No candle data available or fetch failed:', data.message);
            document.getElementById('selected_symbol').textContent = `선택된 코인: ${symbol} (데이터 없음)`;
            document.getElementById('selected_symbol').classList.remove('text-gray-100');
            document.getElementById('selected_symbol').classList.add('text-red-400');
        }
    } catch (error) {
        console.error('Error fetching candle data:', error);
        document.getElementById('selected_symbol').textContent = `선택된 코인: ${symbol} (오류)`;
        document.getElementById('selected_symbol').classList.add('text-red-400');
    }
}

// 초기 로드 시 기본 심벌 설정
window.onload = function() {
    updateStatus();
    fetchLogs();
    fetchData();
    loadChart();
    setInterval(updateStatus, 1000);
    setInterval(fetchLogs, 1000);
    setInterval(fetchData, 1000);
    setInterval(() => {
        if (currentSymbol) updateChart(currentSymbol);
    }, 1000);
};

// window.onload = function() {
//     updateStatus();
//     fetchLogs();
//     fetchData();
//     loadChart();
//     setInterval(updateStatus, 1000);
//     setInterval(fetchLogs, 1000);
//     setInterval(fetchData, 1000);
//     setInterval(() => {
//         if (currentSymbol) updateChart(currentSymbol);
//     }, 1000);
// };