// DASHBAORD APP 

function dashboardApp() {
            return {
                // Data
                buckets: [],
                unmappedCampaigns: [],
                litifyLeads: [],
                filteredLitifyLeads: [],
                availableBuckets: [],
                summary: {
                    totalCost: 0,
                    totalLeads: 0,
                    totalCases: 0,
                    totalRetainers: 0,
                    totalPending: 0,
                    avgCostPerLead: 0
                },
                
                // YouTube summary
                youtubeSummary: {
                    totalCost: 0,
                    totalLeads: 0,
                    totalCases: 0,
                    totalRetainers: 0
                },
                
                // Exclusion filters
                includeSpam: false,
                includeAbandoned: false,
                includeDuplicate: false,
                excludedCounts: {
                    spam: 0,
                    abandoned: 0,
                    duplicate: 0,
                    total: 0
                },
                
                // Filters
                selectedState: 'all',
                selectedCampaign: 'all',
                litifyBucketFilter: 'all',
                startDate: '',
                endDate: '',
                dateRangePreset: 'today',
                
                // Filtered data
                filteredBuckets: [],
                filteredSummary: {},
                
                // UI State
                showLitifyDetail: true,
                darkMode: false,
                sidebarCollapsed: false,
                
                // Status
                apiStatus: {
                    google_ads_connected: false,
                    litify_connected: false
                },
                dataSource: 'Demo Data',
                isLoading: true,
                isRefreshing: false,
                hasError: false,
                errorMessage: '',
                lastUpdated: 'Never',
                chartInstance: null,
                chartUpdateTimeout: null,
                
                // Helper function to identify YouTube campaigns
                isYouTubeBucket(bucket) {
                    if (!bucket.campaigns) return false;
                    // Check if any campaign in this bucket contains "crisp" (case-insensitive)
                    return bucket.campaigns.some(campaign => 
                        campaign.toLowerCase().includes('crisp')
                    );
                },
                
                async init() {
                    // Load preferences
                    const savedDarkMode = localStorage.getItem('darkMode');
                    if (savedDarkMode !== null) {
                        this.darkMode = savedDarkMode === 'true';
                    }
                    
                    const savedSidebar = localStorage.getItem('sidebarCollapsed');
                    if (savedSidebar !== null) {
                        this.sidebarCollapsed = savedSidebar === 'true';
                    }
                    
                    // Load exclusion filter preferences
                    const savedIncludeSpam = localStorage.getItem('includeSpam');
                    if (savedIncludeSpam !== null) {
                        this.includeSpam = savedIncludeSpam === 'true';
                    }
                    
                    const savedIncludeAbandoned = localStorage.getItem('includeAbandoned');
                    if (savedIncludeAbandoned !== null) {
                        this.includeAbandoned = savedIncludeAbandoned === 'true';
                    }
                    
                    const savedIncludeDuplicate = localStorage.getItem('includeDuplicate');
                    if (savedIncludeDuplicate !== null) {
                        this.includeDuplicate = savedIncludeDuplicate === 'true';
                    }
                    
                    // Set default to today
                    this.setDateRange('today');
                    
                    await this.checkStatus();
                    await this.fetchData();
                    
                    // Initialize chart after data is loaded
                    this.$nextTick(() => {
                        setTimeout(() => {
                            if (this.filteredBuckets.length > 0) {
                                this.initChart();
                            }
                        }, 100);
                    });
                    
                    // Watch for sidebar changes
                    this.$watch('sidebarCollapsed', (value) => {
                        localStorage.setItem('sidebarCollapsed', value);
                    });
                    
                    // Watch for exclusion filter changes
                    this.$watch('includeSpam', (value) => {
                        localStorage.setItem('includeSpam', value);
                    });
                    
                    this.$watch('includeAbandoned', (value) => {
                        localStorage.setItem('includeAbandoned', value);
                    });
                    
                    this.$watch('includeDuplicate', (value) => {
                        localStorage.setItem('includeDuplicate', value);
                    });
                    
                    // Cleanup on page unload
                    window.addEventListener('beforeunload', () => {
                        this.cleanup();
                    });
                },
                
                cleanup() {
                    // Clear any pending chart updates
                    if (this.chartUpdateTimeout) {
                        clearTimeout(this.chartUpdateTimeout);
                        this.chartUpdateTimeout = null;
                    }
                    
                    // Destroy chart instance
                    if (this.chartInstance) {
                        try {
                            this.chartInstance.destroy();
                        } catch (e) {
                            // Ignore destroy errors
                        }
                        this.chartInstance = null;
                    }
                },
                
                toggleDarkMode() {
                    this.darkMode = !this.darkMode;
                    localStorage.setItem('darkMode', this.darkMode);
                    
                    // Use debounced chart update
                    if (this.filteredBuckets.length > 0) {
                        this.updateChart();
                    }
                },
                
                hasExclusionFilters() {
                    return this.includeSpam || this.includeAbandoned || this.includeDuplicate;
                },
                
                getIncludedCount() {
                    let count = 0;
                    if (this.includeSpam) count += this.excludedCounts.spam;
                    if (this.includeAbandoned) count += this.excludedCounts.abandoned;
                    if (this.includeDuplicate) count += this.excludedCounts.duplicate;
                    return count;
                },
                
                clearExclusionFilters() {
                    this.includeSpam = false;
                    this.includeAbandoned = false;
                    this.includeDuplicate = false;
                    this.updateFilters();
                },
                
                get availableCampaigns() {
                    let campaigns = this.buckets.map(b => b.name);
                    
                    if (this.selectedState !== 'all') {
                        campaigns = campaigns.filter(name => {
                            const bucket = this.buckets.find(b => b.name === name);
                            return bucket && bucket.state === this.selectedState;
                        });
                    }
                    
                    return campaigns;
                },
                
                async checkStatus() {
                    try {
                        const response = await fetch('/api/status');
                        const data = await response.json();
                        this.apiStatus = data;
                    } catch (error) {
                        console.error('Error checking status:', error);
                    }
                },
                
                async fetchData() {
                    this.isLoading = this.buckets.length === 0;
                    this.hasError = false;
                    
                    try {
                        const params = new URLSearchParams({
                            start_date: this.startDate,
                            end_date: this.endDate,
                            limit: 1000,
                            include_spam: this.includeSpam,
                            include_abandoned: this.includeAbandoned,
                            include_duplicate: this.includeDuplicate
                        });
                        
                        const response = await fetch(`/api/dashboard-data?${params}`);
                        if (!response.ok) throw new Error('Failed to fetch data');
                        
                        const data = await response.json();
                        
                        this.buckets = data.buckets || [];
                        this.unmappedCampaigns = data.unmapped_campaigns || [];
                        this.litifyLeads = data.litify_leads || [];
                        this.availableBuckets = data.available_buckets || [];
                        this.dataSource = data.data_source || 'Demo Data';
                        this.excludedCounts = data.excluded_lead_counts || {spam: 0, abandoned: 0, duplicate: 0, total: 0};
                        
                        // Calculate summary
                        this.summary = {
                            totalCost: this.buckets.reduce((sum, b) => sum + (b.cost || 0), 0),
                            totalLeads: this.buckets.reduce((sum, b) => sum + (b.leads || 0), 0),
                            totalCases: this.buckets.reduce((sum, b) => sum + (b.cases || 0), 0),
                            totalRetainers: this.buckets.reduce((sum, b) => sum + (b.retainers || 0), 0),
                            totalPending: this.buckets.reduce((sum, b) => sum + (b.pendingRetainers || 0), 0),
                            avgCostPerLead: 0
                        };
                        
                        if (this.summary.totalLeads > 0) {
                            this.summary.avgCostPerLead = this.summary.totalCost / this.summary.totalLeads;
                        }
                        
                        this.lastUpdated = new Date().toLocaleTimeString();
                        this.isLoading = false;
                        
                        this.updateFilters();
                        this.filterLitifyLeads();
                    } catch (error) {
                        console.error('Error fetching data:', error);
                        this.errorMessage = error.message;
                        this.hasError = true;
                        this.isLoading = false;
                    }
                },
                
                filterLitifyLeads() {
                    if (this.litifyBucketFilter === 'all') {
                        this.filteredLitifyLeads = this.litifyLeads;
                    } else {
                        this.filteredLitifyLeads = this.litifyLeads.filter(lead => 
                            lead.bucket === this.litifyBucketFilter
                        );
                    }
                },
                
                handleDateChange() {
                    this.dateRangePreset = 'custom';
                    this.fetchData();
                },
                
                setDateRange(range) {
                    const today = new Date();
                    const formatDate = (date) => {
                        const year = date.getFullYear();
                        const month = String(date.getMonth() + 1).padStart(2, '0');
                        const day = String(date.getDate()).padStart(2, '0');
                        return `${year}-${month}-${day}`;
                    };
                    
                    this.dateRangePreset = range;
                    
                    switch(range) {
                        case 'today':
                            this.startDate = formatDate(today);
                            this.endDate = formatDate(today);
                            break;
                        case 'yesterday':
                            const yesterday = new Date(today);
                            yesterday.setDate(today.getDate() - 1);
                            this.startDate = formatDate(yesterday);
                            this.endDate = formatDate(yesterday);
                            break;
                        case 'week':
                            const weekStart = new Date(today);
                            weekStart.setDate(today.getDate() - today.getDay());
                            this.startDate = formatDate(weekStart);
                            this.endDate = formatDate(today);
                            break;
                        case 'month':
                            const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
                            this.startDate = formatDate(monthStart);
                            this.endDate = formatDate(today);
                            break;
                        case 'last30':
                            const thirtyDaysAgo = new Date(today);
                            thirtyDaysAgo.setDate(today.getDate() - 30);
                            this.startDate = formatDate(thirtyDaysAgo);
                            this.endDate = formatDate(today);
                            break;
                    }
                    
                    this.fetchData();
                },
                
                getDateRangeText() {
                    if (!this.startDate || !this.endDate) return '';
                    
                    const start = new Date(this.startDate);
                    const end = new Date(this.endDate);
                    
                    if (this.startDate === this.endDate) {
                        return start.toLocaleDateString('en-US', { 
                            month: 'short', 
                            day: 'numeric', 
                            year: 'numeric' 
                        });
                    }
                    
                    return `${start.toLocaleDateString('en-US', { 
                        month: 'short', 
                        day: 'numeric' 
                    })} - ${end.toLocaleDateString('en-US', { 
                        month: 'short', 
                        day: 'numeric', 
                        year: 'numeric' 
                    })}`;
                },
                
                updateFilters() {
                    // First apply state and campaign filters
                    this.filteredBuckets = this.buckets.filter(bucket => {
                        let include = true;
                        
                        if (this.selectedState !== 'all' && bucket.state !== this.selectedState) {
                            include = false;
                        }
                        
                        if (this.selectedCampaign !== 'all' && bucket.name !== this.selectedCampaign) {
                            include = false;
                        }
                        
                        return include;
                    });
                    
                    // Calculate YouTube summary separately
                    this.youtubeSummary = {
                        totalCost: 0,
                        totalLeads: 0,
                        totalCases: 0,
                        totalRetainers: 0
                    };
                    
                    this.filteredBuckets.forEach(bucket => {
                        if (this.isYouTubeBucket(bucket)) {
                            this.youtubeSummary.totalCost += bucket.cost || 0;
                            this.youtubeSummary.totalLeads += bucket.leads || 0;
                            this.youtubeSummary.totalCases += bucket.cases || 0;
                            this.youtubeSummary.totalRetainers += bucket.retainers || 0;
                        }
                    });
                    
                    this.filteredSummary = {
                        totalCost: this.filteredBuckets.reduce((sum, b) => sum + (b.cost || 0), 0),
                        totalLeads: this.filteredBuckets.reduce((sum, b) => sum + (b.leads || 0), 0),
                        totalCases: this.filteredBuckets.reduce((sum, b) => sum + (b.cases || 0), 0),
                        totalRetainers: this.filteredBuckets.reduce((sum, b) => sum + (b.retainers || 0), 0),
                        totalPending: this.filteredBuckets.reduce((sum, b) => sum + (b.pendingRetainers || 0), 0),
                        avgCostPerLead: 0
                    };
                    
                    if (this.filteredSummary.totalLeads > 0) {
                        this.filteredSummary.avgCostPerLead = this.filteredSummary.totalCost / this.filteredSummary.totalLeads;
                    }
                    
                    // Refresh data if exclusion filters changed
                    if (this.hasExclusionFilters()) {
                        this.fetchData();
                    }
                    
                    this.updateChart();
                },
                
                getFilterText() {
                    let parts = [];
                    
                    if (this.selectedState !== 'all') {
                        parts.push(this.selectedState);
                    }
                    
                    if (this.selectedCampaign !== 'all') {
                        parts.push(this.selectedCampaign);
                    }
                    
                    return parts.length > 0 ? parts.join(' - ') : 'All Data';
                },
                
                formatDateTime(dateStr) {
                    if (!dateStr) return '-';
                    const date = new Date(dateStr);
                    return date.toLocaleString('en-US', { 
                        month: 'short', 
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                },
                
                getStatusClass(status) {
                    if (!status) return 'badge-secondary';
                    const s = status.toLowerCase();
                    if (s.includes('signed') || s.includes('retained')) return 'badge-success';
                    if (s.includes('retainer sent')) return 'badge-warning';
                    if (s.includes('working') || s.includes('review')) return 'badge-info';
                    if (s.includes('unqualified') || s.includes('rejected')) return 'badge-danger';
                    return 'badge-secondary';
                },
                
                async refreshData() {
                    this.isRefreshing = true;
                    await this.checkStatus();
                    await this.fetchData();
                    setTimeout(() => {
                        this.isRefreshing = false;
                    }, 500);
                },
                
                initChart() {
                    if (this.chartInstance) {
                        try {
                            this.chartInstance.destroy();
                        } catch (e) {
                            console.warn('Error destroying chart:', e);
                        }
                        this.chartInstance = null;
                    }
                    
                    const ctx = document.getElementById('costChart');
                    if (!ctx) return;
                    
                    try {
                        // Filter out YouTube buckets from the chart
                        const labels = this.filteredBuckets
                            .filter(b => b.cost > 0 && !this.isYouTubeBucket(b))
                            .map(b => b.name);
                        const data = this.filteredBuckets
                            .filter(b => b.cost > 0 && !this.isYouTubeBucket(b))
                            .map(b => b.cost);
                        
                        // Industry standard chart colors
                        const colors = [
                            '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
                            '#8b5cf6', '#06b6d4', '#84cc16', '#f97316',
                            '#6366f1', '#14b8a6', '#eab308', '#ec4899'
                        ];
                        
                        this.chartInstance = new Chart(ctx, {
                            type: 'doughnut',
                            data: {
                                labels: labels,
                                datasets: [{
                                    data: data,
                                    backgroundColor: colors,
                                    borderWidth: 2,
                                    borderColor: this.darkMode ? '#0a0a0a' : '#ffffff'
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {
                                    legend: {
                                        position: 'bottom',
                                        labels: {
                                            color: this.darkMode ? '#f8fafc' : '#334155',
                                            padding: 15,
                                            font: { size: 12 },
                                            usePointStyle: true
                                        }
                                    },
                                    tooltip: {
                                        backgroundColor: this.darkMode ? '#1e293b' : '#ffffff',
                                        titleColor: this.darkMode ? '#f1f5f9' : '#334155',
                                        bodyColor: this.darkMode ? '#cbd5e1' : '#64748b',
                                        borderColor: this.darkMode ? '#475569' : '#e2e8f0',
                                        borderWidth: 1,
                                        callbacks: {
                                            label: function(context) {
                                                const label = context.label || '';
                                                const value = new Intl.NumberFormat('en-US', {
                                                    style: 'currency',
                                                    currency: 'USD',
                                                    minimumFractionDigits: 0,
                                                    maximumFractionDigits: 0
                                                }).format(context.parsed);
                                                return label + ': ' + value;
                                            }
                                        }
                                    }
                                }
                            }
                        });
                    } catch (error) {
                        console.error('Error initializing chart:', error);
                    }
                },
                
                updateChart() {
                    // Debounce chart updates to prevent rapid recreations
                    if (this.chartUpdateTimeout) {
                        clearTimeout(this.chartUpdateTimeout);
                    }
                    
                    this.chartUpdateTimeout = setTimeout(() => {
                        this.doUpdateChart();
                    }, 100);
                },
                
                doUpdateChart() {
                    // Skip update if no chart instance or invalid state
                    if (!this.chartInstance) {
                        if (this.filteredBuckets.length > 0) {
                            this.initChart();
                        }
                        return;
                    }
                    
                    // Check if canvas still exists in DOM
                    const ctx = document.getElementById('costChart');
                    if (!ctx || !ctx.isConnected) {
                        this.chartInstance = null;
                        if (this.filteredBuckets.length > 0) {
                            this.initChart();
                        }
                        return;
                    }
                    
                    // Recreate chart instead of updating to avoid Chart.js issues
                    this.initChart();
                },
                
                getBestConversion() {
                    if (this.filteredBuckets.length === 0) return 'N/A';
                    const valid = this.filteredBuckets.filter(b => b.conversionRate > 0);
                    if (valid.length === 0) return 'N/A';
                    const best = valid.reduce((prev, current) => 
                        (current.conversionRate > prev.conversionRate) ? current : prev
                    );
                    return best.name;
                },
                
                getLowestCPL() {
                    // Exclude YouTube from CPL comparison
                    const valid = this.filteredBuckets.filter(b => b.costPerLead > 0 && !this.isYouTubeBucket(b));
                    if (valid.length === 0) return 'N/A';
                    const best = valid.reduce((prev, current) => 
                        (current.costPerLead < prev.costPerLead) ? current : prev
                    );
                    return best.name;
                },
                
                getHighestVolume() {
                    if (this.filteredBuckets.length === 0) return 'N/A';
                    const best = this.filteredBuckets.reduce((prev, current) => 
                        (current.leads > prev.leads) ? current : prev
                    );
                    return best.name;
                },
                
                getMostEfficient() {
                    // Exclude YouTube from CPA comparison
                    const valid = this.filteredBuckets.filter(b => b.cpa > 0 && !this.isYouTubeBucket(b));
                    if (valid.length === 0) return 'N/A';
                    const best = valid.reduce((prev, current) => 
                        (current.cpa < prev.cpa) ? current : prev
                    );
                    return best.name;
                },
                
                formatCurrency(value) {
                    return new Intl.NumberFormat('en-US', {
                        style: 'currency',
                        currency: 'USD',
                        minimumFractionDigits: 0,
                        maximumFractionDigits: 0
                    }).format(value || 0);
                },
                
                formatNumber(value) {
                    return (value || 0).toLocaleString();
                },
                
                getPercentageClass(value, metricType) {
                    if (!value && value !== 0) return 'badge-secondary';
                    
                    const percentage = value * 100;
                    
                    switch(metricType) {
                        case 'inPractice':
                            // Higher % in practice is better
                            if (percentage >= 80) return 'badge-success';
                            if (percentage >= 60) return 'badge-warning';
                            return 'badge-danger';
                            
                        case 'unqualified':
                            // Higher % unqualified is worse
                            if (percentage <= 20) return 'badge-success';
                            if (percentage <= 40) return 'badge-warning';
                            return 'badge-danger';
                            
                        case 'conversion':
                            // Higher conversion rate is better
                            if (percentage >= 30) return 'badge-success';
                            if (percentage >= 15) return 'badge-warning';
                            if (percentage > 0) return 'badge-info';
                            return 'badge-secondary';
                            
                        default:
                            return 'badge-secondary';
                    }
                },
                
                formatPercentage(value) {
                    return ((value || 0) * 100).toFixed(1) + '%';
                }
            }
        }

//FORECASTING 

     function forecastingApp() {
            return {
                darkMode: false,
                activeTab: 'pacing',
                currentMonth: '',
                currentDayOfMonth: 0,
                totalDaysInMonth: 0,
                remainingDays: 0,
                chartInstance: null,
                dataSource: 'Demo Data', // Will be updated based on API connection
                
                // Conversion rates with sliders
                conversionRates: {
                    leadToCase: 22,  // Default 22%
                    leadToRetainer: 25  // Default 25%
                },
                
                // Settings data structure
                settings: {
                    CA: {
                        spend: { weekdayDaily: 36364, weekendDaily: 18182, monthlyTotal: 1000000 },
                        leads: { weekdayDaily: 51, weekendDaily: 26, monthlyTotal: 1428 },
                        cases: { weekdayDaily: 11, weekendDaily: 6, monthlyTotal: 308 },
                        retainers: { weekdayDaily: 13, weekendDaily: 6, monthlyTotal: 350 }
                    },
                    AZ: {
                        spend: { weekdayDaily: 22727, weekendDaily: 11364, monthlyTotal: 500000 },
                        leads: { weekdayDaily: 18, weekendDaily: 9, monthlyTotal: 500 },
                        cases: { weekdayDaily: 4, weekendDaily: 2, monthlyTotal: 110 },
                        retainers: { weekdayDaily: 5, weekendDaily: 2, monthlyTotal: 125 }
                    },
                    GA: {
                        spend: { weekdayDaily: 9091, weekendDaily: 4545, monthlyTotal: 200000 },
                        leads: { weekdayDaily: 11, weekendDaily: 5, monthlyTotal: 310 },
                        cases: { weekdayDaily: 3, weekendDaily: 1, monthlyTotal: 68 },
                        retainers: { weekdayDaily: 4, weekendDaily: 2, monthlyTotal: 80 }
                    },
                    TX: {
                        spend: { weekdayDaily: 0, weekendDaily: 0, monthlyTotal: 0 },
                        leads: { weekdayDaily: 0, weekendDaily: 0, monthlyTotal: 0 },
                        cases: { weekdayDaily: 0, weekendDaily: 0, monthlyTotal: 0 },
                        retainers: { weekdayDaily: 0, weekendDaily: 0, monthlyTotal: 0 }
                    }
                },
                
                // Actual performance data (will be populated from API)
                actualData: {
                    CA: { spend: 0, leads: 0, cases: 0, retainers: 0 },
                    AZ: { spend: 0, leads: 0, cases: 0, retainers: 0 },
                    GA: { spend: 0, leads: 0, cases: 0, retainers: 0 },
                    TX: { spend: 0, leads: 0, cases: 0, retainers: 0 }
                },
                
                // Computed values
                totalTargetSpend: 0,
                totalTargetLeads: 0,
                totalTargetCases: 0,
                totalTargetRetainers: 0,
                totalActualSpend: 0,
                totalActualLeads: 0,
                totalActualCases: 0,
                totalActualRetainers: 0,
                
                spendProgress: 0,
                leadsProgress: 0,
                casesProgress: 0,
                retainersProgress: 0,
                
                spendPacingStatus: '',
                leadsPacingStatus: '',
                casesPacingStatus: '',
                retainersPacingStatus: '',
                
                dailyAverageSpend: 0,
                dailyAverageLeads: 0,
                dailyAverageCases: 0,
                dailyAverageRetainers: 0,
                
                requiredDailySpend: 0,
                requiredDailyLeads: 0,
                requiredDailyCases: 0,
                requiredDailyRetainers: 0,
                
                projectedSpend: 0,
                projectedLeads: 0,
                projectedCases: 0,
                projectedRetainers: 0,
                
                insights: [],
                
                async init() {
                    // Load preferences
                    const savedDarkMode = localStorage.getItem('forecastingDarkMode');
                    if (savedDarkMode !== null) {
                        this.darkMode = savedDarkMode === 'true';
                    }
                    
                    // Calculate date info
                    const now = new Date();
                    this.currentMonth = now.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
                    this.currentDayOfMonth = now.getDate();
                    
                    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
                    this.totalDaysInMonth = lastDay.getDate();
                    this.remainingDays = this.totalDaysInMonth - this.currentDayOfMonth;
                    
                    // Load settings and actual data
                    await this.loadSettings();
                    await this.fetchActualData();
                    this.calculatePacing();
                    
                    // Initialize chart
                    this.$nextTick(() => {
                        setTimeout(() => {
                            this.initChart();
                        }, 100);
                    });
                },
                
                toggleDarkMode() {
                    this.darkMode = !this.darkMode;
                    localStorage.setItem('forecastingDarkMode', this.darkMode);
                    this.updateChart();
                },
                
                async loadSettings() {
                    try {
                        const response = await fetch('/api/forecast-settings');
                        const data = await response.json();
                        if (data && Object.keys(data).length > 0) {
                            this.settings = data;
                        }
                    } catch (error) {
                        console.error('Error loading settings:', error);
                    }
                },
                
                async saveSettings() {
                    try {
                        const response = await fetch('/api/forecast-settings', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(this.settings)
                        });
                        
                        if (response.ok) {
                            alert('Settings saved successfully!');
                            this.calculatePacing();
                        }
                    } catch (error) {
                        console.error('Error saving settings:', error);
                        alert('Error saving settings');
                    }
                },
                
                loadDefaults() {
                    // Load default values from the spreadsheet
                    this.settings = {
                        CA: {
                            spend: { weekdayDaily: 36364, weekendDaily: 18182, monthlyTotal: 1000000 },
                            leads: { weekdayDaily: 51, weekendDaily: 26, monthlyTotal: 1428 },
                            cases: { weekdayDaily: 11, weekendDaily: 6, monthlyTotal: 308 },
                            retainers: { weekdayDaily: 13, weekendDaily: 6, monthlyTotal: 350 }
                        },
                        AZ: {
                            spend: { weekdayDaily: 22727, weekendDaily: 11364, monthlyTotal: 500000 },
                            leads: { weekdayDaily: 18, weekendDaily: 9, monthlyTotal: 500 },
                            cases: { weekdayDaily: 4, weekendDaily: 2, monthlyTotal: 110 },
                            retainers: { weekdayDaily: 5, weekendDaily: 2, monthlyTotal: 125 }
                        },
                        GA: {
                            spend: { weekdayDaily: 9091, weekendDaily: 4545, monthlyTotal: 200000 },
                            leads: { weekdayDaily: 11, weekendDaily: 5, monthlyTotal: 310 },
                            cases: { weekdayDaily: 3, weekendDaily: 1, monthlyTotal: 68 },
                            retainers: { weekdayDaily: 4, weekendDaily: 2, monthlyTotal: 80 }
                        },
                        TX: {
                            spend: { weekdayDaily: 0, weekendDaily: 0, monthlyTotal: 0 },
                            leads: { weekdayDaily: 0, weekendDaily: 0, monthlyTotal: 0 },
                            cases: { weekdayDaily: 0, weekendDaily: 0, monthlyTotal: 0 },
                            retainers: { weekdayDaily: 0, weekendDaily: 0, monthlyTotal: 0 }
                        }
                    };
                    
                    // Reset conversion rates to defaults
                    this.conversionRates = {
                        leadToCase: 22,
                        leadToRetainer: 25
                    };
                    
                    this.calculatePacing();
                },
                
                recalculateDailyTargets(state, metric) {
                    // Recalculate daily targets based on monthly total
                    const monthlyTotal = this.settings[state][metric].monthlyTotal;
                    const weekdays = this.getWeekdaysInMonth();
                    const weekends = this.totalDaysInMonth - weekdays;
                    
                    // Assuming 2:1 ratio for weekday:weekend
                    const weekdayDaily = Math.round((monthlyTotal * 0.7) / weekdays);
                    const weekendDaily = Math.round((monthlyTotal * 0.3) / weekends);
                    
                    this.settings[state][metric].weekdayDaily = weekdayDaily;
                    this.settings[state][metric].weekendDaily = weekendDaily;
                },
                
                recalculateTargets(state) {
                    // Auto-calculate cases and retainers based on leads and conversion rates
                    const leads = this.settings[state].leads.monthlyTotal;
                    const spend = this.settings[state].spend.monthlyTotal;
                    
                    // Calculate cases based on lead to case conversion rate
                    const cases = Math.round(leads * (this.conversionRates.leadToCase / 100));
                    this.settings[state].cases.monthlyTotal = cases;
                    
                    // Calculate retainers based on lead to retainer conversion rate
                    const retainers = Math.round(leads * (this.conversionRates.leadToRetainer / 100));
                    this.settings[state].retainers.monthlyTotal = retainers;
                    
                    // Recalculate daily targets for all metrics
                    ['spend', 'leads', 'cases', 'retainers'].forEach(metric => {
                        this.recalculateDailyTargets(state, metric);
                    });
                    
                    this.calculatePacing();
                },
                
                updateCalculations() {
                    // Update all state calculations when conversion rates change
                    ['CA', 'AZ', 'GA', 'TX'].forEach(state => {
                        const leads = this.settings[state].leads.monthlyTotal;
                        
                        // Recalculate cases and retainers
                        this.settings[state].cases.monthlyTotal = Math.round(leads * (this.conversionRates.leadToCase / 100));
                        this.settings[state].retainers.monthlyTotal = Math.round(leads * (this.conversionRates.leadToRetainer / 100));
                        
                        // Update daily targets
                        ['cases', 'retainers'].forEach(metric => {
                            this.recalculateDailyTargets(state, metric);
                        });
                    });
                    
                    this.calculatePacing();
                },
                
                getTotalMonthlyTarget(metric) {
                    return ['CA', 'AZ', 'GA', 'TX'].reduce((total, state) => {
                        return total + (this.settings[state][metric]?.monthlyTotal || 0);
                    }, 0);
                },
                
                getAverageCPL() {
                    const totalSpend = this.getTotalMonthlyTarget('spend');
                    const totalLeads = this.getTotalMonthlyTarget('leads');
                    return totalLeads > 0 ? totalSpend / totalLeads : 0;
                },
                
                getAverageCPA() {
                    const totalSpend = this.getTotalMonthlyTarget('spend');
                    const totalCases = this.getTotalMonthlyTarget('cases');
                    return totalCases > 0 ? totalSpend / totalCases : 0;
                },
                
                getLeadToRetainerRate() {
                    const totalLeads = this.getTotalMonthlyTarget('leads');
                    const totalRetainers = this.getTotalMonthlyTarget('retainers');
                    return totalLeads > 0 ? totalRetainers / totalLeads : 0;
                },
                
                getStateName(state) {
                    const names = {
                        'CA': 'California',
                        'AZ': 'Arizona',
                        'GA': 'Georgia',
                        'TX': 'Texas'
                    };
                    return names[state] || state;
                },
                
                getStateCPL(state) {
                    const spend = this.settings[state].spend.monthlyTotal;
                    const leads = this.settings[state].leads.monthlyTotal;
                    return leads > 0 ? spend / leads : 0;
                },
                
                getStateCPA(state) {
                    const spend = this.settings[state].spend.monthlyTotal;
                    const cases = this.settings[state].cases.monthlyTotal;
                    return cases > 0 ? spend / cases : 0;
                },
                
                getWeekdaysInMonth() {
                    const now = new Date();
                    const year = now.getFullYear();
                    const month = now.getMonth();
                    let weekdays = 0;
                    
                    for (let day = 1; day <= this.totalDaysInMonth; day++) {
                        const date = new Date(year, month, day);
                        const dayOfWeek = date.getDay();
                        if (dayOfWeek !== 0 && dayOfWeek !== 6) {
                            weekdays++;
                        }
                    }
                    return weekdays;
                },
                
                async fetchActualData() {
                    try {
                        // Get current month date range
                        const now = new Date();
                        const startDate = new Date(now.getFullYear(), now.getMonth(), 1);
                        const endDate = new Date();
                        
                        const params = new URLSearchParams({
                            start_date: startDate.toISOString().split('T')[0],
                            end_date: endDate.toISOString().split('T')[0]
                        });
                        
                        const response = await fetch(`/api/forecast-pacing?${params}`);
                        const data = await response.json();
                        
                        if (data.states) {
                            this.actualData = data.states;
                            // Check if we have real data (non-zero values)
                            const hasRealData = Object.values(data.states).some(state => 
                                state.spend > 0 || state.leads > 0 || state.cases > 0 || state.retainers > 0
                            );
                            this.dataSource = hasRealData ? 'Live Data' : 'Demo Data';
                        }
                        
                        // Check API connection status
                        const statusResponse = await fetch('/api/status');
                        const statusData = await statusResponse.json();
                        if (statusData.google_ads_connected && statusData.litify_connected) {
                            this.dataSource = 'Live Data';
                        } else if (statusData.google_ads_connected || statusData.litify_connected) {
                            this.dataSource = 'Partial Live Data';
                        }
                    } catch (error) {
                        console.error('Error fetching actual data:', error);
                        // Use demo data for now
                        this.dataSource = 'Demo Data';
                        this.actualData = {
                            CA: { spend: 450000, leads: 650, cases: 140, retainers: 160 },
                            AZ: { spend: 200000, leads: 180, cases: 40, retainers: 45 },
                            GA: { spend: 75000, leads: 110, cases: 24, retainers: 28 },
                            TX: { spend: 0, leads: 0, cases: 0, retainers: 0 }
                        };
                    }
                },
                
                calculatePacing() {
                    // Calculate totals
                    this.totalTargetSpend = Object.values(this.settings).reduce((sum, state) => 
                        sum + (state.spend?.monthlyTotal || 0), 0);
                    this.totalTargetLeads = Object.values(this.settings).reduce((sum, state) => 
                        sum + (state.leads?.monthlyTotal || 0), 0);
                    this.totalTargetCases = Object.values(this.settings).reduce((sum, state) => 
                        sum + (state.cases?.monthlyTotal || 0), 0);
                    this.totalTargetRetainers = Object.values(this.settings).reduce((sum, state) => 
                        sum + (state.retainers?.monthlyTotal || 0), 0);
                    
                    this.totalActualSpend = Object.values(this.actualData).reduce((sum, state) => 
                        sum + (state.spend || 0), 0);
                    this.totalActualLeads = Object.values(this.actualData).reduce((sum, state) => 
                        sum + (state.leads || 0), 0);
                    this.totalActualCases = Object.values(this.actualData).reduce((sum, state) => 
                        sum + (state.cases || 0), 0);
                    this.totalActualRetainers = Object.values(this.actualData).reduce((sum, state) => 
                        sum + (state.retainers || 0), 0);
                    
                    // Calculate progress percentages
                    const expectedProgress = (this.currentDayOfMonth / this.totalDaysInMonth) * 100;
                    
                    this.spendProgress = this.totalTargetSpend > 0 ? 
                        (this.totalActualSpend / this.totalTargetSpend) * 100 : 0;
                    this.leadsProgress = this.totalTargetLeads > 0 ? 
                        (this.totalActualLeads / this.totalTargetLeads) * 100 : 0;
                    this.casesProgress = this.totalTargetCases > 0 ? 
                        (this.totalActualCases / this.totalTargetCases) * 100 : 0;
                    this.retainersProgress = this.totalTargetRetainers > 0 ? 
                        (this.totalActualRetainers / this.totalTargetRetainers) * 100 : 0;
                    
                    // Determine pacing status
                    this.spendPacingStatus = this.getPacingStatus(this.spendProgress, expectedProgress);
                    this.leadsPacingStatus = this.getPacingStatus(this.leadsProgress, expectedProgress);
                    this.casesPacingStatus = this.getPacingStatus(this.casesProgress, expectedProgress);
                    this.retainersPacingStatus = this.getPacingStatus(this.retainersProgress, expectedProgress);
                    
                    // Calculate daily averages
                    this.dailyAverageSpend = this.currentDayOfMonth > 0 ? 
                        this.totalActualSpend / this.currentDayOfMonth : 0;
                    this.dailyAverageLeads = this.currentDayOfMonth > 0 ? 
                        this.totalActualLeads / this.currentDayOfMonth : 0;
                    this.dailyAverageCases = this.currentDayOfMonth > 0 ? 
                        this.totalActualCases / this.currentDayOfMonth : 0;
                    this.dailyAverageRetainers = this.currentDayOfMonth > 0 ? 
                        this.totalActualRetainers / this.currentDayOfMonth : 0;
                    
                    // Calculate required daily pacing for remaining days
                    if (this.remainingDays > 0) {
                        this.requiredDailySpend = Math.max(0, 
                            (this.totalTargetSpend - this.totalActualSpend) / this.remainingDays);
                        this.requiredDailyLeads = Math.max(0, 
                            (this.totalTargetLeads - this.totalActualLeads) / this.remainingDays);
                        this.requiredDailyCases = Math.max(0, 
                            (this.totalTargetCases - this.totalActualCases) / this.remainingDays);
                        this.requiredDailyRetainers = Math.max(0, 
                            (this.totalTargetRetainers - this.totalActualRetainers) / this.remainingDays);
                    }
                    
                    // Calculate projections
                    this.projectedSpend = this.totalActualSpend + 
                        (this.dailyAverageSpend * this.remainingDays);
                    this.projectedLeads = Math.round(this.totalActualLeads + 
                        (this.dailyAverageLeads * this.remainingDays));
                    this.projectedCases = Math.round(this.totalActualCases + 
                        (this.dailyAverageCases * this.remainingDays));
                    this.projectedRetainers = Math.round(this.totalActualRetainers + 
                        (this.dailyAverageRetainers * this.remainingDays));
                    
                    // Generate insights
                    this.generateInsights();
                },
                
                getPacingStatus(actual, expected) {
                    const diff = actual - expected;
                    if (diff >= 10) return 'Ahead of target';
                    if (diff >= 0) return 'On track';
                    if (diff >= -10) return 'Slightly behind';
                    return 'Behind target';
                },
                
                generateInsights() {
                    this.insights = [];
                    
                    // Spend insights
                    if (this.projectedSpend > this.totalTargetSpend * 1.1) {
                        this.insights.push('Spend is projected to exceed target by more than 10%');
                    } else if (this.projectedSpend < this.totalTargetSpend * 0.9) {
                        this.insights.push('Spend is projected to fall short of target by more than 10%');
                    }
                    
                    // Leads insights
                    if (this.dailyAverageLeads > this.requiredDailyLeads * 1.2) {
                        this.insights.push('Lead generation is significantly outperforming targets');
                    } else if (this.dailyAverageLeads < this.requiredDailyLeads * 0.8) {
                        this.insights.push('Lead generation needs acceleration to meet targets');
                    }
                    
                    // Efficiency insights
                    const currentCPL = this.totalActualSpend / this.totalActualLeads;
                    const targetCPL = this.totalTargetSpend / this.totalTargetLeads;
                    if (currentCPL < targetCPL * 0.9) {
                        this.insights.push(`Cost per lead ($${currentCPL.toFixed(0)}) is better than target`);
                    }
                    
                    // State-specific insights
                    ['CA', 'AZ', 'GA'].forEach(state => {
                        const stateProgress = this.getStateProgress(state, 'spend');
                        const expectedProgress = (this.currentDayOfMonth / this.totalDaysInMonth) * 100;
                        if (Math.abs(stateProgress - expectedProgress) > 15) {
                            this.insights.push(`${state} spend pacing needs attention`);
                        }
                    });
                },
                
                getStateTarget(state, metric) {
                    return this.settings[state]?.[metric]?.monthlyTotal || 0;
                },
                
                getStateActual(state, metric) {
                    return this.actualData[state]?.[metric] || 0;
                },
                
                getStateProgress(state, metric) {
                    const target = this.getStateTarget(state, metric);
                    const actual = this.getStateActual(state, metric);
                    return target > 0 ? (actual / target) * 100 : 0;
                },
                
                getStatePacingStatus(state) {
                    const expectedProgress = (this.currentDayOfMonth / this.totalDaysInMonth) * 100;
                    const actualProgress = this.getStateProgress(state, 'spend');
                    return this.getPacingStatus(actualProgress, expectedProgress);
                },
                
                getStatePacingBadgeClass(state) {
                    const status = this.getStatePacingStatus(state);
                    if (status.includes('Ahead') || status === 'On track') {
                        return 'bg-green-100 text-green-800 dark-mode:bg-green-900 dark-mode:text-green-300';
                    } else if (status.includes('Slightly')) {
                        return 'bg-yellow-100 text-yellow-800 dark-mode:bg-yellow-900 dark-mode:text-yellow-300';
                    } else {
                        return 'bg-red-100 text-red-800 dark-mode:bg-red-900 dark-mode:text-red-300';
                    }
                },
                
                getSpendPacingClass() {
                    return this.getPacingClass(this.spendPacingStatus);
                },
                
                getLeadsPacingClass() {
                    return this.getPacingClass(this.leadsPacingStatus);
                },
                
                getCasesPacingClass() {
                    return this.getPacingClass(this.casesPacingStatus);
                },
                
                getRetainersPacingClass() {
                    return this.getPacingClass(this.retainersPacingStatus);
                },
                
                getPacingClass(status) {
                    if (status.includes('Ahead') || status === 'On track') return 'pacing-good';
                    if (status.includes('Slightly')) return 'pacing-warning';
                    return 'pacing-danger';
                },
                
                getProgressBarClass(progress) {
                    const expectedProgress = (this.currentDayOfMonth / this.totalDaysInMonth) * 100;
                    const diff = progress - expectedProgress;
                    
                    if (diff >= 0) return 'bg-green-500';
                    if (diff >= -10) return 'bg-yellow-500';
                    return 'bg-red-500';
                },
                
                initChart() {
                    const ctx = document.getElementById('trendChart');
                    if (!ctx) return;
                    
                    // Generate sample daily data for the month
                    const days = [];
                    const spendData = [];
                    const leadsData = [];
                    
                    for (let i = 1; i <= this.currentDayOfMonth; i++) {
                        days.push(`Day ${i}`);
                        spendData.push(Math.round(this.totalActualSpend / this.currentDayOfMonth * i));
                        leadsData.push(Math.round(this.totalActualLeads / this.currentDayOfMonth * i));
                    }
                    
                    this.chartInstance = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: days,
                            datasets: [
                                {
                                    label: 'Spend',
                                    data: spendData,
                                    borderColor: '#3b82f6',
                                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                                    yAxisID: 'y',
                                    tension: 0.3
                                },
                                {
                                    label: 'Leads',
                                    data: leadsData,
                                    borderColor: '#10b981',
                                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                    yAxisID: 'y1',
                                    tension: 0.3
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            interaction: {
                                mode: 'index',
                                intersect: false,
                            },
                            scales: {
                                y: {
                                    type: 'linear',
                                    display: true,
                                    position: 'left',
                                    title: {
                                        display: true,
                                        text: 'Spend ($)'
                                    },
                                    ticks: {
                                        callback: function(value) {
                                            return '$' + value.toLocaleString();
                                        }
                                    }
                                },
                                y1: {
                                    type: 'linear',
                                    display: true,
                                    position: 'right',
                                    title: {
                                        display: true,
                                        text: 'Leads'
                                    },
                                    grid: {
                                        drawOnChartArea: false,
                                    },
                                }
                            },
                            plugins: {
                                legend: {
                                    position: 'top',
                                },
                                tooltip: {
                                    callbacks: {
                                        label: function(context) {
                                            let label = context.dataset.label || '';
                                            if (label) {
                                                label += ': ';
                                            }
                                            if (context.datasetIndex === 0) {
                                                label += '$' + context.parsed.y.toLocaleString();
                                            } else {
                                                label += context.parsed.y.toLocaleString();
                                            }
                                            return label;
                                        }
                                    }
                                }
                            }
                        }
                    });
                },
                
                updateChart() {
                    if (this.chartInstance) {
                        this.chartInstance.destroy();
                        this.$nextTick(() => {
                            this.initChart();
                        });
                    }
                },
                
                formatCurrency(value) {
                    return new Intl.NumberFormat('en-US', {
                        style: 'currency',
                        currency: 'USD',
                        minimumFractionDigits: 0,
                        maximumFractionDigits: 0
                    }).format(value || 0);
                },
                
                formatNumber(value) {
                    return Math.round(value || 0).toLocaleString();
                },
                
                formatPercentage(value) {
                    return ((value || 0) * 100).toFixed(1) + '%';
                }
            }
        }

//ANNUAL ANALYTICS

 function annualAnalyticsApp() {
    return {
        selectedYear: new Date().getFullYear(),
        availableYears: [],
        monthlyData: [],
        annualSummary: {
            total_spend: 0,
            total_leads: 0,
            total_cases: 0,
            total_retainers: 0,
            total_in_practice: 0,
            total_unqualified: 0,
            avg_cpl: 0,
            avg_cpa: 0,
            avg_cpr: 0,
            avg_conversion_rate: 0
        },
        performanceAnalysis: {},
        dataSource: 'Demo Data',
        darkMode: false,
        isLoading: true,
        trendChart: null,
        conversionChart: null,
        showModal: false,
        selectedMonth: null,
        isRefreshing: false,
        
        async init() {
            // Load preferences
            const savedDarkMode = localStorage.getItem('annualDarkMode');
            if (savedDarkMode !== null) {
                this.darkMode = savedDarkMode === 'true';
            }
            
            // Set available years (last 3 years)
            const currentYear = new Date().getFullYear();
            this.availableYears = [currentYear, currentYear - 1, currentYear - 2];
            
            // Fetch data with force refresh on initial load
            await this.fetchYearData(true);
            
            // Initialize charts after data loads
            this.$nextTick(() => {
                setTimeout(() => {
                    this.initCharts();
                }, 100);
            });
        },
        
        toggleDarkMode() {
            this.darkMode = !this.darkMode;
            localStorage.setItem('annualDarkMode', this.darkMode);
            this.updateCharts();
        },
        
        async fetchYearData(forceRefresh = false) {
            this.isLoading = true;
            this.isRefreshing = forceRefresh;
            
            try {
                const params = new URLSearchParams({
                    year: this.selectedYear,
                    include_spam: false,
                    include_abandoned: false,
                    include_duplicate: false,
                    // Add timestamp to prevent caching
                    _t: Date.now()
                });
                
                // Add cache-busting headers
                const response = await fetch(`/api/annual-data?${params}`, {
                    method: 'GET',
                    headers: {
                        'Cache-Control': 'no-cache',
                        'Pragma': 'no-cache'
                    }
                });
                const data = await response.json();
                
                // Log the data for debugging
                console.log('Annual data received:', data);
                console.log('Data source:', data.data_source);
                console.log('Monthly data count:', data.monthly_data?.length);
                
                this.monthlyData = data.monthly_data || [];
                this.annualSummary = data.annual_summary || this.annualSummary;
                this.performanceAnalysis = data.performance_analysis || {};
                
                // Update data source to show it includes ALL campaigns
                if (data.data_source?.includes('Live Data')) {
                    this.dataSource = data.data_source + ' (All Campaigns)';
                } else {
                    this.dataSource = data.data_source || 'Demo Data';
                }
                
                this.isLoading = false;
                this.isRefreshing = false;
                
                // Update charts if they exist
                if (this.trendChart || this.conversionChart) {
                    this.updateCharts();
                } else {
                    // Initialize charts if they don't exist yet
                    this.$nextTick(() => {
                        setTimeout(() => {
                            this.initCharts();
                        }, 100);
                    });
                }
                
            } catch (error) {
                console.error('Error fetching annual data:', error);
                this.isLoading = false;
                this.isRefreshing = false;
            }
        },
        
        async refreshData() {
            await this.fetchYearData(true);
        },
        
        showMonthDetail(month) {
            this.selectedMonth = month;
            this.showModal = true;
        },
        
        initCharts() {
            // Destroy existing charts if they exist
            if (this.trendChart) {
                this.trendChart.destroy();
                this.trendChart = null;
            }
            if (this.conversionChart) {
                this.conversionChart.destroy();
                this.conversionChart = null;
            }
            
            // Trend Chart
            const trendCtx = document.getElementById('trendChart');
            if (trendCtx) {
                const months = this.monthlyData.filter(m => !m.is_future).map(m => m.month.substring(0, 3));
                const spendData = this.monthlyData.filter(m => !m.is_future).map(m => m.summary.spend);
                const leadsData = this.monthlyData.filter(m => !m.is_future).map(m => m.summary.leads);
                
                this.trendChart = new Chart(trendCtx, {
                    type: 'line',
                    data: {
                        labels: months,
                        datasets: [
                            {
                                label: 'Spend',
                                data: spendData,
                                borderColor: '#6366f1',
                                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                                yAxisID: 'y',
                                tension: 0.3
                            },
                            {
                                label: 'Leads',
                                data: leadsData,
                                borderColor: '#10b981',
                                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                yAxisID: 'y1',
                                tension: 0.3
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            mode: 'index',
                            intersect: false
                        },
                        scales: {
                            y: {
                                type: 'linear',
                                display: true,
                                position: 'left',
                                ticks: {
                                    callback: function(value) {
                                        return '$' + (value / 1000).toFixed(0) + 'k';
                                    }
                                }
                            },
                            y1: {
                                type: 'linear',
                                display: true,
                                position: 'right',
                                grid: {
                                    drawOnChartArea: false
                                }
                            }
                        }
                    }
                });
            }
            
            // Conversion Rate Chart
            const conversionCtx = document.getElementById('conversionChart');
            if (conversionCtx) {
                const months = this.monthlyData.filter(m => !m.is_future).map(m => m.month.substring(0, 3));
                const conversionData = this.monthlyData.filter(m => !m.is_future).map(m => m.summary.conversion_rate);
                
                this.conversionChart = new Chart(conversionCtx, {
                    type: 'bar',
                    data: {
                        labels: months,
                        datasets: [{
                            label: 'Conversion Rate (%)',
                            data: conversionData,
                            backgroundColor: '#a855f7'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            }
                        }
                    }
                });
            }
        },
        
        updateCharts() {
            if (this.trendChart || this.conversionChart) {
                this.initCharts();
            }
        },
        
        formatCurrency(value) {
            return '$' + (value || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
        },
        
        formatNumber(value) {
            return Math.round(value || 0).toLocaleString();
        },
        
        formatPercentage(value) {
            return value.toFixed(1) + '%';
        },
        
        async exportToExcel() {
            // Implementation for Excel export
            console.log('Exporting to Excel...');
            // Add your export logic here
        }
    }
}
