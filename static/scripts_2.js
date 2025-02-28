// static/scripts.js

// 봇 제어 함수
async function startBot() {
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

async function stopBot() {
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
            updateCoinList(); // 포지션 데이터가 업데이트될 때 코인 목록도 갱신
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

// 포지션 정보 업데이트
function updatePositionDisplay(positionData) {
    const positionInfo = document.getElementById('position_info');
    let html = '';
    html += `
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
                    <div class="${symbolColor}">${symbol}</div>
                    <div class="${sizeColor}">${positionAmount.toFixed(3)}</div>
                    <div>${entryPrice.toFixed(4)}</div>
                    <div>${initialMargin.toFixed(2)} USDT</div>
                    <div class="${pnlColor}">${unrealizedPnl.toFixed(2)} USDT (${pnlPercentage}%)</div>
                    <div class="market-badge ${marketStatusClass} text-xs py-1 px-2 rounded">${marketStatusText}</div>
                </div>
            `;
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

// 캔들 차트 관련 변수
let candlestickSerie = null;
let chart = null;

function showTab1(tabId) {
    document.querySelectorAll('.tab-content').forEach(content => content.classList.add('hidden'));
    document.getElementById(tabId).classList.remove('hidden');
    if (tabId === 'candle_chart') {
        loadChart();
        updateCoinList(); // 탭 전환 시 코인 목록 갱신
    }
}
function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(content => content.classList.add('hidden'));
    document.getElementById(tabId).classList.remove('hidden');
    if (tabId === 'candle_chart') {
        loadChart(); // 탭 전환 시 차트 새로 로드
        updateCoinList();
    }
}
function loadChart() {
    const chartContainer = document.getElementById('chart_container');
    const candleTab = document.getElementById('candle_chart');

    // 탭이 숨겨져 있으면 초기화하지 않음
    if (candleTab.classList.contains('hidden')) {
        return;
    }

    // 기존 차트 제거
    if (chart) {
        chart.remove();
        chart = null;
        candlestickSeries = null;
    }

    // 차트 생성
    if (chartContainer && typeof LightweightCharts !== 'undefined') {
        chart = LightweightCharts.createChart(chartContainer, {
            width: chartContainer.clientWidth,
            height: 256,
            timeScale: { timeVisible: true, secondsVisible: false },
            layout: { backgroundColor: '#1a1a1a', textColor: '#d1d4dc' }, // 다크 테마 적용
            grid: { vertLines: { color: '#333' }, horzLines: { color: '#333' } },
        });
        candlestickSeries = chart.addCandlestickSeries({
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderVisible: false,
            wickUpColor: '#26a69a',
            wickDownColor: '#ef5350',
        });
        console.log('Chart initialized successfully');

        // 초기 데이터 로드
        updateChart();
    } else {
        console.error('Chart container or LightweightCharts not found');
    }
}
function loadChart1() {
    // 차트 컨테이너가 숨겨진 경우 초기화하지 않음
    if (document.getElementById('candle_chart').classList.contains('hidden')) {
        return;
    }

    // 기존 차트 제거
    if (chart) {
        chart.remove();
        chart = null;
        candlestickSeries = null;
    }

    // 새 차트 생성
    const chartContainer = document.getElementById('chart_container');
    if (chartContainer && typeof LightweightCharts !== 'undefined') {
        chart = LightweightCharts.createChart(chartContainer, {
            width: chartContainer.clientWidth,
            height: 256,
            timeScale: { timeVisible: true, secondsVisible: false }
        });
        candlestickSeries = chart.addCandlestickSeries(); // ✅ 정상 호출
        console.log('Chart initialized successfully');
    } else {
        console.error('Chart container or LightweightCharts not found');
    }
}
async function updateCoinList() {
    try {
        const response = await fetch('/data');
        const data = await response.json();
        if (data.status === 'success') {
            const selector = document.getElementById('coin_selector');
            if (selector) {
                selector.innerHTML = '<option value="">코인 선택</option>';
                Object.keys(data.position_data).forEach(symbol => {
                    const option = document.createElement('option');
                    option.value = symbol;
                    option.text = symbol;
                    selector.appendChild(option);
                });
                // 기본값으로 첫 번째 코인 선택
                if (Object.keys(data.position_data).length > 0) {
                    selector.value = Object.keys(data.position_data)[0];
                    setTimeout(updateChart, 500); // 0.5초 후 강제 업데이트
                }
            }
        }
    } catch (error) {
        console.error('Failed to update coin list:', error);
    }
}

async function updateChart1() {
    const symbol = document.getElementById('coin_selector').value;
    console.log('Fetching data for symbol:', symbol);
    if (!symbol || !candlestickSeries) {
        console.log('No symbol selected or chart not initialized');
        return;
    }

    try {
        const response = await fetch(`/coin_data/${symbol}?interval=1m`);
        const data = await response.json();
        if (data.status === 'success') {
            candlestickSeries.setData(data.data);
            console.log(`Chart updated for ${symbol}`);
        } else {
            console.error('Failed to fetch candle data:', data.message);
        }
    } catch (error) {
        console.error('Error fetching candle data:', error);
    }
}
async function updateChart() {
    const symbol = document.getElementById('coin_selector').value;
    if (!symbol || !candlestickSeries) {
        console.log('No symbol selected or candlestickSeries not initialized');
        return;
    }

    try {
        const response = await fetch(`/coin_data/${symbol}?interval=1m`);
        const data = await response.json();
        if (data.status === 'success' && data.data.length > 0) {
            candlestickSeries.setData(data.data);
            chart.timeScale().fitContent(); // 데이터에 맞게 시간 범위 조정
            console.log(`Chart updated for ${symbol} with ${data.data.length} candles`);
        } else {
            console.warn('No candle data available or fetch failed:', data.message);
        }
    } catch (error) {
        console.error('Error fetching candle data:', error);
    }
}
// 초기화 및 주기적 업데이트
window.onload = function() {
    updateStatus();
    fetchLogs();
    fetchData();
    loadChart(); // 초기 차트 로드
    setInterval(updateStatus, 1000);
    setInterval(fetchLogs, 1000);
    setInterval(fetchData, 1000);
    setInterval(() => {
        const candleTab = document.getElementById('candle_chart');
        if (!candleTab.classList.contains('hidden')) {
            updateChart(); // 캔들 차트 탭이 보일 때만 업데이트
        }
    }, 1000); // 선택된 symbol이 있을 때만 업데이트
};