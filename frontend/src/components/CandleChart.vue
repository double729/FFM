<template>
  <div class="chart">
    <div ref="chartRef" class="chart__canvas"></div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue';
import * as echarts from 'echarts';
import { useMarketStore } from '../stores/market';

const market = useMarketStore();
const chartRef = ref(null);
let chartInstance;

const renderChart = () => {
  if (!chartRef.value) {
    return;
  }
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value, undefined, {
      renderer: 'canvas'
    });
  }

  const candles = market.candles;
  if (!candles.length) {
    chartInstance.clear();
    return;
  }

  const categories = candles.map((item) => item.event_time);
  const ohlc = candles.map((item) => [item.open, item.close, item.low, item.high]);
  const volumes = candles.map((item, index) => [index, item.volume ?? 0, item.close >= item.open ? 1 : -1]);
  const bollUpper = candles.map((item) => item.boll_upper ?? null);
  const bollMid = candles.map((item) => item.boll_mid ?? null);
  const bollLower = candles.map((item) => item.boll_lower ?? null);
  const volumeMA = candles.map((item) => item.volume_ma ?? null);

  const option = {
    backgroundColor: '#ffffff',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      }
    },
    axisPointer: {
      link: [{ xAxisIndex: 'all' }]
    },
    grid: [{
      left: '5%',
      right: '2%',
      height: '60%'
    }, {
      left: '5%',
      right: '2%',
      top: '72%',
      height: '20%'
    }],
    xAxis: [{
      type: 'category',
      data: categories,
      scale: true,
      boundaryGap: false,
      axisLine: { onZero: false }
    }, {
      type: 'category',
      gridIndex: 1,
      data: categories,
      boundaryGap: false,
      axisLine: { onZero: false }
    }],
    yAxis: [{
      scale: true,
      splitArea: {
        show: true
      }
    }, {
      gridIndex: 1,
      splitNumber: 3,
      axisLabel: { show: true }
    }],
    dataZoom: [{
      type: 'inside',
      xAxisIndex: [0, 1],
      start: 70,
      end: 100
    }, {
      show: true,
      xAxisIndex: [0, 1],
      type: 'slider',
      top: '95%',
      start: 70,
      end: 100
    }],
    series: [{
      name: 'K线',
      type: 'candlestick',
      data: ohlc,
      itemStyle: {
        color: '#ef4444',
        color0: '#22c55e',
        borderColor: '#ef4444',
        borderColor0: '#22c55e'
      }
    }, {
      name: 'BOLL 上轨',
      type: 'line',
      data: bollUpper,
      smooth: true,
      lineStyle: {
        color: '#0ea5e9'
      }
    }, {
      name: 'BOLL 中轨',
      type: 'line',
      data: bollMid,
      smooth: true,
      lineStyle: {
        color: '#6366f1'
      }
    }, {
      name: 'BOLL 下轨',
      type: 'line',
      data: bollLower,
      smooth: true,
      lineStyle: {
        color: '#0ea5e9'
      }
    }, {
      name: '成交量',
      type: 'bar',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: volumes,
      itemStyle: {
        color: (params) => (params.data[2] > 0 ? '#f87171' : '#4ade80')
      }
    }, {
      name: '量均线',
      type: 'line',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: volumeMA,
      lineStyle: {
        color: '#f59e0b'
      }
    }]
  };

  chartInstance.setOption(option, true);
};

watch(
  () => market.candles,
  () => {
    renderChart();
  },
  { deep: true }
);

onMounted(() => {
  renderChart();
  window.addEventListener('resize', resize);
});

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose();
  }
  window.removeEventListener('resize', resize);
});

const resize = () => {
  chartInstance?.resize();
};
</script>

<style scoped>
.chart {
  width: 100%;
  height: 100%;
}

.chart__canvas {
  flex: 1;
  width: 100%;
  height: 100%;
}
</style>
