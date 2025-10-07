const { createApp, ref, reactive, computed, watch, onMounted, nextTick } = Vue;

const API_BASE = window.FFM_API_BASE || 'http://localhost:8000/api';
const api = axios.create({ baseURL: API_BASE, timeout: 20000 });

createApp({
  setup() {
    const availableIntervals = [
      { label: '日线', value: '1d' },
      { label: '60分钟', value: '60' },
      { label: '30分钟', value: '30' },
      { label: '5分钟', value: '5' },
    ];

    const filters = reactive({
      symbol: '',
      startDate: '',
      endDate: '',
      interval: '1d',
    });

    const importState = reactive({
      loading: false,
      message: '',
    });

    const contracts = ref([]);
    const selectedContract = ref('');
    const candles = ref([]);
    const chartInstance = ref(null);

    const playback = reactive({
      active: false,
      playing: false,
      hasMore: false,
      batchSize: 50,
      speed: 1000,
      status: null,
      timer: null,
      message: '',
    });

    const trades = ref([]);
    const tradeForm = reactive({
      symbol: '',
      direction: 'buy',
      price: '',
      quantity: 1,
      note: '',
    });
    const tradeMessage = ref('');
    const portfolio = reactive({ positions: {}, realized_pnl: 0, unrealized_pnl: 0 });

    const hasPositions = computed(() => Object.keys(portfolio.positions || {}).length > 0);

    const selectedRange = computed(() => {
      const info = contracts.value.find((item) => `${item.symbol}|${item.interval}` === selectedContract.value);
      if (!info) return '-';
      const start = info.start_date ? info.start_date.slice(0, 10) : '-';
      const end = info.end_date ? info.end_date.slice(0, 10) : '-';
      return `${start} ~ ${end}`;
    });

    function ensureChart() {
      if (chartInstance.value) {
        return chartInstance.value;
      }
      const el = document.getElementById('chart');
      if (!el) {
        return null;
      }
      chartInstance.value = echarts.init(el);
      window.addEventListener('resize', () => {
        if (chartInstance.value) {
          chartInstance.value.resize();
        }
      });
      return chartInstance.value;
    }

    async function renderChart() {
      await nextTick();
      const chart = ensureChart();
      if (!chart) {
        return;
      }
      const items = candles.value || [];
      if (!items.length) {
        chart.clear();
        return;
      }

      const categories = items.map((item) => item.event_time.replace('T', ' ').replace('Z', ''));
      const kline = items.map((item) => [
        Number(item.open ?? 0),
        Number(item.close ?? 0),
        Number(item.low ?? 0),
        Number(item.high ?? 0),
      ]);
      const bollMid = items.map((item) => (item.boll_mid != null ? Number(item.boll_mid) : null));
      const bollUpper = items.map((item) => (item.boll_upper != null ? Number(item.boll_upper) : null));
      const bollLower = items.map((item) => (item.boll_lower != null ? Number(item.boll_lower) : null));
      const volume = items.map((item) => Number(item.volume ?? 0));
      const volumeMA = items.map((item) => (item.volume_ma != null ? Number(item.volume_ma) : null));

      const option = {
        animation: false,
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' },
        },
        axisPointer: {
          link: [{ xAxisIndex: [0, 1] }],
        },
        dataZoom: [
          { type: 'inside', xAxisIndex: [0, 1], minSpan: 10 },
          { type: 'slider', xAxisIndex: [0, 1], bottom: 10 },
        ],
        grid: [
          { left: '5%', right: '5%', top: '8%', height: '56%' },
          { left: '5%', right: '5%', top: '72%', height: '18%' },
        ],
        xAxis: [
          {
            type: 'category',
            data: categories,
            scale: true,
            boundaryGap: false,
            axisLine: { lineStyle: { color: '#94a3b8' } },
          },
          {
            type: 'category',
            gridIndex: 1,
            data: categories,
            boundaryGap: false,
            axisTick: { show: false },
            axisLabel: { show: false },
            axisLine: { lineStyle: { color: '#94a3b8' } },
          },
        ],
        yAxis: [
          {
            scale: true,
            position: 'right',
            splitLine: { lineStyle: { color: '#e2e8f0' } },
          },
          {
            gridIndex: 1,
            scale: true,
            splitNumber: 2,
            position: 'right',
            axisLine: { show: false },
            axisTick: { show: false },
            splitLine: { lineStyle: { color: '#e2e8f0' } },
          },
        ],
        series: [
          { name: 'K线', type: 'candlestick', data: kline },
          { name: 'BOLL 中轨', type: 'line', data: bollMid, smooth: true, showSymbol: false },
          { name: 'BOLL 上轨', type: 'line', data: bollUpper, smooth: true, showSymbol: false },
          { name: 'BOLL 下轨', type: 'line', data: bollLower, smooth: true, showSymbol: false },
          {
            name: '成交量',
            type: 'bar',
            xAxisIndex: 1,
            yAxisIndex: 1,
            data: volume,
            itemStyle: {
              color: (params) => (kline[params.dataIndex]?.[1] >= kline[params.dataIndex]?.[0] ? '#4ade80' : '#f87171'),
            },
          },
          {
            name: '量均线',
            type: 'line',
            xAxisIndex: 1,
            yAxisIndex: 1,
            data: volumeMA,
            smooth: true,
            showSymbol: false,
            lineStyle: { color: '#0ea5e9' },
          },
        ],
      };

      chart.setOption(option, true);
    }

    async function importData() {
      if (!filters.symbol || !filters.startDate || !filters.endDate) {
        importState.message = '请完整填写导入信息';
        return;
      }

     importState.loading = true;
     importState.message = '';
     try {
        const normalizedSymbol = (filters.symbol || '').trim().toUpperCase();
        filters.symbol = normalizedSymbol;
        const payload = {
          symbol: normalizedSymbol,
          start_date: filters.startDate,
          end_date: filters.endDate,
          interval: filters.interval,
        };
        const { data } = await api.post('/import', payload);
        importState.message = `成功导入 ${data.imported} 条记录`;
        await refreshContracts();
        await loadCandles();
      } catch (error) {
        importState.message = error?.response?.data?.message || error.message || '导入失败';
      } finally {
        importState.loading = false;
      }
    }

    async function refreshContracts() {
      try {
        const { data } = await api.get('/contracts');
        contracts.value = data?.items || [];
        if (contracts.value.length === 0) {
          selectedContract.value = '';
          candles.value = [];
          await renderChart();
          return;
        }
        const exists = contracts.value.find((item) => `${item.symbol}|${item.interval}` === selectedContract.value);
        if (!exists) {
          selectedContract.value = `${contracts.value[0].symbol}|${contracts.value[0].interval}`;
        }
      } catch (error) {
        importState.message = error?.response?.data?.message || error.message || '刷新合约失败';
      }
    }

    async function loadCandles() {
      if (!filters.symbol) {
        return;
      }
      try {
        const normalizedSymbol = (filters.symbol || '').trim().toUpperCase();
        filters.symbol = normalizedSymbol;
        const params = {
          symbol: normalizedSymbol,
          interval: filters.interval,
        };
        if (filters.startDate) params.start_date = filters.startDate;
        if (filters.endDate) params.end_date = filters.endDate;
        const { data } = await api.get('/candles', { params });
        candles.value = data?.items || [];
        await renderChart();
      } catch (error) {
        importState.message = error?.response?.data?.message || error.message || '读取本地数据失败';
      }
    }

    function clearPlaybackTimer() {
      if (playback.timer) {
        clearTimeout(playback.timer);
        playback.timer = null;
      }
    }

    async function fetchNextBatch() {
      if (!playback.active) {
        return false;
      }
      try {
        const { data } = await api.get('/playback/next', {
          params: { count: Math.max(1, Number(playback.batchSize) || 1) },
        });
        const items = data?.items || [];
        if (items.length) {
          candles.value = candles.value.concat(items);
          await renderChart();
        }
        playback.status = data?.status || null;
        playback.hasMore = Boolean(data?.has_more);
        playback.message = '';
        if (!playback.hasMore) {
          playback.playing = false;
          clearPlaybackTimer();
        }
        return items.length > 0;
      } catch (error) {
        playback.message = error?.response?.data?.message || error.message || '回放失败';
        playback.playing = false;
        playback.hasMore = false;
        clearPlaybackTimer();
        return false;
      }
    }

    function schedulePlayback() {
      clearPlaybackTimer();
      if (!playback.playing || !playback.hasMore) {
        return;
      }
      const delay = Math.max(100, Number(playback.speed) || 1000);
      playback.timer = setTimeout(async () => {
        const hasData = await fetchNextBatch();
        if (hasData || playback.hasMore) {
          schedulePlayback();
        }
      }, delay);
    }

    async function startPlayback() {
      if (!filters.symbol) {
        playback.message = '请先选择品种';
        return;
      }
      playback.message = '';
      playback.active = false;
      playback.playing = false;
      clearPlaybackTimer();
      try {
        const normalizedSymbol = (filters.symbol || '').trim().toUpperCase();
        filters.symbol = normalizedSymbol;
        const payload = {
          symbol: normalizedSymbol,
          interval: filters.interval,
          start_date: filters.startDate || undefined,
          end_date: filters.endDate || undefined,
        };
        const { data } = await api.post('/playback/start', payload);
        candles.value = [];
        await renderChart();
        playback.status = data?.status || null;
        playback.active = true;
        playback.playing = Boolean(playback.status?.playing);
        playback.hasMore = true;
        await fetchNextBatch();
        if (playback.playing) {
          schedulePlayback();
        }
      } catch (error) {
        playback.message = error?.response?.data?.message || error.message || '启动回放失败';
        playback.active = false;
        playback.playing = false;
      }
    }

    async function pausePlayback() {
      if (!playback.active) return;
      try {
        const { data } = await api.post('/playback/pause');
        playback.status = data?.status || null;
        playback.playing = false;
        clearPlaybackTimer();
      } catch (error) {
        playback.message = error?.response?.data?.message || error.message || '暂停失败';
      }
    }

    async function resumePlayback() {
      if (!playback.active) return;
      try {
        const { data } = await api.post('/playback/resume');
        playback.status = data?.status || null;
        playback.playing = true;
        playback.message = '';
        schedulePlayback();
      } catch (error) {
        playback.message = error?.response?.data?.message || error.message || '继续失败';
      }
    }

    async function manualStep() {
      await fetchNextBatch();
    }

    async function loadTrades() {
      try {
        const { data } = await api.get('/trades');
        trades.value = data?.items || [];
      } catch (error) {
        tradeMessage.value = error?.response?.data?.message || error.message || '获取交易失败';
      }
    }

    async function removeTrade(id) {
      try {
        await api.delete(`/trades/${id}`);
        tradeMessage.value = '删除成功';
        await loadTrades();
        await loadPortfolio();
      } catch (error) {
        tradeMessage.value = error?.response?.data?.message || error.message || '删除失败';
      }
    }

    async function submitTrade() {
      if (!tradeForm.symbol) {
        tradeMessage.value = '请填写交易品种';
        return;
      }
      const price = Number(tradeForm.price);
      const quantity = Math.floor(Number(tradeForm.quantity));
      if (!Number.isFinite(price) || price <= 0) {
        tradeMessage.value = '价格必须大于 0';
        return;
      }
      if (!Number.isFinite(quantity) || quantity <= 0) {
        tradeMessage.value = '数量必须为正数';
        return;
      }
      try {
        const normalizedSymbol = (tradeForm.symbol || '').trim().toUpperCase();
        tradeForm.symbol = normalizedSymbol;
        const payload = {
          symbol: normalizedSymbol,
          direction: tradeForm.direction,
          price,
          quantity,
          note: tradeForm.note || undefined,
        };
        await api.post('/trades', payload);
        tradeMessage.value = '交易已记录';
        tradeForm.price = '';
        tradeForm.quantity = 1;
        tradeForm.note = '';
        await loadTrades();
        await loadPortfolio();
      } catch (error) {
        tradeMessage.value = error?.response?.data?.message || error.message || '下单失败';
      }
    }

    async function loadPortfolio() {
      try {
        const { data } = await api.get('/portfolio');
        const normalizedPositions = {};
        Object.entries(data?.positions || {}).forEach(([symbol, pos]) => {
          normalizedPositions[symbol] = {
            ...pos,
            average_price: Number(pos.average_price || 0),
            last_price: pos.last_price != null ? Number(pos.last_price) : null,
            quantity: Number(pos.quantity || 0),
          };
        });
        portfolio.positions = normalizedPositions;
        portfolio.realized_pnl = Number(data?.realized_pnl || 0);
        portfolio.unrealized_pnl = Number(data?.unrealized_pnl || 0);
      } catch (error) {
        tradeMessage.value = error?.response?.data?.message || error.message || '刷新持仓失败';
      }
    }

    watch(selectedContract, (value) => {
      if (!value) {
        return;
      }
      const info = contracts.value.find((item) => `${item.symbol}|${item.interval}` === value);
      if (!info) {
        return;
      }
      filters.symbol = info.symbol;
      filters.interval = info.interval;
      filters.startDate = info.start_date ? info.start_date.slice(0, 10) : filters.startDate;
      filters.endDate = info.end_date ? info.end_date.slice(0, 10) : filters.endDate;
      tradeForm.symbol = info.symbol;
      loadCandles();
    });

    watch(
      () => filters.symbol,
      (value) => {
        if (value) {
          tradeForm.symbol = value;
        }
      }
    );

    watch(
      () => playback.speed,
      () => {
        if (playback.playing) {
          schedulePlayback();
        }
      }
    );

    onMounted(async () => {
      ensureChart();
      await refreshContracts();
      await loadTrades();
      await loadPortfolio();
    });

    return {
      availableIntervals,
      filters,
      importState,
      importData,
      loadCandles,
      contracts,
      selectedContract,
      selectedRange,
      refreshContracts,
      playback,
      startPlayback,
      pausePlayback,
      resumePlayback,
      manualStep,
      trades,
      tradeForm,
      tradeMessage,
      submitTrade,
      loadTrades,
      removeTrade,
      portfolio,
      loadPortfolio,
      hasPositions,
    };
  },
}).mount('#app');
