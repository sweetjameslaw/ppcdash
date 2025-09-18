// Dashboard App - jQuery Version with State Filters and Sorting
$(document).ready(function() {
    // State Management
    const state = {
        darkMode: localStorage.getItem('darkMode') === 'true',
        sidebarCollapsed: localStorage.getItem('sidebarCollapsed') === 'true',
        colorCodingDisabled: localStorage.getItem('colorCodingDisabled') === 'true',  // NEW
        dateRangePreset: 'today',
        startDate: '',
        endDate: '',
        includeSpam: false,
        includeAbandoned: false,
        includeDuplicate: false,
        isLoading: false,
        isRefreshing: false,
        dashboardData: {},
        litifyLeads: [],
        filteredLitifyLeads: [],
        litifyBucketFilter: 'all',
        showLitifyDetail: true,
        availableBuckets: [],
        stateFilter: 'all',
        charts: {
            performance: null,
            cost: null
        }
    };

    // Initialize the app
    init();

    function init() {
        console.log('Initializing dashboard...');
        setupEventListeners();
        applyInitialSettings();
        setDateRange('today');
        checkApiStatus();
        fetchData();
    }

    // Apply initial settings
    function applyInitialSettings() {
        if (state.darkMode) {
            $('body').addClass('dark-mode');
            $('#darkModeIcon').removeClass('fa-moon').addClass('fa-sun');
            $('#darkModeText').text('Light Mode');
        }
        
        if (state.sidebarCollapsed) {
            $('#sidebar').addClass('collapsed');
            $('#mainContent').addClass('expanded');
            $('#sidebarIcon').removeClass('fa-chevron-left').addClass('fa-chevron-right');
        }
        
        // Apply color coding setting
        if (state.colorCodingDisabled) {
            $('#disableColorCoding').prop('checked', true);
            $('#colorCodingStatus').show();
        }
    }

    // Setup all event listeners
    function setupEventListeners() {
        $('#sidebarToggle').on('click', toggleSidebar);
        $('#darkModeToggle').on('click', toggleDarkMode);
        
        // NEW: Color coding toggle listener
        $('#disableColorCoding').on('change', function() {
            state.colorCodingDisabled = $(this).prop('checked');
            localStorage.setItem('colorCodingDisabled', state.colorCodingDisabled);
            
            if (state.colorCodingDisabled) {
                $('#colorCodingStatus').show();
            } else {
                $('#colorCodingStatus').hide();
            }
            
            // Re-render tables with new color settings
            renderCampaignTable();
            if (state.litifyLeads && state.litifyLeads.length > 0) {
                renderLitifyTable();
            }
        });
        
        $(document).on('click', '.date-btn', function() {
            const range = $(this).data('range');
            if (range) {
                setDateRange(range);
            }
        });
        
        $(document).on('click', '.state-filter-btn', function() {
            const selectedState = $(this).data('state');
            $('.state-filter-btn').removeClass('active');
            $(this).addClass('active');
            state.stateFilter = selectedState;
            renderCampaignTable();
        });
        
        $('#refreshBtn').on('click', refreshData);
        $('#retryBtn').on('click', function() {
            fetchData();
        });
        $('#exportBtn').on('click', exportData);
        
        $('#includeSpam').on('change', function() {
            state.includeSpam = $(this).prop('checked');
            updateExclusionDisplay();
            fetchData();
        });
        
        $('#includeAbandoned').on('change', function() {
            state.includeAbandoned = $(this).prop('checked');
            updateExclusionDisplay();
            fetchData();
        });
        
        $('#includeDuplicate').on('change', function() {
            state.includeDuplicate = $(this).prop('checked');
            updateExclusionDisplay();
            fetchData();
        });
        
        $('#clearExclusionBtn').on('click', clearExclusionFilters);
        $('#litifyBucketFilter').on('change', filterLitifyLeads);
        $('#litifyToggle').on('click', toggleLitifyDetail);
    }

    function toggleSidebar() {
        state.sidebarCollapsed = !state.sidebarCollapsed;
        
        if (state.sidebarCollapsed) {
            $('#sidebar').addClass('collapsed');
            $('#mainContent').addClass('expanded');
            $('#sidebarIcon').removeClass('fa-chevron-left').addClass('fa-chevron-right');
        } else {
            $('#sidebar').removeClass('collapsed');
            $('#mainContent').removeClass('expanded');
            $('#sidebarIcon').removeClass('fa-chevron-right').addClass('fa-chevron-left');
        }
        
        localStorage.setItem('sidebarCollapsed', state.sidebarCollapsed);
        
        setTimeout(() => {
            if (state.charts.performance) state.charts.performance.resize();
            if (state.charts.cost) state.charts.cost.resize();
        }, 300);
    }

    function toggleDarkMode() {
        state.darkMode = !state.darkMode;
        
        if (state.darkMode) {
            $('body').addClass('dark-mode');
            $('#darkModeIcon').removeClass('fa-moon').addClass('fa-sun');
            $('#darkModeText').text('Light Mode');
        } else {
            $('body').removeClass('dark-mode');
            $('#darkModeIcon').removeClass('fa-sun').addClass('fa-moon');
            $('#darkModeText').text('Dark Mode');
        }
        
        localStorage.setItem('darkMode', state.darkMode);
    }

    function setDateRange(preset) {
        state.dateRangePreset = preset;
        const today = new Date();
        let start, end;
        
        switch(preset) {
            case 'today':
                start = end = formatDate(today);
                break;
            case 'yesterday':
                const yesterday = new Date(today);
                yesterday.setDate(yesterday.getDate() - 1);
                start = end = formatDate(yesterday);
                break;
            case 'week':
                const weekAgo = new Date(today);
                weekAgo.setDate(weekAgo.getDate() - 6);
                start = formatDate(weekAgo);
                end = formatDate(today);
                break;
            case 'month':
                const monthAgo = new Date(today);
                monthAgo.setDate(monthAgo.getDate() - 29);
                start = formatDate(monthAgo);
                end = formatDate(today);
                break;
            case 'custom':
                console.log('Custom date range not implemented yet');
                return;
        }
        
        state.startDate = start;
        state.endDate = end;
        
        $('.date-btn').removeClass('active');
        $(`.date-btn[data-range="${preset}"]`).addClass('active');
        updateDateRangeText();
        
        fetchData();
    }

    function updateDateRangeText() {
        let text = '';
        if (state.startDate === state.endDate) {
            text = formatDisplayDate(state.startDate);
        } else {
            text = `${formatDisplayDate(state.startDate)} - ${formatDisplayDate(state.endDate)}`;
        }
        $('#dateRangeText').text(text);
    }

    function checkApiStatus() {
        $.ajax({
            url: '/api/status',
            method: 'GET',
            success: function(response) {
                const googleStatus = response.google_ads_connected;
                const litifyStatus = response.litify_connected;
                
                $('#googleAdsStatus')
                    .removeClass('bg-amber-500 bg-green-500 bg-red-500')
                    .addClass(googleStatus ? 'bg-green-500' : 'bg-red-500');
                
                $('#litifyStatus')
                    .removeClass('bg-amber-500 bg-green-500 bg-red-500')
                    .addClass(litifyStatus ? 'bg-green-500' : 'bg-red-500');
            }
        });
    }

    function fetchData(forceRefresh = false) {
        if (state.isLoading) return;
        
        state.isLoading = true;
        
        $('#loadingState').show();
        $('#errorState').hide();
        $('#dashboardContent').hide();
        
        $.ajax({
            url: '/api/dashboard-data',
            method: 'GET',
            data: {
                start_date: state.startDate,
                end_date: state.endDate,
                include_spam: state.includeSpam,
                include_abandoned: state.includeAbandoned,
                include_duplicate: state.includeDuplicate,
                force_refresh: forceRefresh,
                _t: new Date().getTime()  // Add cache buster
            },
            success: function(response) {
                console.log('Raw response leads:', response.litify_leads);
                
                state.dashboardData = response;
                
                // Filter litify leads to only show those created in period
                // Use the count_for_leads flag from backend
                state.litifyLeads = (response.litify_leads || []).filter(lead => {
                    // Only include leads that were created in this period
                    return lead.count_for_leads === true;
                });
                
                console.log('Filtered leads (created in period only):', state.litifyLeads);
                console.log('Date range:', state.startDate, 'to', state.endDate);
                
                state.availableBuckets = response.available_buckets || [];
                
                // Add leads summary section above the table
                const leadsSummary = calculateLeadsSummary();
                renderLeadsSummary(leadsSummary);
                
                updateExclusionCounts();
                filterLitifyLeads();
                renderDashboard();
                
                $('#loadingState').hide();
                $('#dashboardContent').show();
                
                if (forceRefresh) {
                    $('#refreshIcon').removeClass('fa-spin');
                    const $refreshBtn = $('#refreshBtn');
                    const $refreshIcon = $('#refreshIcon');
                    
                    $refreshIcon.removeClass('fa-sync-alt fa-spin').addClass('fa-check');
                    $refreshBtn.removeClass('btn-primary').addClass('btn-success');
                    
                    setTimeout(() => {
                        $refreshIcon.removeClass('fa-check').addClass('fa-sync-alt');
                        $refreshBtn.removeClass('btn-success').addClass('btn-primary');
                    }, 2000);
                }
            },
            error: function(xhr, status, error) {
                let errorMessage = 'Failed to load dashboard data. Please try again.';
                
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (response.error) {
                        errorMessage = response.error;
                    }
                } catch (e) {}
                
                $('#errorMessage').text(errorMessage);
                $('#loadingState').hide();
                $('#errorState').show();
            },
            complete: function() {
                state.isLoading = false;
                state.isRefreshing = false;
                if ($('#refreshIcon').hasClass('fa-sync-alt')) {
                    $('#refreshIcon').removeClass('fa-spin');
                }
            }
        });
    }

    function calculateLeadsSummary() {
        // Use the filtered leads that are actually displayed
        const leads = state.filteredLitifyLeads || [];
        const summary = {
            created_today: 0,
            converted_today: 0,
            total: leads.length
        };
        
        leads.forEach(lead => {
            // These are all created in the selected period now
            summary.created_today++;
            
            if (lead.converted_today || (lead.is_converted && lead.conversion_date === state.endDate)) {
                summary.converted_today++;
            }
        });
        
        return summary;
    }

    function renderLeadsSummary(summary) {
        // This will be inserted into the litify section header
        const summaryHtml = `
            <!-- 
                <div class="flex items-center space-x-4 text-sm">
                <span class="px-2 py-1 bg-blue-100 text-blue-800 rounded">
                    <i class="fas fa-plus-circle mr-1"></i>
                    ${summary.created_today} New Today
                </span>
                <span class="px-2 py-1 bg-green-100 text-green-800 rounded">
                    <i class="fas fa-check-circle mr-1"></i>
                    ${summary.converted_today} Converted Today
                </span>
                <span class="px-2 py-1 bg-gray-100 text-gray-800 rounded">
                    <i class="fas fa-list mr-1"></i>
                    ${summary.total} Total
                </span>
            </div>
            -->
        `;
        
        // Update the litify section description with summary
        const existingText = $('#litifyLeadsCount').parent().html();
        if (!existingText.includes('New Today')) {
            $('#litifyLeadsCount').parent().append(summaryHtml);
        }
    }

    function refreshData() {
        if (state.isRefreshing) return;
        state.isRefreshing = true;
        $('#refreshIcon').addClass('fa-spin');
        fetchData(true);
    }

    function updateExclusionCounts() {
        const excluded = state.dashboardData.excluded_lead_counts || {};
        $('#spamCount').text(excluded.spam || 0);
        $('#abandonedCount').text(excluded.abandoned || 0);
        $('#duplicateCount').text(excluded.duplicate || 0);
    }

    function updateExclusionDisplay() {
        const hasFilters = state.includeSpam || state.includeAbandoned || state.includeDuplicate;
        
        if (hasFilters) {
            const filters = [];
            if (state.includeSpam) filters.push('Spam');
            if (state.includeAbandoned) filters.push('Abandoned');
            if (state.includeDuplicate) filters.push('Duplicate');
            
            $('#exclusionList').text(filters.join(', '));
            $('#exclusionText').show();
            $('#exclusionAlert').show();
            
            const excluded = state.dashboardData.excluded_lead_counts || {};
            let count = 0;
            if (state.includeSpam) count += excluded.spam || 0;
            if (state.includeAbandoned) count += excluded.abandoned || 0;
            if (state.includeDuplicate) count += excluded.duplicate || 0;
            $('#includedCount').text(count);
        } else {
            $('#exclusionText').hide();
            $('#exclusionAlert').hide();
        }
        
        updateFilterText();
    }

    function updateFilterText() {
        const filters = [];
        if (state.includeSpam) filters.push('Spam');
        if (state.includeAbandoned) filters.push('Abandoned');
        if (state.includeDuplicate) filters.push('Duplicate');
        
        if (filters.length > 0) {
            $('#filterText').text(`Including: ${filters.join(', ')}`);
        } else {
            $('#filterText').text('Standard filters');
        }
    }

    function clearExclusionFilters() {
        state.includeSpam = false;
        state.includeAbandoned = false;
        state.includeDuplicate = false;
        
        $('#includeSpam, #includeAbandoned, #includeDuplicate').prop('checked', false);
        updateExclusionDisplay();
        fetchData();
    }

    function filterLitifyLeads() {
        const filter = $('#litifyBucketFilter').val() || 'all';
        state.litifyBucketFilter = filter;
        
        // Start with all leads
        let filtered = state.litifyLeads;
        
        // Filter by date range AND the count_for_leads flag
        // This ensures we only show leads that were actually created in the period
        filtered = filtered.filter(lead => {
            // First check if this lead should be counted (created in period)
            if (!lead.count_for_leads) {
                return false;  // Skip leads from previous periods
            }
            
            if (!lead.created_date) return false;
            
            // Parse the created date as a proper Date object
            const createdDate = new Date(lead.created_date);
            
            // Convert to Pacific Time string in YYYY-MM-DD format
            const createdDatePT = createdDate.toLocaleDateString('en-CA', {
                timeZone: 'America/Los_Angeles'
            }); // en-CA gives YYYY-MM-DD format
            
            // Compare to our selected date range
            return createdDatePT >= state.startDate && createdDatePT <= state.endDate;
        });
        
        // Then apply bucket filter if needed
        if (filter !== 'all') {
            filtered = filtered.filter(lead => lead.bucket === filter);
            $('#litifyBucketText').html(` in <span class="font-medium text-gray-700 dark-mode:text-gray-300">${filter}</span>`);
        } else {
            $('#litifyBucketText').text('');
        }
        
        state.filteredLitifyLeads = filtered;
        $('#litifyLeadsCount').text(state.filteredLitifyLeads.length);
        renderLitifyTable();
    }

    function toggleLitifyDetail() {
        state.showLitifyDetail = !state.showLitifyDetail;
        
        if (state.showLitifyDetail) {
            $('#litifyDetail').slideDown();
            $('#litifyToggleIcon').removeClass('fa-chevron-down').addClass('fa-chevron-up');
            renderLitifyTable();
        } else {
            $('#litifyDetail').slideUp();
            $('#litifyToggleIcon').removeClass('fa-chevron-up').addClass('fa-chevron-down');
        }
    }

    function renderDashboard() {
        renderSummaryCards();
        renderCampaignTable();
        renderCharts();
        updateKeyInsights();
        
        if (state.litifyLeads && state.litifyLeads.length > 0) {
            $('#litifySection').show();
            $('#litifyDetail').show();
            $('#litifyToggleIcon').removeClass('fa-chevron-down').addClass('fa-chevron-up');
            updateBucketFilter();
            $('#litifyLeadsCount').text(state.filteredLitifyLeads.length);
            renderLitifyTable();
        } else {
            $('#litifySection').hide();
        }
    }

    function renderSummaryCards() {
        const buckets = state.dashboardData.buckets || [];
        
        const totals = {
            spend: 0,
            leads: 0,
            cases: 0,
            retainers: 0,
            inPractice: 0
        };
        
        buckets.forEach(bucket => {
            if (!bucket.name.includes('Youtube') && !bucket.name.includes('Crisp')) {
                totals.spend += bucket.cost || 0;
                totals.leads += bucket.leads || 0;
                totals.cases += bucket.cases || 0;
                totals.retainers += bucket.retainers || 0;
                totals.inPractice += bucket.inPractice || 0;
            }
        });
        
        const avgCPL = totals.leads > 0 ? totals.spend / totals.leads : 0;
        const avgCPA = totals.cases > 0 ? totals.spend / totals.cases : 0;
        const avgCPR = totals.retainers > 0 ? totals.spend / totals.retainers : 0;
        const convRate = totals.inPractice > 0 ? (totals.retainers / totals.inPractice) : 0;
        
        const cards = `
            <div class="metric-card">
                <div class="metric-label">Ad Spend</div>
                <div class="metric-value">${formatCurrency(totals.spend)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Leads</div>
                <div class="metric-value text-green-600">${formatNumber(totals.leads)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">CPL</div>
                <div class="metric-value">${formatCurrency(avgCPL)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Cases</div>
                <div class="metric-value text-blue-600">${formatNumber(totals.cases)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">CPA</div>
                <div class="metric-value">${formatCurrency(avgCPA)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Retainers</div>
                <div class="metric-value text-purple-600">${formatNumber(totals.retainers)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">CPR</div>
                <div class="metric-value">${formatCurrency(avgCPR)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Conv Rate</div>
                <div class="metric-value">${formatPercentage(convRate)}</div>
            </div>
        `;
        $('#summaryCards').html(cards);
    }

    // MODIFIED: Now respects the colorCodingDisabled state
    function getMetricColorClass(value, type, isText = true) {
        // If color coding is disabled, return empty string
        if (state.colorCodingDisabled) {
            return '';
        }
        
        const prefix = isText ? 'text-' : 'bg-';
        
        switch(type) {
            case 'cpl':
                if (value <= 800) return prefix + 'green-600';
                if (value <= 1200) return prefix + 'yellow-600';
                return prefix + 'red-600';
            case 'cpa':
                if (value <= 3000) return prefix + 'green-600';
                if (value <= 5000) return prefix + 'yellow-600';
                return prefix + 'red-600';
            case 'cpr':
                if (value <= 4000) return prefix + 'green-600';
                if (value <= 6000) return prefix + 'yellow-600';
                return prefix + 'red-600';
            case 'conversion':
                if (value >= 0.25) return prefix + 'green-600';
                if (value >= 0.15) return prefix + 'yellow-600';
                return prefix + 'red-600';
            case 'inpractice':
                if (value >= 0.8) return prefix + 'green-600';
                if (value >= 0.6) return prefix + 'yellow-600';
                return prefix + 'red-600';
            case 'unqualified':
                if (value <= 0.2) return prefix + 'green-600';
                if (value <= 0.35) return prefix + 'yellow-600';
                return prefix + 'red-600';
            default:
                return '';
        }
    }

    function getFullStateName(abbr) {
        const states = {
            'CA': 'California',
            'AZ': 'Arizona', 
            'GA': 'Georgia',
            'TX': 'Texas'
        };
        return states[abbr] || abbr;
    }

    function renderCampaignTable() {
        const buckets = state.dashboardData.buckets || [];
        
        // Filter by state if needed
        let filteredBuckets = buckets;
        if (state.stateFilter !== 'all') {
            filteredBuckets = buckets.filter(bucket => {
                return bucket.name.includes(state.stateFilter) || 
                       bucket.name.includes(getFullStateName(state.stateFilter));
            });
        }
        
        // Render header
        const headerHtml = `
            <th class="table-cell text-left">Bucket</th>
            <th class="table-cell text-right">Spend</th>
            <th class="table-cell text-right">Leads</th>
            <th class="table-cell text-right">In Practice</th>
            <th class="table-cell text-right">In Practice %</th>
            <th class="table-cell text-right">Unqualified</th>
            <th class="table-cell text-right">Unqualified %</th>
            <th class="table-cell text-right">CPL</th>
            <th class="table-cell text-right">Cases</th>
            <th class="table-cell text-right">CPA</th>
            <th class="table-cell text-right">Retainers</th>
            <th class="table-cell text-right">Pending</th>
           <!--  <th class="table-cell text-right">All Retainers</th> --> 
            <th class="table-cell text-right">CPR</th>
            <th class="table-cell text-right">Conv %</th>
        `;
        $('#tableHeader').html(headerHtml);
        
        // Sort buckets by state, then by type
        const sortedBuckets = filteredBuckets.sort((a, b) => {
            // Extract state from bucket name
            const getState = (name) => {
                if (name.includes('California') || name.includes('CA')) return 1;
                if (name.includes('Arizona') || name.includes('AZ')) return 2;
                if (name.includes('Georgia') || name.includes('GA')) return 3;
                if (name.includes('Texas') || name.includes('TX')) return 4;
                return 5;
            };
            
            // Extract type from bucket name
            const getType = (name) => {
                if (name.toLowerCase().includes('prospecting')) return 1;
                if (name.toLowerCase().includes('lsa')) return 2;
                if (name.toLowerCase().includes('brand')) return 3;
                return 4;
            };
            
            const stateA = getState(a.name);
            const stateB = getState(b.name);
            
            if (stateA !== stateB) {
                return stateA - stateB;
            }
            
            return getType(a.name) - getType(b.name);
        });
        
        // Render body
        let bodyHtml = '';
        let totalRow = {
            spend: 0,
            leads: 0,
            inPractice: 0,
            unqualified: 0,
            cases: 0,
            retainers: 0,
            pendingRetainers: 0,
            totalRetainers: 0
        };
        
        // Separate YouTube/Crisp bucket
        let youtubeBucket = null;
        
        sortedBuckets.forEach(bucket => {
            if (true) {
                // Check if this is Crisp/Youtube
                if (bucket.name.includes('Youtube') || bucket.name.includes('Crisp')) {
                    youtubeBucket = bucket;
                } else {
                    // Add to totals
                    totalRow.spend += bucket.cost || 0;
                    totalRow.leads += bucket.leads || 0;
                    totalRow.inPractice += bucket.inPractice || 0;
                    totalRow.unqualified += bucket.unqualified || 0;
                    totalRow.cases += bucket.cases || 0;
                    totalRow.retainers += bucket.retainers || 0;
                    totalRow.pendingRetainers += bucket.pendingRetainers || 0;
                    // totalRow.totalRetainers += bucket.totalRetainers || 0;
                    
                    // Apply color coding (now respects disabled state)
                    const cplColor = getMetricColorClass(bucket.costPerLead, 'cpl');
                    const cpaColor = getMetricColorClass(bucket.cpa, 'cpa');
                    const cprColor = getMetricColorClass(bucket.costPerRetainer, 'cpr');
                    const convColor = getMetricColorClass(bucket.conversionRate, 'conversion');
                    const inPracticeColor = getMetricColorClass(bucket.inPracticePercent, 'inpractice');
                    const unqualifiedColor = getMetricColorClass(bucket.unqualifiedPercent, 'unqualified');
                    
                    bodyHtml += `
                        <tr class="table-row">
                            <td class="table-cell font-medium">${bucket.name}</td>
                            <td class="table-cell text-right">${formatCurrency(bucket.cost)}</td>
                            <td class="table-cell text-center">${formatNumber(bucket.leads)}</td>
                            <td class="table-cell text-center">${formatNumber(bucket.inPractice)}</td>
                            <td class="table-cell text-center ${inPracticeColor}">${formatPercentage(bucket.inPracticePercent)}</td>
                            <td class="table-cell text-center">${formatNumber(bucket.unqualified)}</td>
                            <td class="table-cell text-center ${unqualifiedColor}">${formatPercentage(bucket.unqualifiedPercent)}</td>
                            <td class="table-cell text-center ${cplColor} font-semibold">${formatCurrency(bucket.costPerLead)}</td>
                            <td class="table-cell text-center">${formatNumber(bucket.cases)}</td>
                            <td class="table-cell text-center ${cpaColor} font-semibold">${formatCurrency(bucket.cpa)}</td>
                            <td class="table-cell text-center">${formatNumber(bucket.retainers)}</td>
                            <td class="table-cell text-center">${formatNumber(bucket.pendingRetainers || 0)}</td>
                            <!-- <td class="table-cell text-center font-semibold">${formatNumber(bucket.totalRetainers || bucket.retainers)}</td> -->
                            <td class="table-cell text-right ${cprColor} font-semibold">${formatCurrency(bucket.costPerRetainer)}</td>
                            <td class="table-cell text-right ${convColor} font-semibold">${formatPercentage(bucket.conversionRate)}</td>
                        </tr>
                    `;
                }
            }
        });
        
        // Add total row (excluding YouTube)
        if (bodyHtml) {
            const totalCPL = totalRow.leads > 0 ? totalRow.spend / totalRow.leads : 0;
            const totalCPA = totalRow.cases > 0 ? totalRow.spend / totalRow.cases : 0;
            const totalCPR = totalRow.retainers > 0 ? totalRow.spend / totalRow.retainers : 0;
            const totalConv = totalRow.inPractice > 0 ? totalRow.retainers / totalRow.inPractice : 0;
            const totalInPracticePct = totalRow.leads > 0 ? totalRow.inPractice / totalRow.leads : 0;
            const totalUnqualifiedPct = totalRow.inPractice > 0 ? totalRow.unqualified / totalRow.inPractice : 0;
            
            // Apply color coding to totals (now respects disabled state)
            const totalCplColor = getMetricColorClass(totalCPL, 'cpl');
            const totalCpaColor = getMetricColorClass(totalCPA, 'cpa');
            const totalCprColor = getMetricColorClass(totalCPR, 'cpr');
            const totalConvColor = getMetricColorClass(totalConv, 'conversion');
            const totalInPracticeColor = getMetricColorClass(totalInPracticePct, 'inpractice');
            const totalUnqualifiedColor = getMetricColorClass(totalUnqualifiedPct, 'unqualified');
            
            bodyHtml += `
                <tr class="table-row font-bold bg-gray-100 dark-mode:bg-gray-800">
                    <td class="table-cell">Total (excl. YouTube)</td>
                    <td class="table-cell text-right">${formatCurrency(totalRow.spend)}</td>
                    <td class="table-cell text-right">${formatNumber(totalRow.leads)}</td>
                    <td class="table-cell text-right">${formatNumber(totalRow.inPractice)}</td>
                    <td class="table-cell text-right ${totalInPracticeColor}">${formatPercentage(totalInPracticePct)}</td>
                    <td class="table-cell text-right">${formatNumber(totalRow.unqualified)}</td>
                    <td class="table-cell text-right ${totalUnqualifiedColor}">${formatPercentage(totalUnqualifiedPct)}</td>
                    <td class="table-cell text-right ${totalCplColor}">${formatCurrency(totalCPL)}</td>
                    <td class="table-cell text-right">${formatNumber(totalRow.cases)}</td>
                    <td class="table-cell text-right ${totalCpaColor}">${formatCurrency(totalCPA)}</td>
                    <td class="table-cell text-right">${formatNumber(totalRow.retainers)}</td>
                    <td class="table-cell text-right">${formatNumber(totalRow.pendingRetainers)}</td>
                    <!-- <td class="table-cell text-right">${formatNumber(totalRow.totalRetainers)}</td> -->
                    <td class="table-cell text-right ${totalCprColor}">${formatCurrency(totalCPR)}</td>
                    <td class="table-cell text-right ${totalConvColor}">${formatPercentage(totalConv)}</td>
                </tr>
            `;
            
            // Add YouTube/Crisp row if exists (with color coding)
            if (youtubeBucket) {
                const ytCplColor = getMetricColorClass(youtubeBucket.costPerLead, 'cpl');
                const ytCpaColor = getMetricColorClass(youtubeBucket.cpa, 'cpa');
                const ytCprColor = getMetricColorClass(youtubeBucket.costPerRetainer, 'cpr');
                const ytConvColor = getMetricColorClass(youtubeBucket.conversionRate, 'conversion');
                const ytInPracticeColor = getMetricColorClass(youtubeBucket.inPracticePercent, 'inpractice');
                const ytUnqualifiedColor = getMetricColorClass(youtubeBucket.unqualifiedPercent, 'unqualified');
                
                bodyHtml += `
                    <tr class="youtube-row">
                        <td class="table-cell font-medium">
                            <i class="fab fa-youtube mr-2 text-red-600"></i>
                            ${youtubeBucket.name}
                        </td>
                        <td class="table-cell text-right">${formatCurrency(youtubeBucket.cost)}</td>
                        <td class="table-cell text-right">${formatNumber(youtubeBucket.leads)}</td>
                        <td class="table-cell text-right">${formatNumber(youtubeBucket.inPractice)}</td>
                        <td class="table-cell text-right ${ytInPracticeColor}">${formatPercentage(youtubeBucket.inPracticePercent)}</td>
                        <td class="table-cell text-right">${formatNumber(youtubeBucket.unqualified)}</td>
                        <td class="table-cell text-right ${ytUnqualifiedColor}">${formatPercentage(youtubeBucket.unqualifiedPercent)}</td>
                        <td class="table-cell text-right ${ytCplColor} font-semibold">${formatCurrency(youtubeBucket.costPerLead)}</td>
                        <td class="table-cell text-right">${formatNumber(youtubeBucket.cases)}</td>
                        <td class="table-cell text-right ${ytCpaColor} font-semibold">${formatCurrency(youtubeBucket.cpa)}</td>
                        <td class="table-cell text-right">${formatNumber(youtubeBucket.retainers)}</td>
                        <td class="table-cell text-right">${formatNumber(youtubeBucket.pendingRetainers || 0)}</td>
                        <td class="table-cell text-right font-semibold">${formatNumber(youtubeBucket.totalRetainers || youtubeBucket.retainers)}</td>
                        <!-- <td class="table-cell text-right ${ytCprColor} font-semibold">${formatCurrency(youtubeBucket.costPerRetainer)}</td> --> 
                        <td class="table-cell text-right ${ytConvColor} font-semibold">${formatPercentage(youtubeBucket.conversionRate)}</td>
                    </tr>
                `;
            }
        } else {
            bodyHtml = '<tr><td colspan="15" class="text-center py-4 text-gray-500">No campaign data available</td></tr>';
        }
        
        $('#tableBody').html(bodyHtml);
    }

    function renderLitifyTable() {
    const leads = state.filteredLitifyLeads;
    
    // Updated header with both date columns
    const headerHtml = `
        <th class="table-cell text-left">Created Date</th>
        <th class="table-cell text-left">Client</th>
        <!-- <th class="table-cell text-left">Conversion Date</th> -->
        <th class="table-cell text-left">Status</th>
        <th class="table-cell text-left">Case Type</th>
        <th class="table-cell text-center">In Practice</th>
        <th class="table-cell text-left">Bucket</th>
        <th class="table-cell text-left">UTM Campaign</th>
        <th class="table-cell text-center">Converted</th>
    `;
    $('#litifyTableHeader').html(headerHtml);
    
    let bodyHtml = '';
    leads.forEach(lead => {
        // Determine row styling based on dates
        let rowClass = '';
        let badge = '';
        
        if (lead.is_new_today) {
            rowClass = '';  // Light blue background
            badge = '';
        } else if (lead.converted_today) {
            rowClass = '';  // Light green background
            badge = '';
        }
        
        // Format dates
        const createdDate = lead.created_date_formatted || formatDateTime(lead.created_date);
        
        // Format conversion date properly
        let conversionDateDisplay = '';
        if (lead.conversion_date || lead.retainer_signed_date) {
            const dateStr = lead.conversion_date || lead.retainer_signed_date;
            // Format YYYY-MM-DD to a nicer format
            if (dateStr && dateStr.match(/^\d{4}-\d{2}-\d{2}$/)) {
                const parts = dateStr.split('-');
                const date = new Date(parts[0], parts[1] - 1, parts[2]);
                conversionDateDisplay = date.toLocaleDateString('en-US', { 
                    month: 'short', 
                    day: 'numeric', 
                    year: 'numeric',
                    timeZone: 'America/Los_Angeles'
                });
            } else {
                conversionDateDisplay = dateStr;
            }
        }
        
        // Apply color only if color coding is enabled
        const isConverted = lead.is_converted ? 
            (state.colorCodingDisabled ? 
                '<span class="font-semibold">Yes</span>' : 
                '<span class="text-green-600 font-semibold">Yes</span>') : 
            (state.colorCodingDisabled ? 
                '<span>No</span>' : 
                '<span class="text-red-600">No</span>');
        
        const inPractice = lead.in_practice ? 
            (state.colorCodingDisabled ? 
                '<span class="font-semibold">Yes</span>' : 
                '<span class="text-green-600 font-semibold">Yes</span>') : 
            (state.colorCodingDisabled ? 
                '<span>No</span>' : 
                '<span class="text-red-600">No</span>');
        
        let clientDisplay = lead.client_name || lead.name || '-';
        
        const intakeId = lead.id || lead.intake_id || lead.litify_pm__intake__c || lead.Intake__c;
        
        if (intakeId && intakeId !== '-' && clientDisplay !== '-') {
            const litifyUrl = lead.salesforce_url || 
                `https://sweetjames.lightning.force.com/lightning/r/litify_pm__Intake__c/${intakeId}/view`;
            clientDisplay = `<a href="${litifyUrl}" 
                target="_blank" 
                class="client-link"
                title="View intake record in Litify">
                ${lead.client_name || lead.name}
                <i class="fas fa-external-link-alt text-xs ml-1"></i>
            </a>`;
        }
        
        bodyHtml += `
            <tr class="table-row ${rowClass}">
                <td class="table-cell">
                    <small class="text-gray-600">${createdDate}</small>
                </td>
                <td class="table-cell">
                    ${clientDisplay}
                    ${badge}
                </td>
                
                <!-- <td class="table-cell">
                    ${conversionDateDisplay ? 
                        `<small class="text-green-600 font-semibold">${conversionDateDisplay}</small>` : 
                        '<small class="text-gray-400">-</small>'}
                </td>
                -->
                <td class="table-cell">
                    <span class="px-2 py-1 text-xs rounded-full ${getStatusClass(lead.status)}">
                        ${lead.status}
                    </span>
                </td>
                <td class="table-cell text-sm">${lead.case_type || '-'}</td>
                <td class="table-cell text-center">${inPractice}</td>
                <td class="table-cell">
                    <span class="px-2 py-1 text-xs bg-gray-100 dark-mode:bg-gray-700 rounded">
                        ${lead.bucket || 'Unmapped'}
                    </span>
                </td>
                <td class="table-cell text-xs text-gray-600 dark-mode:text-gray-400">${lead.utm_campaign || '-'}</td>
                <td class="table-cell text-center">${isConverted}</td>
            </tr>
        `;
    });
    
    if (leads.length === 0) {
        bodyHtml = '<tr><td colspan="9" class="text-center py-4 text-gray-500">No leads found for the selected filter</td></tr>';
    }
    
    $('#litifyTableBody').html(bodyHtml);
}

    function updateBucketFilter() {
        const select = $('#litifyBucketFilter');
        select.find('option:gt(0)').remove();
        
        const uniqueBuckets = [...new Set(state.litifyLeads.map(lead => lead.bucket).filter(b => b))];
        
        uniqueBuckets.forEach(bucket => {
            select.append(`<option value="${bucket}">${bucket}</option>`);
        });
    }

    function renderCharts() {
        renderPerformanceChart();
        renderCostChart();
    }

    function renderPerformanceChart() {
        const ctx = document.getElementById('performanceChart');
        if (!ctx) return;
        
        const buckets = state.dashboardData.buckets || [];
        
        if (state.charts.performance) {
            state.charts.performance.destroy();
        }
        
        const activeBuckets = buckets.filter(b => 
            b.leads > 0 && !b.name.includes('Youtube') && !b.name.includes('Crisp')
        );
        const labels = activeBuckets.map(b => {
            return b.name.replace('California', 'CA')
                         .replace('Arizona', 'AZ')
                         .replace('Georgia', 'GA')
                         .replace('Texas', 'TX');
        });
        const leadsData = activeBuckets.map(b => b.leads);
        const casesData = activeBuckets.map(b => b.cases);
        const retainersData = activeBuckets.map(b => b.retainers);
        
        state.charts.performance = new Chart(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Leads',
                    data: leadsData,
                    backgroundColor: 'rgba(16, 185, 129, 0.7)',
                    borderColor: '#10b981',
                    borderWidth: 1
                }, {
                    label: 'Cases',
                    data: casesData,
                    backgroundColor: 'rgba(59, 130, 246, 0.7)',
                    borderColor: '#3b82f6',
                    borderWidth: 1
                }, {
                    label: 'Retainers',
                    data: retainersData,
                    backgroundColor: 'rgba(139, 92, 246, 0.7)',
                    borderColor: '#8b5cf6',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            padding: 15,
                            font: {
                                size: 12
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            font: {
                                size: 11
                            }
                        }
                    },
                    x: {
                        ticks: {
                            font: {
                                size: 11
                            },
                            maxRotation: 45,
                            minRotation: 45
                        }
                    }
                }
            }
        });
    }

    function renderCostChart() {
        const ctx = document.getElementById('costChart');
        if (!ctx) return;
        
        const buckets = state.dashboardData.buckets || [];
        
        if (state.charts.cost) {
            state.charts.cost.destroy();
        }
        
        const filteredBuckets = buckets.filter(b => 
            b.cost > 0 && !b.name.includes('Youtube') && !b.name.includes('Crisp')
        );
        
        const colors = [
            '#667eea', '#764ba2', '#f093fb', '#4facfe', '#00f2fe', '#43e97b',
            '#38f9d7', '#fa709a', '#fee140', '#30cfd0', '#a8edea', '#fed6e3'
        ];
        
        state.charts.cost = new Chart(ctx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: filteredBuckets.map(b => b.name),
                datasets: [{
                    data: filteredBuckets.map(b => b.cost),
                    backgroundColor: colors.slice(0, filteredBuckets.length),
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            padding: 10,
                            font: {
                                size: 11
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = formatCurrency(context.raw);
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.raw / total) * 100).toFixed(1);
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    function updateKeyInsights() {
        const buckets = state.dashboardData.buckets || [];
        const activeBuckets = buckets.filter(b => 
            b.leads > 0 && !b.name.includes('Youtube') && !b.name.includes('Crisp')
        );
        
        if (activeBuckets.length === 0) {
            $('#bestConversion, #lowestCPL, #highestVolume, #mostEfficient').text('N/A');
            return;
        }
        
        const bestConv = activeBuckets.reduce((best, curr) => 
            (curr.conversionRate > best.conversionRate) ? curr : best, 
            activeBuckets[0]
        );
        $('#bestConversion').text(bestConv.name ? `${bestConv.name} (${formatPercentage(bestConv.conversionRate)})` : 'N/A');
        
        const lowestCPL = activeBuckets.reduce((lowest, curr) => 
            (curr.costPerLead < lowest.costPerLead && curr.costPerLead > 0) ? curr : lowest,
            activeBuckets[0]
        );
        $('#lowestCPL').text(lowestCPL.name ? `${lowestCPL.name} (${formatCurrency(lowestCPL.costPerLead)})` : 'N/A');
        
        const highestVol = activeBuckets.reduce((highest, curr) => 
            (curr.leads > highest.leads) ? curr : highest,
            activeBuckets[0]
        );
        $('#highestVolume').text(highestVol.name ? `${highestVol.name} (${formatNumber(highestVol.leads)} leads)` : 'N/A');
        
        const mostEfficient = activeBuckets.filter(b => b.cpa > 0).reduce((best, curr) => 
            (curr.cpa < best.cpa) ? curr : best,
            activeBuckets.find(b => b.cpa > 0) || activeBuckets[0]
        );
        $('#mostEfficient').text(mostEfficient && mostEfficient.cpa > 0 ? 
            `${mostEfficient.name} (${formatCurrency(mostEfficient.cpa)})` : 'N/A');
    }

    function exportData() {
        const params = {
            start_date: state.startDate,
            end_date: state.endDate,
            include_spam: state.includeSpam,
            include_abandoned: state.includeAbandoned,
            include_duplicate: state.includeDuplicate
        };
        
        const queryString = $.param(params);
        window.location.href = `/api/export?${queryString}`;
    }

    function formatDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    function formatDisplayDate(dateStr) {
        if (!dateStr) return '';
        const parts = dateStr.split('-');
        const date = new Date(parts[0], parts[1] - 1, parts[2]);
        return date.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric', 
            year: 'numeric',
            timeZone: 'America/Los_Angeles'
        });
    }

    function formatDateTime(dateStr) {
        if (!dateStr) return '-';
        
        // Check if this is already formatted (contains "PT")
        if (dateStr.includes(' PT')) {
            return dateStr;
        }
        
        const date = new Date(dateStr);
        
        if (isNaN(date.getTime())) {
            // Try to parse YYYY-MM-DD format
            const parts = dateStr.split('-');
            if (parts.length === 3) {
                const localDate = new Date(parts[0], parts[1] - 1, parts[2]);
                return localDate.toLocaleString('en-US', { 
                    month: 'short', 
                    day: 'numeric',
                    year: 'numeric',
                    hour: '2-digit', 
                    minute: '2-digit',
                    timeZone: 'America/Los_Angeles'
                });
            }
            return dateStr;  // Return as-is if we can't parse it
        }
        
        return date.toLocaleString('en-US', { 
            month: 'short', 
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit', 
            minute: '2-digit',
            timeZone: 'America/Los_Angeles'
        });
    }

    function formatCurrency(value) {
        if (value === null || value === undefined || isNaN(value)) return '$0';
        return '$' + Math.round(value).toLocaleString('en-US');
    }

    function formatNumber(value) {
        if (value === null || value === undefined || isNaN(value)) return '0';
        return Math.round(value).toLocaleString('en-US');
    }

    function formatPercentage(value) {
        if (value === null || value === undefined || isNaN(value)) return '0%';
        return (value * 100).toFixed(1) + '%';
    }

    function getStatusClass(status) {
        const statusClasses = {
            'New': 'bg-blue-100 text-blue-800',
            'Contacted': 'bg-yellow-100 text-yellow-800',
            'Qualified': 'bg-green-100 text-green-800',
            'Converted': 'bg-green-100 text-green-800',
            'Retained': 'bg-green-100 text-green-800',
            'Retainer Sent': 'bg-amber-100 text-amber-800',
            'Closed': 'bg-gray-100 text-gray-800',
            'Converted DAI': 'bg-red-100 text-red-800',
            'Turned Down': 'bg-red-100 text-red-800',
            'Referred Out': 'bg-orange-100 text-orange-800',
            'Unknown': 'bg-gray-100 text-gray-800'
        };
        return statusClasses[status] || 'bg-gray-100 text-gray-800';
    }
});