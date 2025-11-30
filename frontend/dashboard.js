class OptionChainDashboard {
    constructor() {
        this.currentSymbol = 'NIFTY';
        this.data = null;
        this.autoRefresh = true;
        this.refreshInterval = 30000; // 30 seconds
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadData();
        this.startAutoRefresh();
    }

    setupEventListeners() {
        // Symbol tabs
        document.querySelectorAll('[data-symbol]').forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                this.switchSymbol(e.target.getAttribute('data-symbol'));
            });
        });

        // Search functionality
        document.getElementById('search-strike').addEventListener('input', (e) => {
            this.filterStrikes(e.target.value);
        });

        // Auto-refresh toggle
        const refreshToggle = document.getElementById('auto-refresh-toggle');
        if (refreshToggle) {
            refreshToggle.addEventListener('change', (e) => {
                this.autoRefresh = e.target.checked;
            });
        }
    }

    switchSymbol(symbol) {
        this.currentSymbol = symbol;
        document.querySelectorAll('.nav-link').forEach(tab => tab.classList.remove('active'));
        document.querySelector(`[data-symbol="${symbol}"]`).classList.add('active');
        this.loadData();
    }

    async loadData() {
        try {
            const response = await fetch(`/api/data/${this.currentSymbol}`);
            if (!response.ok) throw new Error('Network response was not ok');
            
            const responseData = await response.json();
            this.data = responseData.analysis;
            this.signals = responseData.signals;
            this.timestamp = responseData.timestamp;
            
            this.updateDashboard();
        } catch (error) {
            console.error('Error fetching data:', error);
            this.showError('Failed to load data. Please check if the server is running.');
        }
    }

    updateDashboard() {
        this.updateKeyMetrics();
        this.updateTradingSignals();
        this.updateCharts();
        this.updateOptionChainTable();
        this.updateTimestamp();
        this.updateSupportResistance();
    }

    updateKeyMetrics() {
        const metricsDiv = document.getElementById('key-metrics');
        if (!this.data) return;

        const { pcr, max_pain, spot_price, skew_patterns, sentiment_score } = this.data;

        const pcrSignal = pcr.pcr_oi > 1.2 ? 'danger' : (pcr.pcr_oi < 0.8 ? 'success' : 'warning');
        const skewSignal = skew_patterns.bullish_skew ? 'success' : 
                          (skew_patterns.bearish_skew ? 'danger' : 'warning');
        
        // Sentiment score color
        let sentimentClass = 'warning';
        if (sentiment_score >= 70) sentimentClass = 'success';
        else if (sentiment_score <= 30) sentimentClass = 'danger';

        metricsDiv.innerHTML = `
            <div class="col-md-2">
                <div class="card text-white bg-primary">
                    <div class="card-body text-center">
                        <h6>Spot Price</h6>
                        <h3>${spot_price.toFixed(2)}</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card text-white bg-${pcrSignal}">
                    <div class="card-body text-center">
                        <h6>PCR OI</h6>
                        <h3>${pcr.pcr_oi.toFixed(2)}</h3>
                        <small>Volume: ${pcr.pcr_volume.toFixed(2)}</small>
                    </div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card text-white bg-info">
                    <div class="card-body text-center">
                        <h6>Max Pain</h6>
                        <h3>${max_pain}</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card text-white bg-${skewSignal}">
                    <div class="card-body text-center">
                        <h6>OI Skew</h6>
                        <h3>${skew_patterns.bullish_skew ? 'Bullish' : (skew_patterns.bearish_skew ? 'Bearish' : 'Neutral')}</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card text-white bg-${sentimentClass}">
                    <div class="card-body text-center">
                        <h6>Sentiment</h6>
                        <h3>${sentiment_score}</h3>
                        <small>0-100 Scale</small>
                    </div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card text-white bg-secondary">
                    <div class="card-body text-center">
                        <h6>Strikes</h6>
                        <h3>${this.data.strike_data.length}</h3>
                        <small>Analyzed</small>
                    </div>
                </div>
            </div>
        `;
    }

    updateTradingSignals() {
        if (!this.signals) return;
        
        const signalsContainer = document.getElementById('trading-signals');
        if (!signalsContainer) return;
        
        const { signals, confidence, overall_bias } = this.signals;
        
        const biasClass = overall_bias === 'BULLISH' ? 'success' : 
                         overall_bias === 'BEARISH' ? 'danger' : 'warning';
        
        const biasIcon = overall_bias === 'BULLISH' ? 'fa-arrow-up' : 
                        overall_bias === 'BEARISH' ? 'fa-arrow-down' : 'fa-minus';
        
        signalsContainer.innerHTML = `
            <div class="card">
                <div class="card-header bg-${biasClass} text-white d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">
                        <i class="fas fa-bullhorn"></i> Trading Signals 
                        <span class="badge bg-light text-${biasClass} ms-2">
                            <i class="fas ${biasIcon}"></i> ${overall_bias}
                        </span>
                    </h6>
                    <span class="badge bg-info">
                        <i class="fas fa-crosshairs"></i> Confidence: ${confidence}%
                    </span>
                </div>
                <div class="card-body">
                    ${signals && signals.length > 0 ? 
                        signals.map(signal => `
                            <div class="alert alert-${biasClass} alert-dismissible fade show py-2 mb-2" role="alert">
                                <small><i class="fas fa-info-circle me-2"></i> ${signal}</small>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="alert"></button>
                            </div>
                        `).join('') : 
                        '<div class="text-center text-muted py-3"><i class="fas fa-info-circle me-2"></i>No strong signals detected</div>'
                    }
                </div>
            </div>
        `;
    }

    updateSupportResistance() {
        if (!this.data.support_resistance) return;
        
        const srContainer = document.getElementById('support-resistance');
        if (!srContainer) return;
        
        const { support, resistance, strong_support, strong_resistance } = this.data.support_resistance;
        const spotPrice = this.data.spot_price;
        
        srContainer.innerHTML = `
            <div class="card">
                <div class="card-header bg-warning text-dark">
                    <h6 class="mb-0"><i class="fas fa-layer-group"></i> Support & Resistance</h6>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <h6 class="text-success"><i class="fas fa-shield-alt"></i> Support Levels</h6>
                            ${support.length > 0 ? 
                                support.map(level => `
                                    <div class="d-flex justify-content-between align-items-center mb-1 ${level === strong_support ? 'fw-bold text-success' : ''}">
                                        <span>${level}</span>
                                        <span class="badge bg-${level === strong_support ? 'success' : 'light text-dark'}">
                                            ${((level - spotPrice) / spotPrice * 100).toFixed(2)}%
                                        </span>
                                    </div>
                                `).join('') : 
                                '<div class="text-muted">No strong support levels</div>'
                            }
                        </div>
                        <div class="col-md-6">
                            <h6 class="text-danger"><i class="fas fa-mountain"></i> Resistance Levels</h6>
                            ${resistance.length > 0 ? 
                                resistance.map(level => `
                                    <div class="d-flex justify-content-between align-items-center mb-1 ${level === strong_resistance ? 'fw-bold text-danger' : ''}">
                                        <span>${level}</span>
                                        <span class="badge bg-${level === strong_resistance ? 'danger' : 'light text-dark'}">
                                            ${((level - spotPrice) / spotPrice * 100).toFixed(2)}%
                                        </span>
                                    </div>
                                `).join('') : 
                                '<div class="text-muted">No strong resistance levels</div>'
                            }
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    updateCharts() {
        if (!this.data) return;
        
        // Use the advanced charting functions
        if (typeof optionCharts !== 'undefined') {
            optionCharts.updateAllCharts(this.data, 'chart');
        } else {
            // Fallback to basic charts
            this.createOISkewChart();
            this.createVolumeOIChart();
        }
    }

    createOISkewChart() {
        const strikes = this.data.strike_data.map(s => s.strike);
        const oiSkew = this.data.strike_data.map(s => s.oi_skew);

        const trace = {
            x: strikes,
            y: oiSkew,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'OI Skew',
            line: { color: '#007bff' },
            marker: { size: 4 }
        };

        const layout = {
            title: 'OI Skew Across Strikes',
            xaxis: { title: 'Strike Price' },
            yaxis: { title: 'OI Skew Ratio' },
            height: 300,
            showlegend: false
        };

        Plotly.newPlot('oi-skew-chart', [trace], layout);
    }

    createVolumeOIChart() {
        const strikes = this.data.strike_data.map(s => s.strike);
        const ceVolumeOI = this.data.strike_data.map(s => s.ce_volume_oi_ratio || 0);
        const peVolumeOI = this.data.strike_data.map(s => s.pe_volume_oi_ratio || 0);

        const trace1 = {
            x: strikes,
            y: ceVolumeOI,
            type: 'bar',
            name: 'CE Volume/OI',
            marker: { color: 'red' }
        };

        const trace2 = {
            x: strikes,
            y: peVolumeOI,
            type: 'bar',
            name: 'PE Volume/OI',
            marker: { color: 'green' }
        };

        const layout = {
            title: 'Volume-OI Efficiency Ratio',
            xaxis: { title: 'Strike Price' },
            yaxis: { title: 'Volume/OI Ratio' },
            barmode: 'group',
            height: 300
        };

        Plotly.newPlot('volume-oi-chart', [trace1, trace2], layout);
    }

    updateOptionChainTable() {
        const tbody = document.getElementById('chain-table-body');
        if (!tbody) return;

        tbody.innerHTML = '';

        this.data.strike_data.forEach(strike => {
            const row = document.createElement('tr');
            
            // Color coding based on values
            const ceBuildupClass = strike.ce_buildup === 'LONG' ? 'table-success' : 
                                  (strike.ce_buildup === 'SHORT' ? 'table-danger' : '');
            const peBuildupClass = strike.pe_buildup === 'LONG' ? 'table-success' : 
                                  (strike.pe_buildup === 'SHORT' ? 'table-danger' : '');
            const oiSkewClass = strike.oi_skew > 0.3 ? 'table-warning' : 
                               (strike.oi_skew < -0.3 ? 'table-info' : '');

            // Highlight ATM strikes
            const isATM = Math.abs(strike.strike - this.data.spot_price) <= 50;
            const atmClass = isATM ? 'fw-bold table-active' : '';

            row.innerHTML = `
                <td class="${atmClass}"><strong>${strike.strike}</strong></td>
                <td>${this.formatNumber(strike.ce_oi)}</td>
                <td class="${strike.ce_change_oi > 0 ? 'text-success' : 'text-danger'}">
                    ${strike.ce_change_oi > 0 ? '+' : ''}${this.formatNumber(strike.ce_change_oi)}
                </td>
                <td>${this.formatNumber(strike.ce_volume)}</td>
                <td>${(strike.ce_volume_oi_ratio || 0).toFixed(2)}</td>
                <td class="${ceBuildupClass}">${strike.ce_buildup || '-'}</td>
                <td class="${oiSkewClass}">${(strike.oi_skew * 100).toFixed(1)}%</td>
                <td class="${peBuildupClass}">${strike.pe_buildup || '-'}</td>
                <td>${(strike.pe_volume_oi_ratio || 0).toFixed(2)}</td>
                <td>${this.formatNumber(strike.pe_volume)}</td>
                <td class="${strike.pe_change_oi > 0 ? 'text-success' : 'text-danger'}">
                    ${strike.pe_change_oi > 0 ? '+' : ''}${this.formatNumber(strike.pe_change_oi)}
                </td>
                <td>${this.formatNumber(strike.pe_oi)}</td>
            `;
            tbody.appendChild(row);
        });
    }

    filterStrikes(searchTerm) {
        const rows = document.querySelectorAll('#chain-table-body tr');
        rows.forEach(row => {
            const strike = row.cells[0].textContent;
            if (strike.includes(searchTerm)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }

    formatNumber(num) {
        if (num >= 10000000) {
            return (num / 10000000).toFixed(1) + 'Cr';
        } else if (num >= 100000) {
            return (num / 100000).toFixed(1) + 'L';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }

    updateTimestamp() {
        const lastUpdateElement = document.getElementById('last-update');
        if (lastUpdateElement) {
            lastUpdateElement.textContent = new Date().toLocaleTimeString();
        }
    }

    showError(message) {
        // Create or update error message display
        let errorDiv = document.getElementById('error-message');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.id = 'error-message';
            errorDiv.className = 'alert alert-danger alert-dismissible fade show';
            document.querySelector('.container-fluid').prepend(errorDiv);
        }
        
        errorDiv.innerHTML = `
            <i class="fas fa-exclamation-triangle"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
    }

    startAutoRefresh() {
        setInterval(() => {
            if (this.autoRefresh) {
                this.loadData();
            }
        }, this.refreshInterval);
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    new OptionChainDashboard();
});
